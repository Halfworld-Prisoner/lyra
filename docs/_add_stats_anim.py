# -*- coding: utf-8 -*-
r"""给统计页加进入/退出动画:
   进入:背景淡入 → 卡片逐块升起(错开 60ms)→ 圆盘"自己画出来" → 波浪条从底部长出 → 大数字滚动
   退出:整页轻微下沉淡出 → 动画结束再真正关闭
   Esc / 返回 都走同一套退出动画。
"""
import io
import os
import re
import subprocess

STATIC = r"D:\Unity阅读器\webapp\static"

# ---------------- ① CSS ----------------
CSS = os.path.join(STATIC, "css", "extra.css")
c = io.open(CSS, encoding="utf-8").read()
c = re.sub(r"/\* 阅读统计:全屏覆盖层.*?(?=\n/\* |\Z)", "", c, flags=re.S)   # 去掉旧覆盖层样式
c += '''

/* ================= 阅读统计:全屏覆盖层 + 进出动画 ================= */
.stats-overlay {
  position: fixed; inset: 0; z-index: 900; display: none;
  background: var(--bg); overflow: auto; padding: 18px 22px 28px;
}
.stats-overlay.on { display: block; animation: statsBgIn .26s ease both; }
.stats-overlay.closing { animation: statsBgOut .22s ease both; pointer-events: none; }
.stats-overlay-inner { max-width: 1180px; margin: 0 auto; display: grid; gap: 12px; }

/* 背景 */
@keyframes statsBgIn  { from { opacity: 0; backdrop-filter: blur(0); } to { opacity: 1; } }
@keyframes statsBgOut { from { opacity: 1; } to { opacity: 0; } }

/* 卡片逐块升起(进入) */
.stats-overlay.on .stats-overlay-inner > * { animation: statsCardIn .42s cubic-bezier(.2,.8,.2,1) both; }
.stats-overlay.on .stats-overlay-inner > *:nth-child(1) { animation-delay: .02s; }
.stats-overlay.on .stats-overlay-inner > *:nth-child(2) { animation-delay: .08s; }
.stats-overlay.on .stats-overlay-inner > *:nth-child(3) { animation-delay: .14s; }
.stats-overlay.on .stats-overlay-inner > *:nth-child(4) { animation-delay: .20s; }
.stats-overlay.on .stats-overlay-inner > *:nth-child(5) { animation-delay: .26s; }
@keyframes statsCardIn {
  from { opacity: 0; transform: translateY(16px) scale(.985); }
  to   { opacity: 1; transform: none; }
}
/* 退出:整页下沉淡出 */
.stats-overlay.closing .stats-overlay-inner { animation: statsCardOut .2s ease both; }
@keyframes statsCardOut { from { opacity: 1; transform: none; } to { opacity: 0; transform: translateY(10px) scale(.99); } }

/* 大数字:进入时轻微放大 */
.stats-overlay.on .stat-big b { animation: statNum .5s cubic-bezier(.2,.9,.25,1) both; animation-delay: .18s; }
@keyframes statNum { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

/* 圆盘:自己画出来(每段依次铺开) */
.stats-donut .seg { stroke-dasharray: 0 999; transition: stroke-dasharray .85s cubic-bezier(.3,.9,.3,1); }
.stats-overlay.drawn .stats-donut .seg { transition: stroke-dasharray .85s cubic-bezier(.3,.9,.3,1); }
.stats-donut .hole-t, .stats-donut .hole-s { opacity: 0; transition: opacity .5s ease .35s; }
.stats-overlay.drawn .stats-donut .hole-t,
.stats-overlay.drawn .stats-donut .hole-s { opacity: 1; }

/* 波浪条:从底部长出来 */
.stats-wave i { transform-origin: bottom center; height: 0 !important; transition: height .55s cubic-bezier(.2,.8,.2,1); }
.stats-overlay.drawn .stats-wave i { height: var(--hh, 4%) !important; }
.stats-wave i { animation: none; }

/* 排行条:从 0 展开 */
.stats-rank .bar i { width: 0 !important; transition: width .7s cubic-bezier(.2,.8,.2,1); }
.stats-overlay.drawn .stats-rank .bar i { width: var(--ww, 0%) !important; }

@media (prefers-reduced-motion: reduce) {
  .stats-overlay.on, .stats-overlay.closing,
  .stats-overlay.on .stats-overlay-inner > *, .stats-overlay.on .stat-big b { animation: none !important; }
  .stats-donut .seg, .stats-wave i, .stats-rank .bar i { transition: none !important; }
}

.stats-entry { display: none; }
'''
io.open(CSS, "w", encoding="utf-8", newline="\n").write(c)
print("① CSS 动画已写入")

