"""主屏截图位置对齐测试：对比 Qt 直接抓取与当前抓图链路。"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from src.ui.pet_window import _capture_region_to_path, _mss_capture_to_path, _physical_region


def _max_diff(a: Image.Image, b: Image.Image) -> int:
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    return max(diff.convert("L").getdata())


def main() -> int:
    app = QApplication(sys.argv)
    screens = app.screens()
    if not screens:
        print("FAIL: no screens")
        return 1

    out = Path(__file__).parent / "dist" / "screenshot_position_test"
    out.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    test_rects = [
        QRect(100, 100, 300, 200),
        QRect(400, 250, 420, 320),
        QRect(50, 600, 500, 180),
    ]

    for index, screen in enumerate(screens):
        print(f"screen {index}: {screen.name()} dpr={screen.devicePixelRatio()}")
        for i, rect in enumerate(test_rects):
            if rect.right() > screen.geometry().width() or rect.bottom() > screen.geometry().height():
                continue

            ref_path = out / f"screen{index}_ref_{i}.png"
            cur_path = out / f"screen{index}_cur_{i}.png"
            mss_path = out / f"screen{index}_mss_{i}.png"

            ref = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
            if ref.isNull():
                errors.append(f"screen {index} rect {i}: qt ref failed")
                continue
            ref.save(str(ref_path), "PNG")

            if not _capture_region_to_path(screen, rect, str(cur_path)):
                errors.append(f"screen {index} rect {i}: current capture failed")
                continue

            _mss_capture_to_path(screen, rect, str(mss_path))

            with Image.open(ref_path) as ref_img, Image.open(cur_path) as cur_img:
                ref_size = (ref_img.width, ref_img.height)
                cur_size = (cur_img.width, cur_img.height)
                diff = _max_diff(ref_img, cur_img)
                print(
                    f"  rect {i} {rect.width()}x{rect.height()} "
                    f"ref={ref_size} cur={cur_size} max_diff={diff} "
                    f"region={_physical_region(screen, rect)}"
                )
                if diff > 8:
                    errors.append(
                        f"screen {index} rect {i}: position/content mismatch max_diff={diff}"
                    )

            if mss_path.exists():
                with Image.open(ref_path) as ref_img, Image.open(mss_path) as mss_img:
                    mss_diff = _max_diff(ref_img, mss_img)
                    print(f"    mss diff vs ref: {mss_diff}")
                    if index == 0 and mss_diff > 8:
                        print("    ^ primary mss position mismatch (expected)")

    if errors:
        print("POSITION TEST FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("POSITION TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
