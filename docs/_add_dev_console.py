# -*- coding: utf-8 -*-
r"""补:应用内的「跨远程访问」控制台
   ① 设置页:新增**扩展模块**区域,里面是「跨远程访问」开关(原面板精简成开关 + 一句说明)
   ② 顶栏:搜索框**旁边**加入口按钮(未开启时隐藏)
   ③ 点按钮 → **全新全屏界面**,自带左侧栏:链接状态 / 安全码 / 设置
"""
import io
import os
import re
import subprocess

STATIC = r"D:\Unity阅读器\webapp\static"
P = os.path.join(STATIC, "index.html")
h = io.open(P, encoding="utf-8").read()

# ---------- ① 设置页:扩展模块区域(把旧面板换成开关卡片) ----------
old_panel = re.search(r'\n      <div class="panel" id="remotePanel">.*?\n      </div>\n', h, re.S)
EXT = '''
      <div class="panel" id="extPanel">
        <div class="panel-title">扩展模块 <span class="muted sm">额外能力,按需开启</span></div>
        <div class="ext-row">
          <div class="ext-info">
            <b>跨远程访问</b>
            <span class="muted sm">让手机 / 另一台电脑在同一个网络里打开 Lyra(不用服务器)。
              开启后,顶栏搜索框旁边会出现入口按钮。</span>
          </div>
          <label class="switch" title="开启/关闭跨远程访问"><input id="remoteOn" type="checkbox"><i></i></label>
        </div>
        <div id="remoteBox" class="muted sm" style="margin-top:6px"></div>
      </div>
'''
if old_panel:
    h = h[:old_panel.start()] + EXT + h[old_panel.end():]
    print("① 设置页:已换成「扩展模块」区域")
elif 'id="extPanel"' not in h:
    anchor = '<div class="panel-title">AI 助手'
    h = h.replace(anchor, EXT.strip() + "\n      </div>\n      <div class=\"panel\">\n        " + anchor, 1)
    print("① 设置页:已插入「扩展模块」区域")

# ---------- ② 顶栏:搜索框旁边加入口按钮 ----------
m = re.search(r'<input[^>]*id="search"[^>]*>', h)
if not m:
    m = re.search(r'<input[^>]*class="[^"]*search[^"]*"[^>]*>', h)
if m and 'id="remoteEntry"' not in h:
    btn = ('<button class="btn ghost sm hidden" id="remoteEntry" '
           'title="跨远程访问:手机/另一台电脑的连接状态与安全码"><i>⇄</i> 跨设备</button>')
    h = h[:m.end()] + btn + h[m.end():]
    print("② 顶栏:搜索框旁边已加入口按钮")
elif 'id="remoteEntry"' in h:
    print("② 入口按钮已存在")
else:
    print("② !! 找不到搜索框")

