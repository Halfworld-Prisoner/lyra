# -*- coding: utf-8 -*-
"""把 Lyra 主窗口恢复到正常大小并居中(160x28 那种"一条缝"状态下玩家等于什么都点不到)。"""
import ctypes
from ctypes import wintypes

u = ctypes.windll.user32
h = u.FindWindowW("LingYueReaderWindow", None)
if not h:
    h = u.FindWindowW("LyraWindow", None)
print("  窗口句柄 =", h)
if h:
    r = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r))
    print("  当前: %sx%s @ (%s,%s)" % (r.right - r.left, r.bottom - r.top, r.left, r.top))
    sw, sh = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    w, hh = 1180, 820
    x, y = max(0, (sw - w) // 2), max(0, (sh - hh) // 2)
    u.SetWindowPos(h, 0, x, y, w, hh, 0x0004 | 0x0010)      # SWP_NOZORDER | SWP_NOACTIVATE
    u.ShowWindow(h, 9)                                      # SW_RESTORE
    r2 = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r2))
    print("  恢复后: %sx%s @ (%s,%s)" % (r2.right - r2.left, r2.bottom - r2.top, r2.left, r2.top))
    print("  可见 =", bool(u.IsWindowVisible(h)))
