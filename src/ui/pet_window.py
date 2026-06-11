# -*- coding: utf-8 -*-

"""桌面宠物主窗口模块。

透明背景、无边框、可拖拽、播放宠物动画。

支持 GIF 动画（通过 QMovie 高效播放）和静态图片。

"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

def _tmp_pic_path(name: str) -> str:
    """项目 tmpPic 目录下的调试日志路径。"""
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmpPic")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name)

def _open_in_explorer(path: str) -> None:
    """在资源管理器中打开文件或文件夹。"""
    import subprocess

    norm = os.path.normpath(path)
    if os.path.isfile(norm):
        subprocess.Popen(["explorer", "/select,", norm])
    elif os.path.isdir(norm):
        subprocess.Popen(["explorer", norm])

from PySide6.QtCore import Qt, QTimer, QRectF, QRect, QPoint

from PySide6.QtGui import (

    QAction,

    QCursor,

    QGradient,

    QBrush,

    QColor,

    QConicalGradient,

    QGuiApplication,

    QMovie,

    QPainter,

    QPaintEvent,

    QImage,

    QPen,

    QPixmap,

    QScreen,

)

from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

class _SaveNotice(QWidget):
    """保存成功后的路径提示条（自动打开位置 + 可再次打开）。"""

    def __init__(self, anchor: QWidget, path: str, title: str) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setStyleSheet(
            "QWidget{background:rgba(28,28,28,235);border-radius:8px;}"
            "QLabel{color:#f2f2f2;font:13px 'Microsoft YaHei';}"
            "QPushButton{background:#4CAF50;color:white;font:12px 'Microsoft YaHei';"
            "border-radius:4px;padding:4px 12px;}"
            "QPushButton:hover{background:#66BB6A;}"
            "QPushButton#closeBtn{background:#555;}"
            "QPushButton#closeBtn:hover{background:#777;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        layout.addWidget(QLabel(title))
        path_lbl = QLabel(path)
        path_lbl.setWordWrap(True)
        path_lbl.setMaximumWidth(420)
        layout.addWidget(path_lbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_open = QPushButton("打开位置")
        btn_open.clicked.connect(lambda: _open_in_explorer(path))
        btn_close = QPushButton("关闭")
        btn_close.setObjectName("closeBtn")
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_open)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        self.adjustSize()
        ag = anchor.geometry()
        x = ag.x() + max(0, (ag.width() - self.width()) // 2)
        y = ag.y() - self.height() - 10
        if y < 0:
            y = ag.y() + ag.height() + 10
        self.move(x, y)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.close)
        self._timer.start(10000)

from config import BUBBLE_MARGIN, PET_SIZE

from src.ui.info_bubble import InfoBubble

from src.core.state import PetState, evaluate

def _win32_physical_monitors() -> list[dict]:

    """枚举 Win32 物理显示器。临时切到 DPI-unaware，避免 exe 里副屏坐标翻倍。"""

    import ctypes

    from ctypes import wintypes

    user32 = ctypes.windll.user32

    monitors: list[dict] = []

    class MONITORINFOEXW(ctypes.Structure):

        _fields_ = [

            ("cbSize", wintypes.DWORD),

            ("rcMonitor", wintypes.RECT),

            ("rcWork", wintypes.RECT),

            ("dwFlags", wintypes.DWORD),

            ("szDevice", wintypes.WCHAR * 32),

        ]

    def callback(hmon, _hdc, _rect, _data):

        info = MONITORINFOEXW()

        info.cbSize = ctypes.sizeof(MONITORINFOEXW)

        user32.GetMonitorInfoW(hmon, ctypes.byref(info))

        rect = info.rcMonitor

        monitors.append(

            {

                "left": rect.left,

                "top": rect.top,

                "width": rect.right - rect.left,

                "height": rect.bottom - rect.top,

                "is_primary": bool(info.dwFlags & 1),

                "hmon": hmon,

                "dpi_scale": 1.0,

            }

        )

        return 1

    enum_proc = ctypes.WINFUNCTYPE(

        ctypes.c_int,

        ctypes.c_ulong,

        ctypes.c_ulong,

        ctypes.POINTER(wintypes.RECT),

        ctypes.c_long,

    )

    old_context = None

    try:

        old_context = user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-1))

    except Exception:

        pass

    try:

        user32.EnumDisplayMonitors(0, 0, enum_proc(callback), 0)

    finally:

        if old_context:

            try:

                user32.SetThreadDpiAwarenessContext(old_context)

            except Exception:

                pass

    try:

        shcore = ctypes.windll.shcore

        for monitor in monitors:

            hmon = monitor.pop("hmon", None)

            if hmon is None:

                continue

            dpi_x = wintypes.UINT()

            dpi_y = wintypes.UINT()

            if shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:

                monitor["dpi_scale"] = dpi_x.value / 96.0

    except Exception:

        for monitor in monitors:

            monitor.pop("hmon", None)

    primary = [m for m in monitors if m["is_primary"]]

    others = sorted(

        [m for m in monitors if not m["is_primary"]],

        key=lambda item: (item["left"], item["top"]),

    )

    return (primary + others) if primary else monitors

def _monitor_for_screen(screen: QScreen) -> dict | None:

    monitors = _win32_physical_monitors()

    screens = QGuiApplication.screens()

    try:

        index = screens.index(screen)

    except ValueError:

        return None

    if index < len(monitors):

        return monitors[index]

    return None

def _monitor_dpi_scale(screen: QScreen) -> float:

    monitor = _monitor_for_screen(screen)

    geo = screen.geometry()

    qt_dpr = max(1.0, screen.devicePixelRatio())

    if monitor is None or geo.width() <= 0 or geo.height() <= 0:

        return qt_dpr

    win_w = monitor["width"]

    win_h = monitor["height"]

    geo_w = geo.width()

    geo_h = geo.height()

    # Win32 unaware 尺寸与 Qt 逻辑尺寸一致：100% 屏不缩放；主屏高 DPI 用 Qt DPR。

    if abs(win_w - geo_w) <= 2 and abs(win_h - geo_h) <= 2:

        if monitor.get("is_primary") and qt_dpr > 1.01:

            return qt_dpr

        return 1.0

    scale = monitor.get("dpi_scale", 0.0)

    return scale if scale > 0 else qt_dpr

def _physical_region(screen: QScreen, rect: QRect) -> dict[str, int] | None:

    """用 Win32 显示器原点（DPI-unaware）+ GetDpiForMonitor 缩放选区到物理像素。"""

    monitor = _monitor_for_screen(screen)

    if monitor is None:

        return None

    geo = screen.geometry()

    if geo.width() <= 0 or geo.height() <= 0:

        return None

    scale = _monitor_dpi_scale(screen)

    return {

        "left": monitor["left"] + int(rect.x() * scale),

        "top": monitor["top"] + int(rect.y() * scale),

        "width": max(1, int(rect.width() * scale)),

        "height": max(1, int(rect.height() * scale)),

    }

def _pil_physical_bbox(screen: QScreen, rect: QRect) -> tuple[int, int, int, int] | None:

    region = _physical_region(screen, rect)

    if region is None:

        return None

    return (

        region["left"],

        region["top"],

        region["left"] + region["width"],

        region["top"] + region["height"],

    )

def _image_max_brightness(image) -> int:

    gray = image.convert("L")

    return max(gray.getdata())

def _file_max_brightness(path: str) -> int:

    try:

        from PIL import Image

        return _image_max_brightness(Image.open(path))

    except Exception:

        return 0

def _pixmap_max_brightness(pixmap: QPixmap) -> int:

    image = pixmap.toImage()

    if image.isNull():

        return 0

    image = image.convertToFormat(QImage.Format.Format_Grayscale8)

    step = max(1, min(image.width(), image.height()) // 32)

    peak = 0

    for y in range(0, image.height(), step):

        for x in range(0, image.width(), step):

            peak = max(peak, image.pixelColor(x, y).red())

    return peak

def _is_primary_screen(screen: QScreen) -> bool:

    monitor = _monitor_for_screen(screen)

    if monitor is not None:

        return bool(monitor.get("is_primary"))

    primary = QGuiApplication.primaryScreen()

    return primary is not None and screen == primary

def _expected_capture_size(screen: QScreen, rect: QRect) -> tuple[int, int]:

    scale = _monitor_dpi_scale(screen)

    return max(1, int(rect.width() * scale)), max(1, int(rect.height() * scale))

def _pixmap_content_fill(pixmap: QPixmap) -> float:

    image = pixmap.toImage()

    if image.isNull():

        return 0.0

    image = image.convertToFormat(QImage.Format.Format_Grayscale8)

    step = max(1, min(image.width(), image.height()) // 48)

    bright = 0

    total = 0

    for y in range(0, image.height(), step):

        for x in range(0, image.width(), step):

            total += 1

            if image.pixelColor(x, y).red() > 10:

                bright += 1

    return bright / total if total else 0.0

def _pixmap_capture_valid(screen: QScreen, rect: QRect, pixmap: QPixmap) -> bool:

    if pixmap.isNull() or _pixmap_max_brightness(pixmap) < 2:

        return False

    expected_w, expected_h = _expected_capture_size(screen, rect)

    if abs(pixmap.width() - expected_w) > 4 or abs(pixmap.height() - expected_h) > 4:

        return False

    # 拒绝「大面积黑底 + 角落有图」的 Qt 副屏误抓

    if _pixmap_content_fill(pixmap) < 0.12:

        return False

    return True

def _file_capture_valid(screen: QScreen, rect: QRect, path: str) -> bool:

    if _file_max_brightness(path) < 2:

        return False

    try:

        from PIL import Image

        with Image.open(path) as image:

            expected_w, expected_h = _expected_capture_size(screen, rect)

            if abs(image.width - expected_w) > 4 or abs(image.height - expected_h) > 4:

                return False

            gray = image.convert("L")

            step = max(1, min(image.width, image.height) // 48)

            bright = 0

            total = 0

            for y in range(0, image.height, step):

                for x in range(0, image.width, step):

                    total += 1

                    if gray.getpixel((x, y)) > 10:

                        bright += 1

            return (bright / total if total else 0.0) >= 0.12

    except Exception:

        return False

def _qt_grab_region(screen: QScreen, rect: QRect) -> QPixmap | None:

    """与图像助手一致：覆盖层本地坐标直接 grab，不做 DPI 换算。"""

    pixmap = screen.grabWindow(

        0, rect.x(), rect.y(), rect.width(), rect.height()

    )

    return None if pixmap.isNull() else pixmap

def _save_pixmap_png(pixmap: QPixmap, path: str) -> bool:

    return pixmap.save(path, "PNG")

def _mss_capture_to_path(screen: QScreen, rect: QRect, path: str) -> bool:

    try:

        import mss

        import mss.tools

        region = _physical_region(screen, rect)

        if region is None:

            return False

        with mss.MSS() as sct:

            shot = sct.grab(region)

            mss.tools.to_png(shot.rgb, shot.size, output=path)

        return True

    except Exception:

        return False

def _pil_capture_to_path(screen: QScreen, rect: QRect, path: str) -> bool:

    try:

        from PIL import ImageGrab

        bbox = _pil_physical_bbox(screen, rect)

        if bbox is None:

            return False

        image = ImageGrab.grab(bbox=bbox, all_screens=True)

        image.save(path, "PNG")

        return True

    except Exception:

        return False

def _qt_capture_to_path(screen: QScreen, rect: QRect, path: str) -> bool:

    pixmap = _qt_grab_region(screen, rect)

    if pixmap is None:

        return False

    return _save_pixmap_png(pixmap, path)

def _capture_region_to_path(screen: QScreen, rect: QRect, path: str) -> bool:

    """抓取屏幕选区。主屏 Qt 优先；副屏 mss 优先（exe 下 Qt 偶发超大黑底误抓）。"""

    import os

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    if _is_primary_screen(screen):

        capture_chain = (_qt_capture_to_path, _mss_capture_to_path, _pil_capture_to_path)

    else:

        capture_chain = (_mss_capture_to_path, _pil_capture_to_path, _qt_capture_to_path)

    for capture in capture_chain:

        try:

            if capture is _qt_capture_to_path:

                pixmap = _qt_grab_region(screen, rect)

                if pixmap is None or not _pixmap_capture_valid(screen, rect, pixmap):

                    continue

                if not _save_pixmap_png(pixmap, path):

                    continue

            elif not capture(screen, rect, path):

                continue

            if _file_capture_valid(screen, rect, path):

                return True

        except Exception:

            pass

        if os.path.exists(path):

            try:

                os.remove(path)

            except OSError:

                pass

    return False

def _even_recording_size(width: int, height: int) -> tuple[int, int]:
    w = max(2, width - (width % 2))
    h = max(2, height - (height % 2))
    return w, h

def _crop_rgb_top_left(rgb: bytes, w: int, h: int, tw: int, th: int) -> bytes | None:
    """裁切帧到目标尺寸（ffmpeg 要求偶数宽高）。"""
    if w < tw or h < th:
        return None
    if w == tw and h == th:
        return rgb
    row = w * 3
    out = bytearray(tw * th * 3)
    for y in range(th):
        src = y * row
        dst = y * tw * 3
        out[dst : dst + tw * 3] = rgb[src : src + tw * 3]
    return bytes(out)

def _rgb_max_brightness(rgb: bytes) -> int:
    return max(rgb) if rgb else 0

def _grab_recording_frame_mss(region: dict) -> tuple[bytes, int, int] | None:
    try:
        import mss

        with mss.MSS() as sct:
            shot = sct.grab(region)
        if shot is None or shot.width <= 0 or shot.height <= 0:
            return None
        rgb = shot.rgb
        if len(rgb) != shot.width * shot.height * 3 or _rgb_max_brightness(rgb) < 2:
            return None
        return rgb, shot.width, shot.height
    except Exception:
        return None

def _grab_recording_frame_pil(region: dict) -> tuple[bytes, int, int] | None:
    try:
        from PIL import ImageGrab

        bbox = (
            region["left"],
            region["top"],
            region["left"] + region["width"],
            region["top"] + region["height"],
        )
        img = ImageGrab.grab(bbox=bbox, all_screens=True).convert("RGB")
        w, h = img.size
        rgb = img.tobytes()
        if len(rgb) != w * h * 3 or _rgb_max_brightness(rgb) < 2:
            return None
        return rgb, w, h
    except Exception:
        return None

def _grab_recording_frame_qt(screen: QScreen, rect: QRect) -> tuple[bytes, int, int] | None:
    pixmap = _qt_grab_region(screen, rect)
    if pixmap is None or not _pixmap_capture_valid(screen, rect, pixmap):
        return None
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
    w, h = image.width(), image.height()
    ptr = image.bits()
    ptr.setsize(image.sizeInBytes())
    rgb = bytes(ptr)
    if len(rgb) != w * h * 3:
        return None
    return rgb, w, h

def _select_recording_capture(
    screen: QScreen, rect: QRect
) -> tuple[str, dict, int, int] | None:
    region = _physical_region(screen, rect)
    if region is None:
        return None

    if _is_primary_screen(screen):
        chain = ("mss", "pil", "qt")
    else:
        chain = ("mss", "pil", "qt")

    for method in chain:
        if method == "mss":
            got = _grab_recording_frame_mss(region)
        elif method == "pil":
            got = _grab_recording_frame_pil(region)
        else:
            got = _grab_recording_frame_qt(screen, rect)
        if got is None:
            continue
        _rgb, w, h = got
        w, h = _even_recording_size(w, h)
        region = dict(region)
        region["width"] = w
        region["height"] = h
        return method, region, w, h
    return None

def _rec_control_position(rect: QRect, screen_geo: QRect, w: int, h: int) -> tuple[int, int]:
    """把录屏计时器放在选区外，避免进画面且无需隐藏覆盖层。"""
    x = max(screen_geo.x() + 8, rect.x())
    y = rect.y() - h - 8
    if y < screen_geo.y() + 8:
        y = rect.bottom() + 8 + 34 + 8
    return x, y

def _capture_recording_frame(
    overlay: QWidget,
    screen: QScreen,
    rect: QRect,
    region: dict,
    method: str,
    width: int,
    height: int,
) -> bytes | None:
    if method == "mss":
        got = _grab_recording_frame_mss(region)
    elif method == "pil":
        got = _grab_recording_frame_pil(region)
    else:
        got = _grab_recording_frame_qt(screen, rect)

    if got is None:
        return None
    rgb, w, h = got
    if w != width or h != height:
        rgb = _crop_rgb_top_left(rgb, w, h, width, height)
        if rgb is None:
            return None
    elif len(rgb) != width * height * 3:
        return None
    return rgb

class ScreenshotOverlay(QWidget):

    """单屏截图覆盖层（每个屏幕一个实例）。"""

    def __init__(

        self,

        screen,

        save_dir: str,

        on_session_end=None,

        on_saved=None,

        session_overlays=None,

        hide_widgets=None,

    ):

        super().__init__()

        self._save_dir = save_dir

        self._screen = screen

        self._on_session_end = on_session_end

        self._on_saved = on_saved

        self._session_overlays = session_overlays or []

        self._hide_widgets = hide_widgets or []

        self._restore_visible: list[bool] = []

        self.setWindowFlags(

            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint

            | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool

        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setCursor(Qt.CursorShape.CrossCursor)

        geo = self._screen.geometry()

        self.setGeometry(geo)

        self._start_pos = None

        self._end_pos = None

        self._confirmed_rect: QRect | None = None

        from PySide6.QtWidgets import QPushButton

        self._btn_confirm = QPushButton("确认", self)

        self._btn_confirm.setStyleSheet(

            "QPushButton{background:#4CAF50;color:white;font:bold 12px 'Microsoft YaHei';border-radius:5px;} "

            "QPushButton:hover{background:#66BB6A;}"

        )

        self._btn_confirm.setFixedSize(80, 30)

        self._btn_confirm.hide()

        self._btn_confirm.clicked.connect(self._save_and_close)

        self._btn_cancel = QPushButton("取消", self)

        self._btn_cancel.setStyleSheet(

            "QPushButton{background:#B43232;color:white;font:bold 12px 'Microsoft YaHei';border-radius:5px;} "

            "QPushButton:hover{background:#D43838;}"

        )

        self._btn_cancel.setFixedSize(80, 30)

        self._btn_cancel.hide()

        self._btn_cancel.clicked.connect(self._end_session)

    def _end_session(self) -> None:

        if self._on_session_end is not None:

            self._on_session_end()

        else:

            self.close()

    def mousePressEvent(self, event):

        if event.button() != Qt.MouseButton.LeftButton:

            return

        if self._confirmed_rect is not None:

            pos = event.position().toPoint()

            r = self._confirmed_rect

            bx = r.right() - 170

            by = r.bottom() + 8

            if QRect(bx, by, 170, 36).contains(pos):

                return

            self._confirmed_rect = None

            self._btn_confirm.hide()

            self._btn_cancel.hide()

            self.setCursor(Qt.CursorShape.CrossCursor)

            self._start_pos = event.position().toPoint()

            self._end_pos = None

            self.update()

            return

        self._start_pos = event.position().toPoint()

        self._end_pos = None

        self.update()

    def mouseMoveEvent(self, event):

        if self._start_pos and self._confirmed_rect is None:

            self._end_pos = event.position().toPoint()

            self.update()

    def mouseReleaseEvent(self, event):

        if event.button() != Qt.MouseButton.LeftButton:

            return

        if self._start_pos is None or self._confirmed_rect is not None:

            return

        end = event.position().toPoint()

        r = QRect(self._start_pos, end).normalized()

        if r.width() < 5 or r.height() < 5:

            self._end_session()

            return

        self._confirmed_rect = r

        self._start_pos = None

        self._end_pos = end

        self.setCursor(Qt.CursorShape.ArrowCursor)

        bw = 80

        x = r.right() - bw * 2 - 10

        y = r.bottom() + 6

        self._btn_cancel.move(x, y)

        self._btn_confirm.move(x + bw + 10, y)

        self._btn_confirm.show()

        self._btn_cancel.show()

        self.update()

    def keyPressEvent(self, event):

        if event.key() == Qt.Key.Key_Escape:

            if self._confirmed_rect is not None:

                self._confirmed_rect = None

                self._btn_confirm.hide()

                self._btn_cancel.hide()

                self.setCursor(Qt.CursorShape.CrossCursor)

                self.update()

            else:

                self._end_session()

        super().keyPressEvent(event)

    def _prepare_capture(self) -> None:

        import time

        self._restore_visible = []

        for widget in self._hide_widgets:

            self._restore_visible.append(widget.isVisible())

            widget.hide()

        for ov in self._session_overlays:

            ov.hide()

        QApplication.processEvents()

        time.sleep(0.1)

        QApplication.processEvents()

    def _restore_after_capture(self) -> None:

        for widget, was_visible in zip(self._hide_widgets, self._restore_visible):

            if was_visible:

                widget.show()

        self._restore_visible = []

    def _save_and_close(self):

        r = self._confirmed_rect

        if r is None:

            self._end_session()

            return

        # 与图像助手一致：覆盖层已绑定单屏，选区坐标即屏幕本地坐标

        screen = self._screen

        self._prepare_capture()

        try:

            import datetime

            import os

            name = datetime.datetime.now().strftime("%Y%m%d-%H_%M_%S")

            os.makedirs(self._save_dir, exist_ok=True)

            path = os.path.join(self._save_dir, f"{name}.png")

            ok = _capture_region_to_path(screen, r, path)

            if ok and os.path.isfile(path) and os.path.getsize(path) > 0 and self._on_saved:
                self._on_saved(path)

        finally:

            self._restore_after_capture()

        self._end_session()

    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._confirmed_rect is not None:

            r = self._confirmed_rect

            painter.fillRect(0, 0, self.width(), r.top(), QColor(0, 0, 0, 80))

            painter.fillRect(0, r.bottom(), self.width(), self.height() - r.bottom(), QColor(0, 0, 0, 80))

            painter.fillRect(0, r.top(), r.left(), r.height(), QColor(0, 0, 0, 80))

            painter.fillRect(r.right(), r.top(), self.width() - r.right(), r.height(), QColor(0, 0, 0, 80))

            painter.setPen(QPen(QColor(255, 255, 255), 2))

            painter.setBrush(Qt.BrushStyle.NoBrush)

            painter.drawRect(r)

        elif self._start_pos and self._end_pos:

            r = QRect(self._start_pos, self._end_pos).normalized()

            painter.fillRect(0, 0, self.width(), r.top(), QColor(0, 0, 0, 80))

            painter.fillRect(0, r.bottom(), self.width(), self.height() - r.bottom(), QColor(0, 0, 0, 80))

            painter.fillRect(0, r.top(), r.left(), r.height(), QColor(0, 0, 0, 80))

            painter.fillRect(r.right(), r.top(), self.width() - r.right(), r.height(), QColor(0, 0, 0, 80))

            pen = QPen(QColor(255, 255, 255), 2)

            pen.setStyle(Qt.PenStyle.DashLine)

            painter.setPen(pen)

            painter.setBrush(Qt.BrushStyle.NoBrush)

            painter.drawRect(r)

        else:

            painter.fillRect(self.rect(), QColor(0, 0, 0, 80))

        painter.end()

class PetWindow(QWidget):

    """透明宠物窗口。

    职责：

    1. 播放宠物 GIF 动画或显示静态图片

    2. 处理鼠标拖拽移动

    3. 管理信息气泡的显示/隐藏

    4. 接收监控数据并更新 UI

    不变量：

    - 窗口始终透明、无边框、置顶

    - _current_state 与最近一次 on_metrics_updated 一致

    """

    # 支持的动画扩展名

    _ANIMATED_EXTENSIONS: frozenset[str] = frozenset({

        ".gif", ".apng", ".webp",

    })

    def __init__(

        self,

        video_path: str = "",

        video_list: Optional[list[str]] = None,

        parent: Optional[QWidget] = None,

        source_names: Optional[list[str]] = None,

        on_switch_source: Optional[Callable[[str], None]] = None,

        on_weather_report: Optional[Callable[[], None]] = None,

        on_test_health: Optional[Callable[[], None]] = None,

    ) -> None:

        super().__init__(parent)

        self._drag_pos: Optional[QPoint] = None

        self._current_state: PetState = PetState.IDLE

        self._metrics: dict = {}

        self._video_list: list[str] = video_list or []

        self._current_video_index: int = 0

        # GIF 动画播放（QMovie）

        self._movie: Optional[QMovie] = None

        self._current_frame: Optional[QPixmap] = None

        # 判断文件类型并初始化

        path = Path(video_path)

        if path.suffix.lower() in self._ANIMATED_EXTENSIONS and path.exists():

            self._pet_pixmap = QPixmap()  # 占位，动画帧由 QMovie 提供

            self._init_movie(video_path)

            if video_path in self._video_list:

                self._current_video_index = self._video_list.index(video_path)

        else:

            # 静态图片模式

            self._pet_pixmap = QPixmap(video_path)

            if self._pet_pixmap.isNull():

                self._pet_pixmap = self._create_placeholder()

        self._bubble = InfoBubble()

        self._pure_mode: bool = False

        self._last_click_time: float = 0.0

        self._source_names = source_names or []

        self._on_switch_source = on_switch_source

        self._on_weather_report = on_weather_report

        self._on_test_health = on_test_health

        self._save_notice: _SaveNotice | None = None

        self._border_angle: float = 0.0

        self._border_alpha: float = 0.6

        self._border_timer = QTimer(self)

        self._border_timer.timeout.connect(self._update_border)

        self._border_timer.start(50)  # 20fps

        self._content_rect = QRectF()

        self._net_warning_text: Optional[str] = None

        self._net_zero_samples: int = 0

        self._net_warning_timer = QTimer(self)

        self._net_warning_timer.setSingleShot(True)

        self._net_warning_timer.timeout.connect(self._clear_net_warning)

        self._init_window()

    def _init_window(self) -> None:

        """配置窗口属性：透明、无边框、置顶。"""

        self.setWindowFlags(

            Qt.WindowType.FramelessWindowHint

            | Qt.WindowType.WindowStaysOnTopHint

            | Qt.WindowType.Tool

        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setFixedSize(PET_SIZE, PET_SIZE)

        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def _init_movie(self, gif_path: str) -> None:

        """初始化 QMovie 用于 GIF 动画播放。

        QMovie 相比 QMediaPlayer + QVideoSink 方案：

        - 内存占用极低（约 5-15MB vs 300-500MB）

        - 不需要音频解码管线

        - 不需要复杂的视频后端（WMF/FFmpeg）

        """

        self._movie = QMovie(gif_path)

        self._movie.setCacheMode(QMovie.CacheMode.CacheAll)  # 缓存所有帧

        self._movie.frameChanged.connect(self._on_movie_frame)

        self._movie.start()

    def _on_movie_frame(self, frame_number: int) -> None:

        """动画帧变化回调，提取当前帧为 QPixmap 并触发重绘。"""

        pixmap = self._movie.currentPixmap()

        if not pixmap.isNull():

            self._current_frame = pixmap

            self.update()

    # ---- 视频切换 ----

    def switch_video(self, video_path: str) -> None:

        """切换到指定动画/图片文件。"""

        path = Path(video_path)

        if not path.exists():

            return

        # 停止并清理旧的 QMovie

        if self._movie is not None:

            self._movie.stop()

            self._movie.deleteLater()

            self._movie = None

        self._current_frame = None

        if path.suffix.lower() in self._ANIMATED_EXTENSIONS:

            self._init_movie(video_path)

        else:

            self._pet_pixmap = QPixmap(video_path)

            if self._pet_pixmap.isNull():

                self._pet_pixmap = self._create_placeholder()

        if video_path in self._video_list:

            self._current_video_index = self._video_list.index(video_path)

    def switch_next_video(self) -> None:

        """切换到下一个视频（循环）。"""

        if not self._video_list:

            return

        next_idx = (self._current_video_index + 1) % len(self._video_list)

        self.switch_video(self._video_list[next_idx])

    @property

    def video_list(self) -> list[str]:

        """返回可用视频列表。"""

        return list(self._video_list)

    @property

    def current_video_index(self) -> int:

        """返回当前视频索引。"""

        return self._current_video_index

    # ---- 数据更新接口 ----

    def on_metrics_updated(self, metrics: dict) -> None:
        """槽函数：接收 SystemMonitor 发射的指标数据。"""
        self._metrics = metrics
        self._current_state = evaluate(metrics)
        self._update_net_warning(metrics)
        self.update()  # 触发 paintEvent 重绘

    def _update_net_warning(self, metrics: dict) -> None:
        """连续 5 秒下载速率为 0 时显示断网警告。"""
        down = metrics.get("net_down_kb")
        if down is not None and down <= 0:
            self._net_zero_samples += 1
            if self._net_zero_samples >= 5:
                self.show_net_warning("网络连接异常")
        elif down is not None:
            self._net_zero_samples = 0
            self.hide_net_warning()

    def set_pure_mode(self, enabled: bool) -> None:

        """开启/关闭纯净模式。"""

        self._pure_mode = enabled

    def _update_border(self) -> None:

        """更新呼吸边框的旋转角度和透明度。"""

        import math

        self._border_angle = (self._border_angle + 3.0) % 360.0

        # 呼吸效果：alpha 在 0.3 ~ 0.8 之间波动

        breath = math.sin(math.radians(self._border_angle * 2.5))

        self._border_alpha = 0.55 + 0.25 * breath

        self.update()  # 触发重绘

    def show_net_warning(self, text: str) -> None:

        """显示网速警告红字（网络故障时调用），网络恢复前持续显示"""

        self._net_warning_text = text

        self._net_warning_timer.stop()

        self.update()

    def hide_net_warning(self) -> None:

        """网络恢复正常，启动3秒倒计时后自动清除警告"""

        if self._net_warning_text is not None and not self._net_warning_timer.isActive():

            self._net_warning_timer.start(3000)

    def _clear_net_warning(self) -> None:

        """定时器到期，清除网速警告"""

        self._net_warning_text = None

        self.update()

    def _draw_border(self, painter) -> None:

        """绘制炫彩呼吸边框——圆锥渐变，护眼暖色绕圈。"""

        if self._content_rect.isNull() or self._content_rect.isEmpty():

            return

        cx = self._content_rect.center().x()

        cy = self._content_rect.center().y()

        # 圆锥渐变，随时间旋转

        gradient = QConicalGradient(cx, cy, self._border_angle)

        gradient.setSpread(QGradient.Spread.RepeatSpread)

        # 护眼暖色stop：暖绿 → 暖黄 → 暖橙 → 暖粉 → 暖绿

        # 科技蓝紫渐变，首尾平滑闭合（210~270）

        cyber = [

            (0.00, 210),

            (0.08, 218),

            (0.17, 225),

            (0.25, 232),

            (0.33, 238),

            (0.42, 244),

            (0.50, 250),

            (0.58, 256),

            (0.67, 262),

            (0.75, 268),

            (0.83, 270),

            (0.92, 240),

            (1.00, 210),

        ]

        for pos, hue in cyber:

            color = QColor.fromHsvF(hue / 360.0, 0.8, 0.95, self._border_alpha)

            gradient.setColorAt(pos, color)

        pen = QPen(QBrush(gradient), 3)

        painter.setPen(pen)

        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawRect(self._content_rect)

    # ---- 绘制 ----

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802

        """重绘宠物：优先使用动画帧，否则使用静态图片，然后绘制呼吸边框。"""

        painter = QPainter(self)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._current_frame is not None and not self._current_frame.isNull():

            pixmap = self._current_frame

        else:

            pixmap = self._pet_pixmap

        # 计算实际绘制区域（居中保持宽高比）

        scaled = pixmap.scaled(

            self.size(),

            Qt.AspectRatioMode.KeepAspectRatio,

            Qt.TransformationMode.SmoothTransformation,

        )

        px = (self.width() - scaled.width()) // 2

        py = (self.height() - scaled.height()) // 2

        painter.drawPixmap(px, py, scaled)

        # 保存内容区域供边框绘制使用

        self._content_rect = QRectF(

            px, py, scaled.width(), scaled.height()

        )

        self._draw_border(painter)

        # 绘制网速警告（红字，居中顶部）

        if self._net_warning_text:

            painter.setPen(QColor(255, 50, 50))

            font = painter.font()

            font.setPointSize(8)

            font.setBold(True)

            painter.setFont(font)

            painter.drawText(

                self.rect().adjusted(2, 2, -2, -2),

                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,

                self._net_warning_text,

            )

        painter.end()

    def _draw_pixmap(self, painter: QPainter, pixmap: QPixmap) -> None:

        """将指定 pixmap 居中缩放后绘制。"""

        if pixmap.isNull():

            return

        scaled = pixmap.scaled(

            self.size(),

            Qt.AspectRatioMode.KeepAspectRatio,

            Qt.TransformationMode.SmoothTransformation,

        )

        x = (self.width() - scaled.width()) // 2

        y = (self.height() - scaled.height()) // 2

        painter.drawPixmap(x, y, scaled)

    # ---- 鼠标交互 ----

    def mousePressEvent(self, event) -> None:  # noqa: N802

        """记录拖拽开始位置，检测双击。"""

        if event.button() == Qt.MouseButton.LeftButton:

            import time

            now = time.monotonic()

            if now - self._last_click_time < 0.4:

                self._last_click_time = 0.0

                self._drag_pos = None

                menu = QMenu()

                act_shot = QAction("截图", self)

                act_shot.triggered.connect(self._start_screenshot)

                menu.addAction(act_shot)

                act_rec = QAction("录屏", self)

                act_rec.triggered.connect(self._start_recording)

                menu.addAction(act_rec)

                menu.exec(event.globalPosition().toPoint())

                event.accept()

                return

            self._last_click_time = now

            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

            self.setCursor(Qt.CursorShape.ClosedHandCursor)

            self._bubble.pause_hide_timer()

            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802

        """左键拖拽移动窗口。拖拽过程中实时更新气泡位置。"""

        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:

            new_pos = event.globalPosition().toPoint() - self._drag_pos

            self.move(new_pos)

            # 拖拽中实时同步气泡位置

            if self._bubble.isVisible():

                bx, by = self._calc_bubble_position()

                self._bubble.move(bx, by)

            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802

        self._drag_pos = None

        self.setCursor(Qt.CursorShape.OpenHandCursor)

        self._bubble.resume_hide_timer()

        event.accept()

    def enterEvent(self, event) -> None:  # noqa: N802

        """鼠标进入时显示气泡（纯模式不显示）。"""

        if not self._pure_mode:

            bx, by = self._calc_bubble_position()

            self._bubble.show_bubble(bx, by)

        super().enterEvent(event)

    def moveEvent(self, event) -> None:  # noqa: N802

        """窗口移动时，气泡跟随移动。"""

        if self._bubble.isVisible():

            bx, by = self._calc_bubble_position()

            self._bubble.move(bx, by)

        super().moveEvent(event)

    def _calc_bubble_position(self) -> tuple[int, int]:

        """计算气泡最佳位置，自动处理屏幕边缘和角落。

        优先显示在右侧；右侧空间不够则显示在左侧；

        垂直方向超出屏幕则向上偏移。

        Returns:

            (x, y) 屏幕绝对坐标

        """

        # 使用宠物窗口所在的屏幕（而非主屏幕），支持多显示器

        screen = QGuiApplication.screenAt(self.frameGeometry().center())

        if screen is None:

            screen = QGuiApplication.primaryScreen()

        if screen is None:

            return self.x() + self.width() + BUBBLE_MARGIN, self.y()

        screen_rect = screen.availableGeometry()

        bubble_w = self._bubble.width()

        bubble_h = self._bubble.height()

        pet_x = self.x()

        pet_y = self.y()

        pet_w = self.width()

        pet_h = self.height()

        # 水平：优先右侧，空间不足则左侧

        space_right = screen_rect.right() - (pet_x + pet_w + BUBBLE_MARGIN + bubble_w)

        if space_right >= 0:

            bx = pet_x + pet_w + BUBBLE_MARGIN

        else:

            bx = pet_x - BUBBLE_MARGIN - bubble_w

        # 水平超出左边界修正

        if bx < screen_rect.left():

            bx = screen_rect.left()

        # 垂直：与宠物居中对齐

        by = pet_y + (pet_h - bubble_h) // 2

        if by + bubble_h > screen_rect.bottom():

            by = screen_rect.bottom() - bubble_h

        if by < screen_rect.top():

            by = screen_rect.top()

        return bx, by

    # ---- 辅助 ----

    @staticmethod

    def _create_placeholder() -> QPixmap:

        """图片加载失败时的占位图：灰色圆形。"""

        pixmap = QPixmap(PET_SIZE, PET_SIZE)

        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)

        painter.setBrush(QBrush(QColor(180, 180, 180)))

        painter.setPen(QPen(QColor(120, 120, 120), 2))

        painter.drawEllipse(10, 10, PET_SIZE - 20, PET_SIZE - 20)

        painter.end()

        return pixmap

    def closeEvent(self, event) -> None:  # noqa: N802

        """关闭时清理动画和气泡窗口。"""

        if self._movie is not None:

            self._movie.stop()

            self._movie.deleteLater()

            self._movie = None

        self._bubble.close()

        super().closeEvent(event)

    def set_quick_actions(

        self,

        source_names: list[str] | None = None,

        on_switch_source: None = None,

        on_weather_report: None = None,

        on_test_health: None = None,

    ) -> None:

        self._source_names = source_names or []

        self._on_switch_source = on_switch_source

        self._on_weather_report = on_weather_report

        self._on_test_health = on_test_health

    def _notify_save_result(self, path: str, title: str = "已保存") -> None:
        """保存成功后自动打开位置并显示路径提示。"""
        _open_in_explorer(path)
        if self._save_notice is not None:
            try:
                self._save_notice.close()
            except RuntimeError:
                pass
        self._save_notice = _SaveNotice(self, path, title)
        self._save_notice.show()

    def _end_screenshot_session(self) -> None:

        for ov in getattr(self, "_overlays", []):

            ov.close()

        self._overlays = []

    def _start_screenshot(self) -> None:

        import os

        pics = os.path.join(os.path.expanduser("~"), "Pictures", "HSN_截图")

        screens = QApplication.screens() or [QApplication.primaryScreen()]

        self._overlays = []

        for s in screens:

            ov = ScreenshotOverlay(

                s,

                save_dir=pics,

                on_session_end=self._end_screenshot_session,

                on_saved=lambda p: self._notify_save_result(p, "截图已保存"),

                session_overlays=self._overlays,

            )

            self._overlays.append(ov)

            ov.show()

            ov.raise_()

            ov.activateWindow()

    def _start_recording(self) -> None:

        """启动录屏（延迟创建覆盖层，避免 menu.exec 模态循环干扰）。"""

        import logging as _log

        _log.debug("_start_recording called")

        from PySide6.QtCore import QTimer

        QTimer.singleShot(100, self._delayed_recording)

    def _delayed_recording(self) -> None:

        """录屏：直接用原生 Qt 覆盖层，完全不用 RecordingOverlay 类。"""

        try:

            from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QApplication as _QA

            from PySide6.QtCore import QRect, QTimer as _QT

            from PySide6.QtGui import QColor, QPainter, QPen

            import time as _time

            import mss as _mss

            import subprocess as _sp

            import os as _os

            screens = _QA.screens() or [_QA.primaryScreen()]

            self._rec_ovs = []   # 覆盖层列表

            self._rec_region = None

            self._recording = False

            self._rec_proc = None

            self._rec_output = None

            self._rec_start_t = 0.0

            class _RecOverlay(QWidget):

                """录屏覆盖层（内联类，不依赖外部模块）。"""

                def __init__(self, screen, parent):

                    super().__init__()

                    self._screen = screen

                    self._parent_ref = parent

                    self._start_pos = None

                    self._end_pos = None

                    self._confirmed_rect = None

                    self._recording = False

                    self._btn_start = None

                    self._btn_stop = None

                    self._timer_lbl = None

                    self.setWindowFlags(

                        Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint

                        | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool

                    )

                    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

                    self.setCursor(Qt.CursorShape.CrossCursor)

                    geo = self._screen.geometry()

                    self.setGeometry(geo)

                def paintEvent(self, event):

                    p = QPainter(self)

                    p.setRenderHint(QPainter.RenderHint.Antialiasing)

                    if self._recording:
                        if self._confirmed_rect:
                            r = self._confirmed_rect
                            pen = QPen(QColor(231, 76, 60), 3)
                            p.setPen(pen)
                            p.setBrush(Qt.BrushStyle.NoBrush)
                            p.drawRect(r.adjusted(-2, -2, 2, 2))
                        return

                    if self._confirmed_rect:

                        r = self._confirmed_rect

                        self._draw_shadow(p, r)

                        pen = QPen(QColor(255, 255, 255), 2)

                        pen.setStyle(Qt.PenStyle.DashLine)

                        p.setPen(pen)

                        p.setBrush(Qt.BrushStyle.NoBrush)

                        p.drawRect(r)

                    elif self._start_pos and self._end_pos:

                        r = QRect(self._start_pos, self._end_pos).normalized()

                        self._draw_shadow(p, r)

                        pen = QPen(QColor(255, 255, 255), 2)

                        pen.setStyle(Qt.PenStyle.DashLine)

                        p.setPen(pen)

                        p.setBrush(Qt.BrushStyle.NoBrush)

                        p.drawRect(r)

                    else:

                        p.fillRect(0, 0, self.width(), self.height(), QColor(0, 0, 0, 80))

                        p.setPen(QColor(255, 255, 255))

                        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "拖拽选择录制区域")

                def _draw_shadow(self, p, r):

                    p.fillRect(0, 0, self.width(), r.top(), QColor(0, 0, 0, 80))

                    p.fillRect(0, r.bottom(), self.width(), self.height() - r.bottom(), QColor(0, 0, 0, 80))

                    p.fillRect(0, r.top(), r.left(), r.height(), QColor(0, 0, 0, 80))

                    p.fillRect(r.right(), r.top(), self.width() - r.right(), r.height(), QColor(0, 0, 0, 80))

                def mousePressEvent(self, event):

                    if event.button() != Qt.MouseButton.LeftButton or self._recording:

                        return

                    if self._confirmed_rect:

                        pos = event.position().toPoint()

                        r = self._confirmed_rect

                        bx = r.right() - 150

                        by = r.bottom() + 8

                        btn_zone = getattr(self, '_btn_zone', None)

                        if btn_zone is not None and btn_zone.contains(pos):

                            return

                        self._confirmed_rect = None

                        self.setCursor(Qt.CursorShape.CrossCursor)

                    self._start_pos = event.position().toPoint()

                    self._end_pos = None

                    self.update()

                    event.accept()

                def mouseMoveEvent(self, event):

                    if self._start_pos and self._confirmed_rect is None and not self._recording:

                        self._end_pos = event.position().toPoint()

                        self.update()

                def mouseReleaseEvent(self, event):

                    if event.button() != Qt.MouseButton.LeftButton or self._recording:

                        return

                    if self._start_pos and self._end_pos:

                        r = QRect(self._start_pos, self._end_pos).normalized()

                        if r.width() > 20 and r.height() > 20:

                            self._confirmed_rect = r

                            self.setCursor(Qt.CursorShape.ArrowCursor)

                            self._show_btn(r)

                            self.update()

                def _show_btn(self, r):

                    self._parent_ref._show_rec_controls(self, r)

                def mouseDoubleClickEvent(self, event):

                    """双击关闭当前覆盖层。"""

                    self._parent_ref._cancel_rec()

            # 创建覆盖层

            self._rec_ovs = []

            for s in screens:

                ov = _RecOverlay(s, self)

                self._rec_ovs.append(ov)

                ov.show()

            _QA.processEvents()

            for ov in self._rec_ovs:

                ov.raise_()

                ov.activateWindow()

        except Exception as _e:

            import traceback

            try:

                with open(_tmp_pic_path("_recording_error.txt"), "w", encoding="utf-8") as _f:
                    _f.write(traceback.format_exc())

            except Exception:

                pass

    def _show_rec_controls(self, overlay, rect):

        """在指定覆盖层上显示开始录制/取消/重框按钮。"""

        try:

            from PySide6.QtWidgets import QPushButton

            self._rec_active_ov = overlay

            btn_style = (

                "QPushButton{background:#E74C3C;color:white;font:bold 13px 'Microsoft YaHei';"

                "border-radius:5px;padding:4px 10px;}"

                "QPushButton:hover{background:#F0625C;}"

            )

            btn_sec_style = (

                "QPushButton{background:#555555;color:white;font:bold 13px 'Microsoft YaHei';"

                "border-radius:5px;padding:4px 10px;}"

                "QPushButton:hover{background:#777777;}"

            )

            # 开始录制按钮

            overlay._btn_start = QPushButton("开始录制", overlay)

            overlay._btn_start.setStyleSheet(btn_style)

            overlay._btn_start.setFixedSize(100, 34)

            bx_start = rect.right() - 110

            by = rect.bottom() + 8

            overlay._btn_start.move(bx_start, by)

            overlay._btn_start.show()

            overlay._btn_start.clicked.connect(lambda: self._start_recording_inner(overlay, rect))

            # 重新框选按钮（在开始录制左侧）

            overlay._btn_reselect = QPushButton("重新框选", overlay)

            overlay._btn_reselect.setStyleSheet(btn_sec_style)

            overlay._btn_reselect.setFixedSize(100, 34)

            overlay._btn_reselect.move(bx_start - 110, by)

            overlay._btn_reselect.show()

            overlay._btn_reselect.clicked.connect(

                lambda: self._reselect_rec(overlay)

            )

            # 取消按钮（在最左侧）

            overlay._btn_cancel = QPushButton("取消", overlay)

            overlay._btn_cancel.setStyleSheet(btn_sec_style)

            overlay._btn_cancel.setFixedSize(60, 34)

            overlay._btn_cancel.move(bx_start - 180, by)

            overlay._btn_cancel.show()

            overlay._btn_cancel.clicked.connect(self._cancel_rec)

            # 更新按钮区域，用于 mousePressEvent 判断

            overlay._btn_zone = QRect(

                bx_start - 180, by, 280, 40

            )

        except Exception as _e:

            import traceback

            try:

                with open(_tmp_pic_path("_recording_controls_error.txt"), "w", encoding="utf-8") as _f_e:
                    _f_e.write(traceback.format_exc())

            except Exception:

                pass

    def _start_recording_inner(self, overlay, rect):

        """开始录屏。"""

        try:

            from PySide6.QtWidgets import QLabel, QPushButton

            from PySide6.QtCore import QTimer as _QT

            import subprocess as _sp

            import threading

            import time as _time

            from src.services.screen_recorder import _recording_path

            selected = _select_recording_capture(overlay._screen, rect)

            if selected is None:

                return

            capture_method, region, width, height = selected

            for ov_ in self._rec_ovs:

                if ov_ is not overlay:

                    ov_.hide()

            if overlay._btn_start:

                overlay._btn_start.hide()

            if getattr(overlay, "_btn_reselect", None):

                overlay._btn_reselect.hide()

            if getattr(overlay, "_btn_cancel", None):

                overlay._btn_cancel.hide()

            output = _recording_path()

            overlay._timer_lbl = QLabel("00:00.0", overlay)

            overlay._timer_lbl.setStyleSheet(

                "color:#E74C3C;font:bold 22px 'Microsoft YaHei';"

                "background:rgba(0,0,0,180);border-radius:4px;padding:4px 8px;"

            )

            overlay._timer_lbl.setFixedSize(130, 36)

            overlay._timer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            tx, ty = _rec_control_position(
                rect, overlay._screen.geometry(), overlay._timer_lbl.width(), overlay._timer_lbl.height()
            )
            overlay._timer_lbl.move(tx, ty)

            overlay._timer_lbl.show()

            overlay._btn_stop = QPushButton("停止录制", overlay)

            overlay._btn_stop.setStyleSheet(

                "QPushButton{background:#B43232;color:white;font:bold 14px 'Microsoft YaHei';"

                "border-radius:5px;padding:4px 12px;}"

            )

            overlay._btn_stop.setFixedSize(110, 34)

            overlay._btn_stop.move(rect.right() - 120, rect.bottom() + 8)

            overlay._btn_stop.show()

            overlay._rec_start_time = _time.time()

            overlay._rec_timer = _QT(overlay)

            overlay._rec_timer.timeout.connect(

                lambda: overlay._timer_lbl.setText(

                    f"{int((_time.time() - overlay._rec_start_time) // 60):02d}:"

                    f"{int((_time.time() - overlay._rec_start_time) % 60):02d}."

                    f"{int(((_time.time() - overlay._rec_start_time) * 10) % 10)}"

                )

            )

            overlay._rec_timer.start(100)

            cmd = [

                "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo",

                "-s", f"{width}x{height}", "-pix_fmt", "rgb24", "-r", "10",

                "-i", "-", "-an", "-c:v", "libx264", "-preset", "fast",

                "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart",

                output,

            ]

            proc = _sp.Popen(

                cmd, stdin=_sp.PIPE, bufsize=1024 * 1024 * 10,

                creationflags=_sp.CREATE_NO_WINDOW,

            )

            overlay._rec_proc = proc

            overlay._rec_output = output

            overlay._recording = True

            overlay.update()

            def _cleanup_rec_ui(ov) -> None:
                ov._recording = False
                ov._confirmed_rect = None
                if getattr(ov, "_rec_timer", None):
                    ov._rec_timer.stop()
                    ov._rec_timer.deleteLater()
                    ov._rec_timer = None
                for attr in ("_btn_stop", "_timer_lbl", "_btn_start", "_btn_reselect", "_btn_cancel"):
                    w = getattr(ov, attr, None)
                    if w is not None:
                        w.hide()
                        w.deleteLater()
                        setattr(ov, attr, None)
                ov.hide()
                ov.update()

            def _stop_rec():
                if not overlay._recording:
                    return
                _cleanup_rec_ui(overlay)

            overlay._btn_stop.clicked.connect(_stop_rec)

            def _capture():

                import time as _t

                fps = 10

                interval = 1.0 / fps

                last = 0.0

                frame_count = 0

                try:

                    while overlay._recording:

                        now = _t.time()

                        if now - last < interval:

                            _t.sleep(0.005)

                            continue

                        rgb = _capture_recording_frame(

                            overlay,

                            overlay._screen,

                            rect,

                            region,

                            capture_method,

                            width,

                            height,

                        )

                        if rgb is None:

                            _t.sleep(0.05)

                            continue

                        proc.stdin.write(rgb)

                        frame_count += 1

                        last = now

                except BrokenPipeError:

                    pass

                except Exception:

                    pass

                finally:

                    try:

                        proc.stdin.close()

                    except Exception:

                        pass

                    try:

                        proc.wait(timeout=15)

                    except Exception:

                        try:

                            proc.kill()

                        except Exception:

                            pass

                    if frame_count == 0:

                        try:

                            import os as _os

                            if _os.path.exists(output) and _os.path.getsize(output) < 1024:

                                _os.remove(output)

                        except OSError:

                            pass

                    _QT.singleShot(0, lambda: self._finish_recording(output, frame_count > 0))

            threading.Thread(target=_capture, daemon=True).start()

        except Exception:
            import logging
            import traceback
            logging.getLogger(__name__).error("录屏启动失败:\n%s", traceback.format_exc())
            try:
                with open(_tmp_pic_path("_recording_start_error.txt"), "w", encoding="utf-8") as _f:
                    _f.write(traceback.format_exc())
            except OSError:
                pass

    def _finish_recording(self, output: str, ok: bool) -> None:
        """录屏结束后回到主线程清理 UI。"""
        import os as _os

        for ov in getattr(self, "_rec_ovs", []):
            try:
                ov._recording = False
                ov._confirmed_rect = None
                ov.hide()
                ov.close()
            except Exception:
                pass
        self._rec_ovs = []

        if ok and _os.path.isfile(output) and _os.path.getsize(output) > 1024:
            self._notify_save_result(output, "录屏已保存")

    def _reselect_rec(self, overlay):

        """重新框选：恢复到选区模式。"""

        if hasattr(overlay, '_btn_reselect') and overlay._btn_reselect:

            try:

                overlay._btn_reselect.close()

            except Exception:

                pass

            overlay._btn_reselect = None

        if hasattr(overlay, '_btn_cancel') and overlay._btn_cancel:

            try:

                overlay._btn_cancel.close()

            except Exception:

                pass

            overlay._btn_cancel = None

        if hasattr(overlay, '_btn_start') and overlay._btn_start:

            try:

                overlay._btn_start.close()

            except Exception:

                pass

            overlay._btn_start = None

        overlay._confirmed_rect = None

        overlay._start_pos = None

        overlay._end_pos = None

        overlay._btn_zone = None

        overlay.setCursor(Qt.CursorShape.CrossCursor)

        overlay.update()

    def _cancel_rec(self):

        """取消录屏（关闭所有覆盖层）。"""

        for ov in getattr(self, "_rec_ovs", []):

            try:

                ov._recording = False

                proc = getattr(ov, "_rec_proc", None)

                if proc is not None:

                    try:

                        proc.stdin.close()

                    except Exception:

                        pass

                    try:

                        proc.kill()

                    except Exception:

                        pass

                ov.close()

            except Exception:

                pass

        self._rec_ovs = []

