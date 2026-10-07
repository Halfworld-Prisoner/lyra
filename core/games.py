# -*- coding: utf-8 -*-
"""游戏库:自动发现已安装的游戏(Steam 库 / 桌面快捷方式)+ 从 exe 提取图标。

- Steam:读注册表 SteamPath → steamapps/libraryfolders.vdf 拿到所有库 →
  逐个 appmanifest_*.acf 取 name/installdir → 在 steamapps/common/<目录> 里挑主程序 exe
- 桌面:%USERPROFILE%\\Desktop 与 %PUBLIC%\\Desktop 的 .lnk → 解析真实目标 exe
- 图标:ExtractIconEx + DrawIconEx 画进 32 位 DIB,转 PNG data URL(带缓存,界面直接 <img src>)
- 玩家自己加的游戏存在 config.json 的 games 里
"""
import base64
import ctypes
import io
import os
import re
import sys
from ctypes import wintypes
from pathlib import Path

# 明显不是游戏主程序的 exe
_SKIP_TOKENS = (
    "unins", "uninstall", "setup", "install", "vcredist", "vc_redist", "dxsetup", "directx",
    "dotnet", "crashpad", "crashreport", "crashhandler", "handler", "report", "update",
    "updater", "easyanticheat", "eac_", "battleye", "beservice", "steamerrorreporter",
    "unitycrashhandler", "touchup", "helper", "server", "editor",
)
_SELF_NAMES = ("lyra", "聆阅", "gametextreader", "安装程序", "installer")


# ---------------------------------------------------------------- exe 挑选
def _is_candidate(exe: Path) -> bool:
    name = exe.name.lower()
    if not name.endswith(".exe"):
        return False
    if any(t in name for t in _SKIP_TOKENS):
        return False
    if any(t in name for t in _SELF_NAMES):
        return False
    try:
        if exe.stat().st_size < 200 * 1024:      # 太小的多半是启动器/工具
            return False
    except OSError:
        return False
    return True


