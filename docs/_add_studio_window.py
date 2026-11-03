# -*- coding: utf-8 -*-
"""改成:设置 → UI 创作 → 弹出**独立全屏 Windows 窗口**跑设计页,窗口里有退出按钮回主程序。

① player.cpp:支持 `--designer` —— 全屏窗口 + 打开 /designer;
   并处理网页里的 window.close()(退出按钮)→ 关掉自己这个窗口。
② server.py:POST /api/ui/studio → 用 subprocess 启动宿主 --designer
   (并去掉"点 UI 设计就开浏览器"的旧接口调用点)。
③ designer.html:顶部加「退出设计(回到 Lyra)」按钮 → window.close()。
④ 设置页加「UI 创作」按钮;侧栏那个 UI 设计入口改成"打开设计窗口"。
"""
import io
import re
import subprocess

SRC = r"D:\Unity阅读器"
PC = SRC + r"\installer\player.cpp"
SV = SRC + r"\webapp\server.py"
STATIC = SRC + r"\webapp\static"

# ---------------- ① player.cpp ----------------
t = io.open(PC, encoding="utf-8").read()

# 1.1 解析 --designer(挂在已有的命令行解析附近)
if "g_designer" not in t:
    t = t.replace("int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE hPrev, LPWSTR cmdLine, int show) {",
                  "static bool g_designer = false;      /* --designer:独立的全屏设计窗口 */\n\n"
                  "int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE hPrev, LPWSTR cmdLine, int show) {", 1)
    t = t.replace("    g_hInst = hInst;",
                  "    g_hInst = hInst;\n"
                  "    if (cmdLine && wcsstr(cmdLine, L\"--designer\")) g_designer = true;", 1)
    print("① player.cpp:已解析 --designer")

# 1.2 窗口尺寸:设计窗口用全屏
m = re.search(r"int w = (\d+), h = (\d+);", t)
if m and "g_designer" not in t[m.start():m.start() + 400]:
    old = m.group(0)
    new = ("int w = g_designer ? GetSystemMetrics(SM_CXSCREEN) : %s;\n"
           "    int h = g_designer ? GetSystemMetrics(SM_CYSCREEN) : %s;\n"
           "    int x0 = g_designer ? 0 : (GetSystemMetrics(SM_CXSCREEN) - w) / 2;\n"
           "    int y0 = g_designer ? 0 : (GetSystemMetrics(SM_CYSCREEN) - h) / 2;" % (m.group(1), m.group(2)))
    t = t[:m.start()] + new + t[m.end():]
    # 后续用 x / y 变量名的地方跟着改
    t = re.sub(r"int x = \(GetSystemMetrics\(SM_CXSCREEN\) - w\) / 2;\s*\n\s*int y = \(GetSystemMetrics\(SM_CYSCREEN\) - h\) / 2;",
               "int x = x0, y = y0;", t, count=1)
    print("① player.cpp:设计窗口 = 全屏")

# 1.3 标题 + 窗口样式(设计窗口不要最小化/最大化按钮也行,保留关闭)
t = t.replace('wc.lpszClassName = L"LingYueReaderWindow";',
              'wc.lpszClassName = L"LingYueReaderWindow";', 1)
t = re.sub(r'CreateWindowExW\(0, wc\.lpszClassName, ([^,]+),',
           'CreateWindowExW(0, wc.lpszClassName, g_designer ? L"Lyra · UI \u521b\u4f5c" : \\1,', t, count=1)

# 1.4 导航目标:设计窗口打开 /designer
nav = re.search(r'Navigate\([^;]*L"/"[^;]*\);', t)
if nav and "g_designer" not in nav.group(0):
    t = t[:nav.start()] + 'Navigate(g_designer ? L"/designer" : L"/");' + t[nav.end():]
    print("① player.cpp:设计窗口导航到 /designer")

# 1.5 window.close() → 关闭本窗口
if "WindowCloseRequested" not in t:
    t = t.replace("        InterlockedExchange(&g_ready, 1);",
                  "        /* 网页里 window.close()(设计窗口的"退出"按钮)→ 关掉自己 */\n"
                  "        EventRegistrationToken ctok;\n"
                  "        g_view->add_WindowCloseRequested(\n"
                  "            Callback<ICoreWebView2WindowCloseRequestedEventHandler>(\n"
                  "                [](ICoreWebView2*, ICoreWebView2WindowCloseRequestedEventArgs*) -> HRESULT {\n"
                  "                    if (g_hWnd) PostMessageW(g_hWnd, WM_CLOSE, 0, 0);\n"
                  "                    return S_OK;\n"
                  "                }).Get(), &ctok);\n"
                  "        InterlockedExchange(&g_ready, 1);", 1)
    print("① player.cpp:已加 window.close 处理")
