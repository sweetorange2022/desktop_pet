"""微信 UI 自动化发送消息模块。

通过 pyautogui + pyperclip 模拟操作微信桌面版发送消息。
使用 Win32 API 查找微信窗口（按类名查找，更可靠），
若找不到则尝试从任务栏点击打开。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import os
import re
import time
from typing import Optional

import pyautogui
import pyperclip

logger = logging.getLogger(__name__)

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_wechat_debug.log")
user32 = ctypes.windll.user32

# 微信窗口类名（新旧版本）
_WECHAT_CLASSES = [
    "WeChatMainWndForPC",   # 旧版微信
    "WeixinMainWndForPC",   # 新版微信
    "Qt51514QWindowIcon",   # 新版微信（Qt 框架）
]

def _log(msg: str) -> None:
    logger.info(msg)
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            f.flush()
    except Exception:
        pass

def _get_foreground_title() -> str:
    try:
        fg = user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(fg, buf, 256)
        return buf.value
    except Exception:
        return ""

def _sanitize_message(text: str) -> str:
    text = re.sub(r'[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF\u200d\ufe0f]', '', text)
    text = text.replace('\n', ' | ')
    return text.strip()

def _find_wechat_by_class() -> Optional[int]:
    """按窗口类名查找微信窗口（最可靠的方式）。"""
    for cls_name in _WECHAT_CLASSES:
        hwnd = user32.FindWindowW(cls_name, None)
        if hwnd and user32.IsWindowVisible(hwnd):
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title, 256)
            _log(f"按类名找到微信: hwnd={hwnd}, 类名={cls_name}, 标题=[{title.value}]")
            return hwnd
    return None

def _find_wechat_by_title() -> Optional[int]:
    """按窗口标题查找微信窗口（备用方案）。"""
    hwnd = user32.FindWindowW(None, "\u5fae\u4fe1")  # FindWindowW(None, "微信")
    if hwnd and user32.IsWindowVisible(hwnd):
        _log(f"按标题找到微信: hwnd={hwnd}")
        return hwnd
    return None

def _click_taskbar_wechat() -> Optional[int]:
    """从任务栏点击微信图标打开窗口。

    使用 pyautogui.locateOnScreen 在任务栏区域查找微信图标，
    若找不到则尝试用 Win+D 显示桌面后再查找。
    """
    _log("尝试从任务栏点击微信图标...")

    # 获取屏幕尺寸
    screen_w, screen_h = pyautogui.size()

    # 任务栏高度约 40px，搜索整个底部区域
    # 微信图标通常在任务栏的固定位置
    # 尝试用 Win 键打开开始菜单搜索
    _log("使用 Win+S 搜索微信...")
    pyautogui.hotkey("win", "s")
    time.sleep(1.0)

    # 输入"微信"
    pyperclip.copy("\u5fae\u4fe1")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(1.5)

    # Enter 打开第一个结果
    pyautogui.press("enter")
    time.sleep(2.0)

    # 检查是否找到微信窗口
    hwnd = _find_wechat_by_class() or _find_wechat_by_title()
    if hwnd:
        _log("通过任务栏搜索成功打开微信")
        return hwnd

    _log("任务栏搜索未能打开微信")
    return None

def _find_wechat() -> Optional[int]:
    """查找微信窗口，多种方式尝试。"""
    # 方式1: 按类名查找（最可靠）
    hwnd = _find_wechat_by_class()
    if hwnd:
        return hwnd

    # 方式2: 按标题查找
    hwnd = _find_wechat_by_title()
    if hwnd:
        return hwnd

    # 方式3: 从任务栏搜索打开
    return _click_taskbar_wechat()

def _force_foreground(hwnd: int) -> bool:
    """强制将窗口设为前台。"""
    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            time.sleep(0.5)
        user32.ShowWindow(hwnd, 5)  # SW_SHOW
        time.sleep(0.3)

        fg_tid = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
        target_tid = user32.GetWindowThreadProcessId(hwnd, None)
        user32.AttachThreadInput(fg_tid, target_tid, True)
        user32.keybd_event(0x12, 0, 0, 0)  # Alt down
        user32.keybd_event(0x12, 0, 2, 0)  # Alt up
        time.sleep(0.1)
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        user32.AttachThreadInput(fg_tid, target_tid, False)
        time.sleep(0.5)

        title = _get_foreground_title()
        _log(f"前台窗口: [{title}]")
        return True
    except Exception as e:
        _log(f"前台失败: {e}")
        return False

def _type_text(text: str) -> None:
    pyperclip.copy(text)
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)

def _get_foreground_hwnd() -> int:
    """获取当前前台窗口句柄。"""
    try:
        return user32.GetForegroundWindow()
    except Exception:
        return 0

def _minimize_window(hwnd: int) -> None:
    """最小化指定窗口。"""
    try:
        user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        time.sleep(0.3)
    except Exception as e:
        _log(f"最小化失败: {e}")

def _restore_foreground(hwnd: int) -> None:
    """恢复指定窗口到前台。"""
    try:
        if hwnd and hwnd != 0:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            time.sleep(0.2)
            user32.SetForegroundWindow(hwnd)
    except Exception as e:
        _log(f"恢复前台失败: {e}")

def send_wechat_message(target_name: str, message: str) -> bool:
    """发送消息给微信好友/群（后台模式，发送完自动恢复原窗口）。

    流程：
    1. 保存当前前台窗口
    2. 查找微信窗口（类名 → 标题 → 任务栏搜索）
    3. 激活微信窗口
    4. Ctrl+F 搜索 → Enter 选中 → 输入消息 → 发送
    5. 最小化微信窗口
    6. 恢复原前台窗口
    """
    message = _sanitize_message(message)
    _log(f"准备发送给 [{target_name}]: {message[:80]}...")

    # Step 0: 保存当前前台窗口
    original_hwnd = _get_foreground_hwnd()
    original_title = _get_foreground_title()
    _log(f"保存当前前台窗口: [{original_title}] hwnd={original_hwnd}")

    # Step 1: 找微信
    hwnd = _find_wechat()
    if hwnd is None:
        _log("错误: 找不到微信窗口")
        return False

    success = False
    try:
        # Step 2: 激活
        if not _force_foreground(hwnd):
            _log("警告: 前台可能不成功")

        time.sleep(0.3)

        # Step 3: Ctrl+F 搜索
        _log("Ctrl+F 搜索...")
        pyautogui.hotkey("ctrl", "f")
        time.sleep(1.0)

        title = _get_foreground_title()
        _log(f"Ctrl+F 后前台: [{title}]")

        # Step 4: 输入搜索名称
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.2)
        _log(f"输入: {target_name}")
        _type_text(target_name)
        time.sleep(2.0)

        # Step 5: Enter 选中
        _log("Enter 选中...")
        pyautogui.press("enter")
        time.sleep(1.5)

        # Step 6: 输入消息
        _log("输入消息...")
        _type_text(message)
        time.sleep(0.3)

        # Step 7: 发送
        _log("Enter 发送...")
        pyautogui.press("enter")
        time.sleep(0.5)

        success = True
        _log(f"发送成功 -> {target_name}")

    except Exception as e:
        _log(f"发送过程出错: {e}")
        success = False
    finally:
        # Step 8: 最小化微信，恢复原窗口
        _log("最小化微信窗口...")
        _minimize_window(hwnd)
        time.sleep(0.2)

        if original_hwnd and original_hwnd != hwnd:
            _log(f"恢复原前台窗口: [{original_title}]")
            _restore_foreground(original_hwnd)

    return success

def send_wechat_image(target_name: str, image_path: str) -> bool:
    """发送图片给微信好友/群（后台模式，发送完自动恢复原窗口）。

    流程与 send_wechat_message 一致，但发送图片而非文本：
    1. 保存当前前台窗口
    2. 查找微信窗口
    3. 激活微信窗口
    4. Ctrl+F 搜索 → Enter 选中
    5. 将图片复制到剪贴板 → Ctrl+V 粘贴
    6. Enter 发送
    7. 最小化微信窗口
    8. 恢复原前台窗口
    """
    import os as _os

    if not _os.path.isfile(image_path):
        _log(f"错误: 图片文件不存在 {image_path}")
        return False

    _log(f"准备发送图片给 [{target_name}]: {image_path}")

    # Step 0: 保存当前前台窗口
    original_hwnd = _get_foreground_hwnd()
    original_title = _get_foreground_title()
    _log(f"保存当前前台窗口: [{original_title}] hwnd={original_hwnd}")

    # Step 1: 找微信
    hwnd = _find_wechat()
    if hwnd is None:
        _log("错误: 找不到微信窗口")
        return False

    success = False
    try:
        # Step 2: 激活
        if not _force_foreground(hwnd):
            _log("警告: 前台可能不成功")

        time.sleep(0.3)

        # Step 3: Ctrl+F 搜索
        _log("Ctrl+F 搜索...")
        pyautogui.hotkey("ctrl", "f")
        time.sleep(1.0)

        title = _get_foreground_title()
        _log(f"Ctrl+F 后前台: [{title}]")

        # Step 4: 输入搜索名称
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.2)
        _log(f"输入: {target_name}")
        _type_text(target_name)
        time.sleep(2.0)

        # Step 5: Enter 选中
        _log("Enter 选中...")
        pyautogui.press("enter")
        time.sleep(1.5)

        # Step 6: 复制图片到剪贴板并 Ctrl+V 粘贴
        _log("复制图片到剪贴板...")
        _copy_image_to_clipboard(image_path)
        time.sleep(0.3)

        _log("Ctrl+V 粘贴图片...")
        pyautogui.hotkey("ctrl", "v")
        time.sleep(1.0)

        # Step 7: Enter 发送
        _log("Enter 发送...")
        pyautogui.press("enter")
        time.sleep(0.5)

        success = True
        _log(f"图片发送成功 -> {target_name}")

    except Exception as e:
        _log(f"发送图片过程出错: {e}")
        success = False
    finally:
        # Step 8: 最小化微信，恢复原窗口
        _log("最小化微信窗口...")
        _minimize_window(hwnd)
        time.sleep(0.2)

        if original_hwnd and original_hwnd != hwnd:
            _log(f"恢复原前台窗口: [{original_title}]")
            _restore_foreground(original_hwnd)

    return success

def _copy_image_to_clipboard(image_path: str) -> bool:
    """通过 PowerShell 将图片复制到系统剪贴板。"""
    import subprocess as _sp

    ps_script = (
        f'Add-Type -AssemblyName System.Windows.Forms; '
        f'$img = [System.Drawing.Image]::FromFile("{image_path}"); '
        f'[System.Windows.Forms.Clipboard]::SetImage($img); '
        f'$img.Dispose(); '
        f'Write-Output "OK"'
    )
    try:
        result = _sp.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        ok = result.returncode == 0 and result.stdout.strip() == "OK"
        _log(f"剪贴板复制图片: {'成功' if ok else '失败'}")
        return ok
    except Exception as e:
        _log(f"剪贴板复制异常: {e}")
        return False
