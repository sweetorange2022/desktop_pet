"""天气卡片文字渲染为图片。

将 _build_card() 生成的天气文字渲染为美观的天气卡片图片，
用于发送到微信（以图片替代纯文本）。
"""

from __future__ import annotations

import io
import os
import subprocess
import tempfile
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# 字体路径（Windows）
# ---------------------------------------------------------------------------
_FONT_DIR = r"C:\Windows\Fonts"
_FONT_ZH = os.path.join(_FONT_DIR, "msyh.ttc")        # 微软雅黑（正文）
_FONT_BOLD = os.path.join(_FONT_DIR, "msyhbd.ttc")    # 微软雅黑粗体（标题）
_FONT_EMOJI = os.path.join(_FONT_DIR, "seguiemj.ttf") # Segoe UI Emoji
_FONT_MONO = os.path.join(_FONT_DIR, "consola.ttf")   # 等宽（数值）

# ---------------------------------------------------------------------------
# 色彩方案
# ---------------------------------------------------------------------------
_BG_COLOR = (22, 22, 42)          # 深蓝紫背景
_CARD_BG = (30, 30, 55)           # 卡片底色
_BORDER_COLOR = (60, 60, 90)      # 卡片边框
_TITLE_COLOR = (255, 200, 100)    # 标题金色
_TEXT_COLOR = (210, 210, 230)     # 正文浅灰白
_LABEL_COLOR = (140, 170, 255)    # 字段标签蓝色
_SEP_COLOR = (60, 60, 90)         # 分隔线
_FOOTER_COLOR = (120, 120, 150)   # 底部署名

# 边距与间距
_MARGIN = 40
_PADDING = 30
_LINE_SPACING = 12
_SECTION_GAP = 8

