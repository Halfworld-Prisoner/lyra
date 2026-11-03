# -*- coding: utf-8 -*-
r"""退场动画改成明显的"反向收起":
   · 卡片**依次下沉 + 缩小 + 淡出**(从下往上,依次 0/30/60/90ms)
   · 整层背景同时淡出,总时长 0.3s(原来只有 0.2s 的纯淡出,几乎看不见)
   · 加 ?stats=1&autoclose=1 调试参数:打开 2 秒后自动关闭,方便截中间帧
"""
import io
import os
import subprocess

STATIC = r"D:\Unity阅读器\webapp\static"
CSS = os.path.join(STATIC, "css", "extra.css")
c = io.open(CSS, encoding="utf-8").read()

# 换掉退场相关规则
c = c.replace(".stats-overlay.closing { animation: statsBgOut .22s ease both; pointer-events: none; }",
              ".stats-overlay.closing { animation: statsBgOut .3s ease both; pointer-events: none; }")
c = c.replace('''.stats-overlay.closing .stats-overlay-inner { animation: statsCardOut .2s ease both; }
@keyframes statsCardOut { from { opacity: 1; transform: none; } to { opacity: 0; transform: translateY(10px) scale(.99); } }''',
'''.stats-overlay.closing .stats-overlay-inner > * { animation: statsCardOut .3s cubic-bezier(.4, 0, .75, .25) both; }
.stats-overlay.closing .stats-overlay-inner > *:nth-child(1) { animation-delay: 0ms; }
.stats-overlay.closing .stats-overlay-inner > *:nth-child(2) { animation-delay: 30ms; }
.stats-overlay.closing .stats-overlay-inner > *:nth-child(3) { animation-delay: 60ms; }
.stats-overlay.closing .stats-overlay-inner > *:nth-child(4) { animation-delay: 90ms; }
.stats-overlay.closing .stats-overlay-inner > *:nth-child(5) { animation-delay: 120ms; }
@keyframes statsCardOut {
  from { opacity: 1; transform: none; }
  to   { opacity: 0; transform: translateY(34px) scale(.965); }
}''')
# 大数字也一起收
c = c.replace('.stats-overlay.closing .stats-overlay-inner { animation',
              '.stats-overlay.closing .stat-big b, .stats-overlay.closing .stats-overlay-inner { animation')
io.open(CSS, "w", encoding="utf-8", newline="\n").write(c)
print("① CSS 退场动画已加强")

JS = os.path.join(STATIC, "js", "views", "stats.js")
s = io.open(JS, encoding="utf-8").read()
s = s.replace("    }, 210);", "    }, 340);")
if "autoclose" not in s:
    s = s.replace("""  try {
    if (new URLSearchParams(location.search).get('stats')) setTimeout(show, 600);
  } catch (e) { /* 忽略 */ }""",
"""  try {
    const q = new URLSearchParams(location.search);
    if (q.get('stats')) setTimeout(show, 600);
    if (q.get('autoclose')) setTimeout(() => { show(); setTimeout(hide, 2000); }, 600);   // 调试用
  } catch (e) { /* 忽略 */ }""")
    print("② 已加 autoclose 调试参数")
io.open(JS, "w", encoding="utf-8", newline="\n").write(s)

r = subprocess.run(["node", "--check", JS], capture_output=True, text=True)
print("   node --check:", "通过" if r.returncode == 0 else r.stderr[:180])

for f in ("css/extra.css", "js/views/stats.js"):
    src = os.path.join(STATIC, f.replace("/", os.sep))
    dst = os.path.join(r"D:\Lyra\app\webapp\static", f.replace("/", os.sep))
    import shutil
    shutil.copy2(src, dst)
print("   已部署")
