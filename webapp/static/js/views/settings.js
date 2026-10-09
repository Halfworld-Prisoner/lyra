/* 设置页 */
import { $, $$, esc, toast, get, post, choose } from '../core.js';
import { store, refresh, registerRender } from '../state.js';

/* ---------------- 设置 ---------------- */
$('strict').onchange = (e) => post('/api/settings', { hook: { strict: e.target.checked } }).then(() => toast('已保存'));
$('interrupt').onchange = (e) => post('/api/settings', { hook: { interrupt: e.target.checked } }).then(() => toast('已保存'));
$('minCjk').onchange = (e) => post('/api/settings', { hook: { min_cjk: Number(e.target.value) } }).then(() => toast('已保存'));
$('onTop').onchange = (e) => post('/api/settings', { on_top: e.target.checked }).then(() => toast('窗口置顶:' + (e.target.checked ? '开' : '关')));
$('watchGame').onchange = (e) => post('/api/settings', { watch_game: e.target.checked })
  .then(() => toast(e.target.checked ? '游戏关闭后会跟着退出' : '游戏关闭后不退出'));
$('saveFilter').onclick = async () => {
  const words = $('extraWords').value.split(/[,，、;；\s]+/).map((x) => x.trim()).filter(Boolean);
  await post('/api/settings', { hook: { extra_words: words } });
  toast('已保存额外过滤词(' + words.length + ' 个)');
};
$('clearLearned').onclick = async () => { await post('/api/story/clear-learned'); toast('已清空学到的忽略规则'); refresh(); };

/* 自动下一句:剧情念完 → 停一下 → 自动点一下游戏画面 */
$('autoNext').onchange = (e) => post('/api/settings', { auto_next: e.target.checked }).then(() => {
  if (e.target.checked && !store.S.settings.auto_say) {
    toast('已打开 —— 但要同时开着「自动朗读」才会点下一句');
  } else {
    toast(e.target.checked ? '剧情读完后会自动点下一句' : '已关闭自动下一句');
  }
});
$('autoNextDelay').onchange = (e) => {
  const v = Math.max(0, Math.min(10, Number(e.target.value) || 0));
  e.target.value = v;
  post('/api/settings', { auto_next_delay: v }).then(() => toast('读完停顿 ' + v + ' 秒再点'));
};
$('autoNextPoint').onchange = (e) => post('/api/settings', { auto_next_point: e.target.value })
  .then(() => toast('点哪儿:' + e.target.selectedOptions[0].textContent));
$('autoNextSilent').onchange = (e) => post('/api/settings', { auto_next_silent: e.target.checked })
  .then(() => toast(e.target.checked ? '静默推进:鼠标不会动' : '改用移动鼠标点一下'));
$('autoNextFallback').onchange = (e) => post('/api/settings', { auto_next_fallback: e.target.checked })
  .then(() => toast(e.target.checked ? '静默推进失败时会用鼠标兜底' : '静默推进失败就不点了'));
$('testAdvance').onclick = async () => {
  const b = $('testAdvance');
  b.disabled = true; b.textContent = '正在试 …';
  const r = await post('/api/autoclick/test', {});
  b.disabled = false; b.textContent = '测试一次静默推进';
  toast(r.msg || (r.ok ? '成功' : '失败'));
};
$('autoNextBlank').onchange = (e) => post('/api/settings', { auto_next_blank: e.target.checked })
  .then(() => toast(e.target.checked ? '没有文字的过场会自动再点一下' : '已关闭:没有文字时不点'));
$('autoNextBlankWait').onchange = (e) => {
  const v = Math.max(1, Math.min(15, Number(e.target.value) || 2.5));
  e.target.value = v;
  post('/api/settings', { auto_next_blank_wait: v })
    .then(() => toast('没新台词超过 ' + v + ' 秒就当作"这一步没文字"'));
};

/* 悬浮窗 */
$('floatOn').onchange = (e) => post('/api/settings', { float_on: e.target.checked })
  .then(() => toast(e.target.checked ? '悬浮窗已打开(左上角)' : '悬浮窗已关闭'));
$('floatCorner').onchange = (e) => {
  const v = Math.max(0, Math.min(30, Number(e.target.value) || 0));
  e.target.value = v;
  post('/api/settings', { float_corner: v }).then(() => toast('悬浮窗圆角:' + v));
};

/* LDC 档位:保存 + 重装 */
$('saveProfile').onclick = async () => {
  const profile = $('hookProfile').value;
  await post('/api/settings', { hook_profile: profile });
  const g = (store.S.settings && store.S.settings.game) || '';
  if (!g) { toast('已保存 —— 选一个游戏后再装 LDC'); return; }
  const r = await post('/api/hook/install', { path: g, proxy: $('hookProxy').value });
  toast(((r && r.msg) || '已重装') + ' · 档位 ' + profile);
  refresh();
};


$('saveProxy').onclick = async () => {
  const proxy = $('hookProxy').value;
  await post('/api/settings', { hook_proxy: proxy });
  const g = (store.S.settings && store.S.settings.game) || '';
  if (!g) { toast('已保存 —— 选一个游戏后再装 LDC'); return; }
  $('proxyHint').textContent = '正在用 ' + proxy + ' 重新安装 …';
  const r = await post('/api/hook/install', { path: g, proxy: proxy });
  $('proxyHint').textContent = (r && r.msg) ? r.msg : '完成';
  toast((r && r.msg) || '已重装 LDC');
  refresh();
};


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
    const el = $(id);
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
