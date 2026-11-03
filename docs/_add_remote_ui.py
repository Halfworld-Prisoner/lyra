# -*- coding: utf-8 -*-
r"""跨设备访问的界面:
   ① webapp/static/m.html —— 手机浏览器打开的精简页(独立自包含,不依赖 app 模块,不会因为模块加载失败而白屏)
   ② webapp/static/js/views/remote.js —— 设置页那个面板:开关 / 安全码 / 地址列表 + 自动体检
   ③ index.html —— 设置页插入「跨设备访问」面板
"""
import io
import os
import subprocess

STATIC = r"D:\Unity阅读器\webapp\static"

M_HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#12141c">
<title>Lyra · 手机遥控</title>
<style>
  :root{--bg:#12141c;--panel:#1b1f2b;--line:#2c3243;--txt:#e6e9f2;--muted:#8b93a7;--acc:#7c5cff;--acc2:#4aa8ff}
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  body{margin:0;background:var(--bg);color:var(--txt);font:16px/1.65 "Microsoft YaHei",system-ui,sans-serif;
       padding:12px 12px calc(88px + env(safe-area-inset-bottom));}
  .hd{display:flex;align-items:center;gap:8px;margin-bottom:10px}
  .hd b{font-size:17px}
  .hd .st{margin-left:auto;font-size:12px;color:var(--muted);display:flex;align-items:center;gap:6px}
  .dot{width:8px;height:8px;border-radius:50%;background:#39c5a0}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px;margin-bottom:10px}
  .now{font-size:20px;line-height:1.7;min-height:3.4em}
  .now .who{color:var(--acc);font-weight:600;margin-right:4px}
  .meta{display:flex;gap:12px;flex-wrap:wrap;color:var(--muted);font-size:12px;margin-top:8px}
  .meta b{color:var(--txt);font-weight:600}
  .list{max-height:44vh;overflow:auto;-webkit-overflow-scrolling:touch}
  .list div{padding:9px 6px;border-bottom:1px solid var(--line);font-size:14px;line-height:1.5}
  .list div:last-child{border-bottom:0}
  .list .who{color:var(--acc)}
  .bar{position:fixed;left:0;right:0;bottom:0;display:flex;gap:8px;padding:10px 12px calc(10px + env(safe-area-inset-bottom));
       background:rgba(18,20,28,.94);backdrop-filter:blur(8px);border-top:1px solid var(--line)}
  button{flex:1;font:600 15px/1 inherit;color:var(--txt);background:#232838;border:1px solid var(--line);
         border-radius:12px;padding:14px 8px;cursor:pointer}
  button:active{transform:scale(.97)}
  button.p{background:linear-gradient(135deg,var(--acc),var(--acc2));border-color:transparent;color:#fff}
  .tabs{display:flex;gap:6px;margin-bottom:10px}
  .tabs button{padding:9px;font-size:13px;border-radius:999px}
  .tabs button.on{background:var(--acc);border-color:var(--acc);color:#fff}
  .big{font-size:34px;font-weight:700;color:var(--acc)}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
  .grid div{background:#232838;border-radius:10px;padding:9px 11px;font-size:12px;color:var(--muted)}
  .grid b{display:block;color:var(--txt);font-size:15px;margin-top:2px}
  .days{display:flex;align-items:flex-end;gap:4px;height:64px;margin-top:12px}
  .days i{flex:1;background:linear-gradient(180deg,var(--acc),var(--acc2));border-radius:4px 4px 0 0;min-height:4px;opacity:.85}
</style>
</head>
<body>
<div class="hd">
  <b>Lyra</b><span class="st"><span class="dot" id="dot"></span><span id="conn">连接中…</span></span>
</div>

<div class="tabs">
  <button class="on" data-t="now">当前</button>
  <button data-t="list">剧情</button>
  <button data-t="stat">统计</button>
</div>

<!-- 当前 -->
<div id="tab-now">
  <div class="card"><div class="now" id="line">等着游戏说话…</div>
    <div class="meta">
      <span>语音 <b id="voice">—</b></span><span>速度 <b id="rate">—</b></span><span>已读 <b id="count">0</b></span>
    </div>
  </div>
</div>

<!-- 剧情 -->
<div id="tab-list" style="display:none">
  <div class="card list" id="lines"><div style="color:var(--muted)">还没有读到剧情</div></div>
</div>

<!-- 统计 -->
<div id="tab-stat" style="display:none">
  <div class="card">
    <div class="big"><span id="sChars">0</span> <span style="font-size:14px;color:var(--muted)">字</span></div>
    <div class="meta"><span id="sGame">—</span><span>今天 <b id="sToday">0</b> 字</span></div>
    <div class="grid" style="margin-top:12px">
      <div>累计句数<b id="sLines">0</b></div>
      <div>阅读时长<b id="sTime">—</b></div>
      <div>平均速度<b id="sAvg">—</b></div>
      <div>连续天数<b id="sStreak">0</b></div>
    </div>
    <div class="days" id="sDays"></div>
  </div>
</div>

<div class="bar">
  <button id="bPlay" class="p">▶ 朗读一次</button>
  <button id="bStop">■ 停止</button>
  <button id="bAuto">自动</button>
</div>

<script>
const $ = (id) => document.getElementById(id);
let S = {}, stats = {}, lastLines = '';
const api = async (p, body) => {
  const r = await fetch(p, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {});
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
};
function fmtTime(sec) {
  sec = Math.round(sec || 0);
  if (sec >= 3600) return (sec / 3600).toFixed(1) + ' 小时';
  if (sec >= 60) return Math.round(sec / 60) + ' 分钟';
  return sec + ' 秒';
}
function draw() {
  const st = S.settings || {}, m = S.metrics || {};
  const ls = S.lines || [];
  const last = ls.length ? String(ls[ls.length - 1]) : '';
  const mm = /^【([^】]+)】([\s\S]*)$/.exec(last);
  $('line').innerHTML = last
    ? (mm ? '<span class="who">【' + mm[1] + '】</span>' + mm[2].replace(/</g, '&lt;') : last.replace(/</g, '&lt;'))
    : '<span style="color:var(--muted)">等着游戏说话…</span>';
  $('voice').textContent = (st.voice_label || st.voice || '—').replace(/^(sapi|sherpa):/, '');
  $('rate').textContent = (m.rate != null ? Number(m.rate).toFixed(1) : '—') + ' 字/秒';
  $('count').textContent = m.count != null ? m.count : 0;
  $('bAuto').textContent = st.auto_say ? '自动 ✓' : '自动';
  const sig = ls.length + '|' + (ls[ls.length - 1] || '');
  if (sig !== lastLines) {
    lastLines = sig;
    $('lines').innerHTML = ls.length
      ? ls.slice().reverse().slice(0, 100).map((x) => {
          const a = /^【([^】]+)】([\s\S]*)$/.exec(String(x));
          return '<div>' + (a ? '<span class="who">【' + a[1] + '】</span>' + a[2].replace(/</g, '&lt;') : String(x).replace(/</g, '&lt;')) + '</div>';
        }).join('')
      : '<div style="color:var(--muted)">还没有读到剧情</div>';
  }
  if (stats) {
    $('sChars').textContent = (stats.chars || 0).toLocaleString();
    $('sGame').textContent = stats.name || '—';
    $('sToday').textContent = (stats.today || 0).toLocaleString();
    $('sLines').textContent = (stats.lines || 0).toLocaleString();
    $('sTime').textContent = fmtTime(stats.seconds);
    $('sAvg').textContent = stats.seconds > 0 ? Math.round(stats.chars / (stats.seconds / 60)) + ' 字/分' : '—';
    const ds = (stats.days || []).slice(-7);
    const max = Math.max(1, ...ds.map((d) => d[1]));
    $('sDays').innerHTML = ds.map((d) => '<i style="height:' + Math.max(4, Math.round(d[1] / max * 56)) + 'px" title="' + d[0] + ':' + d[1] + '"></i>').join('');
    let streak = 0; const day = new Date(); const keys = new Set((stats.days || []).map((d) => d[0]));
    for (;;) {
      const k = day.getFullYear() + '-' + String(day.getMonth() + 1).padStart(2, '0') + '-' + String(day.getDate()).padStart(2, '0');
      if (keys.has(k)) { streak++; day.setDate(day.getDate() - 1); } else break;
      if (streak > 400) break;
    }
    $('sStreak').textContent = streak + ' 天';
  }
}
async function tick() {
  try {
    const d = await api('/api/state');
    S = d; stats = d.stats || stats;
    $('dot').style.background = '#39c5a0'; $('conn').textContent = '已连接';
    draw();
  } catch (e) {
    $('dot').style.background = '#e2566a'; $('conn').textContent = '断开';
  }
}
document.querySelectorAll('.tabs button').forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll('.tabs button').forEach((x) => x.classList.toggle('on', x === b));
    ['now', 'list', 'stat'].forEach((t) => { $('tab-' + t).style.display = (t === b.dataset.t) ? '' : 'none'; });
  };
});
$('bPlay').onclick = async () => {
  const ls = S.lines || [];
  await api('/api/speak', { text: ls[ls.length - 1] || '' }).catch(() => {});
};
$('bStop').onclick = () => api('/api/stop', {}).catch(() => {});
$('bAuto').onclick = async () => {
  const on = !((S.settings || {}).auto_say);
  await api('/api/settings', { auto_say: on }).catch(() => {});
  setTimeout(tick, 300);
};
tick(); setInterval(tick, 1000);
</script>
</body>
</html>
'''
io.open(os.path.join(STATIC, "m.html"), "w", encoding="utf-8", newline="\n").write(M_HTML)
print("① m.html(手机页)已写入")

# ---------------- ② remote.js ----------------
REMOTE_JS = '''/* remote.js —— 设置页的「跨设备访问」面板
   开关 → 自动体检 → 列出所有可用地址(电脑热点 / 手机热点 / USB / 同一 WiFi)并标出最优 */
import { $, esc, post, toast } from '../core.js';

let DATA = null;

function rowHtml(r) {
  const badge = r.best ? '<b style="color:var(--accent)">推荐</b> ' : '';
  const ok = r.bound === true ? '<span style="color:#39c5a0">✓ 连通</span>'
           : (r.bound === false ? '<span style="color:#e0a23a">未监听</span>' : '');
  return '<div class="remote-row">'
    + '<div class="remote-k">' + badge + esc(r.label) + ok + '</div>'
    + '<div class="remote-u">' + esc(r.url) + '</div>'
    + '<div class="remote-h">' + esc(r.hint) + (r.iface ? ' · ' + esc(r.iface) : '') + '</div>'
    + '</div>';
}

async function refresh(check) {
  const box = $('remoteBox');
  if (!box) return;
  try {
    const st = await post('/api/remote', {});
    DATA = st;
    if ($('remoteOn')) $('remoteOn').checked = !!st.on;
    if ($('remotePin')) $('remotePin').textContent = st.pin || '----';
    if ($('remotePort')) $('remotePort').textContent = st.port || '';
    if (!st.on) {
      box.innerHTML = '<p class="muted sm">打开后,手机会在下面这些地址里选一个访问(同一网络下)。</p>';
      return;
    }
    box.innerHTML = '<p class="muted sm">正在体检…</p>';
    const r = await post('/api/remote/check', {});
    if (!r.ok) { box.innerHTML = '<p class="muted sm">' + esc(r.msg || '检测失败') + '</p>'; return; }
    const fw = (r.firewall || {}).ok
      ? '<span style="color:#39c5a0">防火墙已放行 ✓</span>'
      : '<span style="color:#e0a23a">防火墙还没放行</span> <button class="btn ghost sm" id="remoteFw">点此放行</button>';
    box.innerHTML = '<div class="muted sm" style="margin:4px 0 8px">' + rw(fw) + '</div>'
      + (r.routes || []).map(rowHtml).join('')
      + '<p class="muted sm" style="margin:10px 0 0">' + esc((r.best && ('最优: ' + r.best.label + ' ' + r.best.url)) || r.msg || '') + '</p>'
      + '<p class="muted sm" style="margin:6px 0 0">' + (r.tips || []).map((t) => '· ' + esc(t)).join('<br>') + '</p>';
    const f = $('remoteFw');
    if (f) f.onclick = async () => {
      const x = await post('/api/remote/firewall', {});
      toast(x.msg || '已申请');
    };
  } catch (e) {
    box.innerHTML = '<p class="muted sm">读取失败:' + esc(String(e && e.message || e)) + '</p>';
  }
}
function rw(s) { return s; }

export function installRemoteUI() {
  const sw = $('remoteOn');
  if (sw) sw.onchange = async () => {
    const r = await post('/api/remote', { on: sw.checked });
    toast(r.msg || (sw.checked ? '已开启' : '已关闭'));
    refresh(true);
  };
  const np = $('remotePinBtn');
  if (np) np.onclick = async () => {
    const r = await post('/api/remote', { new_pin: true });
    if ($('remotePin')) $('remotePin').textContent = r.pin || '';
    toast(r.msg || '已换新安全码');
  };
  const ck = $('remoteCheck');
  if (ck) ck.onclick = () => refresh(true);
  refresh(false);
}
'''
io.open(os.path.join(STATIC, "js", "views", "remote.js"), "w", encoding="utf-8", newline="\n").write(REMOTE_JS)
print("② remote.js 已写入")

# ---------------- ③ index.html:设置页面板 + 样式 ----------------
P = os.path.join(STATIC, "index.html")
h = io.open(P, encoding="utf-8").read()
PANEL = '''
      <div class="panel" id="remotePanel">
        <div class="panel-title">跨设备访问 <span class="muted sm">手机 / 平板连同一个网络就能打开 Lyra</span>
          <span class="grow"></span>
          <button class="btn ghost sm" id="remoteCheck">重新体检</button>
          <label class="switch" title="打开后局域网内的设备可以访问(需要 4 位安全码)"><input id="remoteOn" type="checkbox"><i></i></label>
        </div>
        <div class="mini-stats" style="margin-bottom:8px">
          <div><span>安全码</span><b id="remotePin">----</b></div>
          <div><span>远程端口</span><b id="remotePort">—</b></div>
          <div><button class="btn ghost sm" id="remotePinBtn">换一个码</button></div>
        </div>
        <div id="remoteBox"><p class="muted sm">打开右上角开关后,这里会列出手机可以访问的地址。</p></div>
      </div>
'''
if 'id="remotePanel"' not in h:
    anchor = '<div class="panel-title">UI 创作'
    if anchor in h:
        h = h.replace(anchor, PANEL.strip() + "\n      </div>\n      <div class=\"panel\">\n        " + anchor, 1)
    else:
        anchor2 = '<div class="panel-title">AI 助手'
        h = h.replace(anchor2, PANEL.strip() + "\n      </div>\n      <div class=\"panel\">\n        " + anchor2, 1)
    io.open(P, "w", encoding="utf-8", newline="\n").write(h)
    print("③ 设置页已加「跨设备访问」面板")
else:
    print("③ 面板已存在")

# 样式
CSS = os.path.join(STATIC, "css", "extra.css")
c = io.open(CSS, encoding="utf-8").read()
if ".remote-row" not in c:
    c += '''

/* ---- 跨设备访问 ---- */
.remote-row { border: 1px solid var(--line); border-radius: 10px; padding: 9px 12px; margin-bottom: 8px; background: var(--panel-2, var(--soft)); }
.remote-k { font-size: 13px; font-weight: 600; display: flex; gap: 8px; align-items: center; }
.remote-u { font-family: Consolas, monospace; font-size: 14px; color: var(--accent); margin: 2px 0; user-select: all; }
.remote-h { font-size: 11.5px; color: var(--muted); }
'''
    io.open(CSS, "w", encoding="utf-8", newline="\n").write(c)
    print("③ 样式已加")

# boot.js 加载
B = os.path.join(STATIC, "js", "boot.js")
b = io.open(B, encoding="utf-8").read()
if "remote.js" not in b:
    b = b.replace("installContextMenu();",
                  "installContextMenu();\n"
                  "import('./views/remote.js').then((m) => m.installRemoteUI())\n"
                  "  .catch((e) => { window.__JSERR = 'remote:' + e; });", 1)
    io.open(B, "w", encoding="utf-8", newline="\n").write(b)
    print("③ boot.js 已加载 remote.js")

for f in (os.path.join(STATIC, "js", "views", "remote.js"), B):
    r = subprocess.run(["node", "--check", f], capture_output=True, text=True)
    print("   node --check %-12s %s" % (os.path.basename(f), "通过" if r.returncode == 0 else r.stderr[:160]))
