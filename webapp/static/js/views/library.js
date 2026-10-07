/* 游戏库页 */
import { $, $$, esc, toast, get, post, choose, dialog, closeModals, backendTag } from '../core.js';
import { store, refresh, registerRender, scanData, setScanData } from '../state.js';

/* ---------------- 游戏库 ---------------- */
function iconHTML(g, big) {
  const cls = big ? 'gc-icon' : 'mi-icon';
  if (g.icon) return `<div class="${cls}"><img src="${g.icon}" alt=""></div>`;
  return `<div class="${cls}">${esc((g.name || '?').trim().charAt(0) || '?')}</div>`;
}

let _gridSig = '';
let pickedAdd = null;      /* 手动添加时选中的 exe 路径(拆模块时漏了声明) */
function gamesSignature(list, cur) {
  return list.map((g) => (g.path || '') + '|' + (g.dlp === false ? 0 : 1)
    + '|' + ((g.info || {}).installed ? 1 : 0)).join('#') + '@' + cur;
}
export function renderGames() {
  const box = $('games');
  const kw = ($('search').value || '').trim().toLowerCase();
  const cur = store.S.settings.game || '';
  const all = store.S.games || [];
  const list = all.filter((g) => !kw || (g.name + ' ' + g.path).toLowerCase().includes(kw));

  $('gamesCount').textContent = all.length ? `共 ${all.length} 个` : '';
  /* 数据没变就不重绘(否则每 0.4 秒重建一次 DOM 反而更卡) */
  const sig = gamesSignature(all, cur) + '|' + kw;
  if (sig === _gridSig) return;
  _gridSig = sig;
  box.innerHTML = '';

  list.forEach((g) => {
    const info = g.info || {};
    const card = document.createElement('div');
    card.className = 'game-card' + (g.path === cur ? ' active' : '');
  card.dataset.path = g.path || '';        /* 右键菜单要用 */
  card.dataset.name = g.name || '';
    card.innerHTML = `
      <button class="gc-del" title="从库中移除">✕</button>
      <div class="gc-top">
        ${iconHTML(g, true)}
        <div style="min-width:0">
          <div class="gc-name" title="${esc(g.name)}">${esc(g.name)}</div>
          <div class="gc-path" title="${esc(g.path)}">${esc(g.path)}</div>
        </div>
      </div>
      <div class="gc-tags">
        ${backendTag(info.backend)}
        ${info.bits ? `<span class="tag">${info.bits} 位</span>` : ''}
        ${info.installed ? '<span class="tag ok">LDC 已装</span>' : ''}
        ${info.steam_appid ? '<span class="tag">Steam</span>' : ''}
      </div>
      <div class="gc-actions dlp-row">
        ${info.installed
          ? `<span class="dlp-label" title="关掉后:就算游戏在运行也不读它的文字">LDC获取剧情</span>
             <label class="switch"><input type="checkbox" ${g.dlp === false ? '' : 'checked'}><i></i></label>`
          : `<span class="muted sm">还没装 LDC —— 选中它点「安装 LDC」</span>`}
      </div>`;
    card.onclick = (e) => {
      if (e.target.closest('.switch')) return;
      if ((store.S.running || {}).active && g.path !== cur) { toast('游戏运行中,先「终止游戏」再切换'); return; }
      useGame(g.path);
    };
    card.querySelector('.gc-del').onclick = async (e) => {
      e.stopPropagation();
      const ok = await choose('从游戏库移除',
        '<p>确定把「<b>' + esc(g.name) + '</b>」从游戏库移除吗?</p>'
        + '<p class="muted sm">只是从这个列表里拿掉;LDC(如果装过)不受影响,'
        + '想彻底清掉可以在选中它之后点「卸载 LDC」。</p>',
        [{ text: '移除', value: true, primary: true }, { text: '取消', value: false }]);
      if (!ok) return;
      await post('/api/games/remove', { path: g.path });
      toast('已从游戏库移除');
      refresh();
    };
    const sw = card.querySelector('.switch input');
    if (sw) sw.onchange = async (e) => {
      e.stopPropagation();
      await post('/api/games/dlp', { path: g.path, on: e.target.checked });
      toast(e.target.checked ? `「${g.name}」开始读取剧情` : `「${g.name}」不再读取文字(游戏照常玩)`);
      refresh();
    };
    box.appendChild(card);
  });

  /* 虚线「＋ 添加游戏」卡片 */
  const add = document.createElement('div');
  add.className = 'game-card add-card';
  add.innerHTML = `
    <div class="add-inner">
      <div class="add-plus">＋</div>
      <div class="add-title">添加游戏</div>
      <div class="add-sub">自动列出 Steam / 桌面游戏,也可以自己选路径</div>
    </div>`;
  add.onclick = () => openAdd();
  box.appendChild(add);

  $('gamesEmpty').classList.toggle('hidden', all.length > 0);

  /* 启动条 */
  const sel = $('gameSelect');
  const want = all.map((g) => g.path).join('|') + '#' + cur;
  if (sel.dataset.k !== want) {
    sel.dataset.k = want;
    sel.innerHTML = '';
    if (!all.length) {
      const o = document.createElement('option');
      o.textContent = '(游戏库还是空的,点「＋ 添加游戏」)';
      sel.appendChild(o);
    }
    all.forEach((g) => {
      const o = document.createElement('option');
      o.value = g.path;
      o.textContent = g.name;
      if (g.path === cur) o.selected = true;
      sel.appendChild(o);
    });
  }
  const found = all.find((g) => g.path === cur);
  $('lbIcon').innerHTML = found && found.icon
    ? `<img src="${found.icon}" alt="">`
    : '<span>' + esc(found ? (found.name[0] || '?') : '?') + '</span>';
}

