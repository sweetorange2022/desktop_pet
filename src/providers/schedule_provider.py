# -*- coding: utf-8 -*-

"""课程表信息提供者。

根据当前时间自动判断当天课程进度，显示完整课程安排。
支持周末、法定节假日、调休日等场景的个性化提示。
所有内容带"大王"和"麒麟洞-马小九提示"前缀。
"""

from __future__ import annotations

import datetime as _dt
import json
from datetime import datetime
from typing import Optional

from src.providers.base import InfoProvider

_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

_MORNING_TIMES = {
    "第1节": (8, 20),
    "第2节": (9, 35),
    "第3节": (10, 30),
    "第4节": (11, 25),
}

_AFTERTNOON_TIMES = {
    "下午第1节": (14, 30),
    "下午第2节": (15, 25),
    "下午第3节": (16, 20),
    "下午第4节": (17, 15),
}

_ALL_TIMES = {**_MORNING_TIMES, **_AFTERTNOON_TIMES}

# 前缀
_PREFIX = "大王，麒麟洞-马小九提示："


class ScheduleProvider(InfoProvider):

    """课程表信息提供者。"""

    def __init__(self, schedule_path: Optional[str] = None) -> None:
        self._schedule: dict = {}
        if schedule_path:
            self.load(schedule_path)

    @property
    def name(self) -> str:
        return "课程表"

    def load(self, path: str) -> None:
        """从 JSON 文件加载课表数据。"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._schedule = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._schedule = {}

    def update(self) -> None:
        pass

    def get_data(self) -> dict[str, str]:
        now = datetime.now()
        weekday = _WEEKDAYS[now.weekday()]
        hour, minute = now.hour, now.minute
        current_min = hour * 60 + minute

        # ---- 判断是否为法定节假日 ----
        if self._is_holiday(now):
            # 假期最后一天晚上
            if hour >= 19 and self._is_holiday(self._tomorrow(now)):
                pass  # 继续到正常逻辑
            elif hour >= 19 and not self._is_holiday(self._tomorrow(now)):
                # 假期最后一天晚
                first = self._get_tomorrow_first_class(now)
                lines = [_PREFIX, "假期余额不足，明天要上班啦~"]
                if first:
                    lines.append(first)
                return self._make_result(lines)
            else:
                return self._make_result([_PREFIX, "今天是假期，好好放松~"])

        # ---- 周六 ----
        if now.weekday() == 5:
            return self._make_result([_PREFIX, "周末，好好享受~"])

        # ---- 周日 ----
        if now.weekday() == 6:
            if hour >= 20:
                # 周日晚上提醒明天上班
                first = self._get_tomorrow_first_class(now)
                lines = [_PREFIX, "明天要上班啦，早点休息~"]
                if first:
                    lines.append(first)
                return self._make_result(lines)
            return self._make_result([_PREFIX, "周末，好好享受~"])

        # ---- 工作日 ----
        today_schedule = self._schedule.get(weekday, {})

        # 无课日
        if not today_schedule:
            return self._make_result([_PREFIX, "今天没有课，辛苦啦~"])

        # 计算最后一节课结束时间
        last_class_end = self._get_last_class_end(today_schedule)

        # 19:00 以后：辛苦啦
        if hour >= 19:
            return self._make_result([_PREFIX, "辛苦啦，好好休息~"])

        # 最后一节课结束到 19:00 之间：显示明天课程预览
        if last_class_end and current_min >= last_class_end:
            # 判断明天是否为周末
            tomorrow = self._tomorrow(now)
            if tomorrow.weekday() >= 5:  # 明天周六或周日
                return self._make_result([_PREFIX, "明天是周末，好好休息~"])
            preview = self._get_tomorrow_preview(now)
            if preview:
                lines = [_PREFIX, "明天课程："]
                lines.extend(preview)
                return self._make_result(lines)
            return self._make_result([_PREFIX, "明天没有课，辛苦啦~"])

        # 白天：显示今天全部课程
        lines = [_PREFIX, "今天课程："]
        lines.extend(self._format_full_schedule(today_schedule))
        return self._make_result(lines)

    # ---- 辅助方法 ----

    def _make_result(self, lines: list[str]) -> dict[str, str]:
        """将多行文本转为 dict 格式，适配 InfoBubble。"""
        result: dict[str, str] = {}
        for i, line in enumerate(lines):
            result[f"_{i + 1}"] = line
        return result

    def _format_full_schedule(self, schedule: dict) -> list[str]:
        """格式化当天全部课程。"""
        lines: list[str] = []
        for period_name, course in schedule.items():
            times = _ALL_TIMES.get(period_name)
            if times and course and course not in ("休息，", "（空）", ""):
                lines.append(f"{times[0]}:{times[1]:02d} {course}")
        return lines if lines else ["今天没有课程安排"]

    def _get_last_class_end(self, schedule: dict) -> Optional[int]:
        """获取最后一节课结束时间（分钟）。"""
        latest = 0
        for period_name, course in schedule.items():
            if course in ("休息，", "（空）", ""):
                continue
            times = _ALL_TIMES.get(period_name)
            if times:
                end_min = times[0] * 60 + times[1] + 40
                if end_min > latest:
                    latest = end_min
        return latest if latest > 0 else None

    def _get_tomorrow_preview(self, now: datetime) -> Optional[list[str]]:
        """获取明天课程预览。"""
        tomorrow = self._tomorrow(now)
        tomorrow_weekday = _WEEKDAYS[tomorrow.weekday()]
        tomorrow_schedule = self._schedule.get(tomorrow_weekday, {})
        if not tomorrow_schedule:
            return None
        lines: list[str] = []
        for period_name, course in tomorrow_schedule.items():
            times = _ALL_TIMES.get(period_name)
            if times and course and course not in ("休息，", "（空）", ""):
                lines.append(f"{times[0]}:{times[1]:02d} {course}")
        return lines if lines else None

    def _get_tomorrow_first_class(self, now: datetime) -> Optional[str]:
        """获取明天第一节课（单行）。"""
        tomorrow = self._tomorrow(now)
        tomorrow_weekday = _WEEKDAYS[tomorrow.weekday()]
        tomorrow_schedule = self._schedule.get(tomorrow_weekday, {})
        if not tomorrow_schedule:
            return None
        for period_name, course in tomorrow_schedule.items():
            times = _ALL_TIMES.get(period_name)
            if times and course and course not in ("休息，", "（空）", ""):
                return f"{times[0]}:{times[1]:02d} {course}"
        return None

    @staticmethod
    def _tomorrow(now: datetime) -> datetime:
        return now + _dt.timedelta(days=1)

    @staticmethod
    def _is_holiday(date: datetime) -> bool:
        """判断是否为法定节假日。"""
        from config import HOLIDAYS_2026, WORKDAYS_EXTRA_2026
        month_day = (date.month, date.day)
        if month_day in WORKDAYS_EXTRA_2026:
            return False  # 调休补班日不算假期
        if month_day in HOLIDAYS_2026:
            return True
        # 周末
        return date.weekday() >= 5