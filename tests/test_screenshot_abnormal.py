"""检测副屏误抓：超大画布 + 角落有内容。"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from src.ui.pet_window import (
    _capture_region_to_path,
    _expected_capture_size,
    _is_primary_screen,
)


def _content_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    gray = image.convert("L")
    w, h = gray.size
    minx, miny, maxx, maxy = w, h, 0, 0
    found = False
    for y in range(h):
        for x in range(w):
            if gray.getpixel((x, y)) > 10:
                found = True
                minx = min(minx, x)
                miny = min(miny, y)
                maxx = max(maxx, x)
                maxy = max(maxy, y)
    if not found:
        return None
    return minx, miny, maxx, maxy


def main() -> int:
    app = QApplication(sys.argv)
    screens = app.screens()
    out = Path(__file__).parent / "dist" / "screenshot_abnormal_test"
    out.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    rects = [
        QRect(120, 120, 360, 260),
        QRect(500, 300, 520, 400),
        QRect(80, 700, 640, 220),
    ]

    for index, screen in enumerate(screens):
        for i, rect in enumerate(rects):
            geo = screen.geometry()
            if rect.right() > geo.width() or rect.bottom() > geo.height():
                continue
            path = out / f"screen{index}_rect{i}.png"
            if not _capture_region_to_path(screen, rect, str(path)):
                errors.append(f"screen {index} rect {i}: capture failed")
                continue
            with Image.open(path) as image:
                ew, eh = _expected_capture_size(screen, rect)
                bbox = _content_bbox(image)
                print(
                    f"screen {index} primary={_is_primary_screen(screen)} "
                    f"rect={rect.width()}x{rect.height()} file={image.size} "
                    f"expected={ew}x{eh} bbox={bbox}"
                )
                if abs(image.width - ew) > 4 or abs(image.height - eh) > 4:
                    errors.append(f"screen {index} rect {i}: bad size {image.size}")
                if bbox and (bbox[0] > image.width * 0.2 or bbox[1] > image.height * 0.2):
                    errors.append(f"screen {index} rect {i}: corner island {bbox}")

    if errors:
        print("ABNORMAL TEST FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("ABNORMAL TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
