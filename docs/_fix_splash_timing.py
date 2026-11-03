# -*- coding: utf-8 -*-
"""修「关掉开机动画后仍然播放」。

根因:boot.js 在页面刚加载时就调 playSplash(store.S.settings),而那一刻
      store.S 还是空的(首次 /api/state 还没回来)→ 只能按"默认开"处理。
修法:先等首帧数据(refresh 完成)再决定放不放;关掉时立刻撤掉遮罩,不会闪一下。
"""
import io
import os
import subprocess

STATIC = r"D:\Unity阅读器\webapp\static"
p = os.path.join(STATIC, "js", "boot.js")
t = io.open(p, encoding="utf-8").read()

old = '''/* 开机动画:先放动画,数据到位后再淡出(动画在 css/splash.css 里,纯 CSS/SVG) */
import('./splash.js').then((m) => {
  m.playSplash((window.store && window.store.S && window.store.S.settings) || null);
}).catch(() => { document.body.classList.add('ready'); });
startWave();
installContextMenu();
refresh();
setInterval(refresh, 400);      /* 刷新间隔:越小越跟手 */'''

new = '''startWave();
installContextMenu();

/* ★先取一次数据,再决定要不要放开机动画★
   以前这里直接 playSplash(store.S.settings),可那一刻数据还没到,
   于是"关掉动画"的设置不生效(总按默认开播)。现在等首帧数据回来再判断;
   关掉的话立刻撤掉遮罩,不会闪。动画本身在 css/splash.css + js/splash.js 里。 */
refresh().then(() => import('./splash.js')
  .then((m) => m.playSplash((store.S && store.S.settings) || null))
  .catch(() => document.body.classList.add('ready')))
  .catch(() => document.body.classList.add('ready'));

setInterval(refresh, 400);      /* 刷新间隔:越小越跟手 */'''

assert old in t, "boot.js 那段没匹配"
t = t.replace(old, new, 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(t)
print("boot.js 已改：等首帧数据再决定动画")
r = subprocess.run(["node", "--check", p], capture_output=True, text=True)
print("node --check:", "通过" if r.returncode == 0 else r.stderr[:200])
