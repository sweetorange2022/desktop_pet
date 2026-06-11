"""生成桌面宠物所需的图片资源。运行一次后可删除此文件。"""

import os
import sys

# 确保 QApplication 在 QPainter 之前创建
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPainter, QColor, QPixmap
from PySide6.QtCore import Qt

app = QApplication(sys.argv)

os.makedirs("assets/generated", exist_ok=True)

def fill(p: QPainter, x: int, y: int, w: int, h: int, color: QColor) -> None:
    p.fillRect(x, y, w, h, color)

# === 生成 pet.png (120x120 像素猫) ===
size = 120
pm = QPixmap(size, size)
pm.fill(Qt.GlobalColor.transparent)

p = QPainter(pm)
p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

ORANGE = QColor(255, 165, 0)
DARK_ORANGE = QColor(200, 120, 0)
WHITE = QColor(255, 255, 255)
BLACK = QColor(0, 0, 0)
PINK = QColor(255, 150, 180)
LIGHT_ORANGE = QColor(255, 200, 120)

# 身体主体
fill(p, 30, 50, 60, 50, ORANGE)
fill(p, 25, 55, 70, 40, ORANGE)
fill(p, 35, 45, 50, 60, ORANGE)

# 肚子
fill(p, 40, 65, 40, 30, LIGHT_ORANGE)

# 头部
fill(p, 25, 20, 70, 50, ORANGE)
fill(p, 30, 15, 60, 55, ORANGE)
fill(p, 35, 10, 50, 60, ORANGE)

# 左耳
fill(p, 25, 10, 15, 20, ORANGE)
fill(p, 28, 5, 10, 15, ORANGE)
fill(p, 28, 10, 8, 12, PINK)

# 右耳
fill(p, 80, 10, 15, 20, ORANGE)
fill(p, 82, 5, 10, 15, ORANGE)
fill(p, 84, 10, 8, 12, PINK)

# 眼睛白色
fill(p, 38, 32, 14, 14, WHITE)
fill(p, 68, 32, 14, 14, WHITE)

# 瞳孔
fill(p, 42, 34, 8, 10, BLACK)
fill(p, 72, 34, 8, 10, BLACK)

# 高光
fill(p, 43, 35, 3, 3, WHITE)
fill(p, 73, 35, 3, 3, WHITE)

# 鼻子
fill(p, 56, 48, 8, 6, PINK)

# 嘴巴
fill(p, 52, 54, 4, 2, DARK_ORANGE)
fill(p, 64, 54, 4, 2, DARK_ORANGE)
fill(p, 54, 56, 12, 2, DARK_ORANGE)

# 胡须
fill(p, 20, 46, 18, 1, BLACK)
fill(p, 22, 50, 16, 1, BLACK)
fill(p, 82, 46, 18, 1, BLACK)
fill(p, 82, 50, 16, 1, BLACK)

# 前爪
fill(p, 32, 90, 18, 16, ORANGE)
fill(p, 70, 90, 18, 16, ORANGE)
fill(p, 32, 98, 18, 8, LIGHT_ORANGE)
fill(p, 70, 98, 18, 8, LIGHT_ORANGE)

# 尾巴
fill(p, 90, 60, 8, 30, ORANGE)
fill(p, 94, 55, 8, 10, ORANGE)
fill(p, 98, 50, 8, 8, DARK_ORANGE)

p.end()
pm.save("assets/generated/pet.png")
print("OK: assets/generated/pet.png")

# === 生成 tray.png (32x32 小猫头图标) ===
tray = QPixmap(32, 32)
tray.fill(Qt.GlobalColor.transparent)

p2 = QPainter(tray)
p2.setRenderHint(QPainter.RenderHint.Antialiasing, False)

fill(p2, 6, 8, 20, 18, ORANGE)
fill(p2, 8, 6, 16, 20, ORANGE)
fill(p2, 6, 4, 6, 8, ORANGE)
fill(p2, 20, 4, 6, 8, ORANGE)
fill(p2, 7, 5, 4, 5, PINK)
fill(p2, 21, 5, 4, 5, PINK)
fill(p2, 10, 12, 4, 4, WHITE)
fill(p2, 18, 12, 4, 4, WHITE)
fill(p2, 11, 13, 2, 3, BLACK)
fill(p2, 19, 13, 2, 3, BLACK)
fill(p2, 15, 18, 3, 2, PINK)

p2.end()
tray.save("assets/generated/tray.png")
print("OK: assets/generated/tray.png")
