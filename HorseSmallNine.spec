# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['g:\\desktop_pet\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('g:\\desktop_pet\\assets', 'assets'), ('g:\\desktop_pet\\config', 'config'), ('g:\\desktop_pet\\src', 'src'), ('g:\\desktop_pet\\schedule.json', '.')],
    hiddenimports=['src.ui.weather_image', 'mss', 'mss.tools', 'PIL.ImageGrab', 'src.services.screen_recorder', 'imageio', 'imageio.plugins.ffmpeg'],
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
    version='g:\\desktop_pet\\docs\\version_info.txt',
    icon=['g:\\desktop_pet\\assets\\ico\\cat.ico'],
)
