# -*- coding: utf-8 -*-
"""悬浮窗(左上角常驻的运行信息条)。

两种形态:
  · **未展开(默认)**:左上角一个小胶囊 —— 状态点 + 状态文字,下面一行小字是
    「游戏名 · 已读 N」。最右边有个展开按钮。
  · **展开**:变成一个长方形信息卡 —— 状态、游戏、当前台词、指标,
    外加**关键开关按钮**:自动朗读 / 自动点击,以及 停止 / 读一下 / 主界面 / 隐藏。

固定在屏幕左上角(不可拖动,需求如此),点展开/收起按钮切换形态。

实现要点(都是踩过的坑,照抄旧项目验证过的做法):
- 建 Win32 **分层窗口**(WS_EX_LAYERED|TOPMOST|TOOLWINDOW|NOACTIVATE + WS_POPUP),
  PIL 渲染成 RGBA → 预乘 alpha → UpdateLayeredWindow,所以圆角是抗锯齿的。
- NOACTIVATE:点它不会把游戏切出去(玩游戏时最要紧)。
- 分层窗口创建后必须 ShowWindow(SW_SHOWNOACTIVATE),否则不显示。
- WNDPROC 参数要用 WPARAM/LPARAM(整数),用 c_void_p 时消息里为 0 会变 None。
- 改窗口尺寸必须回到窗口线程做(用自定义消息通知),否则不生效。
- 只有收到 WM_LBUTTONDOWN 才认 WM_LBUTTONUP,免得杂散消息误触发按钮。
- 面板/按钮都用**不透明**颜色:半透明会把游戏画面透出来,看着像按钮是透明的。
"""
import ctypes
import threading
import time
from ctypes import wintypes

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- Win32 常量
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
SWP_NOACTIVATE = 0x0010
HWND_TOPMOST = -1
SW_SHOWNOACTIVATE = 4

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_TIMER = 0x0113
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_MOUSELEAVE = 0x02A3
WM_APP_STATUS = 0x8001
WM_APP_QUIT = 0x8002
WM_APP_FORM = 0x8003
TME_LEAVE = 0x00000002
IDT_REFRESH = 1

FONT_CANDIDATES = (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc",
                   r"C:\Windows\Fonts\simhei.ttf")

# ================================================================ 配色
# 悬浮窗跟随「界面主题」:dark / light / sepia / md3 四套调色板。
#
# 几个约定:
#  · 全部颜色**不透明**(alpha=255)。半透明会让游戏画面透出来,看着像"按钮边缘是
#    透明的"(用户实测反馈),浅色主题下更明显。
#  · 键名与老常量一一对应;另外补了几个老代码里写死的颜色(CARD_EDGE / STATUS_TXT /
#    GAME_TXT / PLACEHOLDER / CELL_VAL / CHEVRON / SW_* / STOP_* / READ_* / BTN_LABEL)。
#  · PIL 每帧都是**现画**的(没有持久画刷),所以切换主题不需要重建任何东西:
#    窗口线程里 500ms 一次的 WM_TIMER 会重新取 data 并重画,下一帧自然就是新配色。
#  · 主体颜色对齐 webapp 的四套 CSS 主题;md3 那套取 Material 3 **dark 基线**
#    (surface-container #211F26 / on-surface #E6E0E9 / primary #D0BCFF /
#     on-primary #381E72 / outline-variant #49454F)。
#
# 暗色那套就是原来的常量,数值一字未改 —— 暗夜主题的观感保持原样。
_DARK = {
    "CARD": (30, 33, 44, 255),
    "CARD_EDGE": (74, 80, 98, 255),
    "INK": (236, 238, 245, 255),          # 主文字
    "DIM": (150, 156, 172, 255),          # 次要文字
    "DIM2": (130, 136, 152, 255),
    "LINE_STRONG": (74, 80, 98, 255),     # 卡片描边 / 控件描边
    "LINE_SOFT": (56, 61, 76, 255),       # 分隔线
    "BTN": (64, 69, 85, 255),             # 普通按钮
    "BTN_HOVER": (78, 84, 102, 255),
    "BTN_DOWN": (46, 50, 62, 255),
    "ACCENT": (113, 98, 255, 255),        # 主色(开着的开关)
    "ACCENT_DOWN": (92, 78, 226, 255),
    "ACCENT_HOVER": (126, 112, 255, 255),
    "CELL": (40, 44, 58, 255),            # 指标格底色
    "CELL_EDGE": (62, 68, 84, 255),
    "STATUS_TXT": (255, 255, 255, 255),   # 状态文字(胶囊/卡片顶栏)
    "GAME_TXT": (206, 212, 226, 255),     # 游戏名
    "PLACEHOLDER": (110, 116, 132, 255),  # 「还没有读到剧情」
    "CELL_VAL": (226, 232, 244, 255),     # 指标格右侧数值
    "CHEVRON": (226, 230, 240, 255),      # 胶囊上的展开箭头(常态)
    "CHEVRON_ON": (255, 255, 255, 255),   # 箭头画在主色底上时
    "ACCENT_INK": (255, 255, 255, 255),   # 「收起」按钮悬停(主色底)时的文字
    "BTN_LABEL": (245, 247, 252, 255),    # 操作按钮文字
    "SW_OFF": (54, 59, 73, 255),          # 关着的开关底色
    "SW_LABEL": (240, 242, 250, 255),     # 开关文字
    "SW_ST_ON": (255, 255, 255, 255),     # 开关「开」字
    "SW_ST_OFF": (178, 184, 200, 255),    # 开关「关」字
    "STOP": (150, 72, 84, 255),
    "STOP_HOVER": (170, 82, 96, 255),
    "STOP_DOWN": (128, 58, 70, 255),
    "STOP_EDGE": (110, 52, 62, 255),
    "STOP_TXT": (255, 255, 255, 255),
    "READ": (56, 110, 150, 255),
    "READ_HOVER": (64, 126, 170, 255),
    "READ_DOWN": (46, 94, 130, 255),
    "READ_EDGE": (44, 86, 118, 255),
    "READ_TXT": (255, 255, 255, 255),
}

