"""健康提醒信息提供者。

在工作日的工作时段内每隔整点提醒用户喝水、活动。
非工作日（周末、节假日、调休补班外的周末）不提醒。
气泡显示鼓励语和下班倒计时。
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from config import (
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

class _ReminderEmitter(QObject):
    """内部信号发射器（分离 QObject 避免与 ABC 的元类冲突）。"""

    reminder_triggered = Signal(str, str)

class HealthReminderProvider(InfoProvider):
    """健康提醒 Provider。

    职责：
    1. 判断当前是否为工作日（排除周末、节假日、调休补班）
    2. 在工作日的工作时段内，每小时整点触发提醒
    3. 气泡显示鼓励语和下班倒计时
    4. 通过信号发射提醒事件（title, message）
    """

    def __init__(self) -> None:
        self._emitter = _ReminderEmitter()
        self.reminder_triggered = self._emitter.reminder_triggered

        self._last_reminder_hour: int = -1
        self._next_reminder_time: Optional[datetime] = None
        self._is_work_time: bool = False
        self._remaining_seconds: int = 0
        self._encouragement: str = random.choice(HEALTH_ENCOURAGEMENTS)
        self._off_work_remaining: str = ""

        # 每秒检查一次
        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    @property
    def name(self) -> str:
        return "健康提醒"

    def start(self) -> None:
        """启动定时检查。"""
        self._tick()
        self._timer.start()

    def stop(self) -> None:
        """停止定时检查。"""
        self._timer.stop()

    def test_reminder(self) -> None:
        """立即触发一次健康提醒（用于测试）。"""
        import random
        from config import HEALTH_ENCOURAGEMENTS, HEALTH_REMINDER_TITLE, HEALTH_REMINDER_MSG
        self._encouragement = random.choice(HEALTH_ENCOURAGEMENTS)
        self.reminder_triggered.emit(
            HEALTH_REMINDER_TITLE,
            HEALTH_REMINDER_MSG,
        )

    def update(self) -> None:
        """数据由定时器驱动，外部无需调用。"""

    def get_data(self) -> dict[str, str]:
        """返回当前状态信息。"""
        now = datetime.now()

        if not self._is_workday(now):
            return {
                "状态": "休息日",
                "提示": "好好休息~",
            }

        if not self._is_in_work_hours(now):
            return {
                "状态": "非工作时段",
                "提示": self._get_next_session_info(now),
            }

        # 鼓励语分行显示（在逗号处拆分，无标签行用 _ 前缀键）
        parts = self._encouragement.split("，", 1)
        result: dict[str, str] = {"_1": parts[0]}
        if len(parts) > 1:
            result["_2"] = parts[1]

        # 下班倒计时
        off_str = self._get_off_work_countdown(now)
        if off_str:
            result["距下班"] = off_str

        return result

    # ---- 私有方法 ----

    def _tick(self) -> None:
        """每秒执行一次，按系统时钟整点触发提醒。"""
        now = datetime.now()

        # 非工作日直接跳过
        if not self._is_workday(now):
            self._remaining_seconds = 0
            self._next_reminder_time = None
            self._last_reminder_hour = -1
            return

        if not self._is_in_work_hours(now):
            self._remaining_seconds = 0
            self._next_reminder_time = None
            self._last_reminder_hour = -1
            return

        interval_h = max(1, HEALTH_REMINDER_INTERVAL_S // 3600)
        h, m, s = now.hour, now.minute, now.second

        # 整点提醒：在 h:00 的前几秒内触发
        if m == 0 and s < 5 and h != self._last_reminder_hour:
            self._last_reminder_hour = h
            # 每次提醒随机选一条鼓励语
            self._encouragement = random.choice(HEALTH_ENCOURAGEMENTS)
            # 根据当前是该段工作的第几个小时，选择对应提醒文案
            elapsed_h = self._get_elapsed_hours(now)
            msg = HEALTH_REMINDER_BY_ELAPSED.get(
                str(elapsed_h),
                HEALTH_REMINDER_BY_ELAPSED.get("default", HEALTH_REMINDER_MSG),
            )
            self.reminder_triggered.emit(
                HEALTH_REMINDER_TITLE,
                msg,
            )

        # 计算下一个整点提醒时间
        base_hour = 9
        next_h = h + 1
        while next_h < 24:
            if (next_h - base_hour) % interval_h == 0:
                break
            next_h += 1

        if next_h >= 24:
            self._remaining_seconds = 0
            self._next_reminder_time = None
            return

        self._next_reminder_time = now.replace(
            hour=next_h, minute=0, second=0, microsecond=0
        )
        delta = (self._next_reminder_time - now).total_seconds()
        self._remaining_seconds = max(0, int(delta))

    def _is_workday(self, now: Optional[datetime] = None) -> bool:
        """判断当天是否为工作日。

        工作日 = 周一至周五（排除法定节假日）或 调休补班日。
        """
        if now is None:
            now = datetime.now()
        month_day = (now.month, now.day)

        # 如果是法定节假日，无论周几都是休息日
        if month_day in HOLIDAYS_2026:
            return False

        # 如果是调休补班日，无论周几都是工作日
        if month_day in WORKDAYS_EXTRA_2026:
            return True

        # 周一~周五为工作日，周六日为休息日
        return now.weekday() < 5

    def _is_in_work_hours(self, now: Optional[datetime] = None) -> bool:
        """判断当前是否在工作时段内。"""
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
        """计算距最近的下班时间倒计时。

        每段工作时间对应一个下班时间：
        - 9:00~12:10 段 → 12:10 下班
        - 13:30~24:00 段 → 18:00 下班
        """
        if now is None:
            now = datetime.now()

        current_minutes = now.hour * 60 + now.minute

        # 逐段匹配：当前时间在某段工作时间内，且未超过该段对应的下班时间
        for i, (sh, sm, eh, em) in enumerate(HEALTH_WORK_HOURS):
            work_start = sh * 60 + sm
            work_end = eh * 60 + em
            if not (work_start <= current_minutes < work_end):
                continue
            # 获取该段对应的下班时间
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
        """计算当前是该段工作的第几个小时（从1开始）。

        遍历 HEALTH_WORK_HOURS，找到当前时间所在的段，
        用 (当前时间 - 该段起始时间) 得到已工作小时数。
        如 9:00→1, 10:00→2, 13:30→1（下午段重新计数）。
        """
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
        """非工作时段时，显示下一段工作时间信息。"""
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
