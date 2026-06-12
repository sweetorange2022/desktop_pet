"""脚本：将桌面宠物打包为独立 exe。

用法：cd desktop_pet && python build.py
      cd desktop_pet && python build.py --name HsnLite
      cd desktop_pet && python build.py --skip-tests
输出：desktop_pet/release/<name>.exe
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description="打包桌面宠物为独立 exe")
parser.add_argument("--name", default="HorseSmallNine", help="输出文件名（不含 .exe）")
parser.add_argument("--skip-tests", action="store_true", help="跳过截图/录屏自检")
args = parser.parse_args()

ROOT = Path(__file__).parent
MAIN = ROOT / "main.py"
ASSETS = ROOT / "assets"
ICON = ASSETS / "ico" / "cat.ico"
DIST = ROOT / "release"
EXE_NAME = args.name

# hidden-import: 根据精简版需求裁剪
# 精简版不需要：mss（截图）、imageio/ffmpeg（视频）、psutil（系统监控）、PIL.ImageGrab
HIDDEN_IMPORTS = [
    "src.ui.weather_image",
    "src.ui.work_hours_dialog",
]

cmd = [
    sys.executable,
    "-m", "PyInstaller",
    "--noconfirm",
    "--onefile",
    "--windowed",
    "--name", EXE_NAME,
    "--icon", str(ICON),
    "--add-data", f"{ASSETS};assets",
    "--add-data", f"{ROOT / 'config'};config",
    "--exclude-module", "mss",
    "--exclude-module", "psutil",
    "--exclude-module", "imageio",
    "--exclude-module", "imageio_ffmpeg",
    "--exclude-module", "numpy",
    "--add-data", f"{ROOT / 'src'};src",
    "--add-data", f"{ROOT / 'schedule.json'};.",
    "--version-file", str(ROOT / "docs" / "version_info.txt"),
    "--distpath", str(DIST),
    "--workpath", str(ROOT / "build"),
    "--specpath", str(ROOT),
]

# 精简版排除视频文件
if EXE_NAME.lower() in ("hsnlite", "lite"):
    import shutil
    video_dir = ASSETS / "videos"
    backup_dir = ROOT / "_videos_backup"
    if video_dir.exists():
        shutil.move(str(video_dir), str(backup_dir))
        print(f"临时移除 {video_dir} 以减小体积")

for mod in HIDDEN_IMPORTS:
    cmd.append("--hidden-import")
    cmd.append(mod)

cmd.append(str(MAIN))

if not args.skip_tests:
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

_video_backup = ROOT / "_videos_backup"
try:
    result = subprocess.run(cmd, cwd=str(ROOT))
finally:
    # 恢复 videos 目录
    if _video_backup.exists():
        import shutil
        shutil.move(str(_video_backup), str(ASSETS / "videos"))
        print("已恢复 assets/videos 目录")

if result.returncode == 0:
    exe_path = DIST / f"{EXE_NAME}.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / 1024 / 1024
        print("")
        print(f"打包成功！")
        print(f"输出: {exe_path}")
        print(f"大小: {size_mb:.1f} MB")
    else:
        print("")
        print("打包完成，但未找到预期输出文件: {0}".format(exe_path))
        print("请检查 release/ 目录下的实际输出文件名。")
else:
    print("")
    print(f"打包失败，退出码：{result.returncode}")
    sys.exit(1)