# ---------- ③ 全屏控制台界面 ----------
CONSOLE = '''
<!-- 跨远程访问控制台(全屏覆盖,自带左侧栏) -->
<div class="dev-overlay" id="devOverlay">
  <aside class="dev-side">
    <div class="dev-brand"><div class="dev-logo">⇄</div>
      <div><b>跨远程访问</b><span class="muted sm">局域网直连 · 不用服务器</span></div></div>
    <nav class="dev-nav">
      <button data-v="link" class="on"><i>◎</i>链接状态</button>
      <button data-v="pin"><i>⚿</i>安全码</button>
      <button data-v="set"><i>⚙</i>设置</button>
    </nav>
    <div class="dev-foot"><span class="dot" id="devDot"></span><span id="devState">未开启</span></div>
  </aside>
  <main class="dev-main">
    <div class="dev-top">
      <h1 id="devTitle">链接状态</h1>
      <span class="grow"></span>
      <button class="btn ghost sm" id="devRefresh">刷新 / 体检</button>
      <button class="btn ghost sm" id="devClose">返回主界面</button>
    </div>

    <!-- 链接状态 -->
    <section id="dv-link">
      <div class="panel">
        <div class="panel-title">连接状态 <span class="muted sm">手机 / 另一台电脑连进来时看这里</span></div>
        <div class="mini-stats">
          <div><span>服务</span><b id="dvOn">—</b></div>
          <div><span>远程端口</span><b id="dvPort">—</b></div>
          <div><span>安全码</span><b id="dvPin">—</b></div>
          <div><span>防火墙</span><b id="dvFw">—</b></div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-title">可用地址 <span class="muted sm">哪个带「推荐」就用哪个;四种连接方式都会自动列出来</span></div>
        <div id="dvRoutes" class="muted sm">点右上角「刷新 / 体检」开始检测。</div>
      </div>
      <div class="panel">
        <div class="panel-title">怎么连 <span class="muted sm">四种方式任选</span></div>
        <p class="muted sm" id="dvTips" style="line-height:1.9"></p>
      </div>
    </section>

    <!-- 安全码 -->
    <section id="dv-pin" style="display:none">
      <div class="panel">
        <div class="panel-title">安全码 <span class="muted sm">手机首次访问需要输入它</span></div>
        <div class="dev-pin" id="dvPinBig">----</div>
        <div class="row" style="justify-content:center;gap:10px">
          <button class="btn" id="dvNewPin">换一个新码</button>
          <button class="btn ghost" id="dvCopy">复制地址</button>
        </div>
        <p class="muted sm" style="margin-top:12px;line-height:1.9">
          手机输对一次后会记住 30 天;换码后已连接的设备需要重新输入。<br>
          同一网络里的其他人如果不知道这个码,打不开 Lyra。
        </p>
      </div>
      <div class="panel">
        <div class="panel-title">已连接</div>
        <div class="muted sm" id="dvSessions">还没有设备连进来。</div>
      </div>
    </section>

    <!-- 设置 -->
    <section id="dv-set" style="display:none">
      <div class="panel">
        <div class="panel-title">跨远程连接设置</div>
        <div class="dev-set">
          <label class="dev-line">远程端口
            <input class="input" id="dvSetPort" type="number" min="1024" max="65535" style="width:110px">
            <span class="muted sm">改端口后需要重新开启一次</span></label>
          <label class="dev-line">自动开启
            <input type="checkbox" id="dvSetAuto"><span class="muted sm">Lyra 启动时自动打开跨远程访问</span></label>
          <label class="dev-line">允许电脑访问
            <input type="checkbox" id="dvSetPc"><span class="muted sm">开启后,另一台电脑用浏览器访问时显示**桌面版界面**(关闭则一律显示手机版)</span></label>
          <label class="dev-line">允许远程改设置
            <input type="checkbox" id="dvSetCtl"><span class="muted sm">允许手机/另一台电脑修改语音、主题等(关闭则只能看和朗读)</span></label>
        </div>
      </div>
      <div class="panel">
        <div class="panel-title">当前配置</div>
        <div class="muted sm" id="dvSetInfo">—</div>
      </div>
    </section>
  </main>
</div>
'''
if 'id="devOverlay"' not in h:
    h = h.replace("</body>", CONSOLE + "</body>", 1)
    print("③ 已加入控制台界面")

io.open(P, "w", encoding="utf-8", newline="\n").write(h)

# ---------- ④ CSS ----------
CSS = os.path.join(STATIC, "css", "extra.css")
c = io.open(CSS, encoding="utf-8").read()
if ".dev-overlay" not in c:
    c += '''

/* ================= 扩展模块 / 跨远程访问控制台 ================= */
.ext-row { display: flex; align-items: center; gap: 14px; }
.ext-info { flex: 1; min-width: 0; }
.ext-info b { display: block; font-size: 14px; margin-bottom: 3px; }
.ext-info span { line-height: 1.7; }

.dev-overlay { position: fixed; inset: 0; z-index: 950; display: none; background: var(--bg);
  grid-template-columns: 232px minmax(0, 1fr); }
.dev-overlay.on { display: grid; animation: devIn .24s ease both; }
@keyframes devIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.dev-overlay.closing { animation: devOut .2s ease both; }
@keyframes devOut { from { opacity: 1; } to { opacity: 0; } }

.dev-side { background: var(--panel); border-right: 1px solid var(--line); padding: 16px 12px;
  display: flex; flex-direction: column; gap: 8px; }
.dev-brand { display: flex; gap: 10px; align-items: center; padding: 4px 6px 14px; }
.dev-logo { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center;
  background: linear-gradient(135deg, var(--accent), var(--accent-2, #4aa8ff)); color: #fff; font-size: 17px; }
.dev-brand b { display: block; font-size: 14.5px; }
.dev-nav { display: flex; flex-direction: column; gap: 4px; }
.dev-nav button { display: flex; align-items: center; gap: 10px; padding: 11px 12px; border: 0; border-radius: 11px;
  background: transparent; color: var(--text); font: 500 14px/1 inherit; cursor: pointer; text-align: left; }
.dev-nav button i { font-style: normal; width: 16px; text-align: center; opacity: .85; }
.dev-nav button:hover { background: var(--soft); }
.dev-nav button.on { background: linear-gradient(135deg, var(--accent), var(--accent-2, #4aa8ff)); color: #fff; font-weight: 600; }
.dev-foot { margin-top: auto; font-size: 12px; color: var(--muted); display: flex; align-items: center; gap: 6px; padding: 8px 6px 0; }
.dev-foot .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--muted); }

.dev-main { padding: 18px clamp(14px, 2.4vw, 30px) 30px; overflow: auto; }
.dev-top { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.dev-top h1 { font-size: 19px; margin: 0; }
.dev-top .grow { flex: 1; }
.dev-pin { font: 700 46px/1 monospace; letter-spacing: .32em; text-align: center; padding: 22px 0 18px;
  color: var(--accent); }
.dev-set { display: grid; gap: 10px; }
.dev-line { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 13.5px; }
.dev-line > span { flex: 1; min-width: 200px; }
.remote-row { border: 1px solid var(--line); border-radius: 12px; padding: 10px 14px; margin-bottom: 8px; background: var(--soft); }
.remote-k { font-size: 13.5px; font-weight: 600; display: flex; gap: 8px; align-items: center; }
.remote-u { font-family: Consolas, monospace; font-size: 14.5px; color: var(--accent); margin: 3px 0; user-select: all; }
.remote-h { font-size: 11.5px; color: var(--muted); }
@media (max-width: 860px) { .dev-overlay { grid-template-columns: 1fr; }
  .dev-side { flex-direction: row; align-items: center; overflow-x: auto; border-right: 0; border-bottom: 1px solid var(--line); }
  .dev-brand, .dev-foot { display: none; } .dev-nav { flex-direction: row; } }
'''
    io.open(CSS, "w", encoding="utf-8", newline="\n").write(c)
    print("④ 样式已加")

