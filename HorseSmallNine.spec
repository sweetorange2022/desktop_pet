# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['G:\\Pet_Git\\desktop_pet\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('G:\\Pet_Git\\desktop_pet\\assets', 'assets'), ('G:\\Pet_Git\\desktop_pet\\config', 'config'), ('G:\\Pet_Git\\desktop_pet\\src', 'src'), ('G:\\Pet_Git\\desktop_pet\\schedule.json', '.')],
    hiddenimports=['src.ui.weather_image', 'src.ui.work_hours_dialog', 'mss', 'mss.tools', 'PIL.ImageGrab', 'src.services.screen_recorder', 'imageio', 'imageio.plugins.ffmpeg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='HorseSmallNine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='G:\\Pet_Git\\desktop_pet\\docs\\version_info.txt',
    icon=['G:\\Pet_Git\\desktop_pet\\assets\\ico\\cat.ico'],
)