# 明亮主题(对齐 webapp 的 light:#fff 面板 / #1a1f2b 文字 / #6d5efc 主色)
_LIGHT = {
    "CARD": (255, 255, 255, 255),
    "CARD_EDGE": (212, 213, 216, 255),
    "INK": (26, 31, 43, 255),
    "DIM": (93, 106, 128, 255),
    "DIM2": (139, 148, 166, 255),
    "LINE_STRONG": (183, 186, 190, 255),
    "LINE_SOFT": (231, 232, 234, 255),
    "BTN": (246, 247, 251, 255),
    "BTN_HOVER": (230, 231, 236, 255),
    "BTN_DOWN": (218, 220, 226, 255),
    "ACCENT": (109, 94, 252, 255),
    "ACCENT_HOVER": (121, 107, 252, 255),
    "ACCENT_DOWN": (98, 84, 232, 255),
    "CELL": (246, 247, 251, 255),
    "CELL_EDGE": (223, 225, 230, 255),
    "STATUS_TXT": (26, 31, 43, 255),      # 浅底 → 深字
    "GAME_TXT": (26, 31, 43, 255),
    "PLACEHOLDER": (139, 148, 166, 255),
    "CELL_VAL": (26, 31, 43, 255),
    "CHEVRON": (60, 68, 86, 255),
    "CHEVRON_ON": (255, 255, 255, 255),
    "ACCENT_INK": (255, 255, 255, 255),
    "BTN_LABEL": (26, 31, 43, 255),
    "SW_OFF": (240, 241, 245, 255),
    "SW_LABEL": (26, 31, 43, 255),
    "SW_ST_ON": (255, 255, 255, 255),
    "SW_ST_OFF": (93, 106, 128, 255),
    "STOP": (185, 40, 45, 255),
    "STOP_HOVER": (205, 54, 59, 255),
    "STOP_DOWN": (163, 32, 37, 255),
    "STOP_EDGE": (145, 26, 31, 255),
    "STOP_TXT": (255, 255, 255, 255),
    "READ": (30, 100, 190, 255),
    "READ_HOVER": (56, 124, 208, 255),
    "READ_DOWN": (24, 86, 166, 255),
    "READ_EDGE": (22, 76, 148, 255),
    "READ_TXT": (255, 255, 255, 255),
}

# 护眼主题(对齐 webapp 的 sepia:#fbf5e6 面板 / #3f3527 文字 / #9a6a2f 主色)
_SEPIA = {
    "CARD": (251, 245, 230, 255),
    "CARD_EDGE": (209, 200, 181, 255),
    "INK": (63, 53, 39, 255),
    "DIM": (111, 95, 71, 255),
    "DIM2": (141, 124, 98, 255),
    "LINE_STRONG": (196, 186, 165, 255),
    "LINE_SOFT": (225, 217, 200, 255),
    "BTN": (245, 236, 216, 255),
    "BTN_HOVER": (231, 221, 200, 255),
    "BTN_DOWN": (223, 213, 191, 255),
    "ACCENT": (154, 106, 47, 255),
    "ACCENT_HOVER": (172, 122, 59, 255),
    "ACCENT_DOWN": (133, 89, 37, 255),
    "CELL": (245, 236, 216, 255),
    "CELL_EDGE": (220, 209, 188, 255),
    "STATUS_TXT": (63, 53, 39, 255),
    "GAME_TXT": (63, 53, 39, 255),
    "PLACEHOLDER": (141, 124, 98, 255),
    "CELL_VAL": (63, 53, 39, 255),
    "CHEVRON": (78, 66, 48, 255),
    "CHEVRON_ON": (255, 255, 255, 255),
    "ACCENT_INK": (255, 255, 255, 255),
    "BTN_LABEL": (63, 53, 39, 255),
    "SW_OFF": (240, 231, 210, 255),
    "SW_LABEL": (63, 53, 39, 255),
    "SW_ST_ON": (255, 255, 255, 255),
    "SW_ST_OFF": (111, 95, 71, 255),
    "STOP": (181, 73, 63, 255),
    "STOP_HOVER": (198, 88, 77, 255),
    "STOP_DOWN": (154, 58, 50, 255),
    "STOP_EDGE": (134, 48, 41, 255),
    "STOP_TXT": (255, 255, 255, 255),
    "READ": (46, 106, 92, 255),
    "READ_HOVER": (58, 124, 107, 255),
    "READ_DOWN": (38, 90, 78, 255),
    "READ_EDGE": (33, 78, 68, 255),
    "READ_TXT": (255, 255, 255, 255),
}

