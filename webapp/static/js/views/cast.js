/* 角色配音页(含全局声音设置) */
import { $, $$, esc, toast, post, get } from '../core.js';
import { store, refresh, registerRender } from '../state.js';

/* ---------------- 语音 ---------------- */
function voiceKindLabel(v) {
  return v.kind === 'sherpa' ? '离线神经网络' : v.kind === 'sapi' ? 'Windows 本机' : '在线(Edge)';
}
function sameVoice(v, cur) {
  /* 配置里存的是 "sherpa:xiao_ya" 这种带前缀的 id,列表里是裸 id */
  if (!cur) return false;
  return v.id === cur || (v.kind + ':' + v.id) === cur || v.id === String(cur).split(':').pop();
}
$('openPacks').onclick = () => {
  $('modalPacks').classList.remove('hidden');
  packFilter = 'all';
  $$('#packFilter button').forEach((b, i) => b.classList.toggle('on', i === 0));
  renderPacks();
};
let packFilter = 'all';
let packCache = [];
$$('#packFilter button').forEach((b) => {
  b.onclick = () => {
    packFilter = b.dataset.filter;
    $$('#packFilter button').forEach((x) => x.classList.toggle('on', x === b));
    renderPacks();
  };
});
$('reloadVoice').onclick = async () => {
  const r = await post('/api/voices/reload', {});
  toast(r.ok ? '语音引擎已重载' : '重载失败');
  $('openPacks').onclick();
  refresh();
};
async function renderPacks() {
  const box = $('packList');
  const r = await get('/api/voices');
  packCache = r.packs || [];
  const all = packCache;
  const packs = all.filter((p) => packFilter === 'all'
    || (packFilter === 'installed' && p.installed)
    || (packFilter === 'todo' && !p.installed));
  $('packSummary').textContent = '已下载 ' + all.filter((p) => p.installed).length + ' / 共 ' + all.length + ' 个';
  box.innerHTML = '';
  if (!packs.length) { box.innerHTML = '<div class="scan-empty">没有符合条件的语音包</div>'; return; }
  const cur = (store.S.settings || {}).voice || '';
  packs.forEach((p) => {
    const on = cur === ('sherpa:' + p.id) || cur.indexOf('sherpa:' + p.id + '#') === 0;
    const el = document.createElement('div');
    el.className = 'pack-row' + (on ? ' on' : '');
    const spk = p.speakers > 1 ? (' · ' + p.speakers + ' 种男声音色') : '';
    let btns;
    if (p.installed) {
      btns = '<button class="btn sm ghost" data-try>试听</button>'
        + '<button class="btn sm ' + (on ? 'ghost' : 'primary') + '" data-use>' + (on ? '使用中' : '使用') + '</button>'
        + (p.bundled ? '' : '<button class="btn sm ghost" data-del>删除</button>');
    } else {
      btns = '<button class="btn sm primary" data-dl>下载</button>';
    }
    el.innerHTML = '<span class="tag male">男声</span>'
      + '<div class="pk-main"><div class="pk-name">' + esc(p.name)
      + (p.bundled ? ' <span class="vi-badge">自带</span>' : '') + '</div>'
      + '<div class="pk-note">' + esc(p.note || '') + spk + ' · ' + (p.size_mb || '?') + ' MB</div></div>';
    el.insertAdjacentHTML('beforeend', btns);
    const bu = el.querySelector('[data-use]');
    const bd = el.querySelector('[data-del]');
    const bl = el.querySelector('[data-dl]');
    const bt = el.querySelector('[data-try]');
    if (bu) bu.onclick = async () => { await post('/api/settings', { voice: 'sherpa:' + p.id }); toast('已切换到 ' + p.name); renderPacks(); refresh(); };
    if (bd) bd.onclick = async () => { await post('/api/voices/remove', { id: p.id }); toast('已删除 ' + p.name); renderPacks(); refresh(); };
    if (bt) bt.onclick = () => post('/api/voices/try', { voice: 'sherpa:' + p.id });
    if (bl) bl.onclick = async () => {
      toast('正在下载 ' + p.name + '…(可能需要一会儿)');
      bl.textContent = '下载中…'; bl.disabled = true;
      const rr = await post('/api/voices/download', { id: p.id });
      toast(rr.ok === false ? ('下载失败:' + (rr.msg || '')) : (p.name + ' 下载完成'));
      renderPacks(); refresh();
    };
    box.appendChild(el);
  });
}
/* 语音页「朗读方式」开关:统一用 data-cfg,省得每个开关写一遍 id 和处理器 */
const CFG_LABEL = {
  auto_say: '自动朗读', say_name: '念出角色名',
  auto_next: '自动点击(下一句)', auto_next_blank: '没有文字的过场也继续点',
};
$$('input[data-cfg]').forEach((el) => {
  el.onchange = () => post('/api/settings', { [el.dataset.cfg]: el.checked })
    .then(() => {
      toast(CFG_LABEL[el.dataset.cfg] + ':' + (el.checked ? '开' : '关'));
      refresh();
    });
});

