"""脚本：将桌面宠物打包为独立 exe。

用法：cd desktop_pet && python build.py
输出：desktop_pet/dist/HorseSmallNine.exe
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
MAIN = ROOT / "main.py"
ASSETS = ROOT / "assets"
ICON = ASSETS / "ico" / "cat.ico"
DIST = ROOT / "dist"

# hidden-import: weather_image 在 weather_dialog.on_send() 中被动态导入，
# PyInstaller 静态分析无法自动检测到
HIDDEN_IMPORTS = [
    "src.ui.weather_image",
    "mss",
    "mss.tools",
    "PIL.ImageGrab",
    "src.services.screen_recorder",
    "imageio",
    "imageio.plugins.ffmpeg",
]

cmd = [
    sys.executable,
    "-m", "PyInstaller",
    "--noconfirm",
    "--onefile",
    "--windowed",
    "--name", "HorseSmallNine",
    "--icon", str(ICON),
    "--add-data", f"{ASSETS};assets",
    "--add-data", f"{ROOT / 'config'};config",
    "--add-data", f"{ROOT / 'src'};src",
    "--add-data", f"{ROOT / 'schedule.json'};.",
    "--version-file", str(ROOT / "docs" / "version_info.txt"),
    "--distpath", str(DIST),
    "--workpath", str(ROOT / "build"),
    "--specpath", str(ROOT),
]

for mod in HIDDEN_IMPORTS:
    cmd.append("--hidden-import")
    cmd.append(mod)

cmd.append(str(MAIN))

print("运行截图自检...")
test = subprocess.run(
    [sys.executable, str(ROOT / "tests" / "test_screenshot.py")],
    cwd=str(ROOT),
    env={**os.environ, "PYTHONPATH": str(ROOT)},
)
if test.returncode != 0:
    print("")
    print("截图自检失败，已中止打包。")
    sys.exit(1)

print("运行录屏区域自检...")
rec_test = subprocess.run(
    [sys.executable, str(ROOT / "tests" / "test_recording_region.py")],
    cwd=str(ROOT),
    env={**os.environ, "PYTHONPATH": str(ROOT)},
)
if rec_test.returncode != 0:
    print("")
    print("录屏区域自检失败，已中止打包。")
    sys.exit(1)

print("打包中...")
cmd_str = " ".join(str(c) for c in cmd)
print(f"命令: {cmd_str}")
print()
result = subprocess.run(cmd, cwd=str(ROOT))
if result.returncode == 0:
    exe_path = DIST / "HorseSmallNine.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / 1024 / 1024
        print("")
        print(f"打包成功！")
        print(f"输出: {exe_path}")
        print(f"大小: {size_mb:.1f} MB")
    else:
        print("")
        print("打包完成，但未找到预期输出文件: {0}".format(exe_path))
        print("请检查 dist/ 目录下的实际输出文件名。")
else:
    print("")
    print(f"打包失败，退出码：{result.returncode}")
    sys.exit(1)
