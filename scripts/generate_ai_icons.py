"""生成主流 AI 厂商像素风格 .ico 图标，并同步输出 160x160 PNG 预览图。

输出目录：
  assets/ico/ai/ico/  — .ico 多尺寸图标
  assets/ico/ai/png/  — 160x160 PNG 预览图
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ICO_DIR = ROOT / "assets" / "ico" / "ai" / "ico"
PNG_DIR = ROOT / "assets" / "ico" / "ai" / "png"
ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64)]
PNG_SIZE = 160


def _c(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


class PixelIcon:
    """32x32 像素画布，用 NEAREST 缩放生成多尺寸 ICO。"""

    def __init__(self, size: int = 32, bg: tuple[int, int, int, int] = (0, 0, 0, 0)) -> None:
        self.size = size
        self.bg = bg
        self._px: dict[tuple[int, int], tuple[int, int, int, int]] = {}

    def set(self, x: int, y: int, color: tuple[int, int, int, int]) -> None:
        if 0 <= x < self.size and 0 <= y < self.size:
            self._px[(x, y)] = color

    def rect(self, x: int, y: int, w: int, h: int, color: tuple[int, int, int, int]) -> None:
        for dy in range(h):
            for dx in range(w):
                self.set(x + dx, y + dy, color)

    def blit_grid(self, x0: int, y0: int, rows: list[str], palette: dict[str, tuple[int, int, int, int]]) -> None:
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch in palette:
                    self.set(x0 + x, y0 + y, palette[ch])

    def to_image(self) -> Image.Image:
        img = Image.new("RGBA", (self.size, self.size), self.bg)
        px = img.load()
        for (x, y), color in self._px.items():
            px[x, y] = color
        return img

    def save_ico(self, path: Path) -> None:
        base = self.to_image()
        frames = [base.resize(size, Image.Resampling.NEAREST) for size in ICO_SIZES]
        frames[0].save(path, format="ICO", sizes=ICO_SIZES)

    def save_png(self, path: Path, size: int = PNG_SIZE) -> None:
        """放大为指定尺寸 PNG，便于预览（保持像素块清晰）。"""
        img = self.to_image().resize((size, size), Image.Resampling.NEAREST)
        img.save(path, format="PNG")


def _openai() -> PixelIcon:
    g, k, w = _c("#10A37F"), _c("#0D8A6A"), _c("#FFFFFF")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.blit_grid(
        8, 8,
        [
            "..GGGG..",
            ".GWWWWG.",
            "GWGGGGWG",
            "GWG..GWG",
            "GWG..GWG",
            "GWGGGGWG",
            ".GWWWWG.",
            "..GGGG..",
        ],
        {"G": g, "W": w, ".": (0, 0, 0, 0), "K": k},
    )
    icon.rect(14, 14, 4, 4, k)
    return icon


def _gemini() -> PixelIcon:
    b, r, y, gr = _c("#4285F4"), _c("#EA4335"), _c("#FBBC05"), _c("#34A853")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.blit_grid(
        10, 6,
        [
            "...B...",
            "..BRB..",
            ".BRYRB.",
            "BRYGRYB",
            ".BRYRB.",
            "..BRB..",
            "...B...",
        ],
        {"B": b, "R": r, "Y": y, "G": gr, ".": (0, 0, 0, 0)},
    )
    icon.blit_grid(
        10, 18,
        [
            "...G...",
            "..GRG..",
            ".GRBRG.",
            "GRBYRG.",
            ".GRBRG.",
            "..GRG..",
            "...G...",
        ],
        {"B": b, "R": r, "Y": y, "G": gr, ".": (0, 0, 0, 0)},
    )
    return icon


def _claude() -> PixelIcon:
    o, w, d = _c("#D97757"), _c("#FFFFFF"), _c("#B85C3C")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.rect(6, 6, 20, 20, o)
    icon.rect(8, 8, 16, 16, d)
    icon.blit_grid(
        11, 10,
        [
            "WW...WW",
            "W.....W",
            "W.....W",
            "W.....W",
            "W.WW.WW",
            "W..WW.W",
            "WW...WW",
        ],
        {"W": w, ".": (0, 0, 0, 0)},
    )
    return icon


def _copilot() -> PixelIcon:
    blue, c1, c2, c3, c4 = _c("#0078D4"), _c("#00BCF2"), _c("#7FBA00"), _c("#FFB900"), _c("#F25022")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.rect(4, 4, 24, 24, blue)
    icon.blit_grid(
        8, 10,
        [
            "....C1....",
            "...C1C2...",
            "..C1C2C3..",
            ".C1C2C3C4.",
            "..C2C3C4..",
            "...C3C4...",
            "....C4....",
        ],
        {"C1": c1, "C2": c2, "C3": c3, "C4": c4, ".": (0, 0, 0, 0)},
    )
    return icon


def _meta_llama() -> PixelIcon:
    b, w = _c("#0081FB"), _c("#FFFFFF")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.blit_grid(
        6, 10,
        [
            "BB....BB",
            "BWW..WWB",
            "BWW..WWB",
            "BB....BB",
            "..BBBB..",
            ".B....B.",
            "B......B",
            ".B....B.",
        ],
        {"B": b, "W": w, ".": (0, 0, 0, 0)},
    )
    return icon


def _deepseek() -> PixelIcon:
    b, l, w = _c("#4D6BFE"), _c("#7B93FF"), _c("#FFFFFF")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.blit_grid(
        5, 12,
        [
            "....LLLL....",
            "...LLLLLL...",
            "..LLLLLLLL..",
            ".LLLLLLLLLL.",
            "LLLLLLLLLLLL",
            ".LLLLWWLLLL.",
            "..LLLWWLLL..",
            "...LWWLLL...",
        ],
        {"L": l, "W": w, "B": b, ".": (0, 0, 0, 0)},
    )
    icon.blit_grid(
        12, 8,
        [
            "..BB..",
            ".BBBB.",
            "BBBBBB",
            ".BBBB.",
            "..BB..",
        ],
        {"L": l, "W": w, "B": b, ".": (0, 0, 0, 0)},
    )
    return icon


def _baidu_ernie() -> PixelIcon:
    b, w, r = _c("#2932E1"), _c("#FFFFFF"), _c("#FF2741")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.rect(6, 6, 20, 20, b)
    icon.blit_grid(
        10, 10,
        [
            "W...W",
            "WW.WW",
            ".WWW.",
            "WW.WW",
            "W...W",
        ],
        {"W": w, "R": r, ".": (0, 0, 0, 0)},
    )
    icon.set(15, 22, r)
    icon.set(16, 22, r)
    icon.set(15, 23, r)
    icon.set(16, 23, r)
    return icon


def _qwen() -> PixelIcon:
    p, w, o = _c("#615CED"), _c("#FFFFFF"), _c("#FF6A00")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.rect(5, 5, 22, 22, p)
    icon.blit_grid(
        10, 9,
        [
            "WWWW...",
            "W..W...",
            "W..W...",
            "W..WWW.",
            "W....W.",
            "W....W.",
            "WWWWW..",
        ],
        {"W": w, "O": o, ".": (0, 0, 0, 0)},
    )
    icon.set(22, 22, o)
    icon.set(23, 22, o)
    icon.set(22, 23, o)
    icon.set(23, 23, o)
    return icon


def _doubao() -> PixelIcon:
    t, w, d = _c("#00D4AA"), _c("#FFFFFF"), _c("#00A888")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.blit_grid(
        8, 8,
        [
            "..TTTT..",
            ".TTTTTT.",
            "TTWWWWTT",
            "TTWWWWTT",
            "TTWWWWTT",
            "TTTTTTTT",
            ".TTTTTT.",
            "..TTTT..",
        ],
        {"T": t, "W": w, "D": d, ".": (0, 0, 0, 0)},
    )
    return icon


def _hunyuan() -> PixelIcon:
    b, c = _c("#0052D9"), _c("#4DA3FF")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.rect(6, 6, 20, 20, b)
    icon.blit_grid(
        10, 10,
        [
            "..CCCC..",
            ".CC..CC.",
            "CC....CC",
            "CC....CC",
            "CC....CC",
            ".CC..CC.",
            "..CCCC..",
            "...CC...",
        ],
        {"C": c, ".": (0, 0, 0, 0)},
    )
    return icon


def _zhipu_glm() -> PixelIcon:
    b, w = _c("#1E6FFF"), _c("#FFFFFF")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.rect(5, 5, 22, 22, b)
    icon.blit_grid(
        10, 10,
        [
            "WW...WW",
            "WW...WW",
            "WW...WW",
            "WWWWWWW",
            "WW...WW",
            "WW...WW",
            "WW...WW",
        ],
        {"W": w, ".": (0, 0, 0, 0)},
    )
    return icon


def _kimi() -> PixelIcon:
    bg, m, w = _c("#1A1A1A"), _c("#FFFFFF"), _c("#888888")
    icon = PixelIcon(bg=bg)
    icon.blit_grid(
        8, 8,
        [
            "..MMMM..",
            ".MMMMMM.",
            "MMWWWWMM",
            "MMWWWWMM",
            "MMWWWWMM",
            "MMWWWWMM",
            ".MMMMMM.",
            "..MMMM..",
        ],
        {"M": m, "W": w, ".": (0, 0, 0, 0)},
    )
    return icon


def _iflytek_spark() -> PixelIcon:
    r, o, y = _c("#E8453C"), _c("#FF6B35"), _c("#FFD166")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.blit_grid(
        14, 6,
        [
            "..Y..",
            ".YOY.",
            "YOROY",
            ".YOY.",
            "..Y..",
        ],
        {"R": r, "O": o, "Y": y, ".": (0, 0, 0, 0)},
    )
    icon.blit_grid(
        10, 14,
        [
            "...R...",
            "..ROO..",
            ".ROOOO.",
            "ROOOOOO",
            ".ROOOO.",
            "..ROO..",
            "...R...",
        ],
        {"R": r, "O": o, "Y": y, ".": (0, 0, 0, 0)},
    )
    return icon


def _huawei_pangu() -> PixelIcon:
    r, w, p = _c("#CF0A2C"), _c("#FFFFFF"), _c("#FF4D6A")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.blit_grid(
        10, 8,
        [
            "..RR..",
            ".RwwR.",
            "RwwwwR",
            ".RwwR.",
            "..RR..",
        ],
        {"R": r, "w": w, "P": p, ".": (0, 0, 0, 0)},
    )
    icon.blit_grid(
        8, 16,
        [
            "...PP...",
            "..PPPP..",
            ".PPPPPP.",
            "PPPPPPPP",
            ".PPPPPP.",
            "..PPPP..",
            "...PP...",
        ],
        {"R": r, "w": w, "P": p, ".": (0, 0, 0, 0)},
    )
    return icon


def _mistral() -> PixelIcon:
    o, y, w = _c("#FF7000"), _c("#FFB347"), _c("#FFFFFF")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.blit_grid(
        6, 6,
        [
            "OO....OO",
            "OOO..OOO",
            "OOOOOOOO",
            "OOYYYYOO",
            "OOYYYYOO",
            "OOOOOOOO",
            "OOO..OOO",
            "OO....OO",
        ],
        {"O": o, "Y": y, "W": w, ".": (0, 0, 0, 0)},
    )
    icon.rect(14, 14, 4, 4, w)
    return icon


def _perplexity() -> PixelIcon:
    t, w = _c("#20B2AA"), _c("#FFFFFF")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.blit_grid(
        8, 8,
        [
            "..TTTT..",
            ".T....T.",
            "T..WW..T",
            "T.WWWWW.T",
            "T.WWWWW.T",
            "T..WW..T",
            ".T....T.",
            "..TTTT..",
        ],
        {"T": t, "W": w, ".": (0, 0, 0, 0)},
    )
    return icon


def _grok() -> PixelIcon:
    bg, w = _c("#000000"), _c("#FFFFFF")
    icon = PixelIcon(bg=bg)
    icon.blit_grid(
        8, 8,
        [
            "W....W",
            ".W..W.",
            "..WW..",
            "...W..",
            "..WW..",
            ".W..W.",
            "W....W",
            "W....W",
        ],
        {"W": w, ".": (0, 0, 0, 0)},
    )
    return icon


def _minimax() -> PixelIcon:
    p, l, w = _c("#7B61FF"), _c("#B8A4FF"), _c("#FFFFFF")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.rect(5, 5, 22, 22, p)
    icon.blit_grid(
        8, 12,
        [
            "L.L.L.L.",
            ".L.L.L.L",
            "L.L.L.L.",
            ".L.L.L.L",
            "L.L.L.L.",
        ],
        {"L": l, "W": w, ".": (0, 0, 0, 0)},
    )
    return icon


def _yi_01() -> PixelIcon:
    g, w, d = _c("#00C896"), _c("#FFFFFF"), _c("#009E78")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.rect(5, 5, 22, 22, g)
    icon.blit_grid(
        9, 10,
        [
            "WW..WW",
            "WW..WW",
            "WW..WW",
            "WW..WW",
            "WW..WW",
            "..WW..",
            "...WW.",
        ],
        {"W": w, "D": d, ".": (0, 0, 0, 0)},
    )
    icon.blit_grid(
        18, 10,
        [
            "..WW",
            ".WWW",
            "W.WW",
            "W.WW",
            ".WWW",
            "..WW",
            "...W",
        ],
        {"W": w, "D": d, ".": (0, 0, 0, 0)},
    )
    return icon


def _cohere() -> PixelIcon:
    p, w, l = _c("#39594D"), _c("#FFFFFF"), _c("#6B9080")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.blit_grid(
        8, 8,
        [
            "..PP..",
            ".P..P.",
            "P....P",
            "P....P",
            "P....P",
            ".P..P.",
            "..PP..",
            ".PLLP.",
        ],
        {"P": p, "W": w, "L": l, ".": (0, 0, 0, 0)},
    )
    icon.rect(14, 14, 4, 4, w)
    return icon


def _stability() -> PixelIcon:
    p, l, w = _c("#7E22CE"), _c("#A855F7"), _c("#FFFFFF")
    icon = PixelIcon(bg=(0, 0, 0, 0))
    icon.blit_grid(
        10, 6,
        [
            "..PP..",
            ".PLLP.",
            "PLLLLP",
            "PLLLLP",
            ".PLLP.",
            "..PP..",
        ],
        {"P": p, "L": l, "W": w, ".": (0, 0, 0, 0)},
    )
    icon.blit_grid(
        10, 18,
        [
            "..LL..",
            ".LWWL.",
            "LWWWWL",
            "LWWWWL",
            ".LWWL.",
            "..LL..",
        ],
        {"P": p, "L": l, "W": w, ".": (0, 0, 0, 0)},
    )
    return icon


VENDORS: list[tuple[str, str, callable]] = [
    ("openai", "OpenAI / ChatGPT", _openai),
    ("gemini", "Google Gemini", _gemini),
    ("claude", "Anthropic Claude", _claude),
    ("copilot", "Microsoft Copilot", _copilot),
    ("meta_llama", "Meta Llama", _meta_llama),
    ("deepseek", "DeepSeek", _deepseek),
    ("baidu_ernie", "百度文心", _baidu_ernie),
    ("qwen", "阿里通义千问", _qwen),
    ("doubao", "字节豆包", _doubao),
    ("hunyuan", "腾讯混元", _hunyuan),
    ("zhipu_glm", "智谱 GLM", _zhipu_glm),
    ("kimi", "月之暗面 Kimi", _kimi),
    ("iflytek_spark", "讯飞星火", _iflytek_spark),
    ("huawei_pangu", "华为盘古", _huawei_pangu),
    ("mistral", "Mistral AI", _mistral),
    ("perplexity", "Perplexity", _perplexity),
    ("grok", "xAI Grok", _grok),
    ("minimax", "MiniMax", _minimax),
    ("yi_01", "零一万物 01.AI", _yi_01),
    ("cohere", "Cohere", _cohere),
    ("stability", "Stability AI", _stability),
]


def main() -> int:
    ICO_DIR.mkdir(parents=True, exist_ok=True)
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"ICO 输出: {ICO_DIR}")
    print(f"PNG 输出: {PNG_DIR}")
    for slug, label, factory in VENDORS:
        icon = factory()
        ico_path = ICO_DIR / f"{slug}.ico"
        png_path = PNG_DIR / f"{slug}.png"
        icon.save_ico(ico_path)
        icon.save_png(png_path)
        print(f"  OK  {slug}  ({label})")
    print(f"\n共生成 {len(VENDORS)} 组图标（ico/ + png/ 各 {len(VENDORS)} 个）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
