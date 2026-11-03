# -*- coding: utf-8 -*-
"""按 PID 给窗口截图(绕开 _shot.py 里按进程名找窗口时的 GBK 解码坑)。

用法: python docs/_shot_pid.py <pid> <输出.png>
"""
import ctypes
import sys
from ctypes import wintypes

sys.path.insert(0, r"D:\Unity阅读器\docs")
import _shot  # noqa: E402

user32 = _shot.user32


def windows_of(pid):
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            w, h = r.right - r.left, r.bottom - r.top
            if w > 150 and h > 150:
                found.append((w * h, hwnd))
        return True

    user32.EnumWindows(cb, 0)
    return [h for _, h in sorted(found, reverse=True)]


if __name__ == "__main__":
    pid, out = int(sys.argv[1]), sys.argv[2]
    hs = windows_of(pid)
    if not hs:
        print("NO WINDOW for pid", pid)
        sys.exit(2)
    _shot.shot(hs[0], out)
