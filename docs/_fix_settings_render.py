# -*- coding: utf-8 -*-
"""补回设置页的「配置 → 界面」渲染。

bug:前端只有翻译页写了开关渲染,设置页的开关**从来没有从配置读回界面**,
     所以每次重启软件,开关全显示成 HTML 默认的"关",而后端其实一直开着
     (玩家反馈:"功能在跑,界面显示关闭")。

做法:在 settings.js 末尾加 renderSettings(),把每个控件的值从 store.S.settings 同步过去:
  · 正在被点的控件、或刚点过 1.2 秒内的控件**不覆盖**(避免和玩家抢);
  · 只在值真的不同的时候写,避免每 0.4 秒的无谓 DOM 操作。
"""
import io

JS = r"D:\Unity阅读器\webapp\static\js\views\settings.js"
t = io.open(JS, encoding="utf-8").read()
if "renderSettings" in t:
    print("  已存在 renderSettings,跳过")
else:
    t += '''

/* ---------------- 配置 → 界面:把开关/数值/下拉的状态画出来 ----------------
   以前**没有这段**,于是重启后开关全显示成"关"(HTML 默认值),但后端其实是开的,
   玩家会以为设置没生效。注意:正在操作的控件不覆盖,免得和点击打架。 */
const _SWITCHES = [
  ['strict',            (s) => (s.hook || {}).strict],
  ['interrupt',         (s) => (s.hook || {}).interrupt],
  ['autoNext',          (s) => s.auto_next],
  ['autoNextSilent',    (s) => s.auto_next_silent],
  ['autoNextFallback',  (s) => s.auto_next_fallback],
  ['autoNextBlank',     (s) => s.auto_next_blank],
  ['onTop',             (s) => s.on_top],
  ['watchGame',         (s) => s.watch_game],
  ['floatOn',           (s) => s.float_on],
  ['bbAuto',            (s) => s.auto_say],
  ['sayName',           (s) => s.say_name],
  ['castOn',            (s) => s.cast_on],
];
const _NUMBERS = [
  ['minCjk',            (s) => (s.hook || {}).min_cjk],
  ['autoNextDelay',     (s) => s.auto_next_delay],
  ['autoNextBlankWait', (s) => s.auto_next_blank_wait],
  ['floatCorner',       (s) => s.float_corner],
];
const _SELECTS = [
  ['autoNextPoint',     (s) => s.auto_next_point],
  ['hookProxy',         (s) => s.hook_proxy],
  ['hookProfile',       (s) => s.hook_profile],
];

/* 玩家刚动过的控件:1.2 秒内不要被刷新覆盖(后端回值有时间差) */
document.addEventListener('change', (e) => {
  const el = e.target;
  if (el && el.id) {
    el.__lyTouched = Date.now();
    setTimeout(() => { el.__lyTouched = 0; }, 1200);
  }
}, true);

export function renderSettings() {
  const s = store.S.settings || {};
  const busy = (el) => el === document.activeElement || (el.__lyTouched && Date.now() - el.__lyTouched < 1200);

  for (const [id, get] of _SWITCHES) {
    const el = $('id') && $(id);
    if (!el || busy(el)) continue;
    const v = !!get(s);
    if (el.checked !== v) el.checked = v;
  }
  for (const [id, get] of _NUMBERS) {
    const el = $(id);
    if (!el || busy(el)) continue;
    const v = get(s);
    if (v === undefined || v === null) continue;
    if (String(el.value) !== String(v)) el.value = String(v);
  }
  for (const [id, get] of _SELECTS) {
    const el = $(id);
    if (!el || busy(el)) continue;
    const v = get(s);
    if (v === undefined || v === null || v === '') continue;
    if (el.value !== String(v)) el.value = String(v);
  }
  /* 额外过滤词(逗号分隔) */
  const ew = $('extraWords');
  if (ew && !busy(ew)) {
    const want = (((s.hook || {}).extra_words) || []).join(',');
    if (document.activeElement !== ew && ew.value !== want) ew.value = want;
  }
}

registerRender(renderSettings);
'''
    io.open(JS, "w", encoding="utf-8", newline="\n").write(t)
    print("  已加入 renderSettings(设置页开关/数值/下拉全部从配置读回)")

import py_compile
import os
import subprocess
# JS 语法检查(有 node 就用)
r = subprocess.run(["node", "--check", JS], capture_output=True, text=True)
print("  node --check:", "通过" if r.returncode == 0 else r.stderr[:200])