def _find_main_exe(folder: Path, hint: str = "") -> str | None:
    """在一个游戏目录里挑最像"主程序"的 exe:名字像的优先,其次体积最大的。"""
    if not folder.is_dir():
        return None
    exes = []
    for root, dirs, files in os.walk(folder):
        depth = len(Path(root).relative_to(folder).parts)
        if depth >= 3:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d.lower() not in
                   ("redist", "redistributable", "_commonredist", "directx", "dotnet", "support", "tools")]
        for f in files:
            p = Path(root) / f
            if _is_candidate(p):
                exes.append(p)
    if not exes:
        return None
    hint_tokens = [t for t in re.split(r"[^0-9a-zA-Z\u4e00-\u9fff]+", hint.lower()) if len(t) > 2]

    def score(p: Path):
        name = p.stem.lower()
        s = hint_tokens and sum(1 for t in hint_tokens if t in name) * 1000 or 0
        if name == folder.name.lower():
            s += 500
        if "shipping" in name or "win64" in name:
            s += 50
        try:
            s += min(400, p.stat().st_size // (2 * 1024 * 1024))
        except OSError:
            pass
        return s

    return str(max(exes, key=score))


# ---------------------------------------------------------------- Steam
def _steam_root() -> Path | None:
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    val = winreg.QueryValueEx(k, "SteamPath")[0]
            except OSError:
                continue
            p = Path(str(val).replace("/", "\\"))
            if p.is_dir():
                return p
    except Exception:
        pass
    return None


def _steam_libraries(root: Path) -> list:
    libs = [root]
    vdf = root / "steamapps" / "libraryfolders.vdf"
    try:
        text = vdf.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return libs
    paths = re.findall(r'"path"\s+"([^"]+)"', text)
    if not paths:                                  # 旧版格式:"1"  "D:\\SteamLib"
        paths = re.findall(r'^\s*"\d+"\s+"([^"]+)"', text, re.M)
    for raw in paths:
        p = Path(raw.replace("\\\\", "\\").replace("/", "\\"))
        if p.is_dir() and p not in libs:
            libs.append(p)
    return libs


def steam_games() -> list:
    root = _steam_root()
    if not root:
        return []
    out = []
    for lib in _steam_libraries(root):
        common = lib / "steamapps" / "common"
        for acf in (lib / "steamapps").glob("appmanifest_*.acf"):
            try:
                text = acf.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            name = (re.search(r'"name"\s+"([^"]*)"', text) or [None, ""])[1]
            installdir = (re.search(r'"installdir"\s+"([^"]*)"', text) or [None, ""])[1]
            appid = (re.search(r'"appid"\s+"(\d+)"', text) or [None, ""])[1]
            if not installdir:
                continue
            exe = _find_main_exe(common / installdir, hint=name or installdir)
            if not exe:
                continue
            out.append({
                "id": "steam:" + (appid or installdir),
                "name": name or installdir,
                "path": exe,
                "source": "steam",
                "source_label": "Steam",
            })
    out.sort(key=lambda g: g["name"].lower())
    return out


# ---------------------------------------------------------------- 桌面快捷方式
def _desktop_dirs() -> list:
    dirs = []
    for env in ("USERPROFILE", "PUBLIC"):
        base = os.environ.get(env)
        if not base:
            continue
        for sub in ("Desktop", "桌面"):
            d = Path(base) / sub
            if d.is_dir() and d not in dirs:
                dirs.append(d)
    return dirs


def _resolve_lnk(lnk: Path) -> str | None:
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        target = shell.CreateShortCut(str(lnk)).TargetPath
        return target or None
    except Exception:
        return None


def desktop_games() -> list:
    out, seen = [], set()
    for d in _desktop_dirs():
        for lnk in sorted(d.glob("*.lnk")):
            target = _resolve_lnk(lnk)
            if not target or not target.lower().endswith(".exe"):
                continue
            p = Path(target)
            if not p.is_file():
                continue
            low = str(p).lower()
            if "\\windows\\" in low or any(t in p.name.lower() for t in _SKIP_TOKENS + _SELF_NAMES):
                continue
            if low in seen:
                continue
            seen.add(low)
            out.append({
                "id": "lnk:" + str(lnk),
                "name": lnk.stem,
                "path": str(p),
                "source": "desktop",
                "source_label": "桌面",
            })
    out.sort(key=lambda g: g["name"].lower())
    return out


# ---------------------------------------------------------------- 图标提取
_icon_cache: dict = {}
_protos_done = False


def _protos_gdi() -> None:
    """64 位下 GDI/USER 句柄必须声明成指针,否则会被截断成 32 位。"""
    global _protos_done
    if _protos_done:
        return
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = ctypes.c_void_p
    user32.DrawIconEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                                 ctypes.c_int, ctypes.c_int, wintypes.UINT,
                                 ctypes.c_void_p, wintypes.UINT]
    user32.DrawIconEx.restype = wintypes.BOOL
    user32.DestroyIcon.argtypes = [ctypes.c_void_p]
    user32.ReleaseDC.argtypes = [wintypes.HWND, ctypes.c_void_p]
    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.CreateDIBSection.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
                                       ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
                                       wintypes.DWORD]
    gdi32.CreateDIBSection.restype = ctypes.c_void_p
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.SelectObject.restype = ctypes.c_void_p
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
    _protos_done = True


