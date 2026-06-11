"""monitor.py 单元测试。

通过 mock psutil 验证数据采集逻辑和异常降级行为。
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from typing import Optional

from PySide6.QtWidgets import QApplication
import sys

# 确保 QApplication 存在（SystemMonitor 继承 QObject）
_app: Optional[QApplication] = None


def setUpModule() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)


from src.core.monitor import SystemMonitor


class TestSystemMonitorCollect(unittest.TestCase):
    """测试 _collect 方法的数据采集和降级逻辑。"""

    def setUp(self) -> None:
        self.monitor = SystemMonitor()
        self.received_metrics: list[dict] = []
        self.monitor.metrics_updated.connect(self.received_metrics.append)

    def tearDown(self) -> None:
        self.monitor.stop()

    @patch.object(SystemMonitor, "_get_temperature_wmi", return_value=None)
    @patch("src.core.monitor.psutil")
    def test_collect_emits_all_keys(self, mock_psutil: MagicMock, _mock_wmi) -> None:
        """采集结果始终包含所有预定义键。"""
        mock_psutil.cpu_percent.return_value = 50.0
        mock_vm = MagicMock()
        mock_vm.percent = 60.0
        mock_vm.used = 4 * (1024 ** 3)
        mock_vm.total = 8 * (1024 ** 3)
        mock_psutil.virtual_memory.return_value = mock_vm

        mock_net = MagicMock()
        mock_net.bytes_sent = 1000
        mock_net.bytes_recv = 2000
        mock_psutil.net_io_counters.return_value = mock_net
        mock_psutil.sensors_temperatures.return_value = {}

        # 预热网速
        self.monitor._last_net_io = mock_net
        import time
        self.monitor._last_net_time = time.monotonic() - 1.0

        self.monitor._collect()

        self.assertEqual(len(self.received_metrics), 1)
        m = self.received_metrics[0]

        expected_keys = {
            "cpu_percent", "memory_percent", "memory_used_gb",
            "memory_total_gb", "net_up_kb", "net_down_kb", "temp_cpu",
            "temp_unsupported",
        }
        self.assertEqual(set(m.keys()), expected_keys)

    @patch("src.core.monitor.psutil")
    def test_cpu_returns_none_on_exception(self, mock_psutil: MagicMock) -> None:
        """CPU 采集异常时返回 None。"""
        mock_psutil.cpu_percent.side_effect = OSError("mock error")
        result = self.monitor._get_cpu()
        self.assertIsNone(result)

    @patch("src.core.monitor.psutil")
    def test_memory_returns_none_on_exception(self, mock_psutil: MagicMock) -> None:
        """内存采集异常时返回 None。"""
        mock_psutil.virtual_memory.side_effect = OSError("mock error")
        result = self.monitor._get_memory()
        self.assertIsNone(result)

    @patch("src.core.monitor.psutil")
    def test_network_returns_none_on_first_call(self, mock_psutil: MagicMock) -> None:
        """首次网速采样返回 None（无历史数据）。"""
        mock_net = MagicMock()
        mock_net.bytes_sent = 1000
        mock_net.bytes_recv = 2000
        mock_psutil.net_io_counters.return_value = mock_net

        self.monitor._last_net_io = None
        result = self.monitor._get_network_speed()
        self.assertIsNone(result)

    @patch("src.core.monitor.psutil")
    def test_temperature_returns_none_when_empty(self, mock_psutil: MagicMock) -> None:
        """无温度传感器时返回 None。"""
        mock_psutil.sensors_temperatures.return_value = {}
        result = self.monitor._get_temperature()
        self.assertIsNone(result)

    @patch("src.core.monitor.psutil")
    def test_temperature_returns_none_on_permission_error(
        self, mock_psutil: MagicMock
    ) -> None:
        """权限不足时温度采集返回 None。"""
        mock_psutil.sensors_temperatures.side_effect = PermissionError()
        result = self.monitor._get_temperature()
        self.assertIsNone(result)

    @patch.object(SystemMonitor, "_get_temperature_wmi", return_value=None)
    @patch("src.core.monitor.psutil")
    def test_collect_with_all_failures(self, mock_psutil: MagicMock, _mock_wmi) -> None:
        """所有采集全部失败时，所有字段为 None，不会抛异常。"""
        mock_psutil.cpu_percent.side_effect = OSError()
        mock_psutil.virtual_memory.side_effect = OSError()
        mock_psutil.net_io_counters.side_effect = OSError()
        mock_psutil.sensors_temperatures.side_effect = OSError()

        # 应该不会抛异常
        self.monitor._collect()

        self.assertEqual(len(self.received_metrics), 1)
        m = self.received_metrics[0]
        for key, value in m.items():
            if key == "temp_unsupported":
                self.assertIsInstance(value, bool)
            else:
                self.assertIsNone(value)


class TestSystemMonitorStartStop(unittest.TestCase):
    """测试 start/stop 生命周期。"""

    def setUp(self) -> None:
        self.monitor = SystemMonitor()

    @patch("src.core.monitor.psutil")
    def test_start_warms_up_network(self, mock_psutil: MagicMock) -> None:
        """start 调用后预热网速采样。"""
        mock_net = MagicMock()
        mock_net.bytes_sent = 0
        mock_net.bytes_recv = 0
        mock_psutil.net_io_counters.return_value = mock_net
        mock_psutil.cpu_percent.return_value = 0.0
        mock_psutil.virtual_memory.return_value = MagicMock(
            percent=0, used=0, total=1
        )
        mock_psutil.sensors_temperatures.return_value = {}

        self.monitor.start()
        self.assertIsNotNone(self.monitor._last_net_io)
        self.monitor.stop()

    def test_stop_after_start(self) -> None:
        """stop 后定时器不再活动。"""
        self.monitor._timer.start()
        self.assertTrue(self.monitor._timer.isActive())
        self.monitor.stop()
        self.assertFalse(self.monitor._timer.isActive())


if __name__ == "__main__":
    unittest.main()