# -*- coding: utf-8 -*-
r"""实时剧情页新增「累计阅读」面板:
   · 大字:这台游戏一共读了多少字(永久累计)
   · 副行:句数 · 阅读时长 · 首次开始 · 最近一次 · 今天读了多少
   · 最近 7 天迷你柱状
   · 「清零」按钮(二次确认)
"""
import io
import os
import subprocess

STATIC = r"D:\Unity阅读器\webapp\static"

# ---------------- ① index.html:面板 ----------------
P = os.path.join(STATIC, "index.html")
h = io.open(P, encoding="utf-8").read()
PANEL = '''
      <div class="panel" id="statsPanel">
        <div class="panel-title">累计阅读 <span class="muted sm">这台游戏一共读了多少字 · 永久记录,关了也不会丢</span>
          <span class="grow"></span>
          <span class="muted sm" id="statsPath" title="记录文件位置"></span>
          <button class="btn ghost sm" id="statsReset" title="只清空这台游戏的累计记录">清零</button>
        </div>
        <div class="stat-big">
          <b id="statsChars">0</b><span>字</span>
          <em id="statsToday"></em>
        </div>
        <div class="mini-stats">
          <div><span>累计句数</span><b id="statsLines">0</b></div>
          <div><span>阅读时长</span><b id="statsTime">—</b></div>
          <div><span>首次开始</span><b id="statsFirst">—</b></div>
          <div><span>最近一次</span><b id="statsLast">—</b></div>
        </div>
        <div class="stat-days" id="statsDays" title="最近 7 天每天读了多少字"></div>
        <p class="muted sm" style="margin:8px 0 0">
          记录保存在 <b>%LOCALAPPDATA%\\Lyra\\readstats.json</b>,按游戏分开记 —— 关软件、重启、换游戏都会继续累加。
        </p>
      </div>
'''
if 'id="statsPanel"' not in h:
    anchor = '    <!-- ---------------- 角色配音 ---------------- -->'
    assert anchor in h, "找不到插入点"
    h = h.replace(anchor, PANEL + "\n" + anchor, 1)
    io.open(P, "w", encoding="utf-8", newline="\n").write(h)
    print("① 实时剧情页已加面板")

# ---------------- ② CSS ----------------
C = os.path.join(STATIC, "css", "app.css")
if os.path.isfile(C):
    c = io.open(C, encoding="utf-8").read()
    if ".stat-big" not in c:
        c += '''

/* ---- 累计阅读(实时剧情页) ---- */
.stat-big { display: flex; align-items: baseline; gap: 8px; margin: 4px 0 12px; }
.stat-big b { font-size: 40px; font-weight: 700; letter-spacing: .01em;
  background: linear-gradient(135deg, var(--accent), var(--accent-2, #4aa8ff));
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.stat-big span { color: var(--muted); font-size: 14px; }
.stat-big em { margin-left: auto; font-style: normal; color: var(--muted); font-size: 12.5px; }
.stat-days { display: flex; align-items: flex-end; gap: 6px; height: 54px; margin-top: 10px; }
.stat-days i { flex: 1; background: var(--soft); border-radius: 4px 4px 0 0; position: relative; min-height: 3px; }
.stat-days i.on { background: linear-gradient(180deg, var(--accent), var(--accent-2, #4aa8ff)); }
.stat-days i em { position: absolute; left: 50%; transform: translateX(-50%); bottom: -16px;
  font-style: normal; font-size: 10px; color: var(--muted); white-space: nowrap; }
'''
        io.open(C, "w", encoding="utf-8", newline="\n").write(c)
        print("② 样式已加(app.css)")
    else:
        print("② 样式已存在")
else:
    print("② !! 找不到 app.css")

# ---------------- ③ state.js:渲染 ----------------
S = os.path.join(STATIC, "js", "state.js")
s = io.open(S, encoding="utf-8").read()
if "statsChars" not in s:
    RENDER = '''
  /* 累计阅读(永久记录):只在数值变化时改 DOM,免得每 400ms 重排 */
  const sta = st.stats;
  if (sta && $('statsChars')) {
    const sig = [sta.chars, sta.lines, sta.seconds, sta.today, JSON.stringify(sta.days)].join('|');
    if ($('statsChars').dataset.sig !== sig) {
      $('statsChars').dataset.sig = sig;
      $('statsChars').textContent = (sta.chars || 0).toLocaleString();
      $('statsLines').textContent = (sta.lines || 0).toLocaleString();
      const sec = sta.seconds || 0;
      $('statsTime').textContent = sec >= 3600 ? (sec / 3600).toFixed(1) + ' 小时'
        : (sec >= 60 ? Math.round(sec / 60) + ' 分钟' : Math.round(sec) + ' 秒');
      const fmt = (ts) => {
        if (!ts) return '—';
        const d = new Date(ts * 1000);
        return (d.getMonth() + 1) + '月' + d.getDate() + '日 '
          + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
      };
      $('statsFirst').textContent = fmt(sta.first);
      $('statsLast').textContent = fmt(sta.last);
      $('statsToday').textContent = sta.today ? ('今天 +' + sta.today.toLocaleString() + ' 字') : '';
      if ($('statsPath')) $('statsPath').textContent = sta.games > 1 ? ('共 ' + sta.games + ' 台游戏') : '';
      const box = $('statsDays');
      const days = sta.days || [];
      const max = Math.max(1, ...days.map((d) => d[1]));
      box.innerHTML = days.length
        ? days.map(([day, n]) => {
            const hh = Math.max(3, Math.round((n / max) * 46));
            const dd = day.slice(5).replace('-', '/');
            return `<i class="${n ? 'on' : ''}" style="height:${hh}px" title="${day}:${n} 字"><em>${dd}</em></i>`;
          }).join('')
        : '<span class="muted sm">还没有记录 —— 去读一段剧情吧</span>';
    }
  }
'''
    anchor = "  /* 主题(以配置为准) */"
    assert anchor in s, "state.js 找不到插入点"
    s = s.replace(anchor, RENDER + "\n" + anchor, 1)
    io.open(S, "w", encoding="utf-8", newline="\n").write(s)
    print("③ 渲染已加(state.js)")
else:
    print("③ 渲染已存在")

# 清零按钮
B = os.path.join(STATIC, "js", "boot.js")
b = io.open(B, encoding="utf-8").read()
if "statsReset" not in b:
    b = b.replace("startWave();",
                  '''/* 累计阅读清零(二次确认) */
if ($('statsReset')) $('statsReset').onclick = async () => {
  if (!confirm('只清空【这台游戏】的累计阅读记录,其它游戏的记录不受影响。确定吗?')) return;
  const r = await post('/api/stats/reset', {});
  toast(r.msg || '已清零');
  const c = $('statsChars'); if (c) c.dataset.sig = '';      // 让下一帧重画
};

startWave();''', 1)
    io.open(B, "w", encoding="utf-8", newline="\n").write(b)
    print("④ 清零按钮已接(boot.js)")

r = subprocess.run(["node", "--check", S], capture_output=True, text=True)
print("   node --check state.js:", "通过" if r.returncode == 0 else r.stderr[:200])
r = subprocess.run(["node", "--check", B], capture_output=True, text=True)
print("   node --check boot.js :", "通过" if r.returncode == 0 else r.stderr[:200])