class _BMIH(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def _extract_hicon(exe: str, size: int):
    """取一个指定尺寸的 HICON:优先 PrivateExtractIcons(能拿到高分辨率),
    失败再退 ExtractIconEx(只有 32/48)。"""
    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32
    try:
        user32.PrivateExtractIconsW.argtypes = [wintypes.LPCWSTR, ctypes.c_int, ctypes.c_int,
                                                ctypes.c_int, ctypes.POINTER(ctypes.c_void_p),
                                                ctypes.POINTER(wintypes.UINT), wintypes.UINT,
                                                wintypes.UINT]
        user32.PrivateExtractIconsW.restype = wintypes.UINT
        for want in (size, 256, 128, 64, 48):
            hicon = ctypes.c_void_p()
            got = user32.PrivateExtractIconsW(str(exe), 0, want, want, ctypes.byref(hicon), None, 1, 0)
            if got and hicon.value:
                return hicon.value, want
    except Exception:
        pass
    # 兜底:老 API(只有 32/48,会比较糊)
    shell32.ExtractIconExW.argtypes = [wintypes.LPCWSTR, ctypes.c_int,
                                       ctypes.POINTER(ctypes.c_void_p),
                                       ctypes.POINTER(ctypes.c_void_p), wintypes.UINT]
    shell32.ExtractIconExW.restype = wintypes.UINT
    large = (ctypes.c_void_p * 1)()
    small = (ctypes.c_void_p * 1)()
    cnt = shell32.ExtractIconExW(str(exe), 0, large, small, 1)
    if cnt > 0:
        if large[0]:
            return large[0], 48
        if small[0]:
            return small[0], 32
    return None, 0


def icon_data_url(exe: str, size: int = 128) -> str:
    """取 exe 的图标 → PNG data URL;取不到返回空串。"""
    key = f"{exe}|{size}"
    if key in _icon_cache:
        return _icon_cache[key]
    url = ""
    try:
        from PIL import Image
        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
        _protos_gdi()
        hicon, real = _extract_hicon(exe, size)
        if hicon:
            # 用取到的真实尺寸画,避免被放大成马赛克
            px = max(16, min(256, real or size))
            screen = user32.GetDC(None)
            hdc = gdi32.CreateCompatibleDC(screen)
            bmi = _BMIH()
            bmi.biSize = ctypes.sizeof(_BMIH)
            bmi.biWidth = px
            bmi.biHeight = -px
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0
            bits = ctypes.c_void_p()
            hbmp = gdi32.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
            if hbmp and bits.value:
                old = gdi32.SelectObject(hdc, hbmp)
                ctypes.memset(bits, 0, px * px * 4)
                user32.DrawIconEx(hdc, 0, 0, hicon, px, px, 0, None, 3)      # DI_NORMAL
                raw = ctypes.string_at(bits, px * px * 4)
                img = Image.frombuffer("RGBA", (px, px), raw, "raw", "BGRA", 0, 1).copy()
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
                gdi32.SelectObject(hdc, old)
                gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(hdc)
            user32.ReleaseDC(None, screen)
            user32.DestroyIcon(ctypes.c_void_p(hicon))
        if url:
            _icon_cache[key] = url
    except Exception:
        url = ""
    return url


def attach_icons(games: list, size: int = 128) -> list:
    for g in games:
        g["icon"] = icon_data_url(g.get("path", ""), size)
    return games


# ---------------------------------------------------------------- 对外接口
def discover(limit: int = 60) -> dict:
    """扫描一遍(结果给"添加游戏"对话框挑选用)。"""
    steam, desk = [], []
    try:
        steam = steam_games()
    except Exception:
        steam = []
    try:
        desk = desktop_games()
    except Exception:
        desk = []
    return {
        "steam": attach_icons(steam[:limit]),
        "desktop": attach_icons(desk[:limit]),
    }


def normalize(item: dict) -> dict | None:
    """把外部传入的一条游戏整理成配置里保存的格式。"""
    path = str(item.get("path", "")).strip()
    if not path or not Path(path).is_file():
        return None
    name = str(item.get("name", "")).strip() or Path(path).stem
    return {
        "id": str(item.get("id") or ("user:" + path.lower())),
        "name": name,
        "path": path,
        "source": str(item.get("source") or "user"),
        "source_label": str(item.get("source_label") or "手动添加"),
    }