# ---------------- ② JS:两段式(drawn)触发 + 退出动画 ----------------
JS = os.path.join(STATIC, "js", "views", "stats.js")
s = io.open(JS, encoding="utf-8").read()

# 波浪条/排行条改成写 CSS 变量,交给 CSS 过渡
s = s.replace("""  box.innerHTML = out.map((x) => '<i class="' + (x.n ? 'has' : '') + (x.today ? ' today' : '')
    + '" style="height:' + Math.max(4, Math.round((x.n / max) * 100)) + '%"'
    + ' title="' + x.key + ':' + x.n.toLocaleString() + ' 字"><em>' + x.n.toLocaleString() + '</em></i>').join('');""",
"""  box.innerHTML = out.map((x, i) => '<i class="' + (x.n ? 'has' : '') + (x.today ? ' today' : '')
    + '" style="--hh:' + Math.max(4, Math.round((x.n / max) * 100)) + '%;transition-delay:' + (i * 28) + 'ms"'
    + ' title="' + x.key + ':' + x.n.toLocaleString() + ' 字"><em>' + x.n.toLocaleString() + '</em></i>').join('');""")

s = s.replace("""  box.innerHTML = rows.map((r) => '<div><span>' + esc(r.name || '(未命名)') + '</span>'
    + '<span class="bar"><i style="width:' + Math.round((r.chars / max) * 100) + '%"></i></span>'
    + '<b>' + (r.chars || 0).toLocaleString() + ' 字</b></div>').join('');""",
"""  box.innerHTML = rows.map((r, i) => '<div><span>' + esc(r.name || '(未命名)') + '</span>'
    + '<span class="bar"><i style="--ww:' + Math.round((r.chars / max) * 100) + '%;transition-delay:' + (i * 60) + 'ms"></i></span>'
    + '<b>' + (r.chars || 0).toLocaleString() + ' 字</b></div>').join('');""")

# 打开/关闭
old = s[s.find("export function installStatsUI()"):]
new = '''/* 数字滚动(只在打开时做一次,免得每帧都在动) */
function countUp(el, to, ms) {
  if (!el) return;
  const from = Number(String(el.textContent).replace(/[^\\d]/g, '')) || 0;
  if (from === to) { el.textContent = to.toLocaleString(); return; }
  const t0 = performance.now();
  const step = (now) => {
    const k = Math.min(1, (now - t0) / (ms || 650));
    const v = Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3)));
    el.textContent = v.toLocaleString();
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

export function installStatsUI() {
  const open = $('statsOpen');
  const back = $('statsBack');
  const ov = $('view-stats');

  const show = () => {
    if (!ov) return;
    ov.classList.remove('closing');
    ov.classList.remove('drawn');            // 先回到"未绘制"状态
    ov.classList.add('on');
    void ov.offsetWidth;                     // 强制重排,让动画从头播
    lastSig = '';                            // 重画图表(圆盘/波浪条从 0 开始)
    renderStats();
    loadRank(true).then((rows) => { drawRank(rows); requestAnimationFrame(() => ov.classList.add('drawn')); });
    requestAnimationFrame(() => ov.classList.add('drawn'));
    const st = (store.S || {}).stats || {};
    countUp($('statsChars'), st.chars || 0, 700);
    countUp($('statsCharsMini'), st.chars || 0, 700);
  };

  const hide = () => {
    if (!ov || !ov.classList.contains('on')) return;
    ov.classList.add('closing');             // 先播退出动画
    setTimeout(() => {
      ov.classList.remove('on', 'closing', 'drawn');
      document.body.classList.remove('stats-open');
    }, 210);
  };

  if (open) open.onclick = show;
  if (back) back.onclick = hide;
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(); });
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
'''
s = s.replace(old, new)
io.open(JS, "w", encoding="utf-8", newline="\n").write(s)
print("② JS 已加两段式动画触发")

r = subprocess.run(["node", "--check", JS], capture_output=True, text=True)
print("   node --check stats.js:", "通过" if r.returncode == 0 else r.stderr[:200])
