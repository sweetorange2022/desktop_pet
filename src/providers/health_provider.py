"""健康提醒信息提供者。

集成摄像头健康检测 + 智能决策引擎。
每 20 分钟检查一次（摄像头短暂开启 5 秒），整点走统一决策。
9:00 保留原有右下角弹窗逻辑。
"""

from __future__ import annotations

import logging
import os
import random
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from config import (
    CAMERA_ACTIVE_END,
    CAMERA_ACTIVE_START,
    CAMERA_CHECK_INTERVAL_MIN,
    CAMERA_ENABLED,
    HEALTH_ENCOURAGEMENTS,
    HEALTH_OFF_WORK_TIMES,
    HEALTH_REMINDER_BY_ELAPSED,
    HEALTH_REMINDER_INTERVAL_S,
    HEALTH_REMINDER_MSG,
    HEALTH_REMINDER_TITLE,
    HEALTH_WORK_HOURS,
    HOLIDAYS_2026,
    WORKDAYS_EXTRA_2026,
)
from src.providers.base import InfoProvider

logger = logging.getLogger(__name__)


class _ReminderEmitter(QObject):
    """内部信号发射器。"""
    reminder_triggered = Signal(str, str, str)  # title, message, snapshot_dir


class HealthReminderProvider(InfoProvider):
    """健康提醒 Provider（集成摄像头 + 智能决策）。

    职责：
    1. 每 20 分钟：短暂开摄像头 → 评分 → 智能决策 → 提醒
    2. 每秒：UI 更新（鼓励语、下班倒计时）
    3. 工作日/假日判断
    4. 气泡显示
    """

    def __init__(self) -> None:
        self._emitter = _ReminderEmitter()
        self.reminder_triggered = self._emitter.reminder_triggered

        self._encouragement: str = random.choice(HEALTH_ENCOURAGEMENTS)
        self._last_reminder_hour: int = -1

        # 摄像头 + 决策引擎（延迟初始化）
        self._camera_monitor = None
        self._smart_engine = None
        self._style_service = None
        self._camera_config: dict = {}

        # 每秒 UI 更新定时器
        self._ui_timer = QTimer()
        self._ui_timer.setInterval(1000)
        self._ui_timer.timeout.connect(self._ui_tick)

        # 20 分钟摄像头检查定时器
        self._camera_timer = QTimer()
        self._camera_timer.setInterval(CAMERA_CHECK_INTERVAL_MIN * 60 * 1000)
        self._camera_timer.timeout.connect(self._camera_tick)

        # 周日清理定时器（每小时检查一次）
        self._cleanup_timer = QTimer()
        self._cleanup_timer.setInterval(3600 * 1000)
        self._cleanup_timer.timeout.connect(self._maybe_cleanup)

        # 今日快照统计
        self._today_snapshots: list = []

    def set_camera_services(
        self,
        camera_monitor=None,
        smart_engine=None,
        style_service=None,
        camera_config: dict = None,
    ) -> None:
        """注入摄像头相关服务（由 main.py 调用）。"""
        self._camera_monitor = camera_monitor
        self._smart_engine = smart_engine
        self._style_service = style_service
        self._camera_config = camera_config or {}

    @property
    def name(self) -> str:
        return "健康提醒"

    def start(self) -> None:
        self._ui_tick()
        self._ui_timer.start()
        if CAMERA_ENABLED and self._camera_monitor:
            self._camera_timer.start()
            self._cleanup_timer.start()
            logger.info("摄像头健康检测已启动（每 %d 分钟）", CAMERA_CHECK_INTERVAL_MIN)

    def stop(self) -> None:
        self._ui_timer.stop()
        self._camera_timer.stop()
        self._cleanup_timer.stop()

    def test_reminder(self) -> None:
        """立即触发一次健康提醒（用于测试）。"""
        self._encouragement = random.choice(HEALTH_ENCOURAGEMENTS)
        self.reminder_triggered.emit(HEALTH_REMINDER_TITLE, HEALTH_REMINDER_MSG, "")

    def update(self) -> None:
        pass

    def get_data(self) -> dict[str, str]:
        """返回当前状态信息（气泡显示用）。"""
        now = datetime.now()

        if not self._is_workday(now):
            return {"状态": "休息日", "提示": "好好休息~"}

        if not self._is_in_camera_active_hours(now):
            return {"状态": "非工作时段", "提示": self._get_next_session_info(now)}

        parts = self._encouragement.split("，", 1)
        result: dict[str, str] = {"_1": parts[0]}
        if len(parts) > 1:
            result["_2"] = parts[1]

        off_str = self._get_off_work_countdown(now)
        if off_str:
            result["距下班"] = off_str

        # 摄像头状态
        if self._today_snapshots:
            last = self._today_snapshots[-1]
            if hasattr(last, "fatigue"):
                result["状态"] = f"疲劳{last.fatigue} 坐姿{last.posture}"

        return result

    # ---- 摄像头检查（每 20 分钟） ----

    def _camera_tick(self) -> None:
        """每 20 分钟触发：摄像头采集 → 决策 → 提醒。"""
        now = datetime.now()

        if not self._is_workday(now):
            return
        if not self._is_in_camera_active_hours(now):
            return

        # 摄像头采集
        snapshot = None
        if self._camera_monitor:
            try:
                snapshot = self._camera_monitor.capture_and_analyze()
                self._today_snapshots.append(snapshot)
                if self._smart_engine:
                    self._smart_engine.add_snapshot(snapshot)
                logger.info(
                    "摄像头检测: fatigue=%s posture=%s face=%s",
                    snapshot.fatigue, snapshot.posture, snapshot.face_detected,
                )
            except Exception as e:
                logger.warning("摄像头检测失败: %s", e)

        # 智能决策
        is_hourly = now.minute == 0
        has_valid_snapshot = snapshot is not None and snapshot.image_path
        if self._smart_engine and has_valid_snapshot:
            result = self._smart_engine.decide(snapshot, is_hourly=is_hourly)
            if result.should_remind:
                self._encouragement = result.message
                snap_dir = os.path.dirname(snapshot.image_path) if snapshot.image_path else ""
                self.reminder_triggered.emit(result.title, result.message, snap_dir)
        if is_hourly and (not has_valid_snapshot or not self._smart_engine):
            # 无摄像头或采集失败 → 整点走原有逻辑
            self._hourly_fallback(now)

    def _hourly_fallback(self, now: datetime) -> None:
        """原有整点提醒逻辑（摄像头不可用时的 fallback）。"""
        h = now.hour
        if h != self._last_reminder_hour:
            self._last_reminder_hour = h
            self._encouragement = random.choice(HEALTH_ENCOURAGEMENTS)
            elapsed_h = self._get_elapsed_hours(now)
            msg = HEALTH_REMINDER_BY_ELAPSED.get(
                str(elapsed_h),
                HEALTH_REMINDER_BY_ELAPSED.get("default", HEALTH_REMINDER_MSG),
            )
            self.reminder_triggered.emit(HEALTH_REMINDER_TITLE, msg, "")

    # ---- UI 更新（每秒） ----

    def _ui_tick(self) -> None:
        """每秒更新 UI 数据（鼓励语轮换、下班倒计时等）。"""
        now = datetime.now()
        if not self._is_workday(now):
            return
        if not self._is_in_camera_active_hours(now):
            return
        # 每分钟轮换一次鼓励语
        if now.second == 0:
            self._encouragement = random.choice(HEALTH_ENCOURAGEMENTS)

    # ---- 穿搭建议（10:10 + 18:10） ----

    def trigger_style_advice(self, period: str) -> None:
        """触发每日精气神建议（由外部定时器调用）。"""
        if not self._style_service:
            return

        # 构建天气信息
        weather_info = self._get_weather_info()
        fatigue_trend = ""
        if self._smart_engine:
            fatigue_trend = self._smart_engine.get_today_fatigue_trend()

        # 取最新的摄像头快照
        snapshot = self._today_snapshots[-1] if self._today_snapshots else None
        if snapshot is None:
            from src.services.camera_monitor import CameraSnapshot
            snapshot = CameraSnapshot(timestamp=datetime.now().isoformat(), face_detected=False)

        try:
            advice = self._style_service.generate_advice(
                snapshot=snapshot,
                weather_info=weather_info,
                period=period,
                today_fatigue_trend=fatigue_trend,
            )
            if advice:
                snap_dir = os.path.dirname(snapshot.image_path) if snapshot and snapshot.image_path else ""
                self.reminder_triggered.emit("精气神建议", advice, snap_dir)
        except Exception as e:
            logger.warning("穿搭建议生成失败: %s", e)

    def _get_weather_info(self) -> dict:
        """获取当前天气信息。"""
        try:
            from src.services.weather import fetch_today_weather
            city = self._style_service.get_city() if self._style_service else "未知"
            weather = fetch_today_weather()
            if weather:
                return {
                    "city": city,
                    "desc": weather.weather_desc,
                    "temp": f"{weather.temp_min:.0f}~{weather.temp_max:.0f}°C",
                    "wind": f"{weather.wind_speed_max:.0f}",
                    "rain": f"{weather.rain_prob_max:.0f}",
                    "uv": "",
                }
        except Exception:
            pass
        return {"city": "未知", "desc": "未知", "temp": "未知"}

    # ---- 清理 ----

    def _maybe_cleanup(self) -> None:
        """周日 23:59 清理上周快照。"""
        now = datetime.now()
        if now.weekday() == 6 and now.hour == 23 and now.minute >= 55:
            if self._camera_monitor:
                from src.services.camera_monitor import cleanup_old_snapshots
                from config import CAMERA_SNAPSHOT_DIR
                removed = cleanup_old_snapshots(CAMERA_SNAPSHOT_DIR)
                if removed:
                    logger.info("清理了 %d 个旧快照目录", removed)

    # ---- 时间判断（保留原有逻辑） ----

    def _is_workday(self, now: Optional[datetime] = None) -> bool:
        if now is None:
            now = datetime.now()
        month_day = (now.month, now.day)
        if month_day in HOLIDAYS_2026:
            return False
        if month_day in WORKDAYS_EXTRA_2026:
            return True
        return now.weekday() < 5

    def _is_in_camera_active_hours(self, now: Optional[datetime] = None) -> bool:
        """判断是否在摄像头活跃时段（09:40 ~ 20:40）。"""
        if now is None:
            now = datetime.now()
        current = now.hour * 60 + now.minute
        start_h, start_m = map(int, CAMERA_ACTIVE_START.split(":"))
        end_h, end_m = map(int, CAMERA_ACTIVE_END.split(":"))
        start = start_h * 60 + start_m
        end = end_h * 60 + end_m
        return start <= current <= end

    def _is_in_work_hours(self, now: Optional[datetime] = None) -> bool:
        if now is None:
            now = datetime.now()
        current_minutes = now.hour * 60 + now.minute
        for sh, sm, eh, em in HEALTH_WORK_HOURS:
            start = sh * 60 + sm
            end = eh * 60 + em
            if start <= current_minutes < end:
                return True
        return False

    def _get_off_work_countdown(self, now: Optional[datetime] = None) -> str:
        if now is None:
            now = datetime.now()
        current_minutes = now.hour * 60 + now.minute
        for i, (sh, sm, eh, em) in enumerate(HEALTH_WORK_HOURS):
            work_start = sh * 60 + sm
            work_end = eh * 60 + em
            if not (work_start <= current_minutes < work_end):
                continue
            if i < len(HEALTH_OFF_WORK_TIMES):
                off_h, off_m = HEALTH_OFF_WORK_TIMES[i]
                off_minutes = off_h * 60 + off_m
                if current_minutes < off_minutes:
                    remaining = off_minutes - current_minutes
                    hours = remaining // 60
                    mins = remaining % 60
                    if hours > 0 and mins > 0:
                        return f"{hours}小时{mins}分"
                    elif hours > 0:
                        return f"{hours}小时"
                    else:
                        return f"{mins}分钟"
        return ""

    def _get_elapsed_hours(self, now: Optional[datetime] = None) -> int:
        if now is None:
            now = datetime.now()
        current_minutes = now.hour * 60 + now.minute
        for sh, sm, eh, em in HEALTH_WORK_HOURS:
            start = sh * 60 + sm
            end = eh * 60 + em
            if start <= current_minutes < end:
                elapsed = current_minutes - start
                return max(1, elapsed // 60 + 1)
        return 1

    def _get_next_session_info(self, now: Optional[datetime] = None) -> str:
        if now is None:
            now = datetime.now()
        current_minutes = now.hour * 60 + now.minute
        for sh, sm, eh, em in HEALTH_WORK_HOURS:
            start = sh * 60 + sm
            if current_minutes < start:
                remaining = start - current_minutes
                hours = remaining // 60
                mins = remaining % 60
                if hours > 0 and mins > 0:
                    return f"{hours}小时{mins}分后上班"
                elif hours > 0:
                    return f"{hours}小时后上班"
                else:
                    return f"{mins}分钟后上班"
        return "今天辛苦了~"