async function useGame(path) {
  if (!path) return null;
  const r = await post('/api/game/set', { path });
  toast('已选择:' + ((r.game_info && r.game_info.name) || path.split('\\').pop()));
  await refresh();
  return r;
}
async function installHook() {
  const gi = store.S.game_info;
  if (!gi) { toast('先在下面点一个游戏'); return { ok: false }; }
  if (gi.installed) {                      // 已装 → 卸载 LDC
    if ((store.S.running || {}).active) {
      toast('游戏正在运行,先点「终止游戏」再卸载');
      return { ok: false };
    }
    const yes = await choose('卸载 LDC',
      '<p>把「<b>' + esc(gi.name) + '</b>」的 LDC 卸载掉吗?</p>'
      + '<p class="muted sm">卸载后这个游戏就读不了剧情了(从 Steam 直接启动也一样);'
      + '游戏本身不受影响,以后想读再装回来即可。</p>',
      [{ text: '卸载', value: true, primary: true }, { text: '取消', value: false }]);
    if (!yes) return { ok: true };
    const r = await post('/api/hook/uninstall', {});
    toast(r.msg || '已卸载 LDC');
    await refresh();
    return r;
  }
  toast('正在安装 LDC…(IL2CPP 游戏第一次要复制约 150MB,请稍等)');
  const r = await post('/api/hook/install', {});
  toast(r.msg || (r.ok ? 'LDC已安装' : '安装失败'));
  await refresh();
  return r;
}

/* 主按钮:运行中 = 终止游戏;否则 = 启动游戏 */
function syncLaunchBtn() {
  const b = $('launchGame');
  if (!b) return;
  const run = (store.S.running || {}).active;
  b.innerHTML = run ? '<i>■</i>终止游戏' : '<i>▶</i>启动游戏';
  b.classList.toggle('danger', !!run);
  b.classList.toggle('primary', !run);
  const sel = $('gameSelect');
  if (sel) sel.disabled = !!run;
  const hint = $('runHint');
  if (hint) hint.textContent = run ? ((store.S.running || {}).name + ' 正在运行 —— 关掉它才能切换游戏') : '';
}

/* 按钮文字跟着「是否已装」变 */
function syncInstallBtn() {
  const b = $('installHook');
  if (!b) return;
  const gi = store.S.game_info;
  b.textContent = (gi && gi.installed) ? '卸载 LDC' : '安装 LDC';
  b.classList.toggle('primary', !(gi && gi.installed));
  b.classList.toggle('ghost', !!(gi && gi.installed));
}
async function startGame() {
  if (!store.S.game_info) { toast('先在下面点一个游戏'); return; }
  if (!store.S.game_info.installed) {
    const pick = await choose('这个游戏还没装 LDC',
      '<p>要现在安装「LDC」吗?装了才能读出剧情。</p>'
      + '<p class="muted sm">IL2CPP 游戏第一次安装要复制约 150MB,可能要等十几秒。</p>',
      [{ text: '安装并启动', value: 'install', primary: true },
       { text: '跳过,直接启动', value: 'skip' },
       { text: '取消', value: null }]);
    if (pick === null) return;
    if (pick === 'install') {
      const r = await installHook();
      if (r && r.ok === false) return;
    }
  }
  const r = await post('/api/hook/launch', {});
  toast(r.ok ? (r.msg || '已启动游戏,进游戏看剧情') : ('启动失败:' + (r.msg || '')));
  refresh();
}
$('launchGame').onclick = async () => {
  if ((store.S.running || {}).active) {
    const yes = await choose('终止游戏',
      '<p>要结束「<b>' + esc((store.S.running || {}).name || '') + '</b>」吗?</p>'
      + '<p class="muted sm">会强制关掉游戏进程,没保存的进度可能丢失。</p>',
      [{ text: '终止游戏', value: true, primary: true }, { text: '取消', value: false }]);
    if (!yes) return;
    const r = await post('/api/game/kill', {});
    toast(r.msg || '已结束游戏');
    refresh();
    return;
  }
  const p = $('gameSelect').value;
  if (p && p !== store.S.settings.game) await useGame(p);
  await startGame();
};
$('installHook').onclick = installHook;
$('checkHook').onclick = async () => {
  const r = await post('/api/hook/check', {});
  dialog('检查能否安装 LDC', '<p>' + esc(r.msg || '——') + '</p>');
};
$('gameSelect').onchange = (e) => useGame(e.target.value);
$('rescanGames').onclick = async () => {
  toast('正在重新扫描 Steam 里的 Unity 游戏…');
  const r = await post('/api/games/auto', {});
  toast(`扫描完成:新加入 ${r.added || 0} 个,库内共 ${r.total || 0} 个`);
  refresh();
};
$('addGameBtn').onclick = () => openAdd();

