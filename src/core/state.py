"""宠物状态评估模块。

纯函数，给定系统指标 dict 返回当前状态。
职责：根据 CPU、内存、网速、温度判定宠物状态。
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from config import (
    CPU_HIGH_THRESHOLD,
    MEMORY_HIGH_THRESHOLD,
    NET_HIGH_THRESHOLD_KB,
    TEMP_HIGH_THRESHOLD,
)

class PetState(Enum):
    """宠物状态枚举。Phase 2 扩展时在此新增值即可。"""

    IDLE = "idle"
    HIGH_CPU = "high_cpu"
    HIGH_MEMORY = "high_memory"
    HIGH_TEMP = "high_temp"
    HIGH_NETWORK = "high_network"

def evaluate(metrics: dict[str, Optional[float]]) -> PetState:
    """根据系统指标判定状态。优先级：温度 > CPU > 内存 > 网速 > 空闲。

    不变量：始终返回一个有效的 PetState，不会抛异常。
    """
    temp = metrics.get("temp_cpu")
    if temp is not None and temp >= TEMP_HIGH_THRESHOLD:
        return PetState.HIGH_TEMP

    cpu = metrics.get("cpu_percent")
    if cpu is not None and cpu >= CPU_HIGH_THRESHOLD:
        return PetState.HIGH_CPU

    mem = metrics.get("memory_percent")
    if mem is not None and mem >= MEMORY_HIGH_THRESHOLD:
        return PetState.HIGH_MEMORY

    net_down = metrics.get("net_down_kb")
    if net_down is not None and net_down >= NET_HIGH_THRESHOLD_KB:
        return PetState.HIGH_NETWORK

    return PetState.IDLE

def get_state_color(state: PetState) -> str:
    """返回状态对应的十六进制颜色值。"""
    from config import COLOR_DANGER, COLOR_IDLE, COLOR_WARNING

    color_map: dict[PetState, str] = {
        PetState.IDLE: COLOR_IDLE,
        PetState.HIGH_CPU: COLOR_WARNING,
        PetState.HIGH_MEMORY: COLOR_WARNING,
        PetState.HIGH_TEMP: COLOR_DANGER,
        PetState.HIGH_NETWORK: COLOR_IDLE,
    }
    return color_map[state]

# ── 标签颜色辅助函数 ──────────────────────────────────────

_NET_COLOR_GOOD = "#4CAF50"   # 绿
_NET_COLOR_WARN = "#FF9800"   # 橙
_NET_COLOR_BAD  = "#F44336"   # 红

def get_net_label_color(net_down_kb: float | None) -> str:
    """根据下载速度返回网络标签颜色"""
    if net_down_kb is None:
        return _NET_COLOR_BAD
    if net_down_kb > 200:
        return _NET_COLOR_GOOD
    elif net_down_kb >= 30:
        return _NET_COLOR_WARN
    else:
        return _NET_COLOR_BAD

def get_mem_label_color(mem_percent: float | None) -> str:
    """根据内存使用率返回内存标签颜色"""
    if mem_percent is None:
        return _NET_COLOR_GOOD
    if mem_percent < 70:
        return _NET_COLOR_GOOD
    elif mem_percent < 85:
        return _NET_COLOR_WARN
    else:
        return _NET_COLOR_BAD
