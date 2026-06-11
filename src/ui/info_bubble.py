"""系统信息气泡模块。

支持多信息提供者，通过 Provider 模式切换展示数据。
labels 初始化后永不销毁，只更新文本，彻底消除文字消失问题。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPen, QLinearGradient, QColor, QFont
import re
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from config import (
    BUBBLE_AUTO_HIDE_MS,
    BUBBLE_HEIGHT,
    BUBBLE_STYLE,
    BUBBLE_WIDTH,
)
from src.providers.base import InfoProvider
from src.core.state import get_net_label_color, get_mem_label_color

class _GradientLabel(QLabel):
    """QLabel 子类，用水平渐变颜色渲染文字。
    如果文本包含 HTML <span>（如网络/内存的独立颜色），则回退到普通 QLabel 渲染。
    """

    _GRADIENT_COLORS = ["#00D4FF", "#7B61FF", "#B44AFF"]

    def paintEvent(self, event) -> None:
        text = self.text()
        if not text:
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self.font())
        fm = self.fontMetrics()

        if "<span" in text:
            # 拆分带颜色的标签 + 数值部分
            import re
            m = re.search(r"<span style='color:([^']+)'>([^<]+)</span>", text)
            if m:
                label_color, label_text = m.group(1), m.group(2)
                rest = text[m.end():]
                if rest.startswith("  "):
                    rest = rest[2:]

                # 绘制标签（保留原有颜色）
                painter.setPen(QColor(label_color))
                label_rect = self.rect()
                painter.drawText(label_rect, int(self.alignment()), label_text)

                # 与 CPU 行一致：标签列宽 = 文字 + 两个空格
                label_w = fm.horizontalAdvance(label_text + "  ")

                # 绘制数值部分（渐变）
                grad = QLinearGradient(label_w, 0, self.width(), 0)
                n = len(self._GRADIENT_COLORS)
                for i, h in enumerate(self._GRADIENT_COLORS):
                    grad.setColorAt(i / (n - 1), QColor(h))
                painter.setPen(QPen(grad, 1))

                r = self.rect()
                rest_rect = r.__class__(label_w, r.top(), r.width() - label_w, r.height())
                painter.drawText(rest_rect, int(self.alignment()), rest)
                painter.end()
                return

        # 普通文字：全部渐变
        grad = QLinearGradient(0, 0, self.width(), 0)
        n = len(self._GRADIENT_COLORS)
        for i, h in enumerate(self._GRADIENT_COLORS):
            grad.setColorAt(i / (n - 1), QColor(h))
        painter.setPen(QPen(grad, 1))
        painter.drawText(self.rect(), int(self.alignment()), text)
        painter.end()

class InfoBubble(QWidget):
    """半透明气泡窗口，展示系统指标数据。"""

    MAX_LABELS = 6  # 最多显示 6 行

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("info_bubble")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(BUBBLE_WIDTH)
        self.setMaximumWidth(int(BUBBLE_WIDTH * 3))
        self.setStyleSheet(BUBBLE_STYLE)

        # 固定数量的 label，永不销毁
        self._labels: list[QLabel] = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 10, 14, 10)
        self._layout.setSpacing(6)

        for _ in range(self.MAX_LABELS):
            lbl = _GradientLabel("")
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            lbl.setWordWrap(False)
            self._layout.addWidget(lbl)
            self._labels.append(lbl)

        self._provider: Optional[InfoProvider] = None
        self._metrics: dict | None = None
        self._line_count: int = 0  # 当前有效行数

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(BUBBLE_AUTO_HIDE_MS)
        self._hide_timer.timeout.connect(self.hide)

    @property
    def provider(self) -> Optional[InfoProvider]:
        """当前信息提供者。"""
        return self._provider

    @property
    def provider_name(self) -> str:
        """当前提供者名称。"""
        return self._provider.name if self._provider else "无"

    def set_provider(self, provider: Optional[InfoProvider]) -> None:
        """切换信息提供者。不重建 label，只更新内容。"""
        self._provider = provider
        self._refresh()

    def _refresh(self) -> None:
        """刷新所有 label 内容。永不创建或销毁 label。"""
        self._hide_timer.stop()

        # 清空所有 label
        for lbl in self._labels:
            lbl.setText("")
            lbl.hide()

        if self._provider is None:
            self._line_count = 0
            self._refresh_geometry()
            return

        data = self._provider.get_data()
        if not data:
            self._line_count = 0
            self._refresh_geometry()
            return

        fm = self.fontMetrics()
        max_text_width = 0
        line_idx = 0

        # 先遍历一次计算所有 key 的视觉宽度，便于对齐
        all_keys = []
        max_kw = 0
        for key in data:
            if len(all_keys) >= self.MAX_LABELS:
                break
            kw = fm.horizontalAdvance(key + "  ") if key and not key.startswith("_") else 0
            all_keys.append((key, kw))
            if kw > max_kw:
                max_kw = kw
        space_w = max(1, fm.horizontalAdvance(" "))

        for key, _ in all_keys:
            if line_idx >= self.MAX_LABELS:
                break
            text = data[key]
            kw = fm.horizontalAdvance(key + "  ")
            # 补空格使所有 key 的视觉宽度一致
            pad_needed = max(0, max_kw - kw)
            extra = int(pad_needed / space_w) if space_w > 0 else 0
            prefix = f"{key}  {' ' * extra}" if key and not key.startswith("_") else ""
            full_text = f"{prefix}{text}"
            # 监控模式下给网络、内存标签加颜色
            if self._metrics is not None:
                if key == "网络":
                    c = get_net_label_color(self._metrics.get("net_down_kb"))
                    full_text = full_text.replace(key, f"<span style='color:{c}'>{key}</span>", 1)
                elif key == "内存":
                    c = get_mem_label_color(self._metrics.get("memory_percent"))
                    full_text = full_text.replace(key, f"<span style='color:{c}'>{key}</span>", 1)
            if "<span" in full_text:
                self._labels[line_idx].setTextFormat(Qt.TextFormat.RichText)
            else:
                self._labels[line_idx].setTextFormat(Qt.TextFormat.PlainText)
            self._labels[line_idx].setText(full_text)
            self._labels[line_idx].show()
            # 计算时移除 HTML 标签（排除 span 干扰）
            measure_text = re.sub(r"<[^>]+>", "", full_text)
            tw = fm.horizontalAdvance(measure_text)
            if tw > max_text_width:
                max_text_width = tw
            line_idx += 1

        self._line_count = line_idx
        self._refresh_geometry(max_text_width)

    def _refresh_geometry(self, text_width: int = 0) -> None:
        """根据内容调整气泡大小。"""
        margins = self._layout.contentsMargins()
        if text_width > 0:
            needed = text_width + margins.left() + margins.right() + 20
            clamped = max(BUBBLE_WIDTH, min(needed, self.maximumWidth()))
            if clamped != self.width():
                self.setFixedWidth(clamped)
        else:
            # 无内容时保持最小宽度
            if self.width() != BUBBLE_WIDTH:
                self.setFixedWidth(BUBBLE_WIDTH)
        self.adjustSize()

    def update_data(self, metrics: dict) -> None:
        """兼容旧接口，直接传入数据。"""
        if self._provider is None:
            keys = ["CPU", "内存", "网络"]
            fm = self.fontMetrics()
            # 计算各 key 的视觉宽度并补空格对齐
            key_widths = []
            max_kw = 0
            for key in keys[:self.MAX_LABELS]:
                kw = fm.horizontalAdvance(key + "  ")
                key_widths.append(kw)
                if kw > max_kw:
                    max_kw = kw
            space_w = fm.horizontalAdvance(" ")
            for i, key in enumerate(keys):
                if i >= self.MAX_LABELS:
                    break
                kw = key_widths[i]
                pad_needed = max(0, max_kw - kw)
                extra = int(pad_needed / space_w) if space_w > 0 else 0
                padded_key = key + "  " + " " * extra
                text = f"{padded_key}{metrics.get(key, '--')}"
                self._labels[i].setText(text)
                self._labels[i].show()
                tw = fm.horizontalAdvance(text)
                if tw > max_kw:
                    max_kw = tw
            self._line_count = min(len(keys), self.MAX_LABELS)
            self._refresh_geometry(max_kw)

    def update_metrics(self, metrics: dict) -> None:
        """接收原始监控数据，刷新当前 Provider。"""
        self._metrics = metrics
        if self._provider and hasattr(self._provider, "update_metrics"):
            self._provider.update_metrics(metrics)
            self._refresh()

    def show_bubble(self, x: int, y: int, auto_hide: bool = False) -> None:
        """在指定位置显示气泡，默认一直显示直到下次调用。"""
        self._hide_timer.stop()
        self._refresh()
        self.adjustSize()
        self.move(x, y)
        self.show()
        self.raise_()
        if auto_hide:
            self._hide_timer.start()

    def pause_hide_timer(self) -> None:
        """暂停自动隐藏计时器（拖拽时调用）。"""
        self._hide_timer.stop()

    def resume_hide_timer(self) -> None:
        """恢复自动隐藏计时器（拖拽结束时调用）。"""
        if self.isVisible():
            self._hide_timer.start()
