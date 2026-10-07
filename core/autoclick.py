# -*- coding: utf-8 -*-
"""自动点击:一段剧情读完 → 停一下 → 帮玩家点一下游戏画面,进下一句。

安全第一(照搬旧版读器工具 core/autoclick.py 的思路):
**只有在目标点确实属于这个游戏的窗口时才点**,否则宁可不点,也绝不误点到别的窗口上。
(玩家切出去看网页/聊天时,程序不会乱点。)

这里自带窗口查找,不依赖旧项目的 gamewin.py。
"""
import ctypes
import re
import subprocess
import time
from ctypes import wintypes

USER32 = ctypes.WinDLL("user32", use_last_error=True)

# ---- Win32 声明(句柄都是指针宽度,必须写全 argtypes/restype,否则 64 位会溢出)----
USER32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
USER32.EnumWindows.restype = wintypes.BOOL
USER32.IsWindowVisible.argtypes = [wintypes.HWND]
USER32.IsWindowVisible.restype = wintypes.BOOL
USER32.IsIconic.argtypes = [wintypes.HWND]
USER32.IsIconic.restype = wintypes.BOOL
USER32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
USER32.GetWindowRect.restype = wintypes.BOOL
USER32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
USER32.GetWindowThreadProcessId.restype = wintypes.DWORD
USER32.WindowFromPoint.argtypes = [wintypes.POINT]
USER32.WindowFromPoint.restype = wintypes.HWND
USER32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
USER32.GetAncestor.restype = wintypes.HWND
USER32.GetForegroundWindow.restype = wintypes.HWND
USER32.GetSystemMetrics.argtypes = [ctypes.c_int]
USER32.GetSystemMetrics.restype = ctypes.c_int
USER32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
USER32.SetCursorPos.restype = wintypes.BOOL
USER32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
USER32.GetCursorPos.restype = wintypes.BOOL
USER32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
USER32.SendInput.restype = wintypes.UINT

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
INPUT_MOUSE = 0
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
GA_ROOT = 2


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("mi", _MOUSEINPUT)]


def _send(flags: int, x: int = 0, y: int = 0) -> None:
    """发一个鼠标事件。x/y 是 0~65535 的归一化绝对坐标。"""
    inp = _INPUT()
    inp.type = INPUT_MOUSE
    inp.mi = _MOUSEINPUT(x, y, 0, flags, 0, None)
    USER32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


# ---------------------------------------------------------------- 找游戏窗口
def pids_for_exe(exe_name: str) -> set:
    """按进程名(如 anados.exe)拿 PID 集合。"""
    exe_name = (exe_name or "").strip()
    if not exe_name:
        return set()
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + exe_name, "/NH", "/FO", "CSV"],
                             capture_output=True, timeout=10,
                             creationflags=0x08000000).stdout.decode("utf-8", "replace")
    except Exception:
        return set()
    pids = set()
    for line in out.splitlines():
        parts = [p.strip().strip('"') for p in line.split('","')]
        for p in parts:
            if re.fullmatch(r"\d+", p or ""):
                pids.add(int(p))
                break
    return pids


def find_game_window(exe_name: str):
    """找这个游戏进程的主窗口(可见、面积最大的那个)。返回 dict 或 None。"""
    pids = pids_for_exe(exe_name)
    if not pids:
        return None
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        pid = wintypes.DWORD()
        USER32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in pids or not USER32.IsWindowVisible(hwnd):
            return True
        if USER32.IsIconic(hwnd):          # 最小化的窗口坐标是 (-32000,-32000),不能点
            return True
        r = wintypes.RECT()
        if not USER32.GetWindowRect(hwnd, ctypes.byref(r)):
            return True
        w, h = r.right - r.left, r.bottom - r.top
        if w > 200 and h > 150:
            found.append((w * h, int(hwnd), r.left, r.top, w, h))
        return True

    USER32.EnumWindows(cb, 0)
    if not found:
        return None
    _, hwnd, left, top, w, h = max(found)
    return {"hwnd": hwnd, "left": left, "top": top, "width": w, "height": h,
            "center": (left + w // 2, top + h // 2)}


def _owner_pid_at(x: int, y: int) -> int:
    hwnd = USER32.WindowFromPoint(wintypes.POINT(int(x), int(y)))
    if not hwnd:
        return 0
    pid = wintypes.DWORD()
    USER32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def _root_of(x: int, y: int) -> int:
    """目标点上那个窗口的最顶层父窗口(Unity 游戏常见子窗口)。"""
    hwnd = USER32.WindowFromPoint(wintypes.POINT(int(x), int(y)))
    if not hwnd:
        return 0
    return int(USER32.GetAncestor(hwnd, GA_ROOT) or hwnd)


def click(x: int, y: int) -> bool:
    """在屏幕坐标 (x, y) 点一下左键。

    位置用 SetCursorPos 精确设置 —— 实测归一化绝对坐标在这台机器上会偏
    ((600,500) 点成了 (611,447)),SetCursorPos 一点不差。
    按键用 SendInput 注入(先补一个零位移 MOVE,让读"原始输入"的游戏也能看到这次输入)。
    """
    try:
        USER32.SetCursorPos(int(x), int(y))
        time.sleep(0.06)
        _send(MOUSEEVENTF_MOVE)              # dx=dy=0:产生移动事件但不移动位置
        time.sleep(0.03)
        _send(MOUSEEVENTF_LEFTDOWN)
        time.sleep(0.05)
        _send(MOUSEEVENTF_LEFTUP)
        return True
    except Exception:
        return False


def window_point(win: dict, where: str = "center") -> tuple:
    """按设置算"点哪儿":center 窗口中央 / low 下方文字框一带 / bottom 底部中央。"""
    left, top, w, h = win["left"], win["top"], win["width"], win["height"]
    where = (where or "center").lower()
    if where == "low":
        return left + w // 2, top + int(h * 0.78)
    if where == "bottom":
        return left + w // 2, top + int(h * 0.92)
    return left + w // 2, top + h // 2


def click_for_game(exe_name: str, where: str = "center") -> tuple:
    """在游戏窗口里点一下。返回 (是否点了, 说明文字)。

    目标点上的窗口必须是**这个游戏的进程**,否则不点 —— 防止玩家切出去做别的事时被误点。
    """
    win = find_game_window(exe_name)
    if not win:
        return False, "没找到游戏窗口(游戏可能没开)"
    x, y = window_point(win, where)
    pids = pids_for_exe(exe_name)
    owner = _owner_pid_at(x, y)
    same_hwnd = _root_of(x, y) == int(win["hwnd"])
    if owner not in pids and not same_hwnd:
        return False, "游戏窗口现在不在最前面(你切到别的窗口了),这次不点"
    if not click(x, y):
        return False, "点击失败"
    return True, f"已在游戏画面点了下一句 ({x}, {y})"
