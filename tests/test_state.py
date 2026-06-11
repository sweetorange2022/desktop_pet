"""state.py 单元测试。

覆盖 PetState 枚举、evaluate 纯函数、get_state_color。
"""

from __future__ import annotations

import unittest
from typing import Optional

from config import (
    CPU_HIGH_THRESHOLD,
    MEMORY_HIGH_THRESHOLD,
    NET_HIGH_THRESHOLD_KB,
    TEMP_HIGH_THRESHOLD,
)
from src.core.state import PetState, evaluate, get_state_color


class TestPetStateEnum(unittest.TestCase):
    """PetState 枚举值测试。"""

    def test_all_states_exist(self) -> None:
        self.assertEqual(len(PetState), 5)
        self.assertEqual(PetState.IDLE.value, "idle")
        self.assertEqual(PetState.HIGH_CPU.value, "high_cpu")
        self.assertEqual(PetState.HIGH_MEMORY.value, "high_memory")
        self.assertEqual(PetState.HIGH_TEMP.value, "high_temp")
        self.assertEqual(PetState.HIGH_NETWORK.value, "high_network")


class TestEvaluate(unittest.TestCase):
    """evaluate 纯函数测试。"""

    def _make_metrics(
        self,
        cpu: Optional[float] = None,
        mem: Optional[float] = None,
        temp: Optional[float] = None,
        net_down: Optional[float] = None,
    ) -> dict[str, Optional[float]]:
        return {
            "cpu_percent": cpu,
            "memory_percent": mem,
            "memory_used_gb": None,
            "memory_total_gb": None,
            "net_up_kb": None,
            "net_down_kb": net_down,
            "temp_cpu": temp,
        }

    def test_all_none_returns_idle(self) -> None:
        result = evaluate(self._make_metrics())
        self.assertEqual(result, PetState.IDLE)

    def test_normal_values_returns_idle(self) -> None:
        metrics = self._make_metrics(cpu=50.0, mem=60.0, temp=40.0, net_down=100.0)
        self.assertEqual(evaluate(metrics), PetState.IDLE)

    def test_high_temperature_highest_priority(self) -> None:
        """温度超过阈值，即使 CPU/内存/网速也超，仍返回 HIGH_TEMP。"""
        metrics = self._make_metrics(
            cpu=CPU_HIGH_THRESHOLD + 1,
            mem=MEMORY_HIGH_THRESHOLD + 1,
            temp=TEMP_HIGH_THRESHOLD,
            net_down=NET_HIGH_THRESHOLD_KB + 1,
        )
        self.assertEqual(evaluate(metrics), PetState.HIGH_TEMP)

    def test_high_cpu_second_priority(self) -> None:
        metrics = self._make_metrics(
            cpu=CPU_HIGH_THRESHOLD,
            mem=MEMORY_HIGH_THRESHOLD + 1,
            net_down=NET_HIGH_THRESHOLD_KB + 1,
        )
        self.assertEqual(evaluate(metrics), PetState.HIGH_CPU)

    def test_high_memory_third_priority(self) -> None:
        metrics = self._make_metrics(
            mem=MEMORY_HIGH_THRESHOLD,
            net_down=NET_HIGH_THRESHOLD_KB + 1,
        )
        self.assertEqual(evaluate(metrics), PetState.HIGH_MEMORY)

    def test_high_network_fourth_priority(self) -> None:
        metrics = self._make_metrics(net_down=NET_HIGH_THRESHOLD_KB)
        self.assertEqual(evaluate(metrics), PetState.HIGH_NETWORK)

    def test_boundary_below_threshold_is_idle(self) -> None:
        metrics = self._make_metrics(cpu=CPU_HIGH_THRESHOLD - 0.1)
        self.assertEqual(evaluate(metrics), PetState.IDLE)

    def test_empty_dict_returns_idle(self) -> None:
        self.assertEqual(evaluate({}), PetState.IDLE)

    def test_partial_metrics(self) -> None:
        """只提供部分指标不影响判定。"""
        metrics = {"cpu_percent": 90.0}
        self.assertEqual(evaluate(metrics), PetState.HIGH_CPU)


class TestGetStateColor(unittest.TestCase):
    """get_state_color 测试。"""

    def test_idle_color(self) -> None:
        self.assertEqual(get_state_color(PetState.IDLE), "#4CAF50")

    def test_high_cpu_color(self) -> None:
        self.assertEqual(get_state_color(PetState.HIGH_CPU), "#FF9800")

    def test_high_memory_color(self) -> None:
        self.assertEqual(get_state_color(PetState.HIGH_MEMORY), "#FF9800")

    def test_high_temp_color(self) -> None:
        self.assertEqual(get_state_color(PetState.HIGH_TEMP), "#F44336")

    def test_high_network_color(self) -> None:
        self.assertEqual(get_state_color(PetState.HIGH_NETWORK), "#4CAF50")


if __name__ == "__main__":
    unittest.main()