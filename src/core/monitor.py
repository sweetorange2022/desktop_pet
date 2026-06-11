"""系统资源监控模块。

通过 psutil 采集 CPU、内存、网速、温度数据，
通过 Qt Signal 解耦 UI 层。
"""

from __future__ import annotations

import subprocess
import time
from typing import Optional

import psutil
from PySide6.QtCore import QObject, QTimer, Signal

from config import MONITOR_INTERVAL_MS

class SystemMonitor(QObject):
    """定时采集系统指标，通过信号发射给 UI 层。

    职责：
    1. 定时采集 CPU、内存、网速、温度
    2. 通过 metrics_updated 信号发射数据
    3. 异常时优雅降级，对应字段返回 None

    不变量：
    - metrics_updated 发射的 dict 始终包含所有预定义键
    - 单个字段采集失败不影响其他字段
    """

    metrics_updated = Signal(dict)
    """每秒发射一次，payload 结构：
    {
        "cpu_percent": float | None,
        "memory_percent": float | None,
        "memory_used_gb": float | None,
        "memory_total_gb": float | None,
        "net_up_kb": float | None,       # 上传速度 (KB/s)
        "net_down_kb": float | None,     # 下载速度 (KB/s)
        "temp_cpu": float | None,        # CPU温度 (°C)
    }
    """

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(MONITOR_INTERVAL_MS)
        self._timer.timeout.connect(self._collect)

        # 网速计算：记录上次采样值
        self._last_net_io: Optional[psutil._common.snetio] = None
        self._last_net_time: float = 0.0

        # 温度缓存：WMI 调用慢，只在启动时尝试一次
        self._temp_cached: Optional[float] = None
        self._temp_resolved: bool = False  # 是否已完成首次探测

    def start(self) -> None:
        """启动定时采集。首次调用时预热网速采样。"""
        self._warmup_network()
        self._timer.start()

    def stop(self) -> None:
        """停止采集。"""
        self._timer.stop()

    # ---- 私有采集方法 ----

    def _collect(self) -> None:
        """一次性采集所有指标，异常字段降级为 None。"""
        metrics: dict[str, Optional[float]] = {
            "cpu_percent": self._get_cpu(),
            "memory_percent": None,
            "memory_used_gb": None,
            "memory_total_gb": None,
            "net_up_kb": None,
            "net_down_kb": None,
            "temp_cpu": self._get_temperature(),
            "temp_unsupported": self._temp_resolved and self._temp_cached is None,
        }
        mem = self._get_memory()
        if mem is not None:
            metrics["memory_percent"] = mem["percent"]
            metrics["memory_used_gb"] = mem["used_gb"]
            metrics["memory_total_gb"] = mem["total_gb"]

        net = self._get_network_speed()
        if net is not None:
            metrics["net_up_kb"] = net["up_kb"]
            metrics["net_down_kb"] = net["down_kb"]

        self.metrics_updated.emit(metrics)

    def _get_cpu(self) -> Optional[float]:
        """采集 CPU 使用率。"""
        try:
            return psutil.cpu_percent(interval=None)
        except (AttributeError, OSError):
            return None

    def _get_memory(self) -> Optional[dict[str, float]]:
        """采集内存信息，返回 percent/used_gb/total_gb。"""
        try:
            vm = psutil.virtual_memory()
            return {
                "percent": vm.percent,
                "used_gb": round(vm.used / (1024 ** 3), 1),
                "total_gb": round(vm.total / (1024 ** 3), 1),
            }
        except (AttributeError, OSError):
            return None

    def _warmup_network(self) -> None:
        """预热网速采样（首次差值无意义）。"""
        try:
            self._last_net_io = psutil.net_io_counters()
            self._last_net_time = time.monotonic()
        except (AttributeError, OSError):
            self._last_net_io = None

    def _get_network_speed(self) -> Optional[dict[str, float]]:
        """基于差值计算网速 (KB/s)。"""
        try:
            current = psutil.net_io_counters()
            now = time.monotonic()
        except (AttributeError, OSError):
            return None

        if self._last_net_io is None:
            self._last_net_io = current
            self._last_net_time = now
            return None  # 首次采样无效

        elapsed = now - self._last_net_time
        if elapsed <= 0:
            return None

        up_speed = (current.bytes_sent - self._last_net_io.bytes_sent) / elapsed / 1024
        down_speed = (current.bytes_recv - self._last_net_io.bytes_recv) / elapsed / 1024

        self._last_net_io = current
        self._last_net_time = now

        return {"up_kb": round(up_speed, 1), "down_kb": round(down_speed, 1)}

    def _get_temperature(self) -> Optional[float]:
        """采集 CPU 温度。首次尝试 psutil + WMI，之后使用缓存。

        WMI 调用阻塞且慢，只在首次采集时执行一次。
        """
        if self._temp_resolved:
            return self._temp_cached

        # 首次探测
        result = self._get_temperature_psutil()
        if result is not None:
            self._temp_cached = result
            self._temp_resolved = True
            return result

        # psutil 无数据，尝试 WMI（仅一次）
        result = self._get_temperature_wmi()
        self._temp_cached = result  # None 也缓存，表示不支持
        self._temp_resolved = True
        return result

    def _get_temperature_psutil(self) -> Optional[float]:
        """通过 psutil 采集 CPU 温度。"""
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return None
            for entries in temps.values():
                if entries:
                    return entries[0].current
            return None
        except (AttributeError, OSError, PermissionError):
            return None

    def _get_temperature_wmi(self) -> Optional[float]:
        """通过 WMI 命令行采集 CPU 温度（Windows 降级方案）。

        使用 PowerShell 调用 WMI，不需要额外依赖。
        返回摄氏温度，失败或不支持返回 None。
        """
        try:
            ps_script = (
                "Get-WmiObject MSAcpi_ThermalZoneTemperature "
                "-Namespace 'root/wmi' -ErrorAction Stop | "
                "Select-Object -First 1 -ExpandProperty CurrentTemperature"
            )
            output = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps_script],
                timeout=5,
                stderr=subprocess.DEVNULL,
            )
            raw_centi = float(output.strip())
            if raw_centi <= 0:
                return None  # 返回0表示不支持
            # WMI 返回值是 0.1 开尔文单位，转换为摄氏度
            celsius = raw_centi / 10.0 - 273.15
            if -40 < celsius < 150:
                return round(celsius, 1)
            return None
        except (subprocess.SubprocessError, ValueError, OSError):
            return None
