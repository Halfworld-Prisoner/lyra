# -*- coding: utf-8 -*-
"""① 修 designer.html 里的引号笔误;
   ② server: GET /designer 打开设计器页;POST /api/ui/designer-open 用系统浏览器打开它;
   ③ 应用侧: js/ui/chrome.js —— 把 chrome(侧栏/顶栏/主题/圆角/密度/首屏)真正应用到界面;
      state.js 静态引入(静态导入失败会立刻暴露,不会像动态导入那样静默失效);
   ④ 侧栏「UI 设计」改成"打开浏览器设计器"。
"""
import io
import subprocess

SRC = r"D:\Unity阅读器"
STATIC = SRC + r"\webapp\static"

# ---------- ① 引号笔误 ----------
p = STATIC + r"\designer.html"
t = io.open(p, encoding="utf-8").read()
bad = """      toast('已改 " + k + "');"""
if bad in t:
    t = t.replace(bad, "      toast('已改 ' + k);", 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("① designer.html 引号笔误已修")
else:
    print("① 未发现笔误(可能写法不同)")

# ---------- ② server 路由 ----------
P = SRC + r"\webapp\server.py"
t = io.open(P, encoding="utf-8").read()
if "/api/ui/designer-open" not in t:
    t = t.replace('            if p == "/api/ui/schema":',
'''            if p == "/designer":
                # 独立设计器页(浏览器里打开;不依赖应用里的模块)
                return self._file("designer.html")

            if p == "/api/ui/designer-open":
                # 用系统默认浏览器打开设计器 —— 玩家要的"自动跳转浏览器来制作"
                url = "http://127.0.0.1:%d/designer" % PORT
                try:
                    import webbrowser
                    webbrowser.open(url, new=1, autoraise=True)
                    add_log("已在浏览器打开 UI 设计器:" + url, "info")
                    return self._json({"ok": True, "url": url, "msg": "已在浏览器打开设计器"})
                except Exception as e:
                    return self._json({"ok": False, "url": url, "msg": "打不开浏览器:%s" % e})

            if p == "/api/ui/schema":''', 1)
    io.open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("② server.py 已加 /designer 与 /api/ui/designer-open")

# ---------- ③ chrome.js ----------
CHROME = '''/* chrome.js —— 把"整个界面"的设计应用到程序上
   支持:侧栏(显示/左右/宽度/文字/主题块)、顶栏(显示/搜索/状态灯)、
        主题、圆角、密度、字号、打开先看哪一页。
   原则:只改外观,不动功能;任何一项坏了都退回默认,绝不把界面搞没。 */
import { $ } from '../core.js';

let last = '';

export function applyChrome(ui) {
  const c = (ui && ui.chrome) || null;
  const doc = document.documentElement;
  if (!c) return;
  const sig = JSON.stringify(c);
  if (sig === last) return;
  last = sig;

  const sb = c.sidebar || {}, tb = c.topbar || {}, lk = c.look || {};

  doc.style.setProperty('--sidebar-w', (sb.width || 226) + 'px');
  doc.style.setProperty('--radius', (lk.radius == null ? 12 : lk.radius) + 'px');
  doc.style.setProperty('--radius-sm', Math.max(0, (lk.radius == null ? 12 : lk.radius) - 2) + 'px');
  doc.style.setProperty('--font-scale', ((lk.font_scale || 100) / 100).toString());
  doc.classList.toggle('no-font-scale', !lk.font_scale || lk.font_scale === 100);

  const app = document.querySelector('.app');
  if (app) {
    app.classList.toggle('hide-sidebar', sb.show === false);
    app.classList.toggle('sidebar-right', sb.side === 'right');
    app.classList.toggle('hide-topbar', tb.show === false);
    app.classList.remove('density-compact', 'density-normal', 'density-loose');
    app.classList.add('density-' + (lk.density || 'normal'));
  }
  const side = document.querySelector('.sidebar');
  if (side) {
    side.classList.toggle('no-labels', sb.labels === false);
    side.classList.toggle('no-theme', sb.theme_box === false);
  }
  const top = document.querySelector('.topbar');
  if (top) {
    const se = top.querySelector('.search');
    if (se) se.style.display = tb.search === false ? 'none' : '';
    const st = top.querySelector('.top-actions');
    if (st) st.style.display = tb.status === false ? 'none' : '';
  }
}

/** 打开程序时跳到玩家设定的首屏 */
export function applyHome(ui) {
  const home = ((ui && ui.chrome) || {}).home || 'library';
  if (!home || home === 'library') return;
  if (window.__lyHomeDone) return;
  const b = document.querySelector('.nav-item[data-view="' + home + '"]');
  if (b) { b.click(); window.__lyHomeDone = true; }
}
'''
io.open(STATIC + r"\js\ui\chrome.js", "w", encoding="utf-8", newline="\n").write(CHROME)
print("③ chrome.js 已写入")

# state.js 静态引入 + 每帧应用
p2 = STATIC + r"\js\state.js"
s = io.open(p2, encoding="utf-8").read()
if "applyChrome" not in s:
    s = s.replace("import { $, esc, setStatusText, toast",
                  "import { applyChrome, applyHome } from './ui/chrome.js';\nimport { $, esc, setStatusText, toast", 1)
    s = s.replace("  /* 主题(以配置为准) */",
                  "  /* 整个界面的自定义(侧栏/顶栏/圆角/密度/首屏) */\n"
                  "  try { applyChrome(st.ui); applyHome(st.ui); } catch (e) { window.__JSERR = 'chrome:' + e; }\n\n"
                  "  /* 主题(以配置为准) */", 1)
    io.open(p2, "w", encoding="utf-8", newline="\n").write(s)
    print("③ state.js 已接入(静态导入,不会再静默失效)")

# 侧栏「UI 设计」→ 打开浏览器
p3 = STATIC + r"\index.html"
h = io.open(p3, encoding="utf-8").read()
old = '  <button class="nav-item" data-view="designer"><i>✎</i><span>UI 设计</span></button>'
new = '  <button class="nav-item" id="navDesigner" title="在浏览器里设计整个程序的界面"><i>✎</i><span>UI 设计</span></button>'
if old in h:
    h = h.replace(old, new, 1)
    io.open(p3, "w", encoding="utf-8", newline="\n").write(h)
    print("④ 侧栏「UI 设计」已改为打开浏览器")

p4 = STATIC + r"\js\boot.js"
b = io.open(p4, encoding="utf-8").read()
if "navDesigner" not in b:
    b = b.replace("/* 自定义界面:工作台",
                  "/* 「UI 设计」:让别人用浏览器设计(玩家要求:自动跳转浏览器拖组件) */\n"
                  "if ($('navDesigner')) $('navDesigner').onclick = async () => {\n"
                  "  const r = await post('/api/ui/designer-open', {});\n"
                  "  toast(r.msg || '已在浏览器打开设计器');\n"
                  "};\n\n/* 自定义界面:工作台", 1)
    io.open(p4, "w", encoding="utf-8", newline="\n").write(b)
    print("④ boot.js 已绑定「打开设计器」")

for f in ("webapp/server.py", "webapp/static/js/state.js", "webapp/static/js/boot.js", "webapp/static/js/ui/chrome.js"):
    fp = SRC + "\\" + f.replace("/", "\\")
    if f.endswith(".py"):
        r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % fp],
                           capture_output=True, text=True)
        print("   语法 %-28s %s" % (f, "通过" if r.returncode == 0 else (r.stderr or "")[:150]))
    else:
        r = subprocess.run(["node", "--check", fp], capture_output=True, text=True)
        print("   node --check %-20s %s" % (f.split("/")[-1], "通过" if r.returncode == 0 else r.stderr[:150]))
# designer.html 的 JS 语法(抽出 script 检查)
html = io.open(STATIC + r"\designer.html", encoding="utf-8").read()
js = html.split("<script>")[-1].split("</script>")[0]
tmp = STATIC + r"\_dgcheck.js"
io.open(tmp, "w", encoding="utf-8", newline="\n").write(js)
r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
print("   node --check designer.html 内联脚本 %s" % ("通过" if r.returncode == 0 else r.stderr[:200]))
import os
os.remove(tmp)
