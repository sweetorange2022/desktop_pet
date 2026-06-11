"""屏幕录制模块。

提供全屏覆盖层选择录制区域，使用 mss 逐帧捕获 + ffmpeg 编码为 MP4。
录制文件保存到系统「视频」文件夹。
"""

from __future__ import annotations

import datetime
import logging
import os
import threading
import time
from pathlib import Path

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

_logger = logging.getLogger(__name__)

try:
    _log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmpPic")
    os.makedirs(_log_dir, exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(_log_dir, "_recording.log"),
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        force=True,
    )
except Exception:
    pass

def _videos_dir() -> str:
    """获取系统「视频」文件夹路径。"""
    try:
        import ctypes

        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x000E, None, 0, buf)
        return buf.value
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Videos")

def _recording_path() -> str:
    """生成录制文件路径。"""
    dir_path = _videos_dir()
    ts = datetime.datetime.now().strftime("%Y%m%d-%H_%M_%S")
    return os.path.join(dir_path, f"Recording_{ts}.mp4")

def _physical_region_for_recording(screen, rect: QRect) -> dict[str, int] | None:
    """复用截图模块的物理区域计算。"""
    from src.ui.pet_window import _physical_region

    return _physical_region(screen, rect)

class _ScreenRecorder(threading.Thread):
    """后台录屏线程（直接调用 ffmpeg 编码）。"""

    def __init__(self, region: dict, output_path: str):
        super().__init__(daemon=True)
        self._region = region
        self._output_path = output_path
        self._running = False
        self._proc = None
        self.frame_count = 0

    def run(self) -> None:
        import subprocess as sp
        import mss

        self._running = True
        width = max(1, self._region["width"])
        height = max(1, self._region["height"])
        fps = 10
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{width}x{height}", "-pix_fmt", "rgb24", "-r", str(fps),
            "-i", "-", "-an",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            self._output_path,
        ]
        try:
            proc = sp.Popen(
                cmd, stdin=sp.PIPE, bufsize=1024 * 1024 * 10,
                creationflags=sp.CREATE_NO_WINDOW,
            )
            self._proc = proc
        except Exception as exc:
            _logger.error("ffmpeg start failed: %s", exc)
            return

        last_capture = 0.0
        target_interval = 1.0 / fps
        try:
            with mss.mss() as sct:
                while self._running:
                    now = time.time()
                    if now - last_capture < target_interval:
                        time.sleep(0.005)
                        continue
                    try:
                        frame = sct.grab(self._region)
                        if frame is None or frame.size[0] == 0 or frame.size[1] == 0:
                            time.sleep(0.05)
                            continue
                        proc.stdin.write(frame.rgb)
                        self.frame_count += 1
                    except BrokenPipeError:
                        _logger.error("ffmpeg pipe broken at frame %d", self.frame_count)
                        break
                    except Exception as exc:
                        _logger.warning("capture error at frame %d: %s", self.frame_count, exc)
                        time.sleep(0.05)
                        continue
                    last_capture = now
        finally:
            _logger.info(
                "recording finished: %d frames to %s",
                self.frame_count, self._output_path,
            )
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
            if self.frame_count == 0:
                try:
                    if os.path.exists(self._output_path) and os.path.getsize(self._output_path) < 1024:
                        os.remove(self._output_path)
                except OSError:
                    pass

    def stop(self) -> None:
        self._running = False

