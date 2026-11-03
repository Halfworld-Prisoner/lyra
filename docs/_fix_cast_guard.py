# -*- coding: utf-8 -*-
"""角色配音页:改完下拉后 15 秒内不重建 DOM(上次这条补丁因为引号写错没生效)。"""
import io

p = r"D:\Unity阅读器\webapp\static\js\views\cast.js"
t = io.open(p, encoding="utf-8").read()
MARK = "选了一秒就被刷新掉"
if MARK in t:
    print("已经有了")
else:
    t += """

/* 玩家在这一页改任何下拉/输入之后,都进入"忙碌"窗口(15 秒内不重建 DOM):
   否则 0.4 秒一次的刷新会把刚选好的值刷回旧的 —— 玩家反馈"选了一秒就被刷新掉"。 */
document.addEventListener('change', (e) => {
  const el = e.target;
  if (el && el.closest && el.closest('#view-cast')) _castBusySince = Date.now();
}, true);
document.addEventListener('input', (e) => {
  const el = e.target;
  if (el && el.closest && (el.closest('#view-cast') || el.id === 'castVoice')) {
    _castBusySince = Date.now();
  }
}, true);
"""
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("cast.js:已加守卫(改动后 15 秒不重建)")
