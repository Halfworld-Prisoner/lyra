/* contextmenu.js —— 自己的右键菜单
   浏览器的默认菜单(后退/刷新/检查元素…)在桌面应用里很突兀,而且会把游戏切出去。
   这里统一拦下来,按"点的是什么"给一份自己的菜单:
     · 剧情 / 日志条目 → 朗读、复制、加白名单、加黑名单、标记不是剧情
     · 输入框          → 剪切、复制、粘贴、全选
     · 游戏卡片        → 启动、安装 LDC、复制路径
     · 空白处          → 刷新界面、在浏览器里打开、停止朗读 */
import { esc, toast, post, closeModals } from '../core.js';

let menu = null;

function buildMenu() {
  menu = document.createElement('div');
  menu.id = 'ctxMenu';
  menu.className = 'ctx-menu hidden';
  document.body.appendChild(menu);
  /* 点别处 / 按 Esc / 滚轮 → 关掉 */
  document.addEventListener('mousedown', (e) => {
    if (menu && !menu.contains(e.target)) hide();
  }, true);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(); });
  window.addEventListener('blur', hide);
  document.addEventListener('scroll', hide, true);
  return menu;
}

function hide() {
  if (menu) menu.classList.add('hidden');
}

function show(items, x, y) {
  const m = menu || buildMenu();
  m.innerHTML = '';
  items.forEach((it) => {
    if (it === '-') {
      const sep = document.createElement('i');
      sep.className = 'ctx-sep';
      m.appendChild(sep);
      return;
    }
    const b = document.createElement('button');
    b.className = 'ctx-item' + (it.danger ? ' danger' : '');
    b.innerHTML = '<span class="ci-icon">' + (it.icon || '') + '</span>'
      + '<span class="ci-text">' + esc(it.text) + '</span>';
    b.onclick = async () => {
      hide();
      try { await it.run(); } catch (e) { toast('操作失败:' + ((e && e.message) || e)); }
    };
    m.appendChild(b);
  });
  m.classList.remove('hidden');
  /* 先摆出来量一下尺寸,再决定往哪边翻,免得贴到屏幕外面 */
  const w = m.offsetWidth, h = m.offsetHeight;
  const px = Math.min(x, window.innerWidth - w - 6);
  const py = Math.min(y, window.innerHeight - h - 6);
  m.style.left = Math.max(4, px) + 'px';
  m.style.top = Math.max(4, py) + 'px';
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast('已复制');
  } catch (e) {
    /* WebView2 里偶尔没有剪贴板权限,退回老办法 */
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); toast('已复制'); } catch (e2) { toast('复制失败'); }
    ta.remove();
  }
}

/* 从元素上推出"这句话的原文" */
function lineTextOf(el) {
  const li = el.closest ? el.closest('.texts li') : null;
  if (li) return li.textContent.trim();
  const row = el.closest ? el.closest('.log-row') : null;
  if (row) return (row.querySelector('.lm') || {}).textContent || '';
  return (window.getSelection() || {}).toString() || '';
}

function verdictItem(text, to) {
  return {
    text: to === 'white' ? '加入白名单(一定朗读)' : '加入黑名单(彻底不读)',
    icon: to === 'white' ? '✓' : '✕',
    danger: to !== 'white',
    run: async () => {
      const r = await post('/api/filter/verdict', { text: text, word: text, to: to, mode: 'word' });
      toast(r.msg || '已保存');
    },
  };
}

export function installContextMenu() {
  document.addEventListener('contextmenu', (e) => {
    /* 弹窗开着的时候先关弹窗,别让菜单叠在上面 */
    closeModals();
    e.preventDefault();
    const el = e.target;
    const tag = (el.tagName || '').toLowerCase();
    const isInput = tag === 'input' || tag === 'textarea';
    const sel = (window.getSelection() || {}).toString() || '';
    const line = lineTextOf(el);
    const items = [];

    if (isInput) {
      const editable = !el.readOnly && !el.disabled;
      items.push({ text: '剪切', icon: '✂', run: async () => {
        const s = el.value.substring(el.selectionStart, el.selectionEnd) || el.value;
        await copy(s);
        if (editable) {
          el.value = el.value.substring(0, el.selectionStart) + el.value.substring(el.selectionEnd);
          el.dispatchEvent(new Event('change', { bubbles: true }));
        }
      } });
      items.push({ text: '复制', icon: '⧉', run: () => copy(el.value.substring(el.selectionStart, el.selectionEnd) || el.value) });
      if (editable) {
        items.push({ text: '粘贴', icon: '⇩', run: async () => {
          try {
            const t = await navigator.clipboard.readText();
            const s = el.selectionStart, en = el.selectionEnd;
            el.value = el.value.substring(0, s) + t + el.value.substring(en);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
          } catch (err) { toast('读不到剪贴板,请用 Ctrl+V'); }
        } });
      }
      items.push({ text: '全选', icon: '▤', run: async () => el.select() });
      items.push('-');
    }

    if (line) {
      items.push({ text: '朗读这一句', icon: '▶', run: () => post('/api/speak', { text: line }) });
      items.push({ text: '复制这句原文', icon: '⧉', run: () => copy(line) });
      items.push('-');
      items.push(verdictItem(line, 'white'));
      items.push(verdictItem(line, 'black'));
      if (el.closest && el.closest('.texts li')) {
        items.push({
          text: '标成"不是剧情"', icon: '⊘',
          run: async () => {
            const r = await post('/api/story/mark', { text: line });
            toast(r.label ? `已学会:带【${r.label}】的都忽略` : '已标记这一句不是剧情');
          },
        });
      }
      items.push('-');
    }

    const card = el.closest ? el.closest('.game-card') : null;
    if (card) {
      const path = card.dataset.path || '';
      items.push({ text: '启动这个游戏', icon: '▶', run: () => post('/api/hook/launch', { path: path }) });
      items.push({ text: '复制游戏路径', icon: '⧉', run: () => copy(path) });
      items.push('-');
    }

    items.push({ text: '停止朗读', icon: '■', run: () => post('/api/stop') });
    items.push({ text: '刷新界面', icon: '⟳', run: async () => location.reload() });
    items.push({ text: '在浏览器里打开', icon: '🌐', run: () => post('/api/open_browser', {}) });

    show(items, e.clientX, e.clientY);
  });
}
