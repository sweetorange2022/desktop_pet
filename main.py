# -*- coding: utf-8 -*-

"""桌面宠物应用入口。

组装模块、连接信号槽、启动事件循环。

职责：组装所有模块，连接业务逻辑。

"""

from __future__ import annotations

import sys

from pathlib import Path

from PySide6.QtCore import Qt, QTimer

from PySide6.QtGui import QGuiApplication, QIcon

from PySide6.QtWidgets import QApplication

from config import PET_SIZE

from src.ui.pet_window import PetWindow

import ctypes

import os

if os.name == "nt":

    ctypes.windll.kernel32.FreeConsole()

from src.providers.health_provider import HealthReminderProvider
from src.providers.schedule_provider import ScheduleProvider

from src.ui.tray_manager import TrayManager
from src.ui.work_hours_dialog import WorkHoursDialog
from scripts._autostart import enable as _enable_autostart, is_enabled as _is_autostart_enabled
from scripts._health_reminder import health_reminder

def _resolve_asset(filename: str, subdir: str = "") -> str:

    """解析资源文件的绝对路径，适配 PyInstaller 打包。

    Args:

        filename: 文件名

        subdir: 子目录，如 'generated'、'videos' 等

    """

    if getattr(sys, "frozen", False):

        base = Path(sys._MEIPASS) / "assets"  # type: ignore[attr-defined]

    else:

        base = Path(__file__).parent / "assets"

    if subdir:

        base = base / subdir

    return str(base / filename)

def _find_assets(subdir: str, extensions: frozenset[str]) -> list[str]:

    """扫描指定目录下的资源文件。

    打包后优先搜索 exe 同目录的 assets/，再搜索打包内的资源。

    如果都不存在则返回空，不崩溃。

    """

    search_dirs: list[Path] = []

    if getattr(sys, "frozen", False):

        exe_dir = Path(sys.executable).parent

        temp_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]

        search_dirs = [exe_dir / "assets" / subdir, temp_dir / "assets" / subdir]

    else:

        search_dirs = [Path(__file__).parent / "assets" / subdir]

    seen: set[str] = set()

    results: list[str] = []

    for target_dir in search_dirs:

        if not target_dir.exists():

            continue

        for f in target_dir.iterdir():

            if f.suffix.lower() in extensions and str(f) not in seen:

                seen.add(str(f))

                results.append(str(f))

    return sorted(results)

def _find_videos() -> list[str]:

    """扫描 assets/videos/ 目录下的所有视频文件。"""

    return _find_assets("videos", frozenset({".mp4", ".webm", ".avi", ".mov", ".mkv"}))

def _find_images() -> list[str]:

    """扫描 assets/images/ 目录下的所有静态图片文件。"""

    return _find_assets("images", frozenset({".png", ".jpg", ".jpeg", ".bmp", ".gif"}))

def _find_animated() -> list[str]:

    """扫描 assets/animated/ 目录下的所有动图文件（GIF 等）。"""

    return _find_assets("animated", frozenset({".gif", ".apng", ".webp"}))