/* 设置页「读取模块(进阶)」折叠 */
const foldHead = $('foldHookHead');
if (foldHead) foldHead.onclick = () => $('foldHook').classList.toggle('closed');


/* ---------------- 角色配音 ---------------- */
/* 下拉框里按三类分组,option 的 value 统一是 "kind:id"(和语音页一致,后端直接能用) */
function fillVoiceSelect(sel, keep) {
  if (!sel) return;
  const groups = { sherpa: '离线神经网络', sapi: 'Windows 本机', edge: '在线(Edge)' };
  const by = { sherpa: [], sapi: [], edge: [] };
  (store.S.voices || []).forEach((v) => { (by[v.kind] || by.edge).push(v); });
  sel.innerHTML = '';
  const opt0 = document.createElement('option');
  opt0.value = '';
  opt0.textContent = '— 用全局语音 —';
  sel.appendChild(opt0);
  ['sherpa', 'sapi', 'edge'].forEach((k) => {
    if (!by[k].length) return;
    const og = document.createElement('optgroup');
    og.label = groups[k] + '(' + by[k].length + ')';
    by[k].forEach((v) => {
      const o = document.createElement('option');
      o.value = v.kind + ':' + v.id;
      o.textContent = (v.label || v.name || v.id) + (v.gender === 'male' ? ' · 男'
        : v.gender === 'female' ? ' · 女' : '');
      og.appendChild(o);
    });
    sel.appendChild(og);
  });
  if (keep) sel.value = keep;
}

let _castSig = '';
let _castBusySince = 0;
let _castSaving = 0;      /* 正在提交的配音改动数:>0 时不重建 */

/* 玩家是不是正在这一页上操作(下拉框/输入框)?
   刷新循环每 0.4 秒跑一次,如果正在操作就把 DOM 重建,下拉框会被立刻刷掉 ——
   表现就是"点开就没了,压根选不了"。所以操作期间不重建;
   但最多让它独占 15 秒,免得焦点一直留在那儿把页面冻住。 */
function castBusy() {
  if (_castSaving > 0) return true;   /* 正在保存:等他写完再重建 */
  const ae = document.activeElement;
  const inside = !!(ae && ae.closest && ae.closest('#store.view-cast')
    && (ae.tagName === 'SELECT' || ae.tagName === 'INPUT'));
  if (!inside) { _castBusySince = 0; return false; }
  if (!_castBusySince) _castBusySince = Date.now();
  return (Date.now() - _castBusySince) < 15000;
}

