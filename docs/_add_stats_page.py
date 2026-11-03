# -*- coding: utf-8 -*-
r"""累计阅读统计改成**独立页面**:
   · 实时剧情页:只留一个入口按钮(不再是塞满的面板)
   · 新页面 #view-stats:左上角「← 返回」+ 圆盘图(最近 7 天占比)+ 波浪条 + 大字总计
     + 迷你卡片(句数/时长/今日/首次/最近)+ 各游戏排行
   · 数据来自 /api/stats(已有),进页面时拉一次
"""
import io
import os
import re
import subprocess

STATIC = r"D:\Unity阅读器\webapp\static"
P = os.path.join(STATIC, "index.html")
h = io.open(P, encoding="utf-8").read()

# ---------- ① 把之前塞进实时剧情的大面板换成"入口卡片" ----------
m = re.search(r'\n      <div class="panel" id="statsPanel">.*?\n      </div>\n', h, re.S)
if m:
    entry = '''
      <div class="panel stats-entry">
        <div class="stats-entry-row">
          <div class="stats-entry-num">
            <b id="statsCharsMini">0</b><span>字</span>
            <em class="muted sm">这台游戏累计读到(永久记录)</em>
          </div>
          <button class="btn" id="statsOpen">查看阅读统计 <i>→</i></button>
        </div>
      </div>
'''
    h = h[:m.start()] + entry + h[m.end():]
    print("① 实时剧情:面板 → 入口卡片")
elif 'id="statsOpen"' not in h:
    print("① !! 没找到旧面板")

# ---------- ② 新增统计页 ----------
STATS_VIEW = '''
    <!-- ---------------- 阅读统计(独立页面) ---------------- -->
    <section class="view" id="view-stats">
      <div class="panel">
        <div class="stats-top">
          <button class="btn ghost" id="statsBack" title="返回上一页"><i>←</i> 返回</button>
          <div class="stats-title">
            <b>阅读统计</b>
            <span class="muted sm" id="statsGame">—</span>
          </div>
          <span class="grow"></span>
          <span class="muted sm" id="statsHint">永久累计 · 关闭软件也会保留</span>
          <button class="btn ghost sm" id="statsReset2">清零这台</button>
        </div>
      </div>

      <div class="panel">
        <div class="stats-hero">
          <div class="stats-hero-main">
            <div class="stat-big"><b id="statsChars">0</b><span>字</span></div>
            <div class="muted sm" id="statsToday"></div>
            <div class="mini-stats" style="margin-top:14px">
              <div><span>累计句数</span><b id="statsLines">0</b></div>
              <div><span>阅读时长</span><b id="statsTime">—</b></div>
              <div><span>平均速度</span><b id="statsAvg">—</b></div>
              <div><span>首次开始</span><b id="statsFirst">—</b></div>
              <div><span>最近一次</span><b id="statsLast">—</b></div>
              <div><span>连续天数</span><b id="statsStreak">0</b></div>
            </div>
          </div>
          <div class="stats-donut-wrap">
            <svg class="stats-donut" id="statsDonut" viewBox="0 0 120 120" aria-label="最近七天占比"></svg>
            <div class="stats-donut-legend" id="statsLegend"></div>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-title">最近 14 天 <span class="muted sm">每天读了多少字 · 高度=当天字数</span></div>
        <div class="stats-wave" id="statsWave"></div>
      </div>

      <div class="panel">
        <div class="panel-title">各游戏排行 <span class="muted sm">读得最多的排前面</span></div>
        <div class="stats-rank" id="statsRank"><span class="muted sm">加载中…</span></div>
      </div>
    </section>
'''
if 'id="view-stats"' not in h:
    anchor = '    <!-- ---------------- 角色配音 ---------------- -->'
    h = h.replace(anchor, STATS_VIEW + "\n" + anchor, 1)
    print("② 已加统计页")

# 侧栏也加一个入口(方便直达)
if 'data-view="stats"' not in h:
    h = h.replace('  <button class="nav-item" data-view="settings">',
                  '  <button class="nav-item" data-view="stats"><i>◔</i><span>阅读统计</span></button>\n'
                  '  <button class="nav-item" data-view="settings">', 1)
    print("② 侧栏已加入口")

io.open(P, "w", encoding="utf-8", newline="\n").write(h)

