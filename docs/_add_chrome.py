# -*- coding: utf-8 -*-
"""① 静态资源禁止缓存(no-store)——治"点了没反应"的常见病根:
     窗口里跑的是上一次部署的旧 JS,新加的模块加载不到 → 所有按钮都失效。
   ② 布局模型扩展到"整个界面"(chrome):侧栏位置/宽度/显隐、顶栏、主题、圆角、密度、首屏页。
"""
import io
import subprocess

SRC = r"D:\Unity阅读器"
SV = SRC + r"\webapp\server.py"
UL = SRC + r"\core\uilayout.py"

# ---------------- ① 静态资源不缓存 ----------------
t = io.open(SV, encoding="utf-8").read()
if "no-store" not in t:
    # 找到静态文件响应处:给它补上禁用缓存的头
    old = '''            self.send_header("Content-Type", ctype)'''
    new = '''            self.send_header("Content-Type", ctype)
            # ★禁止缓存★:否则 WebView2 会拿旧的 JS/HTML,新功能点了没反应
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")'''
    n = t.count(old)
    if n:
        t = t.replace(old, new)          # 所有静态响应都加上
        print("① 已给 %d 处静态响应加上 no-store" % n)
    else:
        print("① !! 没找到 Content-Type 发送处,需要人工看")
    io.open(SV, "w", encoding="utf-8", newline="\n").write(t)
else:
    print("① 已有 no-store")

# ---------------- ② 布局模型加 chrome ----------------
u = io.open(UL, encoding="utf-8").read()
if "CHROME_DEFAULTS" not in u:
    u = u.replace("CANVAS_DEFAULT = {",
'''# ---------------------------------------------------------------- 整个界面(chrome)
# 这才是"把整个程序的 UI 交给你设计"的部分:侧栏放哪、多宽、要不要显示,
# 顶栏/搜索/状态灯、主题、圆角、密度、以及打开程序先看哪一页。
CHROME_DEFAULTS = {
    "sidebar": {"show": True, "side": "left", "width": 226, "labels": True, "theme_box": True},
    "topbar": {"show": True, "search": True, "status": True},
    "look": {"theme": "", "radius": 12, "density": "normal", "font_scale": 100},
    "home": "library",          # 打开程序先看哪一页(library/realtime/board/...)
    "board_home": False,        # 是否把"工作台"当首屏
}

PAGES = [("library", "游戏库"), ("realtime", "实时剧情"), ("cast", "角色配音"),
         ("translate", "文本翻译"), ("rules", "过滤规则"), ("logs", "日志"),
         ("board", "工作台"), ("settings", "设置")]


def clean_chrome(src) -> dict:
    """把玩家给的界面设置收拾干净(越界就夹回、类型不对就用默认)。"""
    d = json.loads(json.dumps(CHROME_DEFAULTS))       # 深拷贝默认值
    if not isinstance(src, dict):
        return d
    sb = src.get("sidebar") if isinstance(src.get("sidebar"), dict) else {}
    d["sidebar"]["show"] = sb.get("show", True) is not False
    d["sidebar"]["side"] = "right" if str(sb.get("side")) == "right" else "left"
    d["sidebar"]["width"] = _clamp(sb.get("width"), 120, 420, 226)
    d["sidebar"]["labels"] = sb.get("labels", True) is not False
    d["sidebar"]["theme_box"] = sb.get("theme_box", True) is not False
    tb = src.get("topbar") if isinstance(src.get("topbar"), dict) else {}
    d["topbar"]["show"] = tb.get("show", True) is not False
    d["topbar"]["search"] = tb.get("search", True) is not False
    d["topbar"]["status"] = tb.get("status", True) is not False
    lk = src.get("look") if isinstance(src.get("look"), dict) else {}
    th = str(lk.get("theme") or "")
    d["look"]["theme"] = th if th in ("dark", "light", "sepia", "md3") else ""
    d["look"]["radius"] = _clamp(lk.get("radius"), 0, 28, 12)
    dn = str(lk.get("density") or "normal")
    d["look"]["density"] = dn if dn in ("compact", "normal", "loose") else "normal"
    d["look"]["font_scale"] = _clamp(lk.get("font_scale"), 80, 140, 100)
    home = str(src.get("home") or "library")
    d["home"] = home if home in [k for k, _ in PAGES] else "library"
    d["board_home"] = src.get("board_home", False) is True
    return d


CANVAS_DEFAULT = {''', 1)

    # 默认布局里带上 chrome;validate 里也过一遍
    u = u.replace('''        "version": 1,
        "name": "默认工作台",
        "canvas": dict(CANVAS_DEFAULT),''',
                  '''        "version": 1,
        "name": "默认工作台",
        "chrome": json.loads(json.dumps(CHROME_DEFAULTS)),
        "canvas": dict(CANVAS_DEFAULT),''', 1)
    u = u.replace('''    return {"version": 1, "name": str(layout.get("name") or "我的工作台")[:40],
            "canvas": canvas, "items": out}, notes''',
                  '''    return {"version": 1, "name": str(layout.get("name") or "我的工作台")[:40],
            "chrome": clean_chrome(layout.get("chrome")),
            "canvas": canvas, "items": out}, notes''', 1)
    io.open(UL, "w", encoding="utf-8", newline="\n").write(u)
    print("② uilayout.py 已加 chrome(整个界面)模型 + 校验")
else:
    print("② 已有 chrome")

for f in (SV, UL):
    r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % f],
                       capture_output=True, text=True)
    print("   语法 %-14s %s" % (f.split("\\")[-1], "通过" if r.returncode == 0 else (r.stderr or "")[:200]))