export function renderCast(force) {
  const cast = store.S.cast || {};
  const box = $('castList');
  if (!box) return;
  const sig = JSON.stringify([cast, store.S.cast_default || '', store.S.speakers || []]);
  if (!force && sig === _castSig) return;      // 数据没变 → 一个 DOM 都不动
  if (!force && castBusy()) return;            // 正在操作 → 等他用完再重建
  _castSig = sig;
  /* 默认配音(没名字的台词 / 还没配音的角色) */
  const dsel = $('castDefault');
  if (dsel) {
    /* 玩家正在这个下拉框上操作时,不要重置它的选中值(否则会把他的选择弹回去) */
    if (document.activeElement !== dsel) fillVoiceSelect(dsel, store.S.cast_default || '');
    dsel.onchange = () => post('/api/cast/default', { voice: dsel.value })
      .then(() => { toast('默认配音已改为:' + (dsel.selectedOptions[0].textContent || '跟随全局')); _castSig = ''; refresh(); });
  }
  /* ★「添加/修改角色」的语音下拉也必须填★
     以前漏了这一步,那个框永远是空的 → 根本选不了配音(用户实测)。 */
  const addSel = $('castVoice');
  if (addSel && !addSel.options.length) fillVoiceSelect(addSel, '');
  box.innerHTML = '';
  const names = Object.keys(cast).sort();
  $('castEmpty').style.display = names.length ? 'none' : '';
  names.forEach((name) => {
    const e = cast[name] || {};
    const row = document.createElement('div');
    row.className = 'cast-row';
    row.innerHTML = '<div class="cast-name" title="' + esc(name) + '">' + esc(name) + '</div>';
    const sel = document.createElement('select');
    sel.className = 'input cast-voice';
    fillVoiceSelect(sel, e.voice || '');
    const rate = document.createElement('input');
    rate.className = 'input num cast-num';
    rate.type = 'number'; rate.min = '0.5'; rate.max = '2'; rate.step = '0.05';
    rate.placeholder = '语速'; rate.value = e.rate == null ? '' : e.rate;
    rate.title = '语速(留空跟随全局)';
    const pitch = document.createElement('input');
    pitch.className = 'input num cast-num';
    pitch.type = 'number'; pitch.min = '-12'; pitch.max = '12'; pitch.step = '1';
    pitch.placeholder = '声线'; pitch.value = e.pitch == null ? '' : e.pitch;
    pitch.title = '声线(半音,留空跟随全局)';
    const acts = document.createElement('div');
    acts.className = 'cast-acts';
    const bTry = document.createElement('button');
    bTry.className = 'btn ghost sm'; bTry.textContent = '试听';
    const bDel = document.createElement('button');
    bDel.className = 'btn ghost sm'; bDel.textContent = '删除';
    acts.appendChild(bTry); acts.appendChild(bDel);
    row.appendChild(sel); row.appendChild(rate); row.appendChild(pitch); row.appendChild(acts);
    const save = () => post('/api/cast/set', {
      name: name, voice: sel.value,
      rate: rate.value === '' ? null : Number(rate.value),
      pitch: pitch.value === '' ? null : Number(pitch.value),
    }).then(() => { toast('已保存「' + name + '」的配音'); _castSig = ''; });
    sel.onchange = save;
    rate.onchange = save;
    pitch.onchange = save;
    bTry.onclick = () => post('/api/cast/try', { name: name });
    bDel.onclick = () => post('/api/cast/del', { name: name })
      .then(() => { toast('已取消「' + name + '」的配音'); _castSig = ''; refresh(); });
    box.appendChild(row);
  });

  /* 出现过的角色:点一下 → 填到上面的表单里 */
  const seen = store.S.speakers || [];
  const chips = $('castSeen');
  if (chips) {
    chips.innerHTML = '';
    if (!seen.length) {
      chips.innerHTML = '<span class="muted sm">还没读到带角色名的台词</span>';
    }
    seen.forEach(([nm, n]) => {
      const b = document.createElement('button');
      b.className = 'cast-chip' + (cast[nm] ? ' on' : '');
      b.innerHTML = esc(nm) + ' <em>' + n + '</em>' + (cast[nm] ? ' ✓' : '');
      b.onclick = () => {
        $('castName').value = nm;
        fillVoiceSelect($('castVoice'), (cast[nm] || {}).voice || '');
        $('castRate').value = (cast[nm] || {}).rate == null ? '' : cast[nm].rate;
        $('castPitch').value = (cast[nm] || {}).pitch == null ? '' : cast[nm].pitch;
        toast('已填入「' + nm + '」,选好声音点保存');
      };
      chips.appendChild(b);
    });
  }
}

$('castAdd').onclick = async () => {
  const name = $('castName').value.trim();
  if (!name) { toast('先填角色名'); return; }
  const voice = $('castVoice').value;
  if (!voice) { toast('先选一个声音'); return; }
  await post('/api/cast/set', {
    name: name, voice: voice,
    rate: $('castRate').value === '' ? null : Number($('castRate').value),
    pitch: $('castPitch').value === '' ? null : Number($('castPitch').value),
  });
  toast('已给「' + name + '」配好声音');
  $('castName').value = '';
  $('castRate').value = '';
  $('castPitch').value = '';
  _castSig = '';
  refresh();
};
$('castTryNew').onclick = () => {
  const name = $('castName').value.trim();
  if (!name) { toast('先填角色名'); return; }
  post('/api/cast/try', { name: name });
};
$('castTryDefault').onclick = () => post('/api/speak', { text: '这是没有名字的旁白,会用默认配音念出来。' });
$('castAuto').onclick = async () => {
  const r = await post('/api/cast/auto', {});
  toast(r.added ? ('已给 ' + r.added + ' 个角色自动分配了声音') : '没有需要分配的角色');
  _castSig = '';
  refresh();
};
$('castOn').onchange = (e) => post('/api/settings', { cast_on: e.target.checked })
  .then(() => toast(e.target.checked ? '角色配音:开' : '角色配音:关(全部用全局声音)'));

/* 注册到刷新循环:数据一变就重画这一页 */
registerRender(renderCast);


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
