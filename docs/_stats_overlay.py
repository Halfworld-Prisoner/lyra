# -*- coding: utf-8 -*-
r"""按玩家要求改:
   ① 入口按钮**放在第一个区域(实时监控面板的标题栏)**,不再塞在剧情列表下面;
   ② **从左栏移除**「阅读统计」(不进导航);
   ③ 统计页改成**全屏覆盖层**(position:fixed,盖住侧栏与所有内容),左上角返回键;
   ④ 支持 Esc 关闭;支持 ?stats=1 直接打开(便于测试)。
"""
import io
import os
import re
import subprocess

STATIC = r"D:\Unity阅读器\webapp\static"
P = os.path.join(STATIC, "index.html")
h = io.open(P, encoding="utf-8").read()

# ① 删掉之前塞在剧情列表下面的入口卡片
h = re.sub(r'\n      <div class="panel stats-entry">.*?\n      </div>\n', "\n", h, flags=re.S)

# ② 左栏移除「阅读统计」
h = h.replace('  <button class="nav-item" data-view="stats"><i>◔</i><span>阅读统计</span></button>\n', "")

# ③ 把统计页整段抽出来,改成 body 级全屏覆盖层
m = re.search(r'\n    <!-- ---------------- 阅读统计\(独立页面\) ---------------- -->\n    <section class="view" id="view-stats">.*?\n    </section>\n', h, re.S)
assert m, "找不到统计页区块"
block = m.group(0)
h = h[:m.start()] + "\n" + h[m.end():]
inner = block.split('<section class="view" id="view-stats">', 1)[1].rsplit("</section>", 1)[0]
overlay = ('\n<!-- 阅读统计:全屏覆盖层(盖住侧栏与全部内容;左上角返回) -->\n'
           '<div class="stats-overlay" id="view-stats">\n'
           '  <div class="stats-overlay-inner">\n'
           + inner +
           '  </div>\n</div>\n')
h = h.replace("</body>", overlay + "</body>", 1)

# ④ 入口按钮放进第一个区域(实时监控面板标题栏右侧)
if 'id="statsOpen"' not in h:
    h = h.replace('<div class="panel-title">实时监控 <span class="muted sm">最近 60 秒</span></div>',
                  '<div class="panel-title">实时监控 <span class="muted sm">最近 60 秒</span>'
                  '<span class="grow"></span>'
                  '<button class="btn ghost sm" id="statsOpen" title="查看这台游戏的累计阅读统计">'
                  '<i>◔</i> 阅读统计 <b id="statsCharsMini" style="margin-left:6px">0</b> 字</button></div>', 1)
    print("④ 按钮已放进第一个区域")

io.open(P, "w", encoding="utf-8", newline="\n").write(h)

# ⑤ CSS:覆盖层
CSS = os.path.join(STATIC, "css", "extra.css")
c = io.open(CSS, encoding="utf-8").read()
if ".stats-overlay" not in c:
    c += '''

/* 阅读统计:全屏覆盖层(盖住侧栏和所有内容) */
.stats-overlay {
  position: fixed; inset: 0; z-index: 900; display: none;
  background: var(--bg); overflow: auto;
  padding: 18px 22px 28px;
  animation: statsIn .22s ease;
}
.stats-overlay.on { display: block; }
@keyframes statsIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.stats-overlay-inner { max-width: 1180px; margin: 0 auto; display: grid; gap: 12px; }
.stats-entry { display: none; }
'''
    io.open(CSS, "w", encoding="utf-8", newline="\n").write(c)
    print("⑤ 覆盖层样式已加")

# ⑥ JS:开关改成切 class(不再走导航)
JS = os.path.join(STATIC, "js", "views", "stats.js")
s = io.open(JS, encoding="utf-8").read()
old = s[s.find("export function installStatsUI()"):]
new = '''export function installStatsUI() {
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
'''
s = s.replace(old, new)
# 覆盖层一直存在 → renderStats 不用再判断 .view
s = s.replace("  const panel = $('view-stats');\n  if (!panel) return;\n",
              "  if (!$('statsChars')) return;\n")
io.open(JS, "w", encoding="utf-8", newline="\n").write(s)
print("⑥ stats.js 已改为覆盖层开关")

for f in (JS, os.path.join(STATIC, "js", "boot.js")):
    r = subprocess.run(["node", "--check", f], capture_output=True, text=True)
    print("   node --check %-12s %s" % (os.path.basename(f), "通过" if r.returncode == 0 else r.stderr[:180]))
