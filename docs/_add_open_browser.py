# -*- coding: utf-8 -*-
r"""补上 /api/open_browser —— 让"在浏览器里打开"真正**自动跳转**。

现状:前端(boot.js 的 🌐 按钮、右键菜单)都在调 /api/open_browser,
      但后端**没有这个接口** → 404 → 只能提示玩家手动访问 ✗

实现:四级兜底,任何一级成功就返回,不需要玩家做任何操作
  ① os.startfile(url)                    —— 系统默认浏览器,最干净
  ② webbrowser.open(url)                 —— 标准库
  ③ cmd /c start "" url                  —— 兼容性最好(有些机器 ① 会被拦)
  ④ 直接拉 Edge / Chrome 打开            —— 最后手段
"""
import io
import subprocess

P = r"D:\Unity阅读器\webapp\server.py"
t = io.open(P, encoding="utf-8").read()

HELPER = '''def _open_in_browser(url: str):
    """用系统浏览器打开 url。返回 (成功?, 方式说明)。

    玩家点"在浏览器里打开"就该**直接跳过去**,不该让他自己复制地址。
    所以这里层层兜底:默认浏览器 → webbrowser → cmd start → Edge/Chrome。
    """
    # ① 系统默认浏览器(不会弹"你要用什么打开")
    try:
        os.startfile(url)                                    # noqa: S606
        return True, "默认浏览器"
    except Exception:
        pass
    # ② 标准库
    try:
        import webbrowser
        if webbrowser.open(url, new=2, autoraise=True):
            return True, "默认浏览器"
    except Exception:
        pass
    # ③ cmd start(兼容性最好)
    try:
        subprocess.Popen('cmd /c start "" "%s"' % url, shell=True,
                         creationflags=0x08000000)           # CREATE_NO_WINDOW
        return True, "默认浏览器"
    except Exception:
        pass
    # ④ 直接拉常见的浏览器
    import glob
    cands = []
    for base in (os.environ.get("ProgramFiles", r"C:\\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)"),
                 os.environ.get("LOCALAPPDATA", "")):
        for sub in ("Microsoft\\Edge\\Application\\msedge.exe",
                    "Google\\Chrome\\Application\\chrome.exe",
                    "BraveSoftware\\Brave-Browser\\Application\\brave.exe"):
            if base:
                cands.append(os.path.join(base, sub))
    for exe in cands:
        try:
            if os.path.isfile(exe):
                subprocess.Popen([exe, url], creationflags=0x08000000)
                return True, os.path.basename(exe)
        except Exception:
            continue
    return False, ""


'''

if "def _open_in_browser" not in t:
    t = t.replace("def metrics() -> dict:", HELPER + "def metrics() -> dict:", 1)
    print("① 已加 _open_in_browser 多级兜底")

if '"/api/open_browser"' not in t:
    ROUTE = '''            if p == "/api/open_browser":
                # ★在浏览器里打开★:前端 🌐 按钮 / 右键菜单都走这里,自动跳转
                url = "http://127.0.0.1:%d/" % PORT
                ok, how = _open_in_browser(url)
                if ok:
                    add_log("已在浏览器打开:" + url + "(" + how + ")", "info")
                    return self._json({"ok": True, "url": url,
                                       "msg": "已在浏览器里打开(用%s)" % how})
                return self._json({"ok": False, "url": url,
                                   "msg": "打不开浏览器,请手动访问 " + url})

'''
    anchor = '            if p == "/api/rules":'
    if anchor in t:
        t = t.replace(anchor, ROUTE + anchor, 1)
        print("② 已加 /api/open_browser 路由")
    else:
        print("② !! 找不到插入点")

io.open(P, "w", encoding="utf-8", newline="\n").write(t)
r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % P],
                   capture_output=True, text=True)
print("   语法:", "通过" if r.returncode == 0 else (r.stderr or "")[:250])
print("   含 _open_in_browser:", "def _open_in_browser" in t, "| 含路由:", '"/api/open_browser"' in t)