# Material 3(官方 dark 基线)
_MD3 = {
    "CARD": (33, 31, 38, 255),            # surface-container #211F26
    "CARD_EDGE": (73, 69, 79, 255),       # outline-variant #49454F
    "INK": (230, 224, 233, 255),          # on-surface #E6E0E9
    "DIM": (202, 196, 208, 255),          # on-surface-variant #CAC4D0
    "DIM2": (147, 143, 153, 255),         # outline #938F99
    "LINE_STRONG": (147, 143, 153, 255),  # outline(控件描边)
    "LINE_SOFT": (73, 69, 79, 255),       # outline-variant(分隔线)
    "BTN": (54, 52, 59, 255),             # surface-container-highest #36343B
    "BTN_HOVER": (68, 66, 73, 255),       # +8% on-surface
    "BTN_DOWN": (75, 73, 80, 255),        # +12% on-surface
    "ACCENT": (208, 188, 255, 255),       # primary #D0BCFF
    "ACCENT_HOVER": (196, 175, 244, 255),  # +8% on-primary
    "ACCENT_DOWN": (190, 169, 238, 255),   # +12% on-primary
    "CELL": (43, 41, 48, 255),            # surface-container-high #2B2930
    "CELL_EDGE": (73, 69, 79, 255),       # outline-variant
    "STATUS_TXT": (230, 224, 233, 255),   # on-surface
    "GAME_TXT": (230, 224, 233, 255),
    "PLACEHOLDER": (147, 143, 153, 255),  # outline
    "CELL_VAL": (230, 224, 233, 255),
    "CHEVRON": (230, 224, 233, 255),      # on-surface(常态:箭头在 surface 色按钮上)
    "CHEVRON_ON": (56, 30, 114, 255),     # on-primary(悬停时按钮变主色)
    "ACCENT_INK": (56, 30, 114, 255),     # on-primary
    "BTN_LABEL": (230, 224, 233, 255),
    "SW_OFF": (54, 52, 59, 255),
    "SW_LABEL": (230, 224, 233, 255),
    "SW_ST_ON": (56, 30, 114, 255),       # on-primary #381E72
    "SW_ST_OFF": (202, 196, 208, 255),
    "STOP": (140, 29, 24, 255),           # error-container #8C1D18
    "STOP_HOVER": (149, 44, 40, 255),
    "STOP_DOWN": (153, 52, 47, 255),
    "STOP_EDGE": (110, 22, 18, 255),
    "STOP_TXT": (249, 222, 220, 255),     # on-error-container #F9DEDC
    "READ": (79, 55, 139, 255),           # primary-container #4F378B
    "READ_HOVER": (91, 68, 148, 255),
    "READ_DOWN": (98, 75, 153, 255),
    "READ_EDGE": (63, 44, 111, 255),
    "READ_TXT": (234, 221, 255, 255),     # on-primary-container #EADDFF
}

PALETTES = {"dark": _DARK, "light": _LIGHT, "sepia": _SEPIA, "md3": _MD3}

# 状态色:同一个状态在浅色底上必须用更深的颜色,否则(255,176,84)这类会在白底上糊掉。
# md3 用官方基线角色 + 官方扩展调色板的 tone 80(blue80 #A1C9FF / green80 #80DA88 …)。
STATE_ACCENTS = {
    "dark": {
        "reading": (74, 168, 255), "speaking": (61, 220, 151), "idle": (124, 108, 255),
        "paused": (150, 156, 172), "norun": (255, 176, 84), "nogame": (150, 156, 172),
        "hookoff": (255, 120, 120), "menu": (255, 176, 84),
    },
    "light": {
        "reading": (21, 101, 192), "speaking": (16, 130, 66), "idle": (96, 80, 235),
        "paused": (110, 118, 136), "norun": (194, 118, 10), "nogame": (110, 118, 136),
        "hookoff": (200, 52, 58), "menu": (194, 118, 10),
    },
    "sepia": {
        "reading": (40, 100, 160), "speaking": (47, 125, 79), "idle": (154, 106, 47),
        "paused": (111, 95, 71), "norun": (164, 105, 13), "nogame": (111, 95, 71),
        "hookoff": (181, 73, 63), "menu": (164, 105, 13),
    },
    "md3": {
        "reading": (161, 201, 255), "speaking": (128, 218, 136), "idle": (208, 188, 255),
        "paused": (147, 143, 153), "norun": (255, 182, 131), "nogame": (147, 143, 153),
        "hookoff": (242, 184, 181), "menu": (255, 182, 131),
    },
}