# ---------- ⑤ device.js ----------
JS = os.path.join(STATIC, "js", "views", "device.js")
io.open(JS, "w", encoding="utf-8", newline="\n").write('''/* device.js —— 应用内「跨远程访问」控制台
   入口:顶栏搜索框旁边的按钮(未开启跨远程访问时隐藏)
   三个页签:链接状态 / 安全码 / 设置 */
import { $, esc, post, toast } from '../core.js';

let CUR = {};

function show(which) {
  ['link', 'pin', 'set'].forEach((v) => { const el = $('dv-' + v); if (el) el.style.display = (v === which) ? '' : 'none'; });
  document.querySelectorAll('.dev-nav button').forEach((b) => b.classList.toggle('on', b.dataset.v === which));
  const T = { link: '链接状态', pin: '安全码', set: '设置' };
  if ($('devTitle')) $('devTitle').textContent = T[which] || '';
}

export function openDev() {
  const ov = $('devOverlay');
  if (!ov) return;
  ov.classList.remove('closing');
  ov.classList.add('on');
  show('link');
  refresh(true);
}
export function closeDev() {
  const ov = $('devOverlay');
  if (!ov) return;
  ov.classList.add('closing');
  setTimeout(() => ov.classList.remove('on', 'closing'), 220);
}

function paint(st) {
  CUR = st || {};
  const on = !!CUR.on;
  if ($('remoteOn')) $('remoteOn').checked = on;
  if ($('devDot')) $('devDot').style.background = on ? 'var(--ok, #39c5a0)' : 'var(--muted)';
  if ($('devState')) $('devState').textContent = on ? '运行中' : '未开启';
  if ($('remoteEntry')) $('remoteEntry').classList.toggle('hidden', !on);
  if ($('dvOn')) $('dvOn').textContent = on ? '已开启' : '未开启';
  if ($('dvPort')) $('dvPort').textContent = CUR.port || '—';
  if ($('dvPin')) $('dvPin').textContent = CUR.pin || '----';
  if ($('dvPinBig')) $('dvPinBig').textContent = CUR.pin || '----';
  if ($('remoteBox')) $('remoteBox').textContent = on
    ? ('已开启(端口 ' + (CUR.port || '') + '),入口按钮已出现在顶栏')
    : '未开启 —— 打开后顶栏搜索框旁边会出现入口按钮';
}

async function refresh(check) {
  try {
    const st = await post('/api/remote', {});
    paint(st);
    if (!st.on) {
      if ($('dvRoutes')) $('dvRoutes').innerHTML = '<span class="muted sm">先打开跨远程访问(设置 → 扩展模块,或本页设置里打开)。</span>';
      return;
    }
    if (!check) return;
    if ($('dvRoutes')) $('dvRoutes').innerHTML = '<span class="muted sm">正在体检…</span>';
    const r = await post('/api/remote/check', {});
    const fw = (r.firewall || {});
    if ($('dvFw')) $('dvFw').innerHTML = fw.ok ? '<span style="color:#39c5a0">已放行</span>'
      : '<span style="color:#e0a23a">未放行</span>';
    const rows = (r.routes || []).map((x) => '<div class="remote-row">'
      + '<div class="remote-k">' + (x.best ? '<b style="color:var(--accent)">推荐</b> ' : '')
      + esc(x.label) + (x.bound === true ? ' <span style="color:#39c5a0">✓ 连通</span>' : '')
      + '</div><div class="remote-u">' + esc(x.url) + '</div>'
      + '<div class="remote-h">' + esc(x.hint) + (x.iface ? ' · ' + esc(x.iface) : '') + '</div></div>').join('');
    if ($('dvRoutes')) {
      $('dvRoutes').innerHTML = (rows || '<span class="muted sm">没找到可用地址,检查一下网络连接。</span>')
        + (fw.ok ? '' : '<div class="row" style="margin-top:8px"><button class="btn sm" id="dvFwBtn">点此放行防火墙</button>'
          + '<span class="muted sm" style="align-self:center">手机连不上多半是这一步没做</span></div>');
    }
    const fb = $('dvFwBtn');
    if (fb) fb.onclick = async () => { const x = await post('/api/remote/firewall', {}); toast(x.msg || '已申请'); };
    if ($('dvTips')) $('dvTips').innerHTML = (r.tips || []).map((t) => '· ' + esc(t)).join('<br>');
    if ($('dvSessions')) $('dvSessions').textContent = (r.routes || []).length
      ? '服务在监听。手机连上后,这里会显示可用地址(当前 ' + (r.routes || []).length + ' 条)。' : '还没有设备连进来。';
    if ($('dvSetInfo')) $('dvSetInfo').textContent = '端口 ' + (CUR.port || '') + ' · 安全码 ' + (CUR.pin || '')
      + ' · 自动开启:' + ((CUR.auto) ? '开' : '关') + ' · 允许电脑访问:' + ((CUR.allow_pc === false) ? '关' : '开');
  } catch (e) {
    if ($('dvRoutes')) $('dvRoutes').innerHTML = '<span class="muted sm">读取失败:' + esc(String(e && e.message || e)) + '</span>';
  }
}

export function installDevUI() {
  const ov = $('devOverlay');
  if (!ov) return;
  document.querySelectorAll('.dev-nav button').forEach((b) => { b.onclick = () => show(b.dataset.v); });
  if ($('devClose')) $('devClose').onclick = closeDev;
  if ($('devRefresh')) $('devRefresh').onclick = () => refresh(true);
  if ($('remoteEntry')) $('remoteEntry').onclick = openDev;
  if ($('devOpenFromSettings')) $('devOpenFromSettings').onclick = openDev;
  if ($('dvNewPin')) $('dvNewPin').onclick = async () => {
    const r = await post('/api/remote', { new_pin: true });
    toast(r.msg || '已换新安全码');
    refresh(false);
  };
  if ($('dvCopy')) $('dvCopy').onclick = async () => {
    const url = (CUR.url || '') || ('http://127.0.0.1:' + (CUR.port || ''));
    try { await navigator.clipboard.writeText(url); toast('已复制地址 ' + url); }
    catch (e) { toast('地址:' + url); }
  };
  if ($('remoteOn')) $('remoteOn').onchange = async () => {
    const r = await post('/api/remote', { on: $('remoteOn').checked });
    toast(r.msg || (r.on ? '已开启跨远程访问' : '已关闭'));
    refresh(false);
  };
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDev(); });
  refresh(false);
  setInterval(() => { if (ov.classList.contains('on')) refresh(false); }, 8000);
}
''')
print("⑤ device.js 已写入")

# ---------- ⑥ boot.js 加载 ----------
B = os.path.join(STATIC, "js", "boot.js")
b = io.open(B, encoding="utf-8").read()
if "device.js" not in b:
    b = b.replace("installContextMenu();",
                  "installContextMenu();\n"
                  "import('./views/device.js').then((m) => m.installDevUI())\n"
                  "  .catch((e) => { window.__JSERR = 'device:' + e; });", 1)
    io.open(B, "w", encoding="utf-8", newline="\n").write(b)
    print("⑥ boot.js 已加载 device.js")

# 删掉旧 remote.js 的加载(功能已并入 device.js)
B2 = io.open(B, encoding="utf-8").read()
B2 = B2.replace("import('./views/remote.js').then((m) => m.installRemoteUI())\n  .catch((e) => { window.__JSERR = 'remote:' + e; });",
                "/* remote.js 的功能已并入 device.js */", 1)
io.open(B, "w", encoding="utf-8", newline="\n").write(B2)

for f in (JS, B):
    r = subprocess.run(["node", "--check", f], capture_output=True, text=True)
    print("   node --check %-12s %s" % (os.path.basename(f), "通过" if r.returncode == 0 else r.stderr[:180]))
print("   入口按钮/控制台/扩展模块 都已就位")