def _load_font(size: int, bold: bool = False, emoji: bool = False) -> ImageFont.FreeTypeFont:
    """按需加载字体，带后备方案。"""
    if emoji:
        path = _FONT_EMOJI
    elif bold:
        path = _FONT_BOLD
    else:
        path = _FONT_ZH

    try:
        return ImageFont.truetype(path, size)
    except (OSError, IOError):
        # 后备字体
        fallbacks = [
            _FONT_ZH,
            os.path.join(_FONT_DIR, "SIMHEI.TTF"),
            os.path.join(_FONT_DIR, "simsun.ttc"),
        ]
        for fb in fallbacks:
            try:
                return ImageFont.truetype(fb, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()

def render_weather_card(text: str, output_path: str) -> str:
    """将天气卡片文字渲染为图片。

    Args:
        text: 由 _build_card() 生成的天气文字（含 emoji）
        output_path: 输出 PNG 图片路径

    Returns:
        output_path（成功时）

    Raises:
        IOError: 图片写入失败
    """
    lines = text.split("\n")

    # ------------------------------------------------------------------
    # 1. 计算文字尺寸
    # ------------------------------------------------------------------
    font_body = _load_font(16)
    font_title = _load_font(22, bold=True)
    font_footer = _load_font(13)
    font_label = _load_font(15)
    font_emoji = _load_font(18, emoji=True)

    line_heights: list[int] = []
    line_widths: list[int] = []
    total_h = _PADDING * 2

    for line in lines:
        # 标题行（【...】）
        if line.startswith("【"):
            f = font_title
            lh = 32
        elif line.startswith("---"):
            f = font_footer
            lh = 20
        elif not line.strip():
            lh = 12  # 空行
            f = font_body
        else:
            f = font_body
            lh = 24

        # 近似宽度：中文字符约 1.2 倍 emoji 宽度，这里简化为取最大
        # 用 font.getbbox 或 font.getlength
        try:
            lw = int(f.getlength(line))
        except Exception:
            lw = len(line) * 12

        # 加上 emoji 的额外宽度（emoji 比中文字略宽）
        emoji_count = sum(1 for c in line if ord(c) > 0x2000)
        lw += emoji_count * 4

        line_widths.append(lw)
        line_heights.append(lh)
        total_h += lh

    total_h += _LINE_SPACING * (len(lines) - 1)

    # 图片宽度：内容最宽 + 边距
    max_w = max(line_widths) if line_widths else 400
    img_w = max(max_w + _MARGIN * 2, 340)
    # 限制最大宽度
    img_w = min(img_w, 600)
    img_h = max(total_h + _PADDING * 2, 200)

    # ------------------------------------------------------------------
    # 2. 创建画布
    # ------------------------------------------------------------------
    canvas = Image.new("RGBA", (img_w, img_h), _BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    # 绘制卡片背景（圆角矩形，略小于画布）
    card_x, card_y = _MARGIN // 2, _MARGIN // 2
    card_w = img_w - _MARGIN
    card_h = img_h - _MARGIN
    _draw_rounded_rect(draw, card_x, card_y, card_w, card_h, radius=16, fill=_CARD_BG, outline=_BORDER_COLOR)

    # ------------------------------------------------------------------
    # 3. 逐行渲染
    # ------------------------------------------------------------------
    x = _MARGIN
    y = _MARGIN

    for i, line in enumerate(lines):
        if not line.strip():
            y += 10
            continue

        if line.startswith("【"):
            # 标题 — 居中，金色
            f = font_title
            try:
                tw = int(f.getlength(line))
            except Exception:
                tw = len(line) * 14
            tx = img_w - tw - _MARGIN // 2
            draw.text((tx, y), line, fill=_TITLE_COLOR, font=f, embedded_color=True)
            y += 32 + _SECTION_GAP

        elif line.startswith("---"):
            # 底部署名 — 右对齐，灰色
            f = font_footer
            try:
                tw = int(f.getlength(line))
            except Exception:
                tw = len(line) * 9
            tx = img_w - tw - _MARGIN // 2
            draw.text((tx, y), line, fill=_FOOTER_COLOR, font=f, embedded_color=True)
            y += 20

        else:
            # 数据行 — 左对齐
            f_body = font_body
            f_emoji = font_emoji

            # 分离 emoji 和文字逐段渲染
            _render_mixed_text(draw, x + 10, y, line, f_emoji, f_body, _TEXT_COLOR, _LABEL_COLOR)
            y += 24 + _LINE_SPACING

    # ------------------------------------------------------------------
    # 4. 保存
    # ------------------------------------------------------------------
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    canvas = canvas.convert("RGB")  # 去掉 alpha 通道，兼容性更好
    canvas.save(output_path, "PNG")
    return output_path

def _render_mixed_text(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    text: str,
    font_emoji: ImageFont.FreeTypeFont,
    font_body: ImageFont.FreeTypeFont,
    color_text: tuple[int, int, int],
    color_label: tuple[int, int, int],
) -> None:
    """逐字符渲染文本，emoji 用 emoji 字体，其他用正文。"""
    cx = x
    # 检查是否有冒号分隔（字段标签）
    colon_idx = text.find("：")
    if colon_idx > 0 and colon_idx < 10:
        # 有字段标签，标签用蓝色
        label = text[: colon_idx + 1]
        value = text[colon_idx + 1 :]
        # 渲染标签
        for ch in label:
            f = font_emoji if _is_emoji(ch) else font_body
            try:
                bw = int(f.getlength(ch))
            except Exception:
                bw = f.size
            draw.text((cx, y), ch, fill=color_label, font=f, embedded_color=True)
            cx += bw
        # 渲染值
        for ch in value:
            f = font_emoji if _is_emoji(ch) else font_body
            try:
                bw = int(f.getlength(ch))
            except Exception:
                bw = f.size
            draw.text((cx, y), ch, fill=color_text, font=f, embedded_color=True)
            cx += bw
    else:
        # 无字段标签，统一颜色
        for ch in text:
            f = font_emoji if _is_emoji(ch) else font_body
            try:
                bw = int(f.getlength(ch))
            except Exception:
                bw = f.size
            draw.text((cx, y), ch, fill=color_text, font=f, embedded_color=True)
            cx += bw

def _is_emoji(ch: str) -> bool:
    """判断字符是否为 emoji。"""
    cp = ord(ch)
    # 常见 emoji 范围
    if 0x1F300 <= cp <= 0x1F9FF:
        return True
    if 0x2600 <= cp <= 0x27BF:
        return True
    if 0xFE00 <= cp <= 0xFE0F:  # 异体选择器
        return True
    if cp == 0x200D:  # ZWJ
        return True
    return False

def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    x: int, y: int, w: int, h: int,
    radius: int = 12,
    fill: tuple[int, int, int] = (30, 30, 55),
    outline: tuple[int, int, int] = (60, 60, 90),
) -> None:
    """绘制圆角矩形。"""
    draw.rounded_rectangle(
        [x, y, x + w, y + h],
        radius=radius,
        fill=fill,
        outline=outline,
        width=1,
    )

def copy_image_to_clipboard(image_path: str) -> bool:
    """通过 PowerShell 将图片复制到系统剪贴板。

    使用 .NET 的 System.Windows.Forms.Clipboard.SetImage()，
    这是 Windows 上将图片放到剪贴板最可靠的方式。
    """
    if not os.path.isfile(image_path):
        return False

    # 转义路径（PowerShell 字符串中的反斜杠不需要额外转义）
    ps_script = (
        f'Add-Type -AssemblyName System.Windows.Forms; '
        f'$img = [System.Drawing.Image]::FromFile("{image_path}"); '
        f'[System.Windows.Forms.Clipboard]::SetImage($img); '
        f'$img.Dispose(); '
        f'Write-Output "OK"'
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and result.stdout.strip() == "OK"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
