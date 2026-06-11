"""
健康提醒弹窗模块

固定主屏幕右下角的持久弹窗，不自动消失。
用户手动关闭或被下一条提醒覆盖。

用法：
    from _health_reminder import health_reminder

    health_reminder.show_reminder("喝水提醒", "主人，该喝水了~")
    health_reminder.close()
"""

import sys

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                                QLabel, QPushButton, QApplication)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QScreen


class _HealthReminderWindow(QWidget):
    """健康提醒弹窗 — 单例内部窗口"""

    WIDTH = 360
    HEIGHT = 160
    MARGIN = 20  # 右下角边距

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._position_at_bottom_right()

    def _setup_ui(self):
        self.setWindowTitle("HorseSmallNine")
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # 圆角背景容器
        container = QWidget(self)
        container.setObjectName("container")
        container.setStyleSheet("""
            #container {
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 10px;
            }
            QLabel#title_label {
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 12px 16px 4px 16px;
            }
            QLabel#msg_label {
                color: #cccccc;
                font-size: 13px;
                padding: 4px 16px 12px 16px;
            }
            QPushButton#close_btn {
                background-color: #555555;
                color: #cccccc;
                border: none;
                border-radius: 10px;
                font-size: 13px;
                padding: 4px 12px;
                min-height: 20px;
            }
            QPushButton#close_btn:hover {
                background-color: #777777;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题行（标题 + 关闭按钮）
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(0, 0, 0, 0)

        self._title_label = QLabel("HorseSmallNine")
        self._title_label.setObjectName("title_label")
        title_bar.addWidget(self._title_label, 1)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self.close)
        title_bar.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

        layout.addLayout(title_bar)

        # 消息正文
        self._msg_label = QLabel("")
        self._msg_label.setObjectName("msg_label")
        self._msg_label.setWordWrap(True)
        layout.addWidget(self._msg_label, 1)

        # 容器撑满整个窗口
        container.setGeometry(0, 0, self.WIDTH, self.HEIGHT)

    def _position_at_bottom_right(self):
        """定位到主屏幕右下角"""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        x = geometry.right() - self.WIDTH - self.MARGIN
        y = geometry.bottom() - self.HEIGHT - self.MARGIN
        self.move(x, y)

    def show_reminder(self, title: str, message: str):
        """更新内容并显示"""
        self.setWindowTitle(title)
        self._title_label.setText(title)
        self._msg_label.setText(message)
        self._position_at_bottom_right()
        self.show()

    def closeEvent(self, event):
        """用户手动关闭 — 隐藏而非销毁，下次复用"""
        self.hide()
        event.accept()


class _HealthReminderManager:
    """健康提醒管理器（单例门面）"""

    def __init__(self):
        self._window: _HealthReminderWindow | None = None

    def show_reminder(self, title: str = "健康提醒", message: str = "") -> None:
        """显示健康提醒弹窗。如果已有弹窗，直接覆盖内容。"""
        if self._window is None:
            self._window = _HealthReminderWindow()
        self._window.show_reminder(title, message)

    def close(self) -> None:
        """关闭当前弹窗"""
        if self._window is not None:
            self._window.close()

    @property
    def is_visible(self) -> bool:
        """弹窗当前是否可见"""
        return self._window is not None and self._window.isVisible()


# 全局单例实例
health_reminder = _HealthReminderManager()