# ---------- ③ CSS ----------
CSS = os.path.join(STATIC, "css", "extra.css")
c = io.open(CSS, encoding="utf-8").read()
c = re.sub(r"\n/\* ---- 累计阅读\(实时剧情页新增\) ---- \*/.*$", "", c, flags=re.S)   # 去掉上一版样式
if ".stats-donut" not in c:
    c += '''

/* ================= 阅读统计页 ================= */
.stats-entry-row { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.stats-entry-num { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.stats-entry-num b { font-size: 30px; font-weight: 700;
  background: linear-gradient(135deg, var(--accent), var(--accent-2, #4aa8ff));
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.stats-entry-num span { color: var(--muted); font-size: 13px; }
.stats-entry-num em { font-style: normal; }
.stats-entry-row .btn { margin-left: auto; }

.stats-top { display: flex; align-items: center; gap: 12px; }
.stats-title { display: flex; flex-direction: column; line-height: 1.3; }
.stats-title b { font-size: 17px; }

.stats-hero { display: flex; gap: 26px; align-items: center; flex-wrap: wrap; }
.stats-hero-main { flex: 1; min-width: 320px; }
.stat-big { display: flex; align-items: baseline; gap: 8px; }
.stat-big b { font-size: 46px; font-weight: 700; letter-spacing: .01em;
  background: linear-gradient(135deg, var(--accent), var(--accent-2, #4aa8ff));
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.stat-big span { color: var(--muted); font-size: 15px; }

/* 圆盘 */
.stats-donut-wrap { display: flex; align-items: center; gap: 14px; }
.stats-donut { width: 168px; height: 168px; }
.stats-donut circle { fill: none; stroke-linecap: butt; }
.stats-donut .ring-bg { stroke: var(--soft); stroke-width: 13; }
.stats-donut .seg { stroke-width: 13; transition: stroke-dasharray .6s ease; }
.stats-donut .hole-t { fill: var(--text); font-size: 15px; font-weight: 600; text-anchor: middle; }
.stats-donut .hole-s { fill: var(--muted); font-size: 8.5px; text-anchor: middle; }
.stats-donut-legend { display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: var(--muted); }
.stats-donut-legend i { display: inline-block; width: 9px; height: 9px; border-radius: 3px; margin-right: 6px; }

/* 波浪条 */
.stats-wave { display: flex; align-items: flex-end; gap: 4px; height: 110px; padding-top: 6px; }
.stats-wave i { flex: 1; position: relative; border-radius: 6px 6px 2px 2px; min-height: 4px;
  background: linear-gradient(180deg, var(--accent), var(--accent-2, #4aa8ff));
  opacity: .28; transition: height .5s cubic-bezier(.2,.8,.2,1), opacity .3s; }
.stats-wave i.has { opacity: 1; }
.stats-wave i.today { box-shadow: 0 0 0 2px var(--accent-soft, rgba(124,92,255,.35)); }
.stats-wave i:hover { filter: brightness(1.15); }
.stats-wave i em { position: absolute; top: -16px; left: 50%; transform: translateX(-50%);
  font-style: normal; font-size: 10px; color: var(--muted); white-space: nowrap; opacity: 0; transition: opacity .2s; }
.stats-wave i:hover em { opacity: 1; }
.stats-days-x { display: flex; gap: 4px; margin-top: 6px; }
.stats-days-x span { flex: 1; text-align: center; font-size: 10px; color: var(--muted); }

/* 排行 */
.stats-rank > div { display: grid; grid-template-columns: minmax(120px, 200px) 1fr auto;
  align-items: center; gap: 12px; padding: 7px 0; font-size: 13px; }
.stats-rank .bar { height: 8px; background: var(--soft); border-radius: 999px; overflow: hidden; }
.stats-rank .bar i { display: block; height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, var(--accent), var(--accent-2, #4aa8ff)); transition: width .6s ease; }
'''
    io.open(CSS, "w", encoding="utf-8", newline="\n").write(c)
    print("③ 样式已写入 extra.css")

