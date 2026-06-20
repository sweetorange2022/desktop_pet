# -*- coding: utf-8 -*-
"""AI 账户余额信息提供者。

实现 InfoProvider 接口，将 AI 余额数据以标准格式展示在信息气泡中。
"""

from __future__ import annotations

from typing import Optional

from src.providers.base import InfoProvider
from src.services.ai_balance import AIBalanceService


class AIBalanceProvider(InfoProvider):
    """AI 账户余额信息提供者。

    通过 AIBalanceService 获取各平台余额，
    格式化为气泡可显示的 {标签: 值} 字典。
    """

    def __init__(self, service: Optional[AIBalanceService] = None) -> None:
        self._service = service or AIBalanceService()
        self._display_data: dict[str, str] = {}

    @property
    def name(self) -> str:
        return "AI 余额"

    @property
    def service(self) -> AIBalanceService:
        return self._service

    def get_data(self) -> dict[str, str]:
        """返回当前余额数据。"""
        if not self._display_data:
            # 尝试获取一次
            self._display_data = self._service.get_display_data()
        return self._display_data

    def update(self) -> None:
        """刷新数据（外部定时调用时使用）。"""
        self._display_data = self._service.get_display_data()

    def refresh_from_service(self) -> None:
        """从服务获取最新数据（回调用）。"""
        self._display_data = self._service.get_display_data()

    def start(self) -> None:
        """启动余额查询服务。"""
        # 注册更新回调
        self._service.set_on_update(self.refresh_from_service)
        self._service.start()

    def stop(self) -> None:
        """停止余额查询服务。"""
        self._service.stop()