# -*- coding: utf-8 -*-
"""把「开机动画」开关删掉 —— 动画改为强制播放。

改动:
  ① index.html:删掉侧栏那个开关;
  ② settings.js:删掉它的 onchange 处理与回显表项;
  ③ splash.js:不再读配置(splashEnabled 恒为 true);
  ④ boot.js:启动即播放,不用等数据(动画更早开始);
  ⑤ config.py / server.py:去掉 splash_on 配置项与接口字段(保持配置干净)。
"""
import io
import os
import subprocess

SRC = r"D:\Unity阅读器"
STATIC = os.path.join(SRC, "webapp", "static")


def patch(path, pairs, must=True):
    t = io.open(path, encoding="utf-8").read()
    for old, new in pairs:
        if old in t:
            t = t.replace(old, new, 1)
            print("  OK   %-22s %s" % (os.path.basename(path), old.strip().split("\n")[0][:48]))
        elif must:
            print("  --   %-22s 未匹配: %s" % (os.path.basename(path), old.strip().split("\n")[0][:48]))
    io.open(path, "w", encoding="utf-8", newline="\n").write(t)


# ① 删掉侧栏开关
patch(os.path.join(STATIC, "index.html"), [(
    '''      <label class="switch splash-sw" title="启动时播放的开机动画(天琴座星座 + Logo)">
        <input id="splashOn" type="checkbox"><i></i><span>开机动画</span>
      </label>
''', "")])

# ② settings.js
patch(os.path.join(STATIC, "js", "views", "settings.js"), [
    ('''/* 开机动画开关(侧栏) */
if ($('splashOn')) {
  $('splashOn').onchange = (e) => {
    post('/api/settings', { splash_on: e.target.checked })
      .then(() => toast(e.target.checked ? '开机动画已打开' : '已关闭开机动画'));
  };
}

''', ""),
    ("  ['splashOn',          (s) => s.splash_on !== false],   // 缺省=开\n", ""),
])

# ③ splash.js:强制播放
patch(os.path.join(STATIC, "js", "splash.js"), [
    ('''export function splashEnabled(cfg) {
  if (localStorage.getItem('lyra_splash') === 'off') return false;      // 本机临时关
  if (cfg && cfg.splash_on === false) return false;                    // 设置里关
  try {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
  } catch (e) { /* 老引擎没有 matchMedia,照常播 */ }
  return true;
}''',
     '''export function splashEnabled() {
  /* 开机动画是固定流程(玩家要求:不做开关)。
     只保留一条本机调试用的逃生口:控制台执行 lyraSplashOff() 可临时关掉,
     以及系统「减少动态效果」时不动画。 */
  if (localStorage.getItem('lyra_splash') === 'off') return false;
  try {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
  } catch (e) { /* 老引擎没有 matchMedia,照常播 */ }
  return true;
}'''),
    ('''export function playSplash(cfg) {
  const box = $('splash');
  if (!box || !splashEnabled(cfg)) {''',
     '''export function playSplash() {
  const box = $('splash');
  if (!box || !splashEnabled()) {'''),
    ('''/**
 * 播放开机动画。
 * @param {{splash_on?:boolean}} cfg 当前配置
 * @returns {Promise<void>} 动画结束(或被跳过)后 resolve
 */''',
     '''/**
 * 播放开机动画(固定流程,没有开关)。
 * @returns {Promise<void>} 动画结束(或被跳过)后 resolve
 */'''),
])

# ④ boot.js:启动即播
patch(os.path.join(STATIC, "js", "boot.js"), [(
    '''/* ★先取一次数据,再决定要不要放开机动画★
   以前这里直接 playSplash(store.S.settings),可那一刻数据还没到,
   于是"关掉动画"的设置不生效(总按默认开播)。现在等首帧数据回来再判断;
   关掉的话立刻撤掉遮罩,不会闪。动画本身在 css/splash.css + js/splash.js 里。 */
refresh().then(() => import('./splash.js')
  .then((m) => m.playSplash((store.S && store.S.settings) || null))
  .catch(() => document.body.classList.add('ready')))
  .catch(() => document.body.classList.add('ready'));

setInterval(refresh, 400);      /* 刷新间隔:越小越跟手 */''',
    '''/* 开机动画:固定流程,立刻开始播(动画在 css/splash.css + js/splash.js)
   数据到位后(state.js 会挂 stateReady)动画自动收尾进主界面;
   点击 / 按键也可以立刻跳过。 */
import('./splash.js')
  .then((m) => m.playSplash())
  .catch(() => document.body.classList.add('ready'));
refresh();
setInterval(refresh, 400);      /* 刷新间隔:越小越跟手 */''')])

# ⑤ 去掉配置项与接口字段
patch(os.path.join(SRC, "config.py"), [
    ('    "splash_on": True,               # 启动时播放开机动画(天琴座星座 + Logo)\n', "")])
patch(os.path.join(SRC, "webapp", "server.py"), [
    ('                        "splash_on": cfg.get("splash_on", True) is not False,   # 开机动画(缺省开)\n', "")],
    must=False)

for f in ("js/boot.js", "js/splash.js", "js/views/settings.js"):
    r = subprocess.run(["node", "--check", os.path.join(STATIC, f.replace("/", os.sep))],
                       capture_output=True, text=True)
    print("   node --check %-22s %s" % (f, "通过" if r.returncode == 0 else r.stderr[:150]))
