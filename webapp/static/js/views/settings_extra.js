/* settings_extra.js —— 设置页里的「朗读」与「AI 助手」两块
   (从 cast.js 搬过来的:声音选择/语速/声线/音量本来在角色配音页,玩家要求只留"下载语音包",
     于是全局设置统一收到设置页;AI 配置也集中到这里,过滤规则页/翻译页不再各放一份。) */
import { $, esc, toast, get, post } from '../core.js';
import { store, refresh, registerRender } from '../state.js';

/* ---------------- 朗读:全局声音 ---------------- */
function renderGlobalVoice() {
  const sel = $('globalVoice');
  if (!sel) return;
  const list = store.S.voices || [];
  const cfg = store.S.settings || {};
  const cur = cfg.voice || '';
  const sig = list.map((v) => v.kind + ':' + v.id).join('#') + '@' + cur;
  if (sel.dataset.sig !== sig) {
    sel.dataset.sig = sig;
    const titles = { sherpa: '离线语音包', sapi: 'Windows 本机', edge: '在线(Edge)' };
    const by = { sherpa: [], sapi: [], edge: [] };
    list.forEach((v) => (by[v.kind] || by.edge).push(v));
    sel.innerHTML = '';
    ['sherpa', 'sapi', 'edge'].forEach((k) => {
      if (!by[k].length) return;
      const og = document.createElement('optgroup');
      og.label = titles[k] + '(' + by[k].length + ')';
      by[k].forEach((v) => {
        const o = document.createElement('option');
        o.value = v.kind + ':' + v.id;
        o.textContent = (v.label || v.name || v.id) + (v.bundled ? ' · 自带' : '');
        og.appendChild(o);
      });
      sel.appendChild(og);
    });
    const hit = list.find((v) => (v.kind + ':' + v.id) === cur || v.id === cur);
    sel.value = hit ? (hit.kind + ':' + hit.id) : cur;
  }
  const kind = $('curVoiceKind');
  if (kind) {
    const v = list.find((x) => (x.kind + ':' + x.id) === cur || x.id === cur);
    kind.textContent = v ? (v.kind === 'sherpa' ? '离线,不联网'
      : v.kind === 'sapi' ? 'Windows 本机' : '在线,需要联网') : '';
  }
  const note = $('voiceNote');
  if (note) {
    note.textContent = (store.S.voice_note || '')
      || '只提供男声语音包;想换音色去「角色配音 → 下载语音包」。';
  }
  /* 语速 / 声线 / 音量 回填 */
  const r = Number(cfg.rate || 1), p2 = Number(cfg.pitch || 0), v2 = Number(cfg.volume || 1);
  if ($('rate') && document.activeElement !== $('rate')) {
    $('rate').value = r; $('rateVal').textContent = r.toFixed(2) + 'x';
  }
  if ($('pitch') && document.activeElement !== $('pitch')) {
    $('pitch').value = p2; $('pitchVal').textContent = p2 ? ((p2 > 0 ? '高 ' : '低 ') + Math.abs(p2) + ' 半音') : '原声';
  }
  if ($('volume') && document.activeElement !== $('volume')) {
    $('volume').value = v2; $('volVal').textContent = Math.round(v2 * 100) + '%';
  }
}

$('globalVoice').onchange = async (e) => {
  await post('/api/settings', { voice: e.target.value });
  toast('已切换声音');
  post('/api/speak', { text: '你好,我是新选的声音。' });
  refresh();
};
$('testVoice').onclick = () => post('/api/speak', { text: '这是试听,剧情会这样念出来。' });
$('rate').oninput = (e) => { $('rateVal').textContent = Number(e.target.value).toFixed(2) + 'x'; };
$('rate').onchange = (e) => post('/api/settings', { rate: Number(e.target.value) });
$('pitch').oninput = (e) => {
  const v = Number(e.target.value) || 0;
  $('pitchVal').textContent = v ? ((v > 0 ? '高 ' : '低 ') + Math.abs(v) + ' 半音') : '原声';
};
$('pitch').onchange = (e) => post('/api/settings', { pitch: Number(e.target.value) })
  .then(() => post('/api/speak', { text: '声线试听。' }));
