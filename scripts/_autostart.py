"""
开机自启管理模块

提供三个函数，操作 HKCU Run 注册表项，无需管理员权限：

    enable()      → 写入注册表，开启自启
    disable()     → 删除注册表项，关闭自启
    is_enabled()  → 检查当前是否已开启自启

用法：
    from _autostart import enable, disable, is_enabled

    enable()              # 开启
    disable()             # 关闭
    if is_enabled(): ...  # 检查
"""

import sys
import winreg

_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_DEFAULT_NAME = "DeskPet"


def _open_key(mode: int = winreg.KEY_ALL_ACCESS):
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY_PATH, 0, mode)


def enable(name: str | None = None) -> None:
    """开启开机自启。name 为注册表中的值名称，默认 DeskPet。"""
    value_name = name or _DEFAULT_NAME
    exe_path = sys.executable
    try:
        key = _open_key(winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
    except OSError:
        pass


def disable(name: str | None = None) -> None:
    """关闭开机自启。name 须与 enable 时一致。"""
    value_name = name or _DEFAULT_NAME
    try:
        key = _open_key(winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, value_name)
        winreg.CloseKey(key)
    except FileNotFoundError:
        pass  # 本来就没开，无需处理
    except OSError:
        pass


def is_enabled(name: str | None = None) -> bool:
    """检查当前是否已开启开机自启（值存在且路径匹配当前可执行文件）。"""
    value_name = name or _DEFAULT_NAME
    exe_path = sys.executable
    try:
        key = _open_key(winreg.KEY_READ)
        stored_value, _ = winreg.QueryValueEx(key, value_name)
        winreg.CloseKey(key)
        return bool(stored_value == exe_path)
    except FileNotFoundError:
        return False
    except OSError:
        return False
