"""天气预警信息提供者。

每天定时检查明天天气，异常时通过微信发送提醒。

气泡显示天气状态和预警信息。

"""

from __future__ import annotations

import logging

import random

import time

from datetime import datetime

from typing import Optional

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from config import (

    WEATHER_CHECK_HOUR,

    WEATHER_CITY,

    WECHAT_TARGET_NAME,

)

from src.providers.base import InfoProvider

from src.services.weather import (

    WeatherAlert,

    check_weather_alert,

    fetch_today_weather,

    fetch_tomorrow_weather,

)

from src.services.wechat_sender import send_wechat_message

logger = logging.getLogger(__name__)

class _Emitter(QObject):

    """信号发射器。"""

    weather_alert = Signal(str, str)  # (title, message)

    weather_status = Signal(str)      # 状态文本

    data_updated = Signal()           # 数据更新通知

class _WeatherCheckWorker(QThread):

    """天气检查工作线程（避免阻塞 UI）。"""

    finished = Signal(object)  # WeatherAlert 或 None

    def run(self) -> None:

        try:

            tomorrow = fetch_tomorrow_weather()

            if tomorrow is None:

                self.finished.emit(None)

                return

            today = fetch_today_weather()

            alert = check_weather_alert(tomorrow, today)

            self.finished.emit(alert)

        except Exception as e:

            logger.warning("天气检查失败: %s", e)

            self.finished.emit(None)

class WeatherProvider(InfoProvider):

    """天气预警 Provider。

    职责：

    1. 每分钟检查一次是否到了指定时间（20:00）

    2. 到时获取明天天气并分析预警

    3. 有异常时通过微信发送消息

    4. 气泡显示天气状态

    """

    def __init__(self) -> None:

        self._emitter = _Emitter()

        self.weather_alert = self._emitter.weather_alert

        self.data_updated = self._emitter.data_updated

        self._last_check_time: float = 0.0  # 上次检查时间戳

        self._worker: Optional[_WeatherCheckWorker] = None  # 工作线程

        self._checking: bool = False

        self._status: str = "等待检查..."

        self._alert: Optional[WeatherAlert] = None

        # 30分钟检查一次

        self._timer = QTimer()

        self._timer.setInterval(30 * 60 * 1000)  # 30分钟

        self._timer.timeout.connect(self._tick)

    @property

    def name(self) -> str:

        return "天气预警"

    def start(self) -> None:

        """启动定时检查。"""

        self.refresh_now()

        self._timer.start()

    def refresh_now(self) -> None:

        """立即刷新天气数据，由外部（如源切换时）调用。"""

        self._last_check_time = 0.0

        self._tick()

    def _tick(self) -> None:

        """检查是否需要刷新天气数据（已过间隔则执行）。"""

        now = time.monotonic()

        if now - self._last_check_time < 30 * 60:

            return

        self._last_check_time = now

        self._checking = True

        self._status = "正在检查天气..."

        self._worker = _WeatherCheckWorker()

        self._worker.finished.connect(self._on_check_finished)

        self._worker.start()

    def stop(self) -> None:

        """停止定时检查。"""

        self._timer.stop()

    def update(self) -> None:

        """由定时器驱动，外部无需调用。"""

    def get_data(self) -> dict[str, str]:

        """返回当前天气状态。正常天气时描述和温度分两行显示。"""

        if self._alert is not None and self._alert.has_alert:

            return {"城市": WEATHER_CITY, "": self._status}

        elif self._alert is not None:

            info = self._status.split("，", 1)[-1] if "，" in self._status else self._status

            parts = info.split(" ", 1)

            if len(parts) == 2:

                desc, temp = parts[0], parts[1]

            else:

                desc, temp = info, ""

            return {"城市": WEATHER_CITY, "_desc": desc, "_temp": temp}

        return {"城市": WEATHER_CITY, "": self._status}

    def _on_check_finished(self, alert: Optional[WeatherAlert]) -> None:

        """天气检查完毕回调。"""

        self._checking = False

        if alert is None:
            self._status = "天气获取失败"
            self.data_updated.emit()
            return

        self._alert = alert

        self._status = alert.summary

        if alert.has_alert:

            self.weather_alert.emit("天气预警", alert.summary)

        else:

            logger.info("天气无异常: %s", alert.summary)

        self.data_updated.emit()

    def _send_wechat_alert(self, message: str) -> None:

        """通过微信发送天气预警信息。"""

        logger.info("准备发送微信天气预警...")

        success = send_wechat_message(WECHAT_TARGET_NAME, message)

        if success:

            logger.info("微信天气预警已发送成功")

        else:

            logger.warning("微信天气预警发送失败")

