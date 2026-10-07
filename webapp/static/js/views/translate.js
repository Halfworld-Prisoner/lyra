/* 文本翻译页 */
import { $, $$, esc, toast, get, post, lsRow } from '../core.js';
import { store, refresh, registerRender } from '../state.js';

/* ---------------- 文本翻译 ---------------- */
let _trSig = '';
export async function renderTranslate() {
  let d;
  try { d = await get('/api/translate/state'); } catch (e) { return; }
  const st = d.stats || {};
  const set = (id, v) => { const el = $(id); if (el && document.activeElement !== el) el.checked = !!v; };
  set('trOn', d.on);
  set('trSay', d.say);
  set('trPrefetch', d.prefetch);
  if (document.activeElement !== $('trWait')) $('trWait').value = Number(d.wait);
  const rows = [
    ['当前游戏翻译', d.on ? (d.installed ? '已开启 · 插件已装好' : '已开启(插件没装成功)') : '未开启',
      d.on ? (d.installed ? 'ok' : 'bad') : ''],
    ['翻译插件', d.payload_ready ? ('已就绪(' + d.arch + ')') : '安装包里缺少插件文件', d.payload_ready ? '' : 'bad'],
    ['AI 接口', d.ai_ready ? ('已配置(' + (d.ai_model || '') + ')') : '还没填 API Key', d.ai_ready ? 'ok' : 'warn'],
    ['译文缓存', (st.cached || 0) + ' 句'],
    ['命中 / 新翻 / 失败', (st.hit || 0) + ' / ' + (st.miss || 0) + ' / ' + (st.fail || 0),
      (st.fail || 0) > 0 ? 'warn' : ''],
    ['已跳过(本来就是中文)', (st.skip || 0) + ' 句'],
  ];
  const u = d.usage || {};
  if (u.total_tokens) {
    rows.push(['AI 用量(最近一次)', u.total_tokens + ' tokens(' + (u.prompt_tokens || 0)
      + ' 输入 / ' + (u.completion_tokens || 0) + ' 输出)', 'blue']);
  }
  const box = $('trState');
  if (box) box.innerHTML = rows.map(([k, v, cls]) => lsRow(k, v, cls)).join('');
  const hint = $('trHint');
  if (hint) {
    hint.innerHTML = d.on
      ? '改完设置后<b>重启游戏</b>才生效。第一次翻译某一句会有 1~3 秒延迟,之后同一句走缓存,秒出。'
        + (st.last_error ? '<br><b>最近一次出错:</b>' + esc(st.last_error) : '')
      : '打开上面的开关 = 把翻译插件装进当前游戏的目录(需要先给这个游戏装好 LDC)。';
  }
}
$('trOn').onchange = async (e) => {
  const on = e.target.checked;
  const r = await post('/api/translate/on', { on: on });
  if (r.ok === false) {
    e.target.checked = !on;
    toast(r.msg || '操作失败');
    return;
  }
  toast(r.msg || (on ? '翻译已开启' : '翻译已关闭'));
  renderTranslate();
  refresh();
};
$('trSay').onchange = (e) => post('/api/settings', { translate: { say: e.target.checked } })
  .then(() => { toast(e.target.checked ? '译文也会念出来' : '只改画面,朗读仍按原文'); refresh(); });
$('trPrefetch').onchange = (e) => post('/api/settings', { translate: { prefetch: e.target.checked } })
  .then(() => toast(e.target.checked ? '会提前翻译' : '不提前翻译'));
$('trWait').onchange = (e) => {
  const v = Math.max(0, Math.min(4, Number(e.target.value) || 0));
  e.target.value = v;
  post('/api/settings', { translate: { wait: v } }).then(() => toast('等译文 ' + v + ' 秒'));
};
$('trClear').onclick = async () => { await post('/api/translate/clear', {}); toast('译文缓存已清空'); renderTranslate(); };
$('trReinstall').onclick = async () => {
  const r = await post('/api/translate/on', { on: true });
  toast(r.msg || '已重新写入翻译插件');
  renderTranslate();
};
$('trTest').onclick = async () => {
  const out = $('trTestOut');
  const src = ($('trTestIn').value || '').trim();
  if (!src) { toast('先输入一句原文'); return; }
  out.textContent = '翻译中 …(第一次要几秒)';
  const r = await post('/api/translate/test', { text: src });
  out.innerHTML = r.ok
    ? '<b>' + esc(r.out) + '</b>'
    : '<span class="muted">' + esc(r.msg || '没翻出来') + '</span>';
  renderTranslate();
};

/* 注册到刷新循环:数据一变就重画这一页 */
registerRender(renderTranslate);
