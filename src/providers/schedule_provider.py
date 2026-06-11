# -*- coding: utf-8 -*-

"""课程表信息提供者。

根据当前时间自动判断当天课程进度，显示下一节课或当前课程。

课表数据从 JSON 文件加载，支持右键菜单实时切换。

"""

from __future__ import annotations

import datetime as _dt

import json

from datetime import datetime

from typing import Optional

from src.providers.base import InfoProvider

_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

_AFTERTNOON_TIMES = {

    "下午第1节": (14, 30),

    "下午第2节": (15, 25),

    "下午第3节": (16, 20),

    "下午第4节": (17, 15),

}

_MORNING_TIMES = {

    "第1节": (8, 20),

    "第2节": (9, 35),

    "第3节": (10, 30),

    "第4节": (11, 25),

}

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

        hour = now.hour

        # 20:00+ 显示休息提示

        if hour >= 20:

            if self._is_weekend_tomorrow(now):

                wname = "周六" if (now.weekday() + 1) % 7 == 5 else "周日"

                return {"": "已经很晚了，注意休息", "明天": wname + "，好好放松一下吧~"}

            tomorrow = self._get_tomorrow_simple(now)

            return {

                "": "已经很晚了，注意休息",

                "明天": tomorrow if tomorrow else "明天没有课程",

            }

        # 18:00-19:59 预览明天课程

        if 18 <= hour < 20:

            if self._is_weekend_tomorrow(now):

                wname = "周六" if (now.weekday() + 1) % 7 == 5 else "周日"

                return {"": "明天课程", "关心": wname + "，好好放松一下吧~"}

            tomorrow_detail = self._get_tomorrow_preview_detail(now)

            if tomorrow_detail:

                return {"": "明天课程", **tomorrow_detail}

            return {"": "明天没有课程"}

        # 白天时间：当天课程

        today_schedule = self._schedule.get(weekday, {})

        if not today_schedule:

            return {"": "今天没有课程安排"}

        current_time = now.hour * 60 + now.minute

        result: dict[str, str] = {}

        current_class = self._find_current_class(today_schedule, current_time)

        result["当前"] = current_class if current_class else "无课"

        next_class = self._find_next_class(today_schedule, current_time)

        if next_class:

            result["下一节"] = next_class

        else:

            end_time = self._get_school_end(today_schedule)

            result["下一节"] = f"{end_time} 放学"

        return result

    def _get_tomorrow_simple(self, now: datetime) -> str:

        """获取明天第一节课的简要信息（20点后用）。"""

        tomorrow = now + _dt.timedelta(days=1)

        tomorrow_weekday = _WEEKDAYS[tomorrow.weekday()]

        tomorrow_schedule = self._schedule.get(tomorrow_weekday, {})

        if not tomorrow_schedule:

            return ""

        for period_name, course in tomorrow_schedule.items():

            if course in ("休息，", ""):

                continue

            times = self._get_period_times(period_name)

            if times is None:

                continue

            return f"{course} {times[0]}:{times[1]:02d}开始"

        return ""

    def _get_tomorrow_preview_detail(self, now: datetime) -> Optional[dict[str, str]]:

        """获取明天课程详情（18点后用），返回 None 表示明天无课。"""

        tomorrow = now + _dt.timedelta(days=1)

        tomorrow_weekday = _WEEKDAYS[tomorrow.weekday()]

        tomorrow_schedule = self._schedule.get(tomorrow_weekday, {})

        if not tomorrow_schedule:

            return None

        result: dict[str, str] = {}

        count = 0

        for period_name, course in tomorrow_schedule.items():

            if course in ("休息，", ""):

                continue

            times = self._get_period_times(period_name)

            if times is None:

                continue

            result[f"第{count + 1}节"] = f"{course} {times[0]}:{times[1]:02d}"

            count += 1

            if count >= 3:

                break

        return result if result else None

    def _find_current_class(self, schedule: dict, current_minutes: int) -> Optional[str]:

        for period_name, course in schedule.items():

            times = self._get_period_times(period_name)

            if times is None:

                continue

            start_min = times[0] * 60 + times[1]

            end_min = start_min + 40

            if start_min <= current_minutes < end_min:

                return f"{course} {self._fmt_time(start_min)}-{self._fmt_time(end_min)}"

        return None

    def _find_next_class(self, schedule: dict, current_minutes: int) -> Optional[str]:

        for period_name, course in schedule.items():

            if course in ("休息，", ""):

                continue

            times = self._get_period_times(period_name)

            if times is None:

                continue

            start_min = times[0] * 60 + times[1]

            if current_minutes < start_min:

                return f"{course} {self._fmt_time(start_min)}"

        return None

    @staticmethod

    def _get_school_end(schedule: dict) -> str:

        """获取当天最晚下课时间。"""

        latest = 0

        for period_name in schedule.keys():

            all_times = {**_MORNING_TIMES, **_AFTERTNOON_TIMES}

            times = all_times.get(period_name)

            if times:

                end_min = times[0] * 60 + times[1] + 40

                if end_min > latest:

                    latest = end_min

        if latest > 0:

            return f"{latest // 60:02d}:{latest % 60:02d}"

        return "16:05"

    @staticmethod

    def _get_period_times(period_name: str) -> Optional[tuple[int, int]]:

        all_times = {**_AFTERTNOON_TIMES, **_MORNING_TIMES}

        return all_times.get(period_name)

    @staticmethod

    def _is_weekend_tomorrow(now: datetime) -> bool:

        """判断明天是否是周末。"""

        return (now.weekday() + 1) % 7 >= 5  # 5=周六, 6=周日

    @staticmethod

    def _fmt_time(minutes: int) -> str:

        return f"{minutes // 60:02d}:{minutes % 60:02d}"

