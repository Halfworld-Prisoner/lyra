# -*- coding: utf-8 -*-
"""把开机动画接进应用:
   ① index.html:加 splash.css、插入动画 markup、侧栏加「开机动画」开关;
   ② config.py:新增 splash_on(默认开);
   ③ boot.js:启动时播放动画、首帧数据到位后标记 stateReady;
   ④ settings.js:开关接进 renderSettings + 保存;
   ⑤ 把 logo 图放进 static/img/。
"""
import io
import os
import shutil

SRC = r"D:\Unity阅读器"
STATIC = os.path.join(SRC, "webapp", "static")

# ---------- ⑤ logo 图 ----------
os.makedirs(os.path.join(STATIC, "img"), exist_ok=True)
for cand in (os.path.join(SRC, "installer", "icon-preview-256.png"),
             os.path.join(SRC, "installer", "icon.ico")):
    if os.path.isfile(cand):
        shutil.copy2(cand, os.path.join(STATIC, "img", "logo.png"))
        print("⑤ logo 图已放置:static/img/logo.png(来自 %s)" % os.path.basename(cand))
        break

# ---------- ① index.html ----------
p = os.path.join(STATIC, "index.html")
t = io.open(p, encoding="utf-8").read()

if "splash.css" not in t:
    t = t.replace('<link rel="stylesheet" href="/static/css/extra.css">',
                  '<link rel="stylesheet" href="/static/css/extra.css">\n'
                  '<link rel="stylesheet" href="/static/css/splash.css">', 1)
    print("① splash.css 已引入")

SPLASH_HTML = '''
<!-- ==================== 开机动画(设置里可关)==================== -->
<div id="splash" role="presentation">
  <div class="stars"></div>
  <div class="stars2"></div>
  <div class="stage">
    <!-- 天琴座:织女星 + 那个标志性的平行四边形 -->
    <svg class="constellation" viewBox="0 0 460 300" aria-hidden="true">
      <line x1="300" y1="40"  x2="238" y2="92"></line>
      <line x1="238" y1="92"  x2="140" y2="118"></line>
      <line x1="140" y1="118" x2="92"  y2="206"></line>
      <line x1="92"  y1="206" x2="186" y2="238"></line>
      <line x1="186" y1="238" x2="238" y2="92"></line>
      <circle class="vega" cx="300" cy="40"  r="4.6"></circle>
      <circle cx="238" cy="92"  r="2.8"></circle>
      <circle cx="140" cy="118" r="2.8"></circle>
      <circle cx="92"  cy="206" r="2.8"></circle>
      <circle cx="186" cy="238" r="2.8"></circle>
    </svg>
    <div class="mark"><img src="/static/img/logo.png" alt="Lyra"></div>
    <div class="title"><span>L</span><span>y</span><span>r</span><span>a</span></div>
    <div class="tagline">Unity 游戏朗读器 · 把游戏里的文字念出来</div>
    <div class="bar"><i></i></div>
  </div>
  <div class="skip">点击任意位置跳过</div>
</div>
'''
if 'id="splash"' not in t:
    t = t.replace("<body>\n", "<body>\n" + SPLASH_HTML, 1)
    print("① 动画 markup 已插入")

# 侧栏加开关
old_theme = '''      </div>
    </div>
    <div class="gauge">'''
new_theme = '''      </div>
      <label class="switch splash-sw" title="启动时播放的开机动画(天琴座星座 + Logo)">
        <input id="splashOn" type="checkbox"><i></i><span>开机动画</span>
      </label>
    </div>
    <div class="gauge">'''
if 'id="splashOn"' not in t:
    t = t.replace(old_theme, new_theme, 1)
    print("① 侧栏「开机动画」开关已加")
io.open(p, "w", encoding="utf-8", newline="\n").write(t)

# ---------- ② config.py ----------
p = os.path.join(SRC, "config.py")
c = io.open(p, encoding="utf-8").read()
if "splash_on" not in c:
    c = c.replace('    "theme": "dark",',
                  '    "theme": "dark",\n'
                  '    "splash_on": True,               # 启动时播放开机动画(天琴座星座 + Logo)', 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(c)
    print("② config.py 已加 splash_on(默认开)")

# ---------- ③ boot.js ----------
p = os.path.join(STATIC, "js", "boot.js")
b = io.open(p, encoding="utf-8").read()
if "playSplash" not in b:
    b = b.replace("/* ---------------- 启动 ---------------- */\nstartWave();",
                  '''/* ---------------- 启动 ---------------- */
/* 开机动画:先放动画,数据到位后再淡出(动画在 css/splash.css 里,纯 CSS/SVG) */
import('./splash.js').then((m) => {
  m.playSplash((window.store && window.store.S && window.store.S.settings) || null);
}).catch(() => { document.body.classList.add('ready'); });
startWave();''', 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(b)
    print("③ boot.js 已接入动画")

# ---------- ④ settings.js:开关接线 ----------
p = os.path.join(STATIC, "js", "views", "settings.js")
s = io.open(p, encoding="utf-8").read()
if "splashOn" not in s:
    s = s.replace("""/* 玩家刚动过的控件:1.2 秒内不要被刷新覆盖(后端回值有时间差) */""",
                  """/* 开机动画开关(侧栏) */
if ($('splashOn')) {
  $('splashOn').onchange = (e) => {
    post('/api/settings', { splash_on: e.target.checked })
      .then(() => toast(e.target.checked ? '开机动画已打开' : '已关闭开机动画'));
  };
}

/* 玩家刚动过的控件:1.2 秒内不要被刷新覆盖(后端回值有时间差) */""", 1)
    s = s.replace("  ['castOn',            (s) => s.cast_on],",
                  "  ['castOn',            (s) => s.cast_on],\n"
                  "  ['splashOn',          (s) => s.splash_on],", 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("④ settings.js 已接线(保存 + 回显)")

# ---------- 让主界面在动画结束后淡入(纯装饰,失败也不影响使用)----------
p = os.path.join(STATIC, "css", "splash.css")
css = io.open(p, encoding="utf-8").read()
if "body.ready .app" not in css:
    css += '''
/* 动画结束后主界面淡入(不做隐藏,避免 JS 出错时白屏) */
.app { opacity: .001; transition: opacity .5s ease .05s; }
body.ready .app { opacity: 1; }
'''
    io.open(p, "w", encoding="utf-8", newline="\n").write(css)
    print("   已加主界面淡入")

import subprocess
for f in ("js/boot.js", "js/splash.js", "js/views/settings.js"):
    r = subprocess.run(["node", "--check", os.path.join(STATIC, f.replace("/", os.sep))],
                       capture_output=True, text=True)
    print("   node --check %-22s %s" % (f, "通过" if r.returncode == 0 else r.stderr[:160]))
