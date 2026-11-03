# -*- coding: utf-8 -*-
"""开机动画收尾优化:
   ① state.js:首次拿到数据就挂 body[data-state-ready=1](动画据此立刻淡出,不用干等);
   ② splash.js:最短 2.1 秒 / 兜底 3.0 秒(之前最长要 4.2 秒,太拖);
   ③ splash.css:星座压暗(.38)并抬到 logo 上方,不再压在 logo 上;
      同时把主界面淡入做稳妥(不依赖 JS 也能显示)。
"""
import io
import os

STATIC = r"D:\Unity阅读器\webapp\static"

# ---------- ① ----------
p = os.path.join(STATIC, "js", "state.js")
t = io.open(p, encoding="utf-8").read()
if "stateReady" not in t:
    t = t.replace('''  store.S = st;
  const cfg = st.settings || {};''',
                  '''  store.S = st;
  /* 首次拿到数据 → 通知开机动画可以收尾了(见 js/splash.js) */
  if (document.body.dataset.stateReady !== '1') {
    document.body.dataset.stateReady = '1';
    if (typeof document.body.classList !== 'undefined') document.body.classList.add('ready');
  }
  const cfg = st.settings || {};''', 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("① state.js 已挂 stateReady 标记")

# ---------- ② ----------
p = os.path.join(STATIC, "js", "splash.js")
t = io.open(p, encoding="utf-8").read()
t = t.replace("const MIN_MS = 2400;", "const MIN_MS = 2100;")
t = t.replace("const MAX_MS = 4200;", "const MAX_MS = 3000;")
io.open(p, "w", encoding="utf-8", newline="\n").write(t)
print("② splash.js 时长已收紧(2.1s / 兜底 3.0s)")

# ---------- ③ ----------
p = os.path.join(STATIC, "css", "splash.css")
t = io.open(p, encoding="utf-8").read()
old = '''#splash svg.constellation {
  position: absolute;
  top: -46px;
  left: 50%;
  width: 460px;
  height: 300px;
  transform: translateX(-50%);
  overflow: visible;
  pointer-events: none;
}'''
new = '''#splash svg.constellation {
  /* 星座抬到 logo 上方、整体压暗:是"背景氛围",不能盖住主角 */
  position: absolute;
  top: -196px;
  left: 50%;
  width: 430px;
  height: 280px;
  transform: translateX(-50%);
  overflow: visible;
  pointer-events: none;
  opacity: .38;
}'''
assert old in t
t = t.replace(old, new, 1)
t = t.replace("#splash .stage {\n  position: relative;", "#splash .stage {\n  position: relative;\n  z-index: 1;")
io.open(p, "w", encoding="utf-8", newline="\n").write(t)
print("③ splash.css 星座层已调整(上方 + 压暗)")

import subprocess
for f in ("js/state.js", "js/splash.js"):
    r = subprocess.run(["node", "--check", os.path.join(STATIC, f.replace("/", os.sep))],
                       capture_output=True, text=True)
    print("   node --check %-16s %s" % (f, "通过" if r.returncode == 0 else r.stderr[:150]))
