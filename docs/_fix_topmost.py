# -*- coding: utf-8 -*-
"""修「窗口置顶失效」。

根因:窗口宿主注册的类名是 LingYueReaderWindow(改名 Lyra 时只改了显示名,
      类名没动),而后端 _native_hwnd() 只找 "LyraWindow" → FindWindow 返回 0
      → SetWindowPos 根本没被调用,置顶看起来"坏了"。

修法(三级兜底,以后改类名也不会再坏):
  ① 按已知类名列表找;
  ② 找不到就枚举"进程名是 Lyra.exe / 聆阅.exe"的顶层可见窗口,取面积最大的那个;
  ③ 再不行就退化为"按窗口标题包含 Lyra"找。
"""
import io
import subprocess

SRV = r"D:\Unity阅读器\webapp\server.py"
t = io.open(SRV, encoding="utf-8").read()

old = '''def _native_hwnd():
    """运行器的原生窗口句柄(找不到就返回 0)。"""
    try:
        import ctypes
        return int(ctypes.windll.user32.FindWindowW("LyraWindow", None) or 0)
    except Exception:
        return 0'''

new = '''# 窗口宿主注册过的类名(改名 Lyra 时类名仍是老的 —— 两个都留着,以后改名也不会坏)
_WINDOW_CLASSES = ("LyraWindow", "LingYueReaderWindow", "聆阅Window")
# 宿主进程名(按进程找窗口时的依据)
_HOST_EXES = ("lyra.exe", "聆阅.exe", "lingyuereader.exe")


def _hwnd_by_process() -> int:
    """枚举顶层可见窗口,挑出属于窗口宿主进程、面积最大的那个。"""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    k = ctypes.windll.kernel32
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    best = [0, 0]                      # [面积, hwnd]

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if not u.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = k.OpenProcess(0x1000, False, pid.value)      # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return True
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if not k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return True
            name = buf.value.rsplit("\\\\", 1)[-1].lower()
            if name not in _HOST_EXES:
                return True
            r = wintypes.RECT()
            u.GetWindowRect(hwnd, ctypes.byref(r))
            area = (r.right - r.left) * (r.bottom - r.top)
            if area > best[0]:
                best[0], best[1] = area, int(hwnd)
        finally:
            k.CloseHandle(h)
        return True

    u.EnumWindows(cb, 0)
    return best[1]


def _native_hwnd():
    """运行器的原生窗口句柄(找不到就返回 0)。"""
    try:
        import ctypes
        u = ctypes.windll.user32
        for cls in _WINDOW_CLASSES:                      # ① 按类名
            h = int(u.FindWindowW(cls, None) or 0)
            if h:
                return h
        h = _hwnd_by_process()                           # ② 按宿主进程
        if h:
            return h
        h = int(u.FindWindowW(None, "Lyra") or 0)        # ③ 按标题
        return h
    except Exception:
        return 0'''

assert old in t, "没找到 _native_hwnd"
t = t.replace(old, new, 1)
io.open(SRV, "w", encoding="utf-8", newline="\n").write(t)
print("已修 _native_hwnd:类名列表 + 按宿主进程 + 按标题 三级兜底")
r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % SRV],
                   capture_output=True, text=True)
print("语法:", "通过" if r.returncode == 0 else r.stderr[:200])
