"""录屏区域抓帧自检（双屏）。"""

from __future__ import annotations

import sys
import time

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from src.ui.pet_window import _physical_region, _is_primary_screen


def _test_grab(screen, rect: QRect) -> dict:
    region = _physical_region(screen, rect)
    result = {"region": region, "mss": None, "pil": None, "qt": None}
    if region is None:
        return result

    try:
        import mss

        with mss.mss() as sct:
            shot = sct.grab(region)
        result["mss"] = {
            "size": shot.size,
            "max": max(shot.rgb) if shot.rgb else 0,
            "len": len(shot.rgb),
        }
    except Exception as exc:
        result["mss"] = {"error": str(exc)}

    try:
        from PIL import ImageGrab

        bbox = (
            region["left"],
            region["top"],
            region["left"] + region["width"],
            region["top"] + region["height"],
        )
        img = ImageGrab.grab(bbox=bbox, all_screens=True)
        result["pil"] = {"size": img.size, "max": max(img.convert("L").getdata())}
    except Exception as exc:
        result["pil"] = {"error": str(exc)}

    try:
        pix = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
        img = pix.toImage()
        result["qt"] = {"size": (pix.width(), pix.height()), "null": pix.isNull()}
    except Exception as exc:
        result["qt"] = {"error": str(exc)}

    return result


def main() -> int:
    app = QApplication(sys.argv)
    rect = QRect(200, 200, 480, 360)
    errors: list[str] = []

    for i, screen in enumerate(app.screens()):
        geo = screen.geometry()
        print(
            f"screen {i}: {screen.name()} primary={_is_primary_screen(screen)} "
            f"geo=({geo.x()},{geo.y()},{geo.width()}x{geo.height()}) dpr={screen.devicePixelRatio()}"
        )
        r = _test_grab(screen, rect)
        print(f"  region={r['region']}")
        print(f"  mss={r['mss']}")
        print(f"  pil={r['pil']}")
        print(f"  qt={r['qt']}")

        mss = r.get("mss") or {}
        if mss.get("error") or (mss.get("max", 0) < 2):
            errors.append(f"screen {i}: mss grab failed {mss}")
        region = r["region"]
        if region and mss.get("size"):
            ew, eh = region["width"], region["height"]
            aw, ah = mss["size"]
            if (aw, ah) != (ew, eh):
                errors.append(f"screen {i}: mss size mismatch got={aw}x{ah} expected={ew}x{eh}")

    if errors:
        print("RECORD REGION TEST FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("RECORD REGION TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