$('volume').oninput = (e) => { $('volVal').textContent = Math.round(e.target.value * 100) + '%'; };
$('volume').onchange = (e) => post('/api/settings', { volume: Number(e.target.value) });
async function nudgePitch(d) {
  const v = Math.max(-12, Math.min(12, Number($('pitch').value) + d));
  $('pitch').value = v;
  $('pitchVal').textContent = v ? ((v > 0 ? '高 ' : '低 ') + Math.abs(v) + ' 半音') : '原声';
  await post('/api/settings', { pitch: v });
  post('/api/speak', { text: '声线试听。' });
}
$('pitchDown').onclick = () => nudgePitch(-2);
$('pitchUp').onclick = () => nudgePitch(2);
$('pitchReset').onclick = () => nudgePitch(-Number($('pitch').value));

/* ---------------- AI 助手:配置 + 用量/花费 ---------------- */
function renderAI() {
  const ai = (store.S.settings || {}).ai || {};
  const eps = $('aiEndpoint'), md = $('aiModel'), key = $('aiKey');
  if (eps && document.activeElement !== eps) eps.value = ai.endpoint || ai.base_url || 'https://api.deepseek.com/v1/chat/completions';
  if (md && document.activeElement !== md) md.value = ai.model || 'deepseek-chat';
  if (key && document.activeElement !== key) key.value = ai.api_key || '';
  const pin = $('aiPriceIn'), pout = $('aiPriceOut');
  if (pin && document.activeElement !== pin) pin.value = Number(ai.price_in == null ? 2 : ai.price_in);
  if (pout && document.activeElement !== pout) pout.value = Number(ai.price_out == null ? 8 : ai.price_out);
  const st = $('aiState');
  if (st) {
    st.textContent = (ai.base_url && ai.api_key)
      ? ('已配置(' + (ai.model || 'deepseek-chat') + ');过滤词评审与文本翻译都用它')
      : '还没配置 API Key —— 去 DeepSeek 官网申请后填在这里';
  }
  /* 用量(异步取,失败了也不打扰玩家) */
  get('/api/ai/usage').then((u) => {
    const box = $('aiUsage');
    if (!box || !u || u.ok === false) return;
    const t = u.total || {}, l = u.last || {};
    box.innerHTML = ''
      + '<div class="st"><span>累计调用</span><b>' + (t.calls || 0) + ' 次</b></div>'
      + '<div class="st"><span>累计 token</span><b>' + (t.total_tokens || 0) + '</b></div>'
      + '<div class="st"><span>输入 / 输出</span><b>' + (t.prompt_tokens || 0) + ' / ' + (t.completion_tokens || 0) + '</b></div>'
      + '<div class="st"><span>估算花费</span><b>¥' + Number(u.cost || 0).toFixed(3) + '</b></div>'
      + '<div class="st"><span>最近一次</span><b>' + (l.total_tokens || 0) + ' token</b></div>'
      + '<div class="st"><span>单价(元/百万)</span><b>' + Number(u.price_in || 0) + ' / ' + Number(u.price_out || 0) + '</b></div>';
  }).catch(() => {});
}

$('aiSave').onclick = async () => {
  const ep = ($('aiEndpoint').value || '').trim() || 'https://api.deepseek.com/v1/chat/completions';
  await post('/api/settings', {
    ai: {
      base_url: ep,
      model: ($('aiModel').value || '').trim() || 'deepseek-chat',
      api_key: ($('aiKey').value || '').trim(),
      price_in: Number($('aiPriceIn').value || 0),
      price_out: Number($('aiPriceOut').value || 0),
    },
  });
  toast('AI 设置已保存');
  refresh();
};
$('aiTest').onclick = async () => {
  const st = $('aiState');
  st.textContent = '正在测试连接 …';
  const r = await post('/api/ai/test', {});
  st.textContent = r.ok ? ('连接正常 ✓ ' + (r.msg || '')) : ('连接失败:' + (r.msg || ''));
  toast(r.ok ? 'AI 连接正常' : '连接失败,检查 Key/网络');
  renderAI();
};

registerRender(renderGlobalVoice);
registerRender(renderAI);
