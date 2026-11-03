# -*- coding: utf-8 -*-
"""查:窗口到底建了没 + 应用日志尾部 + WebView2 数据目录。"""
import ctypes
import os
from ctypes import wintypes

u = ctypes.windll.user32
u.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
u.GetWindowTextW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
rows = []


@ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def cb(h, _):
    cn = ctypes.create_unicode_buffer(128); u.GetClassNameW(h, cn, 128)
    if any(k in cn.value for k in ("Lyra", "LingYue", "WebView", "Chrome")):
        tt = ctypes.create_unicode_buffer(256); u.GetWindowTextW(h, tt, 256)
        pid = wintypes.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        r = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r))
        rows.append((cn.value, tt.value, pid.value, bool(u.IsWindowVisible(h)), r.right - r.left, r.bottom - r.top))
    return True


u.EnumWindows(cb, 0)
print("窗口:")
for cn, tt, pid, vis, w, h in rows:
    print("  类=%-26s 标题=%-12s PID=%-6s 可见=%-5s %sx%s" % (cn, tt, pid, vis, w, h))
print("  共 %d 个" % len(rows))

print("\n进程:")
os.system('tasklist /FI "IMAGENAME eq Lyra.exe" /FO CSV /NH')

print("\n日志尾部:")
for p in (r"D:\Lyra\app\install.log", r"D:\Lyra\install.log", r"D:\Lyra\app\_聆阅_日志.txt"):
    if os.path.isfile(p):
        print("  " + p)
        try:
            for line in open(p, encoding="utf-8", errors="ignore").read().splitlines()[-8:]:
                print("    " + line[:150])
        except Exception as e:
            print("    读不了:", e)

print("\n目录:")
for d in (r"D:\Lyra",):
    for x in sorted(os.listdir(d)):
        print("  ", x)
for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("TEMP", "")):
    if not base or not os.path.isdir(base):
        continue
    for x in sorted(os.listdir(base)):
        if "Lyra" in x or "LingYue" in x:
            print("  ", os.path.join(base, x))