class RecordingOverlay(QWidget):
    """录屏区域选择覆盖层（每屏一个实例）。"""

    def __init__(self, screen, session_overlays=None):
        super().__init__()
        self._screen = screen
        self._session_overlays = session_overlays or []
        self._recording = False
        self._recorder: _ScreenRecorder | None = None
        self._output_path: str | None = None

        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(self._screen.geometry())
        self._start_pos = None
        self._end_pos = None
        self._confirmed_rect: QRect | None = None

        self._btn_start = QPushButton("开始录制", self)
        self._btn_start.setStyleSheet(
            "QPushButton{background:#E74C3C;color:white;font:bold 13px 'Microsoft YaHei';"
            "border-radius:5px;padding:4px 12px;} "
            "QPushButton:hover{background:#F0625C;}"
        )
        self._btn_start.setFixedSize(110, 34)
        self._btn_start.hide()
        self._btn_start.clicked.connect(self._start_recording)

        self._btn_stop = QPushButton("结束录制", self)
        self._btn_stop.setStyleSheet(
            "QPushButton{background:#B43232;color:white;font:bold 13px 'Microsoft YaHei';"
            "border-radius:5px;padding:4px 12px;} "
            "QPushButton:hover{background:#D43838;}"
        )
        self._btn_stop.setFixedSize(110, 34)
        self._btn_stop.hide()
        self._btn_stop.clicked.connect(self._stop_recording)

        self._timer_label = QLabel("00:00.0", self)
        self._timer_label.setStyleSheet(
            "color:#E74C3C;font:bold 16px 'Microsoft YaHei';"
            "background:rgba(0,0,0,180);border-radius:4px;padding:4px 8px;"
        )
        self._timer_label.setFixedSize(130, 32)
        self._timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer_label.hide()

        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._toggle_blink)
        self._blink_visible = True
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.timeout.connect(self._update_elapsed)
        self._start_time = 0.0

    def _end_session(self) -> None:
        for ov in self._session_overlays:
            if ov is not self:
                ov.close()
        self.close()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._recording:
            return
        if self._confirmed_rect is not None:
            pos = event.position().toPoint()
            r = self._confirmed_rect
            if QRect(r.right() - 150, r.bottom() + 8, 150, 40).contains(pos):
                return
            self._confirmed_rect = None
            self._btn_start.hide()
            self.setCursor(Qt.CursorShape.CrossCursor)
            self._start_pos = event.position().toPoint()
            self._end_pos = None
            self.update()
            return
        self._start_pos = event.position().toPoint()
        self._end_pos = None
        self.update()

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
                self._show_start_button(r)
                self.update()

    def _show_start_button(self, r: QRect) -> None:
        self._btn_start.move(r.right() - 130, r.bottom() + 8)
        self._btn_start.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._recording:
            if self._confirmed_rect:
                r = self._confirmed_rect
                painter.setPen(QPen(QColor(231, 76, 60), 3))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(r)
                if self._blink_visible:
                    painter.setBrush(QColor(231, 76, 60))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(r.right() - 22, r.top() + 6, 14, 14)
            return
        if self._confirmed_rect is not None:
            r = self._confirmed_rect
            self._draw_shadow(painter, r)
            pen = QPen(QColor(255, 255, 255), 2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)
        elif self._start_pos and self._end_pos:
            r = QRect(self._start_pos, self._end_pos).normalized()
            self._draw_shadow(painter, r)
            pen = QPen(QColor(255, 255, 255), 2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)
        else:
            painter.fillRect(0, 0, self.width(), self.height(), QColor(0, 0, 0, 80))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "拖拽选择录制区域")

    def _draw_shadow(self, painter, r: QRect) -> None:
        painter.fillRect(0, 0, self.width(), r.top(), QColor(0, 0, 0, 80))
        painter.fillRect(0, r.bottom(), self.width(), self.height() - r.bottom(), QColor(0, 0, 0, 80))
        painter.fillRect(0, r.top(), r.left(), r.height(), QColor(0, 0, 0, 80))
        painter.fillRect(r.right(), r.top(), self.width() - r.right(), r.height(), QColor(0, 0, 0, 80))

    def _start_recording(self) -> None:
        if self._confirmed_rect is None:
            return
        r = self._confirmed_rect
        region = _physical_region_for_recording(self._screen, r)
        if region is None:
            return

        self._recording = True
        self._btn_start.hide()
        self._output_path = _recording_path()
        self._start_time = time.time()

        self._btn_stop.move(r.right() - 130, r.bottom() + 8)
        self._btn_stop.show()
        self._timer_label.move(max(8, r.x() + 8), max(8, r.y() + 8))
        self._timer_label.show()
        self._timer_label.setText("00:00.0")

        for ov in self._session_overlays:
            if ov is not self:
                ov.hide()

        self._blink_timer.start(800)
        self._elapsed_timer.start(100)
        self.update()
        self.raise_()
        self.activateWindow()

        self._recorder = _ScreenRecorder(region, self._output_path)
        self._recorder.start()

    def _stop_recording(self) -> None:
        if self._recorder:
            self._recorder.stop()
            self._recorder = None
        self._recording = False
        self._confirmed_rect = None
        self._blink_timer.stop()
        self._elapsed_timer.stop()
        self._btn_stop.hide()
        self._timer_label.hide()
        self.hide()
        if self._output_path and os.path.isfile(self._output_path):
            import subprocess as sp
            if os.path.getsize(self._output_path) > 1024:
                sp.Popen(["explorer", "/select,", self._output_path])
        self._end_session()

    def _toggle_blink(self) -> None:
        self._blink_visible = not self._blink_visible
        self.update()

    def _update_elapsed(self) -> None:
        elapsed = time.time() - self._start_time
        mm = int(elapsed // 60)
        ss = int(elapsed % 60)
        tenths = int((elapsed * 10) % 10)
        self._timer_label.setText(f"{mm:02d}:{ss:02d}.{tenths}")