# 状态 → (文字, 暗色主色)  —— 「文字」四套主题共用;主色见 STATE_ACCENTS
STATES = {
    "reading":  ("读取文字中",   (74, 168, 255)),
    "speaking": ("朗读中",       (61, 220, 151)),
    "idle":     ("待机中",       (124, 108, 255)),
    "paused":   ("已暂停",       (150, 156, 172)),
    "norun":    ("游戏未运行",   (255, 176, 84)),
    "nogame":   ("未选游戏",     (150, 156, 172)),
    "hookoff":  ("阅读模块关",   (255, 120, 120)),
    "menu":     ("菜单中·暂停读", (255, 176, 84)),
}


def theme_of(data):
    """从 data 里取主题名(server.py 的 _float_sample 已经带过来)。"""
    t = (data or {}).get("theme") or "dark"
    t = str(t).strip().lower()
    return t if t in PALETTES else "dark"


def palette(theme):
    """按主题取一整套颜色;未知主题回落暗色。"""
    return PALETTES.get(str(theme or "").strip().lower(), _DARK)


def state_color(theme, state):
    """按主题取状态点颜色。"""
    tb = STATE_ACCENTS.get(str(theme or "").strip().lower(), STATE_ACCENTS["dark"])
    return tb.get(state, tb["idle"])


# 模块级常量 = 暗色那套(保持向后兼容:老代码/外部脚本 import INK、ACCENT… 仍可用)
INK = _DARK["INK"]
DIM = _DARK["DIM"]
DIM2 = _DARK["DIM2"]
LINE_STRONG = _DARK["LINE_STRONG"]
LINE_SOFT = _DARK["LINE_SOFT"]
BTN = _DARK["BTN"]
BTN_HOVER = _DARK["BTN_HOVER"]
BTN_DOWN = _DARK["BTN_DOWN"]
ACCENT = _DARK["ACCENT"]
ACCENT_DOWN = _DARK["ACCENT_DOWN"]
ACCENT_HOVER = _DARK["ACCENT_HOVER"]
CELL = _DARK["CELL"]
CELL_EDGE = _DARK["CELL_EDGE"]

# ---------------------------------------------------------------- 两套布局
# 未展开:小胶囊(状态 + 一行运行数据)
C_W, C_H = 246, 58
# 展开:长方形信息卡
E_W, E_H = 392, 302

PAD = 14
COLLAPSE_BTN = (E_W - PAD - 58, 14, 58, 28)      # 「收起」按钮(渲染和点击判定共用)

# 展开态纵向位置(注意:分隔线要留在状态文字和"游戏"行之间,别压到文字上)
SEP_Y = 50                  # 顶栏分隔线
GAME_Y = 60                 # 游戏行
LABEL_Y = 84                # 「当前台词」
TEXT_Y = 102                # 台词(最多 2 行)
TEXT_LH = 18
GRID_Y = 148                # 指标格(2 行)
GRID_LH = 28
SW_TOP, SW_H = 212, 34      # 开关
BTN_TOP, BTN_H = 254, 34    # 操作按钮

TOGGLES = (("auto_say", "自动朗读"), ("auto_next", "自动点击"))
BUTTONS = (("stop", "停止"), ("read", "读一下"), ("main", "主界面"), ("hide", "隐藏"))

# 未展开态
PB_DOT = (16, 16, 11)                 # 状态点 (x, y, 直径)
PB_TEXT_Y = 11
PB_SUB_Y = 34
PB_BTN = (C_W - 44, 15, 30, 28)       # 展开按钮 (x, y, w, h)


def _font(size, bold=False):
    size = max(9, int(round(size)))       # 必须整数,小数字号会被 PIL 退化成点阵字体
    order = FONT_CANDIDATES if not bold else (FONT_CANDIDATES[1],) + FONT_CANDIDATES
    for p in order:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _protos():
    """声明 Win32 原型:64 位下句柄必须当指针,否则会被截断/溢出。"""
    if getattr(_protos, "done", False):
        return
    u, gdi32, k32 = ctypes.windll.user32, ctypes.windll.gdi32, ctypes.windll.kernel32
    k32.GetModuleHandleW.restype = ctypes.c_void_p
    u.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    u.DefWindowProcW.restype = ctypes.c_longlong
    u.CreateWindowExW.restype = ctypes.c_void_p
    u.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                  wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p]
    u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                               ctypes.c_int, ctypes.c_int, wintypes.UINT]
    u.GetDC.argtypes = [wintypes.HWND]
    u.GetDC.restype = ctypes.c_void_p
    u.ReleaseDC.argtypes = [wintypes.HWND, ctypes.c_void_p]
    u.UpdateLayeredWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                      wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    u.UpdateLayeredWindow.restype = wintypes.BOOL
    u.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
    u.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
    u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    u.ShowWindow.restype = wintypes.BOOL
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
    _protos.done = True


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class _TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("hwndTrack", wintypes.HWND), ("dwHoverTime", wintypes.DWORD)]


def _sw_rect(key):
    """展开态:两个开关各占一半。"""
    inner = E_W - PAD * 2 - 8
    w = inner // 2
    for i, (k, _l) in enumerate(TOGGLES):
        if k == key:
            return PAD + i * (w + 8), SW_TOP, w, SW_H
    return None


def _btn_rect(key):
    """展开态:底部四个按钮平分。"""
    inner = E_W - PAD * 2 - 8 * (len(BUTTONS) - 1)
    w = inner // len(BUTTONS)
    for i, (k, _l) in enumerate(BUTTONS):
        if k == key:
            return PAD + i * (w + 8), BTN_TOP, w, BTN_H
    return None


