"""系统监控信息提供者。

封装现有 monitor.py 的采集逻辑，以 Provider 接口暴露。
"""

from __future__ import annotations

from typing import Optional

from src.providers.base import InfoProvider

class SystemProvider(InfoProvider):
    """系统监控数据提供者。

    从 SystemMonitor 接收 metrics dict，格式化为气泡展示文本。
    """

    def __init__(self) -> None:
        self._cpu: Optional[float] = None
        self._mem_pct: Optional[float] = None
        self._mem_used: Optional[float] = None
        self._mem_total: Optional[float] = None
        self._net_down: Optional[float] = None
        self._net_up: Optional[float] = None

    @property
    def name(self) -> str:
        return "系统监控"

    def update(self) -> None:
        """数据由外部通过 update_metrics() 推送。"""
        # SystemProvider 的数据由主循环推入，update() 无需操作

    def update_metrics(self, metrics: dict) -> None:
        """接收 SystemMonitor 发射的原始 metrics dict。"""
        self._cpu = metrics.get("cpu_percent")
        self._mem_pct = metrics.get("memory_percent")
        self._mem_used = metrics.get("memory_used_gb")
        self._mem_total = metrics.get("memory_total_gb")
        self._net_down = metrics.get("net_down_kb")
        self._net_up = metrics.get("net_up_kb")

    def get_data(self) -> dict[str, str]:
        """返回格式化后的系统信息。"""
        cpu_str = f"{self._cpu:.0f}%" if self._cpu is not None else "--"

        if self._mem_pct is not None:
            mem_str = f"{self._mem_pct:.0f}%"
            if self._mem_used is not None and self._mem_total is not None:
                mem_str += f" {self._mem_used}/{self._mem_total}GB"
        else:
            mem_str = "--"

        net_down = self._fmt_speed(self._net_down)
        net_up = self._fmt_speed(self._net_up)
        return {
            "CPU": cpu_str,
            "内存": mem_str,
            "网络": f"↓{net_down} ↑{net_up}",
        }

    @staticmethod
    def _fmt_speed(value: Optional[float]) -> str:
        if value is None:
            return "--KB/s"
        if value >= 1024:
            return f"{value / 1024:.1f}MB/s"
        return f"{value:.0f}KB/s"
