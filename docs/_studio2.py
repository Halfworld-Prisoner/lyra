# -*- coding: utf-8 -*-
"""修正版:与 _add_studio_window.py 相同,只把字符串里的半角引号换成中文引号。"""
import io
import re

SRC = r"D:\Unity阅读器"
PC = SRC + r"\installer\player.cpp"
SV = SRC + r"\webapp\server.py"
STATIC = SRC + r"\webapp\static"

# ---------------- ① player.cpp ----------------
t = io.open(PC, encoding="utf-8").read()

if "g_designer" not in t:
    t = t.replace("int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE hPrev, LPWSTR cmdLine, int show) {",
                  "static bool g_designer = false;      /* --designer:独立的全屏设计窗口 */\n\n"
                  "int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE hPrev, LPWSTR cmdLine, int show) {", 1)
    t = t.replace("    g_hInst = hInst;",
                  "    g_hInst = hInst;\n"
                  "    if (cmdLine && wcsstr(cmdLine, L\"--designer\")) g_designer = true;", 1)
    print("① 解析 --designer ✓")

m = re.search(r"int w = (\d+), h = (\d+);", t)
if m:
    new = ("int w = g_designer ? GetSystemMetrics(SM_CXSCREEN) : %s;\n"
           "    int h = g_designer ? GetSystemMetrics(SM_CYSCREEN) : %s;\n"
           "    int x0 = g_designer ? 0 : (GetSystemMetrics(SM_CXSCREEN) - w) / 2;\n"
           "    int y0 = g_designer ? 0 : (GetSystemMetrics(SM_CYSCREEN) - h) / 2;" % (m.group(1), m.group(2)))
    t = t[:m.start()] + new + t[m.end():]
    t = re.sub(r"int x = \(GetSystemMetrics\(SM_CXSCREEN\) - w\) / 2;\s*\n\s*int y = \(GetSystemMetrics\(SM_CYSCREEN\) - h\) / 2;",
               "int x = x0, y = y0;", t, count=1)
    print("① 设计窗口=全屏 ✓")

t = re.sub(r'CreateWindowExW\(0, wc\.lpszClassName, ([^,]+),',
           'CreateWindowExW(0, wc.lpszClassName, g_designer ? L"Lyra \u00b7 UI \u521b\u4f5c" : \\1,', t, count=1)

nav = re.search(r'Navigate\([^;]*L"/"[^;]*\);', t)
if nav and "g_designer" not in nav.group(0):
    t = t[:nav.start()] + 'Navigate(g_designer ? L"/designer" : L"/");' + t[nav.end():]
    print("① 设计窗口导航 /designer ✓")

if "WindowCloseRequested" not in t:
    CLOSE_CODE = (
        "        /* \u7f51\u9875\u91cc window.close()\uff08\u8bbe\u8ba1\u7a97\u53e3\u7684\u9000\u51fa\u6309\u94ae\uff09"
        "\u2192 \u5173\u6389\u81ea\u5df1\u8fd9\u4e2a\u7a97\u53e3 */\n"
        "        EventRegistrationToken ctok;\n"
        "        g_view->add_WindowCloseRequested(\n"
        "            Callback<ICoreWebView2WindowCloseRequestedEventHandler>(\n"
        "                [](ICoreWebView2*, ICoreWebView2WindowCloseRequestedEventArgs*) -> HRESULT {\n"
        "                    if (g_hWnd) PostMessageW(g_hWnd, WM_CLOSE, 0, 0);\n"
        "                    return S_OK;\n"
        "                }).Get(), &ctok);\n"
        "        InterlockedExchange(&g_ready, 1);")
    if "InterlockedExchange(&g_ready, 1);" in t:
        t = t.replace("        InterlockedExchange(&g_ready, 1);", CLOSE_CODE, 1)
        print("① window.close 处理 ✓")
    else:
        print("① !! 没找到 g_ready 置位处,window.close 未接")
io.open(PC, "w", encoding="utf-8", newline="\n").write(t)