io.open(PC, "w", encoding="utf-8", newline="\n").write(t)

# ---------------- ② server.py ----------------
s = io.open(SV, encoding="utf-8").read()
if "/api/ui/studio" not in s:
    s = s.replace('            if p == "/designer":',
'''            if p == "/api/ui/studio":
                # ★设置里的「UI 创作」★:另开一个全屏 Windows 窗口跑设计页
                exe = os.path.join(os.path.dirname(ROOT), "Lyra.exe")
                if not os.path.isfile(exe):
                    exe = os.path.join(os.path.dirname(ROOT), "聆阅.exe")
                try:
                    si = subprocess.STARTUPINFO()
                    subprocess.Popen([exe, "--designer"], close_fds=True,
                                     creationflags=0x00000008)      # DETACHED_PROCESS
                    add_log("已打开 UI 创作窗口", "info")
                    return self._json({"ok": True, "msg": "已打开 UI 创作窗口(全屏),右上角可退出"})
                except Exception as e:
                    return self._json({"ok": False, "msg": "打不开设计窗口:%s" % e})

            if p == "/designer":''', 1)
    if "\nimport subprocess" not in s:
        s = s.replace("import os\n", "import os\nimport subprocess\n", 1)
    io.open(SV, "w", encoding="utf-8", newline="\n").write(s)
    print("② server.py:已加 /api/ui/studio")

# ---------------- ③ designer.html:退出按钮 ----------------
p = STATIC + r"\designer.html"
h = io.open(p, encoding="utf-8").read()
if "studioExit" not in h:
    h = h.replace('<button id="reset">恢复默认</button>',
                  '<button id="reset">恢复默认</button>\n'
                  '  <button id="studioExit" style="background:#e2566a;border-color:transparent;color:#fff">退出设计(回到 Lyra)</button>', 1)
    h = h.replace("load().catch((e) => toast('载入失败:' + e));",
                  """$('studioExit').onclick = async () => {
  await api('/api/ui/layout', { layout: (readChrome(), LAY) });   /* 退出前自动保存 */
  toast('已保存,正在关闭…');
  setTimeout(() => { try { window.close(); } catch (e) {} }, 350);
};
load().catch((e) => toast('载入失败:' + e));""", 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(h)
    print("③ designer.html:已加退出按钮(退出前自动保存)")

# ---------------- ④ 设置页入口 + 侧栏入口 ----------------
p2 = STATIC + r"\index.html"
x = io.open(p2, encoding="utf-8").read()
if 'id="uiStudio"' not in x:
    x = x.replace('<div class="panel-title">AI 助手',
                  '<div class="panel-title">UI 创作 <span class="muted sm">自己设计整个程序的界面</span></div>\n'
                  '        <p class="muted sm" style="margin:0 0 10px">点下面的按钮会弹出一个<b>全屏设计窗口</b>,'
                  '在里面拖组件、调侧栏/顶栏/圆角/密度,右上角「退出设计」即可回到主程序。</p>\n'
                  '        <div class="row"><button class="btn" id="uiStudio">打开 UI 创作(全屏窗口)</button></div>\n'
                  '      </div>\n      <div class="panel">\n'
                  '        <div class="panel-title">AI 助手', 1)
    io.open(p2, "w", encoding="utf-8", newline="\n").write(x)
    print("④ index.html:设置页已加「UI 创作」面板")

p3 = STATIC + r"\js\boot.js"
b = io.open(p3, encoding="utf-8").read()
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
print("④ boot.js:侧栏 + 设置页两个入口都接到 /api/ui/studio")

for f, ispy in ((PC, False), (SV, True), (p3, False)):
    if ispy:
        r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % f],
                           capture_output=True, text=True)
        print("   语法 %-16s %s" % (f.split("\\")[-1], "通过" if r.returncode == 0 else (r.stderr or "")[:200]))
    else:
        r = subprocess.run(["node", "--check", f], capture_output=True, text=True) if f.endswith(".js") else (None,)
        print("   检查 %-16s %s" % (f.split("\\")[-1], "通过" if (r is None or r.returncode == 0) else r.stderr[:150]))