# ---------- ④ JS:渲染统计页 ----------
JS = os.path.join(STATIC, "js", "views", "stats.js")
io.open(JS, "w", encoding="utf-8", newline="\n").write('''/* stats.js —— 阅读统计页(圆盘 + 波浪条 + 排行)
   数据:/api/state 里的 stats(轻量,每帧可用)+ 进页面时拉一次 /api/stats(带排行) */
import { $, esc, post, get, toast } from '../core.js';
import { store, registerRender } from '../state.js';

const COLORS = ['#7c5cff', '#4aa8ff', '#39c5a0', '#f0a63a', '#e2566a', '#a06bff', '#2fb3d9'];
let rank = null;              // 各游戏排行(进页面拉一次)
let rankAt = 0;
let lastSig = '';

function fmtTime(sec) {
  sec = Math.round(sec || 0);
  if (sec >= 3600) return (sec / 3600).toFixed(1) + ' 小时';
  if (sec >= 60) return Math.round(sec / 60) + ' 分钟';
  return sec + ' 秒';
}
function fmtDate(ts) {
  if (!ts) return '—';
  const d = new Date(ts * 1000);
  return (d.getMonth() + 1) + ' 月 ' + d.getDate() + ' 日';
}

/* 圆盘:最近 7 天每天的占比 */
function drawDonut(days, total) {
  const svg = $('statsDonut');
  if (!svg) return;
  const R = 46, C = 2 * Math.PI * R;
  const rows = (days || []).slice(-7);
  const sum = rows.reduce((a, b) => a + (b[1] || 0), 0);
  let out = '<circle class="ring-bg" cx="60" cy="60" r="' + R + '"></circle>';
  let acc = 0;
  rows.forEach(([day, n], i) => {
    const frac = sum ? (n / sum) : 0;
    if (frac <= 0) return;
    const len = frac * C;
    out += '<circle class="seg" cx="60" cy="60" r="' + R + '" stroke="' + COLORS[i % COLORS.length] + '"'
      + ' stroke-dasharray="' + len.toFixed(2) + ' ' + (C - len).toFixed(2) + '"'
      + ' stroke-dashoffset="' + (-acc).toFixed(2) + '" transform="rotate(-90 60 60)"></circle>';
    acc += len;
  });
  out += '<text class="hole-t" x="60" y="57">' + (sum ? sum.toLocaleString() : '0') + '</text>';
  out += '<text class="hole-s" x="60" y="70">最近 7 天字数</text>';
  svg.innerHTML = out;

  const lg = $('statsLegend');
  if (lg) {
    lg.innerHTML = rows.length
      ? rows.map(([day, n], i) => '<span><i style="background:' + COLORS[i % COLORS.length] + '"></i>'
          + day.slice(5) + ' · ' + (n || 0).toLocaleString() + '</span>').join('')
      : '<span class="muted sm">还没有数据</span>';
  }
}

/* 波浪条:最近 14 天 */
function drawWave(days) {
  const box = $('statsWave');
  if (!box) return;
  const map = new Map((days || []).map(([d, n]) => [d, n]));
  const out = [], labels = [];
  const today = new Date();
  for (let i = 13; i >= 0; i--) {
    const d = new Date(today.getTime() - i * 86400000);
    const key = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    const n = map.get(key) || 0;
    out.push({ key, n, today: i === 0 });
    labels.push(key.slice(5).replace('-', '/'));
  }
  const max = Math.max(1, ...out.map((x) => x.n));
  box.innerHTML = out.map((x) => '<i class="' + (x.n ? 'has' : '') + (x.today ? ' today' : '')
    + '" style="height:' + Math.max(4, Math.round((x.n / max) * 100)) + '%"'
    + ' title="' + x.key + ':' + x.n.toLocaleString() + ' 字"><em>' + x.n.toLocaleString() + '</em></i>').join('');
  const xb = $('statsWaveX');
  if (xb) xb.innerHTML = labels.map((l) => '<span>' + l + '</span>').join('');
}

async function loadRank(force) {
  if (!force && rank && Date.now() - rankAt < 30000) return rank;
  try {
    const d = await get('/api/stats');
    rank = d.top || [];
    rankAt = Date.now();
  } catch (e) { rank = rank || []; }
  return rank;
}

function drawRank(rows) {
  const box = $('statsRank');
  if (!box) return;
  if (!rows || !rows.length) { box.innerHTML = '<span class="muted sm">还没有记录</span>'; return; }
  const max = Math.max(1, ...rows.map((r) => r.chars));
  box.innerHTML = rows.map((r) => '<div><span>' + esc(r.name || '(未命名)') + '</span>'
    + '<span class="bar"><i style="width:' + Math.round((r.chars / max) * 100) + '%"></i></span>'
    + '<b>' + (r.chars || 0).toLocaleString() + ' 字</b></div>').join('');
}

export function renderStats() {
  const panel = $('view-stats');
  if (!panel) return;
  const st = (store.S || {}).stats;
  if (!st) return;
  const sig = [st.chars, st.lines, st.seconds, st.today, JSON.stringify(st.days), st.name].join('|');
  if (sig !== lastSig) {
    lastSig = sig;
    if ($('statsChars')) $('statsChars').textContent = (st.chars || 0).toLocaleString();
    if ($('statsCharsMini')) $('statsCharsMini').textContent = (st.chars || 0).toLocaleString();
    if ($('statsLines')) $('statsLines').textContent = (st.lines || 0).toLocaleString();
    if ($('statsTime')) $('statsTime').textContent = fmtTime(st.seconds);
    if ($('statsAvg')) $('statsAvg').textContent = st.seconds > 0
      ? Math.round(st.chars / (st.seconds / 60)) + ' 字/分' : '—';
    if ($('statsFirst')) $('statsFirst').textContent = fmtDate(st.first);
    if ($('statsLast')) $('statsLast').textContent = fmtDate(st.last);
    if ($('statsGame')) $('statsGame').textContent = st.name || '还没选游戏';
    if ($('statsToday')) $('statsToday').textContent = st.today
      ? '今天已读 ' + st.today.toLocaleString() + ' 字' : '今天还没开始读';
    /* 连续天数 */
    const ds = (st.days || []).map((d) => d[0]).sort();
    let streak = 0;
    const day = new Date();
    for (;;) {
      const k = day.getFullYear() + '-' + String(day.getMonth() + 1).padStart(2, '0') + '-' + String(day.getDate()).padStart(2, '0');
      if (ds.includes(k)) { streak++; day.setDate(day.getDate() - 1); } else break;
    }
    if ($('statsStreak')) $('statsStreak').textContent = streak + ' 天';
    drawDonut(st.days, st.chars);
    drawWave(st.days);
    loadRank(false).then(drawRank);
  }
}

/* 入口 / 返回 / 清零 */
export function installStatsUI() {
  const open = $('statsOpen');
  if (open) open.onclick = () => {
    window.__lyBackTo = (store.S && store.S.view) || 'realtime';
    const b = document.querySelector('.nav-item[data-view="stats"]');
    if (b) b.click();
    lastSig = '';
    loadRank(true).then(drawRank);
  };
  const back = $('statsBack');
  if (back) back.onclick = () => {
    const v = window.__lyBackTo || 'realtime';
    const b = document.querySelector('.nav-item[data-view="' + v + '"]');
    if (b) b.click();
  };
  const rs = $('statsReset2');
  if (rs) rs.onclick = async () => {
    if (!confirm('只清空【这台游戏】的累计阅读记录,其它游戏不受影响。确定吗?')) return;
    const r = await post('/api/stats/reset', {});
    toast(r.msg || '已清零');
    lastSig = '';
    rank = null;
  };
}

registerRender(renderStats);
''')
print("④ stats.js 已写入")

# 波浪条要有个 x 轴容器
h2 = io.open(P, encoding="utf-8").read()
if 'id="statsWaveX"' not in h2:
    h2 = h2.replace('<div class="stats-wave" id="statsWave"></div>',
                    '<div class="stats-wave" id="statsWave"></div>\n        <div class="stats-days-x" id="statsWaveX"></div>', 1)
    io.open(P, "w", encoding="utf-8", newline="\n").write(h2)
    print("④ x 轴容器已加")

# boot.js:加载 stats.js + installStatsUI
B = os.path.join(STATIC, "js", "boot.js")
b = io.open(B, encoding="utf-8").read()
if "views/stats.js" not in b:
    b = b.replace("installContextMenu();",
                  "installContextMenu();\n"
                  "import('./views/stats.js').then((m) => m.installStatsUI()).catch(() => {});", 1)
    io.open(B, "w", encoding="utf-8", newline="\n").write(b)
    print("④ boot.js 已加载 stats.js")

for f in (JS, B, os.path.join(STATIC, "js", "state.js")):
    r = subprocess.run(["node", "--check", f], capture_output=True, text=True)
    print("   node --check %-12s %s" % (os.path.basename(f), "通过" if r.returncode == 0 else r.stderr[:160]))
