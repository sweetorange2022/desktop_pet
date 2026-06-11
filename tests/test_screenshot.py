"""截图功能自检脚本，打包前运行。"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import QApplication, QWidget

from src.ui.pet_window import (
    ScreenshotOverlay,
    _capture_region_to_path,
    _file_max_brightness,
    _monitor_dpi_scale,
)


def _debug_screen_capture(screen, rect: QRect, label: str) -> None:
    try:
        from src.ui.pet_window import _monitor_for_screen, _physical_region, _win32_physical_monitors

        geo = screen.geometry()
        monitor = _monitor_for_screen(screen)
        region = _physical_region(screen, rect)
        print(
            f"  debug {label}: geo={geo.x()},{geo.y()},{geo.width()}x{geo.height()} "
            f"dpr={screen.devicePixelRatio()} win32={_win32_physical_monitors()} "
            f"monitor={monitor} region={region}"
        )
    except Exception as exc:
        print(f"  debug {label}: error={exc}")


def _test_direct_capture(screens, out_dir: Path) -> list[str]:
    errors: list[str] = []
    rect = QRect(200, 200, 400, 300)
    for index, screen in enumerate(screens):
        path = out_dir / f"direct_screen_{index}.png"
        _debug_screen_capture(screen, rect, f"screen {index}")
        if not _capture_region_to_path(screen, rect, str(path)):
            errors.append(f"screen {index}: direct capture failed")
            continue
        from PIL import Image

        brightness = _file_max_brightness(str(path))
        with Image.open(path) as image:
            scale = _monitor_dpi_scale(screen)
            expected_w = max(1, int(rect.width() * scale))
            expected_h = max(1, int(rect.height() * scale))
            print(
                f"  direct screen {index}: max_brightness={brightness} "
                f"size={image.width}x{image.height} expected={expected_w}x{expected_h} "
                f"dpi_scale={_monitor_dpi_scale(screen)}"
            )
            if abs(image.width - expected_w) > 2 or abs(image.height - expected_h) > 2:
                errors.append(
                    f"screen {index}: size mismatch {image.width}x{image.height} "
                    f"!= {expected_w}x{expected_h}"
                )
        if brightness < 2:
            errors.append(f"screen {index}: direct capture is black (max={brightness})")
    return errors


def _test_overlay_capture(screens, out_dir: Path) -> list[str]:
    errors: list[str] = []
    session: list[ScreenshotOverlay] = []

    for screen in screens:
        overlay = ScreenshotOverlay(
            screen,
            save_dir=str(out_dir),
            session_overlays=session,
            hide_widgets=[],
        )
        session.append(overlay)
        overlay.show()

    QApplication.processEvents()
    time.sleep(0.15)

    for index, overlay in enumerate(session):
        rect = QRect(250, 250, 420, 320)
        overlay._confirmed_rect = rect
        screen = overlay._screen
        overlay._prepare_capture()
        path = out_dir / f"overlay_screen_{index}.png"
        if not _capture_region_to_path(screen, rect, str(path)):
            errors.append(f"screen {index}: overlay capture failed")
            continue
        from PIL import Image

        brightness = _file_max_brightness(str(path))
        with Image.open(path) as image:
            scale = _monitor_dpi_scale(screen)
            expected_w = max(1, int(rect.width() * scale))
            expected_h = max(1, int(rect.height() * scale))
            print(
                f"  overlay screen {index}: max_brightness={brightness} "
                f"size={image.width}x{image.height} expected={expected_w}x{expected_h} "
                f"dpi_scale={_monitor_dpi_scale(screen)}"
            )
            if abs(image.width - expected_w) > 2 or abs(image.height - expected_h) > 2:
                errors.append(
                    f"screen {index}: overlay size mismatch {image.width}x{image.height} "
                    f"!= {expected_w}x{expected_h}"
                )
        if brightness < 2:
            errors.append(f"screen {index}: overlay capture is black (max={brightness})")

    for overlay in session:
        overlay.close()

    return errors


def main() -> int:
    app = QApplication(sys.argv)
    screens = app.screens()
    if not screens:
        print("FAIL: no screens detected")
        return 1

    out_dir = Path(__file__).parent / "dist" / "screenshot_selftest"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"检测到 {len(screens)} 个屏幕，开始自检...")
    for index, screen in enumerate(screens):
        geo = screen.geometry()
        print(
            f"  screen {index}: {screen.name()} "
            f"geo=({geo.x()}, {geo.y()}, {geo.width()}, {geo.height()}) "
            f"dpr={screen.devicePixelRatio()}"
        )

    errors: list[str] = []
    print("1) 直接抓图测试")
    errors.extend(_test_direct_capture(screens, out_dir))
    print("2) 覆盖层流程测试")
    errors.extend(_test_overlay_capture(screens, out_dir))

    if errors:
        print("截图自检失败:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("截图自检全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