/* ---------------- 添加游戏弹窗 ---------------- */
function openAdd() {
  $('modalAdd').classList.remove('hidden');
  $$('#modalAdd .tab').forEach((t, i) => t.classList.toggle('active', i === 0));
  $('tab-scan').classList.remove('hidden');
  $('tab-manual').classList.add('hidden');
  doScan();
}
$$('#modalAdd .tab').forEach((t) => {
  t.onclick = () => {
    $$('#modalAdd .tab').forEach((x) => x.classList.toggle('active', x === t));
    $('tab-scan').classList.toggle('hidden', t.dataset.tab !== 'scan');
    $('tab-manual').classList.toggle('hidden', t.dataset.tab !== 'manual');
  };
});
async function doScan() {
  $('steamList').innerHTML = '<div class="scan-empty">扫描中…</div>';
  $('deskList').innerHTML = '<div class="scan-empty">扫描中…</div>';
  const r = await get('/api/games/discover');
  const all = r.games || [];
  scanData.steam = all.filter((g) => g.source === 'steam');
  scanData.desktop = all.filter((g) => g.source !== 'steam');
  renderScan();
}
function renderScan() {
  const have = new Set((store.S.games || []).map((g) => g.path));
  const fill = (box, items) => {
    box.innerHTML = '';
    if (!items.length) { box.innerHTML = '<div class="scan-empty">没找到</div>'; return; }
    items.forEach((g) => {
      const row = document.createElement('label');
      row.className = 'scan-item';
      const added = have.has(g.path);
      row.innerHTML = `
        <input type="checkbox" ${added ? 'disabled' : ''}>
        ${iconHTML({ name: g.name, icon: g.icon })}
        <div class="si-text">
          <div class="si-name">${esc(g.name)}</div>
          <div class="si-path">${esc(g.path)}</div>
        </div>
        ${backendTag(g.backend)}
        ${added ? '<span class="tag ok">已在库中</span>' : ''}`;
      row.querySelector('input').onchange = () => { g._sel = row.querySelector('input').checked; };
      box.appendChild(row);
    });
  };
  fill($('steamList'), scanData.steam);
  fill($('deskList'), scanData.desktop);
  $('steamCount').textContent = scanData.steam.length ? `已找到 ${scanData.steam.length} 个` : '';
  $('deskCount').textContent = scanData.desktop.length ? `已找到 ${scanData.desktop.length} 个` : '';
}
$('rescan').onclick = doScan;
$('addConfirm').onclick = async () => {
  const picked = [...scanData.steam, ...scanData.desktop].filter((g) => g._sel);
  if (pickedAdd) picked.push({ name: $('addName').value.trim() || pickedAdd.split('\\').pop().replace(/\.exe$/i, ''), path: pickedAdd });
  if (!picked.length) { toast('先勾选(或手动选择)要添加的游戏'); return; }
  const cur = store.S.games || [];
  const have = new Set(cur.map((g) => g.path));
  let n = 0;
  picked.forEach((g) => {
    if (have.has(g.path)) return;
    cur.push({ name: g.name, path: g.path, dlp: true, info: { backend: g.backend, bits: g.bits, installed: g.installed } });
    have.add(g.path);
    n++;
  });
  await post('/api/settings', { games: cur });
  closeModals();
  pickedAdd = null;
  $('addPath').value = ''; $('addName').value = '';
  toast(`已添加 ${n} 个游戏`);
  refresh();
};
$('addBrowse').onclick = async () => {
  const r = await post('/api/game/pick', {});
  if (!r.path) return;
  pickedAdd = r.path;
  $('addPath').value = r.path;
  const name = r.path.split('\\').pop().replace(/\.exe$/i, '');
  $('addName').placeholder = name;
  $('mpName').textContent = name;
  $('mpPath').textContent = r.path;
  /* 把 exe 的真实图标显示出来 */
  const info = await get('/api/icon?path=' + encodeURIComponent(r.path));
  const icon = (info && info.icon) || '';
  $('mpIcon').innerHTML = icon ? '<img src="' + icon + '" alt="">'
                               : esc(name.charAt(0) || '?');
};
$('addPath').oninput = () => { pickedAdd = $('addPath').value.trim() || null; };

/* 注册到刷新循环:数据一变就重画这一页 */
registerRender(renderGames);
registerRender(syncInstallBtn);
registerRender(syncLaunchBtn);
