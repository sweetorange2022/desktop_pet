"""系统托盘管理模块。

提供系统托盘图标及菜单。
职责：系统托盘图标显示、菜单（信息源切换、天气预报、测试提醒、退出）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtGui import QAction, QActionGroup, QCursor, QImage, QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

class TrayManager:
    """系统托盘，通过托盘方式控制应用。"""

    def __init__(
        self,
        parent: QWidget,
        on_quit: Callable[[], None],
        on_switch_source: Optional[Callable[[str], None]] = None,
        source_names: Optional[list[str]] = None,
        current_source: str = "",
        icon_path: Optional[str] = None,
        on_test_health: Optional[Callable[[], None]] = None,
        on_weather_report: Optional[Callable[[], None]] = None,
        on_toggle_autostart: Optional[Callable[[bool], None]] = None,
        autostart_enabled: bool = False,
        on_set_work_hours: Optional[Callable[[], None]] = None,
    ) -> None:
        self._parent = parent
        self._tray = QSystemTrayIcon(parent)

        # 图标
        if icon_path and Path(icon_path).exists():
            qimg = QImage(icon_path)
            if not qimg.isNull():
                pix = QPixmap.fromImage(qimg)
                self._tray.setIcon(QIcon(pix))
            else:
                self._tray.setIcon(QIcon(QPixmap(32, 32)))
        else:
            self._tray.setIcon(QIcon(QPixmap(32, 32)))

        # 构建菜单
        self._menu = QMenu(parent)
        self._source_actions: list[QAction] = []
        self._source_names: list[str] = []

        # 信息源作为顶层菜单项（单选）
        if on_switch_source and source_names:
            self._source_names = source_names
            group = QActionGroup(parent)
            group.setExclusive(True)

            for name in source_names:
                act = QAction(name, parent)
                act.setCheckable(True)
                act.setChecked(name == current_source)
                group.addAction(act)
                act.triggered.connect(lambda checked=False, n=name: on_switch_source(n))
                self._menu.addAction(act)
                self._source_actions.append(act)

        # 天气预报（含城市设置）
        if on_weather_report is not None:
            act_weather = QAction("天气预报", parent)
            act_weather.triggered.connect(on_weather_report)
            self._menu.addAction(act_weather)

        # 测试提醒
        if on_test_health is not None:
            act_test = QAction("测试提醒", parent)
            act_test.triggered.connect(on_test_health)
            self._menu.addAction(act_test)

        # 设置工作时间
        if on_set_work_hours is not None:
            act_work_hours = QAction("设置工作时间", parent)
            act_work_hours.triggered.connect(on_set_work_hours)
            self._menu.addAction(act_work_hours)

        # 开机自启
        if on_toggle_autostart is not None:
            act_autostart = QAction("开机自启", parent)
            act_autostart.setCheckable(True)
            act_autostart.setChecked(autostart_enabled)
            act_autostart.triggered.connect(on_toggle_autostart)
            self._menu.addAction(act_autostart)

        self._menu.addSeparator()

        act_quit = QAction("退出", parent)
        act_quit.triggered.connect(on_quit)
        self._menu.addAction(act_quit)

        # 左右键均弹出同一菜单
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_activated)
        self._tray.setToolTip("HSN")

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """左键点击弹出菜单（与右键一致），用 exec 确保多显示器定位准确。"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._menu.exec(QCursor.pos())

    def show(self) -> None:
        """显示托盘图标。"""
        self._tray.show()

    def hide(self) -> None:
        """隐藏托盘图标。"""
        self._tray.hide()

    def show_message(self, title: str, message: str) -> None:
        """显示系统通知。"""
        self._tray.showMessage(title, message)

    def set_active_source(self, name: str) -> None:
        """更新当前选中的信息源菜单项。"""
        for act in self._source_actions:
            act.setChecked(act.text() == name)