class FloatWin:
    """左上角悬浮窗:未展开是小胶囊,展开是信息卡(带自动朗读/自动点击开关)。"""

    def __init__(self, data_getter=None, on_action=None, pos=(12, 12)):
        self.data_getter = data_getter or (lambda: {})
        self.on_action = on_action or (lambda key: None)
        self.pos = [int(pos[0]), int(pos[1])]
        self.expanded = False                     # 需求:默认未展开
        self.data = {}

        self._hwnd = 0
        self._thread = None
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._wndproc = None
        self._hover = ""
        self._pressed = ""
        self._armed = False
        self._w = C_W
        self._h = C_H
        self._font_cache = {}
        self._img = None                          # 保住位图引用,别让 GC 收走
        self._theme = "dark"                      # 当前配色主题(由 data["theme"] 驱动)
        self.last_paint_at = time.time()          # 上次**成功**重画的时刻(看门狗用)
        self.last_tick_at = time.time()           # 上次心跳(线程是否还在转)
        self.visible = True                       # False = 被设置关掉(只隐藏,不销毁)

    # ------------------------------------------------------------ 对外接口
    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return True
        self._stop.clear()
        self._ready = threading.Event()            # 必须换新的:老 Event 还留着 set 状态会假成功
        self._thread = threading.Thread(target=self._run, daemon=True, name="floatwin")
        self._thread.start()
        return self._ready.wait(3.0)

    def stop(self):
        self._stop.set()
        if self._hwnd:
            try:
                ctypes.windll.user32.PostMessageW(wintypes.HWND(self._hwnd), WM_APP_QUIT, 0, 0)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2.0)

    def hide_now(self):
        """立刻把窗口藏起来(ShowWindow 跨线程安全),用于看门狗清理卡死的旧窗口。"""
        if self._hwnd:
            try:
                ctypes.windll.user32.ShowWindow(wintypes.HWND(self._hwnd), 0)   # SW_HIDE
            except Exception:
                pass

    def hide(self):
        """设置里关掉悬浮窗:只**隐藏**,不销毁窗口。

        为什么不能销毁再重建:RegisterClassExW 注册的窗口类在进程里只有一份,
        而类的 wndProc 绑的是创建它的那个实例 —— 关了再打开时新窗口会复用旧类,
        消息全被派发给已经作废的旧对象(它的 _hwnd 已是 0),表现就是
        "窗口在、但点了没反应、也不刷新"(用户实测到的问题)。
        """
        self.visible = False
        if not self._hwnd:
            return
        try:
            u = ctypes.windll.user32
            u.KillTimer(wintypes.HWND(self._hwnd), IDT_REFRESH)
            u.ShowWindow(wintypes.HWND(self._hwnd), 0)                          # SW_HIDE
        except Exception:
            pass

    def show(self):
        """设置里重新打开悬浮窗:显示 + 恢复刷新定时器。"""
        self.visible = True
        if not self._hwnd:
            return self.start()
        try:
            u = ctypes.windll.user32
            u.ShowWindow(wintypes.HWND(self._hwnd), SW_SHOWNOACTIVATE)
            u.SetTimer(wintypes.HWND(self._hwnd), IDT_REFRESH, 500, None)
            self.last_paint_at = time.time()
        except Exception:
            pass
        self.poke()
        return True

    def poke(self):
        """让窗口立刻重画一次(设置变了/状态变了)。"""
        if self._hwnd:
            try:
                ctypes.windll.user32.PostMessageW(wintypes.HWND(self._hwnd), WM_APP_STATUS, 0, 0)
            except Exception:
                pass

    def set_expanded(self, on: bool):
        """展开/收起。真正的尺寸调整交给窗口线程(改窗口必须在自己线程里做)。"""
        on = bool(on)
        if on == self.expanded and self._hwnd:
            return
        self.expanded = on
        if self._hwnd:
            try:
                ctypes.windll.user32.PostMessageW(wintypes.HWND(self._hwnd),
                                                  WM_APP_FORM, 1 if on else 0, 0)
            except Exception:
                pass

    @property
    def alive(self) -> bool:
        return bool(self._hwnd) and bool(self._thread and self._thread.is_alive())

    # ------------------------------------------------------------ 字体/取色
    def _f(self, size, bold=False):
        key = (int(size), bool(bold))
        if key not in self._font_cache:
            self._font_cache[key] = _font(size, bold)
        return self._font_cache[key]

    # ------------------------------------------------------------ 渲染
    def _render(self):
        d0 = self.data or {}
        state = d0.get("state", "idle")
        theme = theme_of(d0)
        self._theme = theme                       # 记一下,方便排查"现在用的哪套色"
        label = STATES.get(state, STATES["idle"])[0]
        accent = state_color(theme, state)
        radius = max(0, min(40, int(d0.get("corner", 18) or 0)))
        if self.expanded:
            return self._render_expanded(d0, label, accent, radius)
        return self._render_pill(d0, label, accent, radius)

    def _card(self, img, d, w, h, radius, pal=None):
        """整块不透明卡片。

        边框一律用**不透明**的灰色 —— 半透明(alpha<255)会把底下的游戏画面透出来,
        看上去就是"按钮边缘/那条分隔线是透明的"(用户实测反馈)。
        """
        P = pal or _DARK
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius,
                            fill=P["CARD"], outline=P["CARD_EDGE"], width=1)

    @staticmethod
    def _dot(accent):
        """状态点颜色:允许传 3 元组或 4 元组。"""
        return accent if len(accent) == 4 else tuple(accent) + (255,)

    def _render_pill(self, data, label, accent, radius):
        P = palette(theme_of(data))
        W, H = C_W, C_H
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        self._card(img, d, W, H, radius, P)

        # 状态点 + 状态(读取文字中 / 朗读中 / 待机中 …)
        x, y, dia = PB_DOT
        d.ellipse([x, y, x + dia, y + dia], fill=self._dot(accent))
        d.text((x + dia + 8, PB_TEXT_Y), label, font=self._f(14, True), fill=P["STATUS_TXT"])

        # 第二行:内存 · 读取速度 · 已读
        d.text((x, PB_SUB_Y), data.get("sub") or "", font=self._f(10.5), fill=P["DIM"])

        # 展开按钮
        bx, by, bw, bh = PB_BTN
        hover = self._hover == "expand"
        active = self._pressed == "expand"
        fill = P["ACCENT_DOWN"] if active else (P["ACCENT_HOVER"] if hover else P["BTN"])
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=8, fill=fill,
                            outline=P["LINE_STRONG"], width=1)
        cx, cy = bx + bw / 2, by + bh / 2
        d.polygon([(cx - 5, cy - 2), (cx + 5, cy - 2), (cx, cy + 4)],
                  fill=P["CHEVRON_ON"] if (hover or active) else P["CHEVRON"])
        return img

    def _render_expanded(self, data, label, accent, radius):
        P = palette(theme_of(data))
        W, H = E_W, E_H
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        self._card(img, d, W, H, radius, P)

        # ── 顶栏:状态点 + 状态 + 收起
        d.ellipse([PAD, 18, PAD + 12, 30], fill=self._dot(accent))
        d.text((PAD + 20, 12), label, font=self._f(16, True), fill=P["STATUS_TXT"])
        bx, by, bw, bh = COLLAPSE_BTN
        hover, active = self._hover == "collapse", self._pressed == "collapse"
        fill = P["ACCENT_DOWN"] if active else (P["ACCENT_HOVER"] if hover else P["BTN"])
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=8, fill=fill,
                            outline=P["LINE_STRONG"], width=1)
        d.text((bx + 12, by + 6), "收起", font=self._f(11.5),
               fill=P["ACCENT_INK"] if (hover or active) else P["INK"])
        d.line([PAD, SEP_Y, W - PAD, SEP_Y], fill=P["LINE_SOFT"], width=1)

        # ── 游戏
        d.text((PAD, GAME_Y), "游戏", font=self._f(10.5), fill=P["DIM2"])
        d.text((PAD + 34, GAME_Y - 1), (data.get("game") or "未选择")[:28],
               font=self._f(12), fill=P["GAME_TXT"])

        # ── 当前台词
        d.text((PAD, LABEL_Y), "当前台词", font=self._f(10.5), fill=P["DIM2"])
        text = (data.get("text") or "").strip()
        lines = self._wrap(d, text or "还没有读到剧情", self._f(12.5), W - PAD * 2, 2)
        ty = TEXT_Y
        for ln in lines:
            d.text((PAD, ty), ln, font=self._f(12.5),
                   fill=P["INK"] if text else P["PLACEHOLDER"])
            ty += TEXT_LH

        # ── 指标格 2×2:内存 / 读取速度 / 已读 / 朗读速度
        cells = data.get("cells") or []
        col_w = (W - PAD * 2 - 12) // 2
        for i, (k, v) in enumerate(cells[:4]):
            r, c = divmod(i, 2)
            cx = PAD + c * (col_w + 12)
            cy = GRID_Y + r * GRID_LH
            d.rounded_rectangle([cx, cy, cx + col_w, cy + 24], radius=7,
                                fill=P["CELL"], outline=P["CELL_EDGE"], width=1)
            d.text((cx + 10, cy + 6), k, font=self._f(10.5), fill=P["DIM2"])
            tw = d.textlength(v, font=self._f(12, True))
            d.text((cx + col_w - 10 - tw, cy + 4), v, font=self._f(12, True),
                   fill=P["CELL_VAL"])

        # ── 开关:自动朗读 / 自动点击
        for key, lab in TOGGLES:
            x, y, w, h = _sw_rect(key)
            on = bool(data.get(key))
            hover, active = self._hover == key, self._pressed == key
            if on:
                fill = P["ACCENT_DOWN"] if active else (P["ACCENT_HOVER"] if hover else P["ACCENT"])
            else:
                fill = P["BTN_HOVER"] if (hover or active) else P["SW_OFF"]
            d.rounded_rectangle([x, y, x + w, y + h], radius=9, fill=fill,
                                outline=(P["LINE_STRONG"] if not on else P["ACCENT_DOWN"]), width=1)
            d.text((x + 12, y + 9), lab, font=self._f(12), fill=P["SW_LABEL"])
            st = "开" if on else "关"
            tw = d.textlength(st, font=self._f(12, True))
            d.text((x + w - 12 - tw, y + 9), st, font=self._f(12, True),
                   fill=P["SW_ST_ON"] if on else P["SW_ST_OFF"])

        # ── 操作按钮
        for key, lab in BUTTONS:
            x, y, w, h = _btn_rect(key)
            hover, active = self._hover == key, self._pressed == key
            if key == "stop":
                fill = P["STOP_DOWN"] if active else (P["STOP_HOVER"] if hover else P["STOP"])
                edge, tcol = P["STOP_EDGE"], P["STOP_TXT"]
            elif key == "read":
                fill = P["READ_DOWN"] if active else (P["READ_HOVER"] if hover else P["READ"])
                edge, tcol = P["READ_EDGE"], P["READ_TXT"]
            else:
                fill = P["BTN_DOWN"] if active else (P["BTN_HOVER"] if hover else P["BTN"])
                edge, tcol = P["LINE_STRONG"], P["BTN_LABEL"]
            d.rounded_rectangle([x, y, x + w, y + h], radius=9, fill=fill,
                                outline=edge, width=1)
            f = self._f(12, True)
            lw = d.textlength(lab, font=f)
            d.text((x + (w - lw) / 2, y + (h - 16) / 2), lab, font=f, fill=tcol)
        return img

    @staticmethod
    def _wrap(d, text, font, max_w, max_lines):
        lines, cur = [], ""
        for ch in text:
            if ch == "\n":
                lines.append(cur)
                cur = ""
            elif d.textlength(cur + ch, font=font) > max_w:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
            if len(lines) >= max_lines:
                break
        if len(lines) < max_lines and cur:
            lines.append(cur)
        if lines and len("".join(lines)) < len(text.replace("\n", "")):
            last = lines[-1]
            while last and d.textlength(last + "…", font=font) > max_w:
                last = last[:-1]
            lines[-1] = last + "…"
        return lines[:max_lines]

    # ------------------------------------------------------------ 画到位图
    def _paint(self):
        try:
            self._paint_inner()
        except Exception:
            pass                                  # 画不出来也不能让窗口线程挂掉
        finally:
            self.last_tick_at = time.time()       # 线程还活着(不代表画成功)

    def _paint_inner(self):
        if not self._hwnd:
            return
        _protos()
        import numpy as np

        img = self._render()
        self._img = img                            # 保住引用
        w, h = img.size
        self._w, self._h = w, h
        arr = np.asarray(img, dtype=np.uint8)[:, :, [2, 1, 0, 3]].astype(np.uint16)
        alpha = arr[:, :, 3:4]
        arr[:, :, :3] = (arr[:, :, :3] * alpha // 255)      # 预乘 alpha
        buf = arr.astype(np.uint8).tobytes()

        u, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32

        class BMIH(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long),
                        ("biHeight", ctypes.c_long), ("biPlanes", wintypes.WORD),
                        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                        ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
                        ("biClrImportant", wintypes.DWORD)]

        screen = u.GetDC(0)
        mem = gdi32.CreateCompatibleDC(screen)
        bmi = BMIH()
        bmi.biSize = ctypes.sizeof(BMIH)
        bmi.biWidth, bmi.biHeight = w, -h
        bmi.biPlanes, bmi.biBitCount, bmi.biCompression = 1, 32, 0
        bits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(mem, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        if not (hbmp and bits.value):
            gdi32.DeleteDC(mem)
            u.ReleaseDC(0, screen)
            return
        ctypes.memmove(bits, buf, len(buf))
        old = gdi32.SelectObject(mem, hbmp)

        size, src = _SIZE(w, h), _POINT(0, 0)
        dst = _POINT(int(self.pos[0]), int(self.pos[1]))
        blend = _BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        u.UpdateLayeredWindow(wintypes.HWND(self._hwnd), screen, ctypes.byref(dst),
                              ctypes.byref(size), mem, ctypes.byref(src), 0,
                              ctypes.byref(blend), ULW_ALPHA)
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(mem)
        u.ReleaseDC(0, screen)
        self.last_paint_at = time.time()           # 这一帧真的画上去了

    # ------------------------------------------------------------ 命中判定
    def _hit(self, x, y):
        if not self.expanded:
            bx, by, bw, bh = PB_BTN
            if bx <= x <= bx + bw and by <= y <= by + bh:
                return "expand"
            return "pill"
        if E_W - PAD - 60 <= x <= E_W - PAD and 13 <= y <= 41:
            return "collapse"
        for key, _l in TOGGLES:
            r = _sw_rect(key)
            if r and r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3]:
                return key
        for key, _l in BUTTONS:
            r = _btn_rect(key)
            if r and r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3]:
                return key
        return "panel"

    # ------------------------------------------------------------ 窗口线程
    def _apply_form(self, expanded):
        """按形态调整窗口尺寸(必须在窗口线程里调)。"""
        if not self._hwnd:
            return
        u = ctypes.windll.user32
        w, h = (E_W, E_H) if expanded else (C_W, C_H)
        self._w, self._h = w, h
        u.SetWindowPos(wintypes.HWND(self._hwnd), wintypes.HWND(HWND_TOPMOST),
                       int(self.pos[0]), int(self.pos[1]), w, h, SWP_NOACTIVATE)
        self._paint()

    def _run(self):
        _protos()
        u = ctypes.windll.user32
        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT,
                                     wintypes.WPARAM, wintypes.LPARAM)

        def proc(hwnd, msg, wparam, lparam):
            try:
                return self._proc(hwnd, msg, wparam, lparam, u)
            except Exception:
                return u.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc = WNDPROC(proc)
        hinst = ctypes.windll.kernel32.GetModuleHandleW(None)

        class WNDCLASSEX(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT),
                        ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                        ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                        ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE),
                        ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR),
                        ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]

        # 窗口类名每个实例都不同:窗口类在进程里只能注册一次,而且类的 wndProc 绑的是
        # 注册它的那个实例 —— 用同一个类名重建窗口,消息会跑到旧实例上(点了没反应)。
        cls = "LingYueFloatWin_%x" % (id(self) & 0xFFFFFF)
        wc = WNDCLASSEX()
        wc.cbSize = ctypes.sizeof(WNDCLASSEX)
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = cls
        wc.hCursor = u.LoadCursorW(None, 32649)          # IDC_HAND
        u.RegisterClassExW(ctypes.byref(wc))

        w, h = (E_W, E_H) if self.expanded else (C_W, C_H)
        self._w, self._h = w, h
        self._hwnd = u.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            cls, "Lyra 悬浮窗", WS_POPUP,
            int(self.pos[0]), int(self.pos[1]), w, h, None, None, hinst, None)
        if not self._hwnd:
            self._ready.set()
            return
        u.ShowWindow(wintypes.HWND(self._hwnd), SW_SHOWNOACTIVATE)   # 显示但不抢焦点
        try:                                     # 圆角以外的区域别挡住鼠标
            self.data = self.data_getter() or {}
        except Exception:
            self.data = {}
        self._paint()
        u.SetTimer(wintypes.HWND(self._hwnd), IDT_REFRESH, 500, None)
        self._ready.set()

        msg = wintypes.MSG()
        while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0 and not self._stop.is_set():
            u.TranslateMessage(ctypes.byref(msg))
            u.DispatchMessageW(ctypes.byref(msg))
        try:
            u.KillTimer(wintypes.HWND(self._hwnd), IDT_REFRESH)
            u.DestroyWindow(wintypes.HWND(self._hwnd))
        except Exception:
            pass
        self._hwnd = 0

    def _proc(self, hwnd, msg, wparam, lparam, u):
        if msg == WM_LBUTTONDOWN:
            x = ctypes.c_short(lparam & 0xFFFF).value
            y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
            self._armed = True                     # 必须真的按下过,才认后面的抬起
            self._pressed = self._hit(x, y)
            u.SetCapture(wintypes.HWND(hwnd))
            self._paint()
            return 0

        if msg == WM_MOUSEMOVE:
            x = ctypes.c_short(lparam & 0xFFFF).value
            y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
            if not (u.GetAsyncKeyState(0x01) & 0x8000):
                self._armed = False                # 左键其实已经松了(消息丢了)
            hit = self._hit(x, y)
            if hit != self._hover:
                self._hover = hit
                self._paint()
            tme = _TRACKMOUSEEVENT(ctypes.sizeof(_TRACKMOUSEEVENT), TME_LEAVE,
                                   wintypes.HWND(hwnd), 0)
            u.TrackMouseEvent(ctypes.byref(tme))
            return 0

        if msg == WM_MOUSELEAVE:
            if self._hover:
                self._hover = ""
                self._paint()
            return 0

        if msg == WM_LBUTTONUP:
            if not self._armed:                    # 没按下过的"抬起"是杂散消息,忽略
                return 0
            self._armed = False
            x = ctypes.c_short(lparam & 0xFFFF).value
            y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
            pressed, self._pressed = self._pressed, ""
            u.ReleaseCapture()
            hit = self._hit(x, y)
            if hit == pressed and hit not in ("panel", "pill"):
                self._fire(hit)
            else:
                self._paint()
            return 0

        if msg == WM_APP_FORM:
            self._apply_form(bool(wparam))
            return 0

        if msg in (WM_APP_STATUS, WM_TIMER):
            try:
                self.data = self.data_getter() or {}
            except Exception:
                pass
            self._paint()
            return 0

        if msg == WM_CLOSE:
            u.DestroyWindow(wintypes.HWND(hwnd))
            return 0
        if msg in (WM_DESTROY, WM_APP_QUIT):
            u.PostQuitMessage(0)
            return 0
        return u.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _fire(self, key):
        """按钮/开关:展开收起在窗口线程里直接处理,其它交给外面(动作可能耗时)。"""
        if key == "expand":
            self.set_expanded(True)
            return
        if key == "collapse":
            self.set_expanded(False)
            return

        def run():
            try:
                self.on_action(key)
            except Exception:
                pass
            time.sleep(0.05)
            self.poke()
        threading.Thread(target=run, daemon=True).start()
