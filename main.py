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

from config import PET_SIZE, CAMERA_ENABLED, CAMERA_INDEX, CAMERA_RESOLUTION
from config import CAMERA_CAPTURE_DURATION_S, CAMERA_CAPTURE_FPS, CAMERA_SNAPSHOT_DIR
from config import STYLE_ENABLED, STYLE_MORNING_TIME, STYLE_EVENING_TIME, STYLE_PROFILE
from config import STYLE_OUTFIT_HISTORY_FILE
from src.core.monitor import SystemMonitor

from src.ui.pet_window import PetWindow

import ctypes

import os

if os.name == "nt":

    ctypes.windll.kernel32.FreeConsole()

from src.providers.system_provider import SystemProvider

from src.providers.schedule_provider import ScheduleProvider

from src.providers.health_provider import HealthReminderProvider

from src.providers.weather_provider import WeatherProvider
from src.services.ai_balance import AIBalanceService
from src.ui.ai_accounts_dialog import AIAccountsDialog
from src.ui.weather_dialog import WeatherDialog

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

    # ----- 日志配置 -----
    import logging
    _log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "logs")
    os.makedirs(_log_dir, exist_ok=True)
    _log_file = os.path.join(_log_dir, "horsesmallnine.log")
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stderr),
            logging.FileHandler(_log_file, encoding="utf-8", mode="a"),
        ],
        force=True,
    )
    # 降低第三方库日志
    for _name in ("urllib3", "requests", "PIL", "matplotlib"):
        logging.getLogger(_name).setLevel(logging.WARNING)
    logger = logging.getLogger("main")
    logger.info("===== HorseSmallNine 启动 =====")

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

    tray_icon = _resolve_asset("pet.png", subdir="generated")

    pet_img = _resolve_asset("pet.png", subdir="generated")

    # 默认使用 pet.png，GIF/视频作为可切换备选
    animated_list = _find_animated()
    videos = _find_videos()
    asset_list = animated_list + videos

    pet_asset = pet_img  # 强制默认 pet.png

    # 基础模块

    window = PetWindow(video_path=pet_asset, video_list=asset_list)

    window.setWindowIcon(QIcon(tray_icon))

    monitor = SystemMonitor()

    # 信息提供者

    sys_provider = SystemProvider()

    if getattr(sys, "frozen", False):

        sched_path = str(Path(sys._MEIPASS) / "schedule.json")

    else:

        sched_path = str(Path(__file__).parent / "schedule.json")

    sched_provider = ScheduleProvider(schedule_path=sched_path)

    health_provider = HealthReminderProvider()

    # 摄像头健康检测 + 智能提醒 + 穿搭建议
    camera_monitor = None
    smart_engine = None
    style_service = None
    if CAMERA_ENABLED:
        try:
            from src.services.camera_monitor import CameraMonitor
            from src.services.smart_reminder import SmartReminderEngine
            from src.services.daily_style import DailyStyleService

            _cam_cfg = {
                "enabled": True,
                "camera_index": CAMERA_INDEX,
                "resolution_width": CAMERA_RESOLUTION[0],
                "resolution_height": CAMERA_RESOLUTION[1],
                "capture_duration_s": CAMERA_CAPTURE_DURATION_S,
                "capture_fps": CAMERA_CAPTURE_FPS,
                "snapshot_dir": CAMERA_SNAPSHOT_DIR,
                "snapshot_quality": 85,
                "ear_threshold": 0.21,
                "mar_threshold": 0.7,
                "posture_pitch_threshold": 15,
                "posture_yaw_threshold": 20,
                "fatigue_threshold": 70,
                "posture_threshold": 60,
                "eye_dark_threshold": 60,
                "min_reminder_interval_min": 20,
                "same_topic_cooldown_min": 40,
                "trend_window": 3,
                "trend_threshold": 5,
            }
            camera_monitor = CameraMonitor(_cam_cfg)
            smart_engine = SmartReminderEngine(_cam_cfg)

            _style_cfg = {
                "enabled": STYLE_ENABLED,
                "profile": STYLE_PROFILE,
                "max_chars": 120,
                "outfit_history_file": str(Path(__file__).parent / STYLE_OUTFIT_HISTORY_FILE),
                "outfit_history_days": 7,
            }
            style_service = DailyStyleService(_style_cfg, _cam_cfg)

            health_provider.set_camera_services(
                camera_monitor=camera_monitor,
                smart_engine=smart_engine,
                style_service=style_service,
                camera_config=_cam_cfg,
            )
            print("[init] 摄像头健康检测已初始化")
        except Exception as e:
            print(f"[init] 摄像头初始化失败（降级为纯计时模式）: {e}")

    weather_provider = WeatherProvider()

    ai_balance_service = AIBalanceService()
    window.set_ai_balance_service(ai_balance_service)

    providers = {"系统监控": sys_provider, "课程表": sched_provider, "健康提醒": health_provider}

    source_names = ["纯净模式", "系统监控", "课程表", "健康提醒"]

    current_source = "系统监控"

    is_pure_mode = False

    window._bubble.set_provider(sys_provider)

    window.set_pure_mode(False)

    window.show()

    bx, by = window._calc_bubble_position()

    window._bubble.show_bubble(bx, by, auto_hide=False)

    monitor.metrics_updated.connect(window._bubble.update_metrics)
    monitor.metrics_updated.connect(window.on_metrics_updated)

    weather_provider.data_updated.connect(window._bubble._refresh)

    _restore_timer = QTimer()

    _restore_timer.setSingleShot(True)

    def _restore_source() -> None:

        """Restore original mode after health reminder"""

        nonlocal current_source, is_pure_mode

        if current_source == "纯净模式":

            window.set_pure_mode(True)

        else:

            window.set_pure_mode(False)

            window._bubble.set_provider(providers[current_source])

            bx, by = window._calc_bubble_position()

            window._bubble.show_bubble(bx, by, auto_hide=False)

    _restore_timer.timeout.connect(_restore_source)

    def on_switch_source(name: str) -> None:

        """Switch info source"""

        nonlocal current_source, is_pure_mode

        if name == "纯净模式":

            is_pure_mode = True

            current_source = name

            window.set_pure_mode(True)

            window._bubble.set_provider(None)

            bx, by = window._calc_bubble_position()

            window._bubble.show_bubble(bx, by, auto_hide=False)

        else:

            is_pure_mode = False

            current_source = name

            window.set_pure_mode(False)

            window._bubble.set_provider(providers[name])

            bx, by = window._calc_bubble_position()

            window._bubble.show_bubble(bx, by, auto_hide=False)

        if name == "天气预报":

            weather_provider.refresh_now()

        tray.set_active_source(name)

    _schedule_timer = None

    def on_quit() -> None:

        """Exit the application."""

        if _schedule_timer is not None:
            _schedule_timer.stop()
        monitor.stop()
        health_provider.stop()
        weather_provider.stop()
        ai_balance_service.stop()
        if hasattr(window, "_cancel_rec"):
            window._cancel_rec()
        app.quit()

    def on_weather_report() -> None:

        import logging

        import os as _os
        _log_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "tmpPic")
        _os.makedirs(_log_dir, exist_ok=True)
        logging.basicConfig(
            filename=_os.path.join(_log_dir, "_weather_debug.log"),
            level=logging.DEBUG,
            force=True,
        )

        logging.debug("on_weather_report called")

        try:

            dlg = WeatherDialog(window)

            dlg.exec_()

        except Exception as _e:

            import traceback

            import os as _os
            _log_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "tmpPic")
            _os.makedirs(_log_dir, exist_ok=True)
            with open(_os.path.join(_log_dir, "_weather_dialog_crash.log"), "w", encoding="utf-8") as _f:

                _f.write(traceback.format_exc())

    def on_set_city() -> None:

        """弹出城市选择对话框，更新天气配置并刷新。"""

        from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox
        from src.services.weather import geo_lookup
        import json

        from pathlib import Path

        import config as cfg_mod

        city, ok = QInputDialog.getText(window, "设置城市", "输入城市名称：", QLineEdit.Normal, cfg_mod.WEATHER_CITY)

        if not ok or not city.strip():

            return

        city = city.strip()

        result = geo_lookup(city)

        if result is None:

            QMessageBox.warning(window, "查询失败", f"未找到城市「{city}」，请检查名称")

            return

        wj = Path(__file__).parent / "config" / "weather.json"

        try:

            with open(wj, "r", encoding="utf-8") as f:

                cfg = json.load(f)

        except (FileNotFoundError, json.JSONDecodeError):

            cfg = {}

        cfg["weather_city"] = result["city"]

        cfg["weather_latitude"] = result["lat"]

        cfg["weather_longitude"] = result["lon"]

        with open(wj, "w", encoding="utf-8") as f:

            json.dump(cfg, f, ensure_ascii=False, indent=2)

        from config import config as _cfg
        _cfg.set_many("weather.json", {
            "weather_city": result["city"],
            "weather_latitude": result["lat"],
            "weather_longitude": result["lon"],
        })
        cfg_mod.WEATHER_CITY = result["city"]
        cfg_mod.WEATHER_LATITUDE = result["lat"]
        cfg_mod.WEATHER_LONGITUDE = result["lon"]

        weather_provider._alert = None

        weather_provider._tomorrow_weather = None

        weather_provider._last_check_time = 0.0

        weather_provider.refresh_now()

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
                # 持久化到 health.json
                from config import config as _cfg
                _cfg.set("health.json", "health_work_hours", wh)
                _cfg.set("health.json", "health_off_work_times", ot)

    def on_ai_accounts() -> None:
        """弹出 AI 账户设置对话框，保存后自动刷新余额。"""
        dlg = AIAccountsDialog(window)
        if dlg.exec() == AIAccountsDialog.Accepted:
            # 重新加载配置并刷新余额
            ai_balance_service.reload_config()

    window.set_quick_actions(

        source_names=source_names,

        on_switch_source=on_switch_source,

        on_weather_report=on_weather_report,

        on_test_health=health_provider.test_reminder,

    )
    # ----- 测试回调函数 -----
    def _test_camera():
        """测试摄像头检测：采集一次，弹出结果。"""
        if not camera_monitor:
            tray.show_message("摄像头测试", "摄像头未初始化")
            return
        tray.show_message("摄像头测试", "正在采集 5 秒...")
        QApplication.processEvents()
        try:
            snap = camera_monitor.capture_and_analyze()
            if snap.face_detected:
                msg = (
                    f"✅ 人脸检测成功\n"
                    f"疲劳: {snap.fatigue}/100\n"
                    f"坐姿: {snap.posture}/100\n"
                    f"肤色: {snap.skin_tone}\n"
                    f"黑眼圈: {snap.eye_dark}/100\n"
                    f"快照: {snap.image_path}"
                )
            else:
                msg = f"⚠️ 未检测到人脸\n快照: {snap.image_path or '无'}"
            tray.show_message("摄像头测试结果", msg)
            logger.info("摄像头测试: face=%s fatigue=%s posture=%s path=%s",
                       snap.face_detected, snap.fatigue, snap.posture, snap.image_path)
        except Exception as e:
            tray.show_message("摄像头测试失败", str(e))
            logger.exception("摄像头测试异常")

    def _test_style():
        """测试穿搭建议：触发一次完整的建议生成。"""
        if not style_service:
            tray.show_message("穿搭测试", "穿搭服务未初始化")
            return
        tray.show_message("穿搭测试", "正在生成建议...")
        QApplication.processEvents()
        try:
            # 构建天气信息
            weather_info = {"city": "未知", "desc": "未知", "temp": "未知"}
            try:
                from src.services.weather import fetch_today_weather
                city = style_service.get_city()
                w = fetch_today_weather()
                if w:
                    weather_info = {
                        "city": city, "desc": w.weather_desc,
                        "temp": f"{w.temp_min:.0f}~{w.temp_max:.0f}°C",
                        "wind": f"{w.wind_speed_max:.0f}",
                        "rain": f"{w.rain_prob_max:.0f}", "uv": "",
                    }
            except Exception:
                pass

            # 取最新快照或空快照
            from src.services.camera_monitor import CameraSnapshot
            snap = (health_provider._today_snapshots[-1]
                    if health_provider._today_snapshots
                    else CameraSnapshot(timestamp="", face_detected=False))

            advice = style_service.generate_advice(
                snapshot=snap, weather_info=weather_info,
                period="上午",
            )
            if advice:
                tray.show_message("👔 精气神建议", advice)
                logger.info("穿搭建议测试成功: %s", advice[:100])
            else:
                tray.show_message("穿搭测试", "建议生成失败（检查 API Key）")
        except Exception as e:
            tray.show_message("穿搭测试失败", str(e))
            logger.exception("穿搭测试异常")

    def _show_log():
        """打开日志文件。"""
        import subprocess
        if os.path.isfile(_log_file):
            subprocess.Popen(["notepad", _log_file])
        else:
            tray.show_message("日志", f"日志文件不存在: {_log_file}")

    tray = TrayManager(

        parent=window,

        on_quit=on_quit,

        on_switch_source=on_switch_source,

        source_names=source_names,

        current_source=current_source,

        icon_path=tray_icon,

        on_test_health=health_provider.test_reminder,
        on_weather_report=on_weather_report,
        on_toggle_autostart=on_toggle_autostart,
        autostart_enabled=_is_autostart_enabled("HorseSmallNine"),
        on_set_work_hours=on_set_work_hours,
        on_pick_image=window.pick_image_from_dialog,
        on_ai_accounts=on_ai_accounts,
        on_test_camera=_test_camera,
        on_test_style=_test_style,
        on_show_log=_show_log,
    )

    # 设置 MIMO 余额查询地址
    mimo_cfg = [acc for acc in ai_balance_service._accounts if acc.name == "MiMo"]
    if mimo_cfg and mimo_cfg[0].web_url:
        tray.set_mimo_url(mimo_cfg[0].web_url)

    # ----- 首次启动：弹出工作时间设置 -----
    from config import WORK_HOURS_CONFIGURED
    if not WORK_HOURS_CONFIGURED:
        QTimer.singleShot(500, on_set_work_hours)

    # 连接健康提醒信号

    def _show_reminder(title: str, msg: str) -> None:

        tray.show_message(title, msg)

    health_provider.reminder_triggered.connect(_show_reminder)

    # 启动

    monitor.start()

    health_provider.start()

    # ----- 每日精气神建议定时器（10:10 + 18:10） -----
    if style_service:
        from datetime import datetime as _dt

        def _check_style_advice():
            now = _dt.now()
            h, m = now.hour, now.minute
            if h == 10 and m == 10:
                health_provider.trigger_style_advice("上午")
            elif h == 18 and m == 10:
                health_provider.trigger_style_advice("傍晚")

        _style_timer = QTimer()
        _style_timer.timeout.connect(_check_style_advice)
        _style_timer.start(60000)  # 每分钟检查一次

    weather_provider.start()

    ai_balance_service.start()

    tray.show()

    # ----- 定时发送天气（每天 20:00） -----
    def _send_tomorrow_weather():
        """获取厦门明天天气，生成卡片，发送微信。"""
        from datetime import datetime as _dt
        now = _dt.now()
        # 只在 20:00-20:01 之间触发一次
        if now.hour != 20 or now.minute != 0:
            return

        try:
            from src.services.weather import fetch_tomorrow_weather
            from src.ui.weather_image import render_weather_card
            from src.services.wechat_sender import send_wechat_image
            import os, tempfile

            weather = fetch_tomorrow_weather()
            if weather is None:
                return

            # 构造简单的卡片文本
            card_text = (
                f"\U0001f4cd \u53a6\u95e8\n"
                f"{weather.date}\n\n"
                f"\U0001f321 {weather.temp_min:.0f}~{weather.temp_max:.0f}\u2103  "
                f"\u2601 {weather.weather_desc}\n"
                f"\U0001f4a8 \u98ce\u901f\uff1a{weather.wind_speed_max:.0f}km/h\n"
                f"\U0001f327 \u964d\u6c34\uff1a{weather.rain_prob_max:.0f}%\n\n"
                f"--- \u9a6c\u5c0f\u4e5d\u6e29\u99a8\u63d0\u793a"
            )

            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.close()
            render_weather_card(card_text, tmp.name)
            send_wechat_image("\u695a\u695a\u5927\u9b54\u738b(\u61d2\u7f8a\u7f8a\u7248)", tmp.name)
            os.unlink(tmp.name)
        except Exception as _e:
            import logging
            logging.warning(f"\u5b9a\u65f6\u53d1\u9001\u5929\u6c14\u5931\u8d25: {_e}")

    _schedule_timer = QTimer()
    _schedule_timer.timeout.connect(_send_tomorrow_weather)
    _schedule_timer.start(60000)  # 每分钟检查一次

    return app.exec()

if __name__ == "__main__":

    sys.exit(main())

