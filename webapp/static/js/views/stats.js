/* stats.js —— 阅读统计页(圆盘 + 波浪条 + 排行)
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
  if (!$('statsChars')) return;
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
  const back = $('statsBack');
  const ov = $('view-stats');
  const show = () => {
    if (!ov) return;
    ov.classList.add('on');
    document.body.classList.add('stats-open');
    lastSig = '';
    loadRank(true).then(drawRank);
    renderStats();
  };
  const hide = () => {
    if (!ov) return;
    ov.classList.remove('on');
    document.body.classList.remove('stats-open');
  };
  if (open) open.onclick = show;
  if (back) back.onclick = hide;
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(); });
  /* ?stats=1 直接打开(方便测试/分享) */
  try {
    if (new URLSearchParams(location.search).get('stats')) setTimeout(show, 600);
  } catch (e) { /* 忽略 */ }
  const rs = $('statsReset2');
  if (rs) rs.onclick = async () => {
    if (!confirm('只清空【这台游戏】的累计阅读记录,其它游戏不受影响。确定吗?')) return;
    const r = await post('/api/stats/reset', {});
    toast(r.msg || '已清零');
    lastSig = '';
    rank = null;
    renderStats();
  };
}

registerRender(renderStats);
