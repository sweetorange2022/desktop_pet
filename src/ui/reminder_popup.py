"""持久化健康提醒弹窗模块。

特点：
- 半透明背景，圆角卡片样式
- 右上角关闭按钮（可见）
- "打开数据" 按钮可快速跳转检测数据目录
- 自动在下一次提醒时替换，或手动关闭
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ReminderPopup(QWidget):
    """持久化健康提醒弹窗，显示在屏幕右下角。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(380)
        self._snapshot_dir: str = ""

        self._setup_ui()

    def _setup_ui(self) -> None:
        """构建 UI。"""
        # 外层容器（带背景）
        self._container = QWidget(self)
        self._container.setObjectName("reminder_container")
        self._container.setStyleSheet(
            """
            QWidget#reminder_container {
                background-color: rgba(30, 30, 30, 240);
                border: 1px solid rgba(255, 255, 255, 60);
                border-radius: 14px;
            }
            """
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._container)

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        # 顶部：标题 + 关闭按钮
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self._title_label = QLabel("")
        self._title_label.setStyleSheet(
            "color: #4FC3F7; font-size: 15px; font-weight: bold; "
            "font-family: 'Microsoft YaHei', sans-serif;"
        )
        top_row.addWidget(self._title_label)
        top_row.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(
            """
            QPushButton {
                color: #AAAAAA;
                background-color: transparent;
                border: none;
                font-size: 16px;
                font-weight: bold;
                border-radius: 12px;
            }
            QPushButton:hover {
                color: #FFFFFF;
                background-color: rgba(255, 80, 80, 180);
            }
            """
        )
        btn_close.clicked.connect(self.hide)
        top_row.addWidget(btn_close)

        layout.addLayout(top_row)

        # 消息内容
        self._msg_label = QLabel("")
        self._msg_label.setWordWrap(True)
        self._msg_label.setStyleSheet(
            "color: #F0F0F0; font-size: 13px; line-height: 1.5; "
            "font-family: 'Microsoft YaHei', sans-serif;"
        )
        layout.addWidget(self._msg_label)

        # 底部按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._btn_open = QPushButton("📂 打开数据")
        self._btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_open.setStyleSheet(
            """
            QPushButton {
                color: #FFFFFF;
                background-color: rgba(76, 175, 80, 200);
                border: none;
                border-radius: 8px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: bold;
                font-family: 'Microsoft YaHei', sans-serif;
            }
            QPushButton:hover {
                background-color: rgba(76, 175, 80, 255);
            }
            """
        )
        self._btn_open.clicked.connect(self._open_snapshot_dir)
        btn_row.addWidget(self._btn_open)
        btn_row.addStretch()

        layout.addLayout(btn_row)

    def show_reminder(self, title: str, message: str, snapshot_dir: str = "") -> None:
        """显示提醒弹窗。如果已有弹窗则替换内容。"""
        self._title_label.setText(title)
        self._msg_label.setText(message)
        self._snapshot_dir = snapshot_dir

        # 有数据目录时显示按钮，否则隐藏
        has_dir = bool(snapshot_dir) and os.path.isdir(snapshot_dir)
        self._btn_open.setVisible(has_dir)

        # 定位到屏幕右下角
        self.adjustSize()
        self._move_to_bottom_right()

        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()

    def _move_to_bottom_right(self) -> None:
        """将弹窗移到屏幕右下角。"""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.right() - self.width() - 20
        y = geo.bottom() - self.height() - 60
        self.move(x, y)

    def _open_snapshot_dir(self) -> None:
        """打开快照数据目录。"""
        if not self._snapshot_dir or not os.path.isdir(self._snapshot_dir):
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", os.path.normpath(self._snapshot_dir)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", self._snapshot_dir])
        else:
            subprocess.Popen(["xdg-open", self._snapshot_dir])

    def paintEvent(self, event) -> None:
        """绘制半透明背景。"""
        pass  # 背景由 _container 的样式表处理