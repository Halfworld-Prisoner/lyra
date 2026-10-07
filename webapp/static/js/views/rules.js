/* 过滤规则页 */
import { $, $$, esc, toast, get, post, choose, dialog, closeModals } from '../core.js';
import { store, refresh, registerRender } from '../state.js';

/* ---------------- 过滤规则 ---------------- */
let RULES = { groups: [], lists: [], profiles: [], cur: '', learned: {}, extra: [], active: '' };
export async function loadRules(keep) {
  const d = await get('/api/rules');
  RULES.groups = d.groups || [];
  RULES.lists = d.lists || [];
  RULES.profiles = d.profiles || [];
  RULES.learned = d.learned || {};
  RULES.extra = d.extra_words || [];
  RULES.active = d.active_profile || '';
  if (!keep || navKeys().indexOf(RULES.cur) < 0) {
    /* 默认先给玩家看「当前这款游戏的专用规则」——那才是他最想确认的东西 */
    RULES.cur = RULES.active ? ('pf:' + RULES.active) : ((RULES.groups[0] || {}).key || '');
  }
  renderRulesNav();
  renderRulesList();
}
function navKeys() {
  return RULES.groups.map((g) => g.key)
    .concat(RULES.lists.map((l) => l.key))
    .concat(RULES.profiles.map((p) => 'pf:' + p.key))
    .concat(['__learned', '__extra']);
}
function navBtn(key, name, count, cls) {
  const b = document.createElement('button');
  b.className = (key === RULES.cur ? 'on ' : '') + (cls || '');
  b.innerHTML = '<span>' + esc(name) + '</span><em>' + (count || 0) + '</em>';
  b.onclick = () => { RULES.cur = key; renderRulesNav(); renderRulesList(); };
  return b;
}
function renderRulesNav() {
  const nav = $('rulesNav');
  if (!nav) return;
  nav.innerHTML = '';
  const sec = (title, nodes) => {
    if (!nodes.length) return;
    const h = document.createElement('div');
    h.className = 'rules-sec';
    h.textContent = title;
    nav.appendChild(h);
    nodes.forEach((n) => nav.appendChild(n));
  };
  const gen = RULES.groups.filter((g) => g.key !== 'ai_words');
  const ai = RULES.groups.filter((g) => g.key === 'ai_words');
  /* 顺序:游戏专用排最前面 —— 玩家最想确认的是"这款游戏到底过滤了什么" */
  sec('游戏专用规则', RULES.profiles.map((p) => {
    const n = Object.keys(p.groups || {}).reduce((a, k) => a + (p.groups[k] || []).length, 0);
    return navBtn('pf:' + p.key, p.name, n, p.active ? 'live' : (p.off ? 'off' : ''));
  }));
  sec('通用规则', gen.map((g) => navBtn(g.key, g.name, (g.items || []).length)));
  sec('AI 添加的过滤词', ai.map((g) => navBtn(g.key, g.name, (g.items || []).length, 'ai')));
  sec('我的名单', RULES.lists.map((l) => navBtn(l.key, l.name, (l.items || []).length,
    l.key === 'blacklist' ? 'bad' : 'good')));
  sec('其它', [
    navBtn('__learned', '已学规则', (RULES.learned.labels || []).length),
    navBtn('__extra', '额外过滤词', (RULES.extra || []).length),
  ]);
}
function ruleChip(text, onDel, onEdit, extraCls) {
  const el = document.createElement('span');
  el.className = 'rule-chip' + (extraCls ? ' ' + extraCls : '');
  const t = document.createElement('span');
  t.textContent = text;
  t.title = '双击可以改';
  t.ondblclick = () => {
    const inp = document.createElement('input');
    inp.value = text;
    el.replaceChild(inp, t);
    inp.focus();
    const done = async (save) => {
      if (save && inp.value.trim() && inp.value.trim() !== text) await onEdit(text, inp.value.trim());
      renderRulesList();
    };
    inp.onblur = () => done(true);
    inp.onkeydown = (e) => { if (e.key === 'Enter') done(true); if (e.key === 'Escape') done(false); };
  };
  el.appendChild(t);
  if (onDel) {
    const x = document.createElement('span');
    x.className = 'x';
    x.textContent = '✕';
    x.title = '删除这条规则';
    x.onclick = () => onDel(text);
    el.appendChild(x);
  }
  return el;
}
/* 规则内容一模一样的组也照原样列出来:玩家要的是"看到到底过滤了什么" */
function renderRulesList() {
  const box = $('rulesList');
  if (!box) return;
  box.innerHTML = '';
  const tag = $('rulesTag');
  if (tag) tag.innerHTML = '';
  const g = RULES.groups.find((x) => x.key === RULES.cur);
  const l = RULES.lists.find((x) => x.key === RULES.cur);
  const pf = RULES.cur.indexOf('pf:') === 0
    ? RULES.profiles.find((x) => 'pf:' + x.key === RULES.cur) : null;

  if (g) {
    $('rulesTitle').textContent = g.name;
    $('rulesDesc').textContent = g.desc;
    if (g.key === 'ai_words') {
      if (tag) tag.innerHTML = '<span class="tag ai">AI 专区</span>';
      if (!(g.items || []).length) {
        box.innerHTML = '<div class="muted" style="padding:10px 2px">'
          + 'AI 还没有加过词。点上面的「AI 评审」让它看一眼最近的剧情,它加的词只会进这里。</div>';
        $('rulesNew').placeholder = '也可以自己往这一栏加一个词';
        return;
      }
    }
    (g.items || []).forEach((it) => box.appendChild(ruleChip(it,
      async (v) => { await post('/api/rules/del', { key: g.key, value: v }); toast('已删除:' + v); loadRules(true); },
      async (oldV, newV) => { await post('/api/rules/del', { key: g.key, value: oldV });
                              await post('/api/rules/add', { key: g.key, value: newV });
                              toast('已改为:' + newV); loadRules(true); })));
    $('rulesNew').placeholder = '给「' + g.name + '」新增一条,回车即可';
    return;
  }

  if (l) {
    $('rulesTitle').textContent = l.name + (l.key === 'whitelist' ? '(一定朗读)' : '(彻底不读)');
    $('rulesDesc').textContent = l.desc + ' 写法:普通文字 = 含它就命中;开头加 "=" = 整句完全相同才命中。';
    if (tag) tag.innerHTML = '<span class="tag ' + (l.key === 'blacklist' ? 'bad' : 'good') + '">'
      + (l.key === 'blacklist' ? '黑名单' : '白名单') + '</span>';
    if (!(l.items || []).length) {
      box.innerHTML = '<div class="muted" style="padding:10px 2px">还是空的 —— 去「日志」页点一条记录,'
        + '就能把这句话加进来。</div>';
    }
    (l.items || []).forEach((it) => box.appendChild(ruleChip(it,
      async (v) => { await post('/api/rules/del', { key: l.key, value: v }); toast('已删除:' + v); loadRules(true); },
      async (oldV, newV) => {
        await post('/api/rules/del', { key: l.key, value: oldV });
        await post('/api/rules/add', { key: l.key, value: newV });
        toast('已改为:' + newV); loadRules(true);
      }, l.key === 'blacklist' ? 'bad' : 'good')));
    $('rulesNew').placeholder = '手动加一条到' + l.name + '(回车确认)';
    return;
  }

  if (pf) {
    $('rulesTitle').textContent = pf.name;
    $('rulesDesc').textContent = pf.note + (pf.exe_hint ? '(按 exe 名匹配:' + pf.exe_hint + ')' : '');
    if (tag) {
      tag.innerHTML = pf.active ? '<span class="tag live">当前游戏正在用</span>'
                                : (pf.off ? '<span class="tag off">已停用</span>' : '<span class="tag">当前游戏未匹配</span>');
    }
    const bar = document.createElement('div');
    bar.className = 'row';
    bar.style.margin = '4px 0 10px';
    const sw = document.createElement('button');
    sw.className = 'btn ' + (pf.off ? 'primary' : 'ghost') + ' sm';
    sw.textContent = pf.off ? '启用这份专用规则' : '停用这份专用规则';
    sw.onclick = async () => {
      const r = await post('/api/rules/profile', { key: pf.key, off: !pf.off });
      toast(pf.off ? '已启用' : '已停用');
      if (r && r.profiles) RULES.profiles = r.profiles;
      loadRules(true);
    };
    bar.appendChild(sw);
    const hint = document.createElement('span');
    hint.className = 'muted sm';
    hint.textContent = '这些规则只在玩这款游戏时生效,不会影响别的游戏。';
    bar.appendChild(hint);
    box.appendChild(bar);
    const names = {};
    RULES.groups.concat(RULES.lists).forEach((x) => { names[x.key] = x.name; });
    Object.keys(pf.groups || {}).forEach((k) => {
      const items = pf.groups[k] || [];
      if (!items.length) return;
      const h = document.createElement('div');
      h.className = 'rules-group';
      h.innerHTML = '<b>' + esc(names[k] || k) + '</b><span class="muted sm">' + items.length + ' 条</span>';
      box.appendChild(h);
      const wrap = document.createElement('div');
      wrap.className = 'rules-list';
      items.forEach((it) => wrap.appendChild(ruleChip(it, null, async () => {}, 'ro')));
      box.appendChild(wrap);
    });
    $('rulesNew').placeholder = '(游戏专用规则由程序内置,不能在这里加 —— 要加就加到通用规则里)';
    return;
  }

  if (RULES.cur === '__learned') {
    $('rulesTitle').textContent = '已学规则(自动学出来的界面面板)';
    $('rulesDesc').textContent = '这些是程序自己学到的:带这个名字的句子一律不显示。觉得误杀了就删掉。';
    (RULES.learned.labels || []).forEach((it) => box.appendChild(ruleChip('【' + it + '】',
      async () => { await post('/api/story/clear-learned', {}); toast('已清空已学规则'); loadRules(true); },
      async () => {})));
    (RULES.learned.texts || []).slice(-40).forEach((it) => box.appendChild(ruleChip(it, null, async () => {}, 'ro')));
    $('rulesNew').placeholder = '(这一组由程序自动学习,不能手动加)';
    return;
  }

  if (RULES.cur === '__extra') {
    $('rulesTitle').textContent = '额外过滤词(只对当前游戏生效的手动词)';
    $('rulesDesc').textContent = '含这些词的句子不显示。设置页也有一个一样的输入框。';
    (RULES.extra || []).forEach((it) => box.appendChild(ruleChip(it,
      async (v) => {
        const arr = (RULES.extra || []).filter((x) => x !== v);
        await post('/api/settings', { hook: { extra_words: arr } });
        toast('已删除:' + v); loadRules(true);
      }, async () => {})));
    $('rulesNew').placeholder = '新增一个额外过滤词,回车即可';
  }
}
$('rulesAdd').onclick = async () => {
  const v = ($('rulesNew').value || '').trim();
  if (!v) return;
  if (RULES.cur === '__extra') {
    const arr = (RULES.extra || []).concat([v]);
    await post('/api/settings', { hook: { extra_words: arr } });
  } else if (RULES.cur && RULES.cur.indexOf('__') !== 0 && RULES.cur.indexOf('pf:') !== 0) {
    const r = await post('/api/rules/add', { key: RULES.cur, value: v });
    if (r.ok === false) { toast(r.msg || '添加失败'); return; }
  } else {
    toast(RULES.cur.indexOf('pf:') === 0 ? '游戏专用规则不能手改 —— 请加到「通用规则」里' : '这一组不能手动加');
    return;
  }
  $('rulesNew').value = '';
  toast('已添加:' + v);
  loadRules(true);
};
$('rulesNew').onkeydown = (e) => { if (e.key === 'Enter') $('rulesAdd').onclick(); };
$('rulesClearAll').onclick = async () => {
  const yes = await choose('清空全部过滤规则',
    '<p>把 7 组规则、已学规则、额外过滤词**全部清空**吗?</p>'
    + '<p class="muted sm">清空后什么都不会被过滤(界面文字也会显示出来),'
    + '适合让 AI 从头自动学。想恢复随时点「恢复默认」。</p>',
    [{ text: '清空全部', value: true, primary: true }, { text: '取消', value: false }]);
  if (!yes) return;
  await post('/api/rules/clear', {});
  toast('已清空全部规则,现在可以让 AI 重新学');
  loadRules();
};
$('rulesReset').onclick = async () => {
  const yes = await choose('恢复默认规则',
    '<p>把全部过滤规则恢复成出厂默认吗?</p><p class="muted sm">你自己加/删的规则会丢掉。</p>',
    [{ text: '恢复默认', value: true, primary: true }, { text: '取消', value: false }]);
  if (!yes) return;
  await post('/api/rules/reset', {});
  toast('已恢复默认规则');
  loadRules();
};
$('rulesAi').onclick = async () => {
  const box = $('rulesAiBox'), out = $('rulesAiOut');
  box.style.display = '';
  out.innerHTML = '<p class="muted">正在请 AI 评审规则 …(没配 Key 会提示你先去设置)</p>';
  const r = await post('/api/rules/ai', {});
  if (!r.ok) { out.innerHTML = '<p class="muted">' + esc(r.msg || '调用失败') + '</p>'; return; }
  const parts = [];
  parts.push('<p class="muted sm">' + esc(r.note || '') + '</p>');
  const chipRow = (title, arr, cls) => {
    if (!(arr || []).length) return '';
    return '<div class="ai-line"><span class="k">' + title + '</span>'
      + arr.map((w) => '<span class="rule-chip ' + (cls || '') + '">' + esc(w) + '</span>').join('')
      + '</div>';
  };
  parts.push(chipRow('已加入「AI 添加的过滤词」', r.add, 'ai'));
  parts.push(chipRow('已从 AI 词里删除', r.del, 'ro'));
  if ((r.rejected || []).length) {
    parts.push('<div class="ai-line bad"><span class="k">被本地校验挡下</span></div>');
    (r.rejected || []).forEach((x) => {
      parts.push('<div class="ai-sug"><span class="v">' + esc(x.value) + '</span>'
        + '<span class="muted sm">' + esc(x.why) + '</span></div>');
    });
  }
  if (!(r.add || []).length && !(r.del || []).length && !(r.rejected || []).length) {
    parts.push('<p class="muted sm">AI 觉得当前规则没问题。</p>');
  } else {
    parts.push('<p class="muted sm">这些词已经生效;想撤掉就去左边「AI 添加的过滤词」里删。</p>');
  }
  out.innerHTML = parts.join('');
  loadRules();
};
