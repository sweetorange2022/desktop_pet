"""信息提供者抽象基类。

所有信息源都实现此接口，InfoBubble 通过统一格式显示。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

class InfoProvider(ABC):
    """信息提供者接口。

    实现类负责采集数据并格式化为展示文本。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """提供者名称，用于 UI 显示（如 '系统监控'、'课程表'）。"""

    @abstractmethod
    def get_data(self) -> dict[str, str]:
        """返回当前数据，格式：{行标签: 显示文本}。

        InfoBubble 按字典顺序逐行渲染。
        例如：{"CPU": "52%", "内存": "62%  4.0/8.0 GB"}
        """

    @abstractmethod
    def update(self) -> None:
        """刷新数据（由外部定时调用）。"""