def main() -> int:

    # ----- 启动前清理临时文件 -----
    def _cleanup_temp():
        import os as _os, glob as _glob, shutil as _shutil
        _d = _os.path.dirname(_os.path.abspath(__file__))
        # G:\D 根目录临时文件
        for _p in ["_temp_*.txt", "_analysis_result_*.txt", "_vision_*.txt",
                    "_hd_files.txt", "_id_results.txt", "resp.json"]:
            for _f in _glob.glob(_os.path.join(_d, _p)):
                try:
                    _os.remove(_f)
                except OSError:
                    pass
        # tmpPic 目录
        _pic = _os.path.join(_d, "tmpPic")
        if _os.path.isdir(_pic):
            for _f in _os.listdir(_pic):
                _fp = _os.path.join(_pic, _f)
                if _os.path.isfile(_fp):
                    try:
                        _os.remove(_fp)
                    except OSError:
                        pass
        # dist/screenshot_selftest
        _selftest = _os.path.join(_d, "dist", "screenshot_selftest")
        if _os.path.isdir(_selftest):
            try:
                _shutil.rmtree(_selftest)
            except OSError:
                pass
    _cleanup_temp()

    """应用入口。组装各模块并启动事件循环。"""

    if "--screenshot-test" in sys.argv:
        from tests.test_screenshot import main as screenshot_test_main

        return screenshot_test_main()

    if "--record-test" in sys.argv:
        from tests.test_recording_region import main as record_test_main

        return record_test_main()

    app = QApplication(sys.argv)

    app.setQuitOnLastWindowClosed(False)

    app.setApplicationName("HSN")

    app.setApplicationDisplayName("HSN")
    # 首次启动时自动开启开机自启
    if not _is_autostart_enabled("HorseSmallNine"):
        _enable_autostart("HorseSmallNine")

    tray_icon = _resolve_asset("cat.png", subdir="ico")

    pet_img = _resolve_asset("pet.png", subdir="generated")

    # 优先检查 animated/ 目录下的 GIF（内存小 ~10MB vs MP4 ~500MB）

    animated_list = _find_animated()

    if animated_list:

        pet_asset = animated_list[0]

        asset_list = animated_list

    else:

        videos = _find_videos()

        default_video = next((v for v in videos if "猫小九" in v), "")

        if not default_video and videos:

            default_video = videos[0]

        pet_asset = default_video if default_video else pet_img

        asset_list = videos if videos else []

    # 基础模块

    window = PetWindow(video_path=pet_asset, video_list=asset_list)

    window.setWindowIcon(QIcon(tray_icon))

    health_provider = HealthReminderProvider()

    if getattr(sys, "frozen", False):
        sched_path = str(Path(sys._MEIPASS) / "schedule.json")
    else:
        sched_path = str(Path(__file__).parent / "schedule.json")
    sched_provider = ScheduleProvider(schedule_path=sched_path)

    window.show()

    def on_quit() -> None:

        """Exit the application."""

        health_provider.stop()
        if hasattr(window, "_cancel_rec"):
            window._cancel_rec()
        app.quit()

    def on_toggle_autostart(enabled: bool) -> None:

        """开关开机自启"""

        if enabled:

            _enable_autostart("HorseSmallNine")

        else:

            from scripts._autostart import disable as _disable_autostart

            _disable_autostart("HorseSmallNine")

    def on_set_work_hours() -> None:
        """弹出工作时间设置对话框。"""
        dlg = WorkHoursDialog(window)
        if dlg.exec_() == WorkHoursDialog.Accepted:
            result = dlg.get_result()
            if result:
                import config as cfg_mod
                wh = result["work_hours"]
                ot = result["off_times"]
                cfg_mod.HEALTH_WORK_HOURS = [tuple(x) for x in wh]
                cfg_mod.HEALTH_OFF_WORK_TIMES = [tuple(x) for x in ot]

    # 课程模式定时刷新
    _schedule_refresh_timer = QTimer()
    _schedule_refresh_timer.setInterval(60000)  # 每分钟刷新
    _schedule_mode_active = False

    def _refresh_schedule_bubble() -> None:
        """刷新课程模式气泡内容。"""
        if not _schedule_mode_active:
            return
        sched_provider.update()
        bx, by = window._calc_bubble_position()
        window._bubble.show_bubble(bx, by, auto_hide=False)

    _schedule_refresh_timer.timeout.connect(_refresh_schedule_bubble)

    def on_show_schedule() -> None:
        """切换到课程模式：在桌宠右侧显示今日课程气泡（不弹系统通知）。"""
        nonlocal _schedule_mode_active
        _schedule_mode_active = True
        window._bubble.set_provider(sched_provider)
        bx, by = window._calc_bubble_position()
        window._bubble.show_bubble(bx, by, auto_hide=False)
        _schedule_refresh_timer.start()

    tray = TrayManager(

        parent=window,

        on_quit=on_quit,

        icon_path=tray_icon,

        on_toggle_autostart=on_toggle_autostart,
        autostart_enabled=_is_autostart_enabled("HorseSmallNine"),
        on_set_work_hours=on_set_work_hours,
        on_show_schedule=on_show_schedule,

    )

    # ----- 首次启动：弹出工作时间设置 -----
    from config import WORK_HOURS_CONFIGURED
    if not WORK_HOURS_CONFIGURED:
        QTimer.singleShot(500, on_set_work_hours)

    # 连接健康提醒信号

    def _show_reminder(title: str, msg: str) -> None:

        tray.show_message(title, msg)

    health_provider.reminder_triggered.connect(_show_reminder)

    # 启动

    health_provider.start()

    tray.show()

    return app.exec()

if __name__ == "__main__":

    sys.exit(main())

