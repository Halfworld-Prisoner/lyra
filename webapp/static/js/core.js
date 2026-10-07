/* core.js —— 基础工具与主题
   只有"和具体页面无关"的东西:抓元素、发请求、弹提示、切主题。
   任何页面模块都可以 import 它;它自己不 import 任何页面模块(避免循环依赖)。 */

export const $ = (id) => document.getElementById(id);
export const $$ = (sel) => Array.from(document.querySelectorAll(sel));

/* 出错了就把原因显示在顶栏状态上(平时看不见,排查用) */
window.__JSERR = '';
window.addEventListener('error', (e) => {
  window.__JSERR = (e.message || e.type || '') + ' @' + (e.lineno || '?');
});

export async function get(p) { return (await fetch(p)).json(); }
export async function post(p, body) {
  return (await fetch(p, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  })).json();
}

export function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ---------------- 顶栏状态 ---------------- */
export function setStatusText(text, led) {
  const el = $('status');
  if (!el) return;
  el.innerHTML = '<i class="led' + (led ? ' ' + led : '') + '"></i>' + esc(text);
}

/* ---------------- 提示 ---------------- */
export function toast(msg) {
  const box = $('toasts');
  const d = document.createElement('div');
  d.className = 'toast';
  d.textContent = msg;
  box.appendChild(d);
  setTimeout(() => { d.classList.add('out'); setTimeout(() => d.remove(), 300); }, 2400);
}

/* ---------------- 弹窗 ---------------- */
/* options = [{text, value, primary}],返回值即所选项的 value */
export function choose(caption, html, options) {
  return new Promise((resolve) => {
    $('dlgCaption').textContent = caption;
    $('dlgBody').innerHTML = html;
    const foot = $('dlgFoot');
    foot.innerHTML = '';
    (options || [{ text: '知道了', value: true, primary: true }]).forEach((o) => {
      const b = document.createElement('button');
      b.className = 'btn ' + (o.primary ? 'primary' : 'ghost');
      b.textContent = o.text;
      b.onclick = () => { closeModals(); resolve(o.value); };
      foot.appendChild(b);
    });
    $('modal').classList.remove('hidden');
  });
}

export function dialog(caption, html) {
  $('dlgCaption').textContent = caption;
  $('dlgBody').innerHTML = html;
  $('modal').classList.remove('hidden');
}

export function closeModals() { $$('.modal').forEach((m) => m.classList.add('hidden')); }

document.addEventListener('click', (e) => {
  if (e.target.closest('[data-close]')) closeModals();
  if (e.target.classList && e.target.classList.contains('modal')) closeModals();
});

/* ---------------- 主题 ---------------- */
export const THEMES = { dark: '暗夜', md3: 'MD3', light: '明亮', sepia: '护眼' };

export function applyTheme(name) {
  const t = THEMES[name] ? name : 'dark';
  document.documentElement.setAttribute('data-theme', t);
  const now = $('themeNow');
  if (now) now.textContent = THEMES[t];
  $$('#themePick button').forEach((b) => b.classList.toggle('on', b.dataset.theme === t));
  try { localStorage.setItem('ly_theme', t); } catch (e) {}
  /* 让原生窗口(WebView2 宿主)跟着换底色和标题栏明暗:
     宿主收到这条消息会调 put_DefaultBackgroundColor 与 DWMWA_USE_IMMERSIVE_DARK_MODE,
     否则切到明亮/护眼主题时窗口自己的底色还是黑的(用户反馈过) */
  try {
    const dark = (t === 'light' || t === 'sepia') ? 0 : 1;
    const bg = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim() || '#0d0f14';
    const wv = window.chrome && window.chrome.webview;
    if (wv && wv.postMessage) wv.postMessage({ type: 'theme', dark: dark, bg: bg });
  } catch (e) {}
}

/* 主题按钮(在左边栏底部) */
$$('#themePick button').forEach((b) => {
  b.onclick = async () => {
    applyTheme(b.dataset.theme);
    await post('/api/settings', { theme: b.dataset.theme });
    toast('界面主题:' + THEMES[b.dataset.theme]);
  };
});
try {
  applyTheme(localStorage.getItem('ly_theme')
    || document.documentElement.getAttribute('data-theme') || 'dark');
} catch (e) {}

/* ---------------- 小工具 ---------------- */
export function pitchText(v) {
  const n = Number(v) || 0;
  return n ? (n > 0 ? '高 ' : '低 ') + Math.abs(n) + ' 半音' : '原声';
}

export function backendTag(b) {
  if (b === 'IL2CPP') return '<span class="tag il2cpp">IL2CPP</span>';
  if (b === 'Mono') return '<span class="tag mono">Mono</span>';
  if (b === 'Mono(推测)') return '<span class="tag maybe">可能可以</span>';
  if (b) return '<span class="tag no">非 Unity</span>';
  return '';
}

/* 日志/状态面板里的一行「键 —— 值」 */
export function lsRow(k, v, cls) {
  return '<div class="ls-item"><span class="k">' + k + '</span>'
    + '<span class="v ' + (cls || '') + '" title="' + esc(v) + '">' + esc(v) + '</span></div>';
}

/* ---------------- 鼠标按下期间禁止重建 DOM ---------------- */
/* 刷新每 0.4 秒一次;如果重建正好夹在 mousedown 与 mouseup 中间,
   click 就不会触发(两个事件落在不同元素上)——表现就是"点不到 / 下拉框被掀掉"。 */
window.__LY_DOWN = 0;
window.addEventListener('pointerdown', () => { window.__LY_DOWN = 1; }, true);
window.addEventListener('pointerup', () => { window.__LY_DOWN = 0; }, true);
window.addEventListener('pointercancel', () => { window.__LY_DOWN = 0; }, true);
window.addEventListener('blur', () => { window.__LY_DOWN = 0; }, true);