# ---------------- ② server.py ----------------
s = io.open(SV, encoding="utf-8").read()
if "/api/ui/studio" not in s:
    s = s.replace('            if p == "/designer":',
'''            if p == "/api/ui/studio":
                # ★设置里的「UI 创作」★:另开一个全屏 Windows 窗口跑设计页
                base = os.path.dirname(ROOT)
                exe = os.path.join(base, "Lyra.exe")
                if not os.path.isfile(exe):
                    exe = os.path.join(base, "\u8046\u9605.exe")
                try:
                    subprocess.Popen([exe, "--designer"], close_fds=True,
                                     creationflags=0x00000008)      # DETACHED_PROCESS
                    add_log("\u5df2\u6253\u5f00 UI \u521b\u4f5c\u7a97\u53e3", "info")
                    return self._json({"ok": True, "msg": "\u5df2\u6253\u5f00 UI \u521b\u4f5c\u7a97\u53e3(\u5168\u5c4f)"})
                except Exception as e:
                    return self._json({"ok": False, "msg": "\u6253\u4e0d\u5f00\u8bbe\u8ba1\u7a97\u53e3:%s" % e})

            if p == "/designer":''', 1)
    if "\nimport subprocess" not in s:
        s = s.replace("import os\n", "import os\nimport subprocess\n", 1)
    io.open(SV, "w", encoding="utf-8", newline="\n").write(s)
    print("② /api/ui/studio ✓")

# ---------------- ③ designer.html 退出按钮 ----------------
p = STATIC + r"\designer.html"
h = io.open(p, encoding="utf-8").read()
if "studioExit" not in h:
    h = h.replace('<button id="reset">恢复默认</button>',
                  '<button id="reset">恢复默认</button>\n'
                  '  <button id="studioExit" style="background:#e2566a;border-color:transparent;color:#fff">'
                  '退出设计(回到 Lyra)</button>', 1)
    h = h.replace("load().catch((e) => toast('载入失败:' + e));",
                  "$('studioExit').onclick = async () => {\n"
                  "  readChrome();\n"
                  "  await api('/api/ui/layout', { layout: LAY });\n"
                  "  toast('已保存,正在关闭…');\n"
                  "  setTimeout(() => { try { window.close(); } catch (e) {} }, 350);\n"
                  "};\n"
                  "load().catch((e) => toast('载入失败:' + e));", 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(h)
    print("③ 退出按钮 ✓")

# ---------------- ④ 设置页 + 侧栏入口 ----------------
p2 = STATIC + r"\index.html"
x = io.open(p2, encoding="utf-8").read()
if 'id="uiStudio"' not in x:
    x = x.replace('<div class="panel-title">AI 助手',
                  '<div class="panel-title">UI 创作 <span class="muted sm">自己设计整个程序的界面</span></div>\n'
                  '        <p class="muted sm" style="margin:0 0 10px">点下面的按钮会弹出一个<b>全屏设计窗口</b>:'
                  '拖组件、调侧栏/顶栏/圆角/密度,窗口右上角「退出设计」即可回到主程序。</p>\n'
                  '        <div class="row"><button class="btn" id="uiStudio">打开 UI 创作(全屏窗口)</button></div>\n'
                  '      </div>\n      <div class="panel">\n'
                  '        <div class="panel-title">AI 助手', 1)
    io.open(p2, "w", encoding="utf-8", newline="\n").write(x)
    print("④ 设置页入口 ✓")

p3 = STATIC + r"\js\boot.js"
b = io.open(p3, encoding="utf-8").read()
if "openStudio" not in b:
    b = b.replace("""if ($('navDesigner')) $('navDesigner').onclick = async () => {
  const r = await post('/api/ui/designer-open', {});
  toast(r.msg || '已在浏览器打开设计器');
};""",
                  """/* 侧栏「UI 设计」= 打开全屏设计窗口(不再跳浏览器) */
async function openStudio() {
  const r = await post('/api/ui/studio', {});
  toast(r.msg || '已打开 UI 创作窗口');
}
if ($('navDesigner')) $('navDesigner').onclick = openStudio;
if ($('uiStudio')) $('uiStudio').onclick = openStudio;""", 1)
    io.open(p3, "w", encoding="utf-8", newline="\n").write(b)
    print("④ 侧栏/设置两个入口 ✓")
print("完成")
