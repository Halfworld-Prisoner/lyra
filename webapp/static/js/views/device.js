/* device.js —— 跨远程访问:扩展模块开关 + 独立控制台页面
 *
 *  · 设置页的「扩展模块」面板只有一个名字 + 一个开关
 *  · 顶栏「⇄ 跨设备」按钮 → 打开**独立全屏页面**,自带左侧栏:链接状态 / 安全码 / 设置
 *  · 页面 DOM 全部由本模块**动态创建**,不依赖 index.html 结构(避免改坏界面)
 *  · 绑定与"页面是否存在"无关:开关永远可用、状态永远会保存
 */
import { $, esc, post, toast } from '../core.js';

let OV = null;          // 控制台根节点
let STATE = {};         // 后端状态

/* ---------------------------------------------------------------- 建页面 */
function build() {
  if (OV && document.body.contains(OV)) return OV;
  const ov = document.createElement('div');
  ov.className = 'dev-overlay';
  ov.id = 'devOverlay';
  ov.innerHTML = [
    '<aside class="dev-side">',
    '  <div class="dev-brand"><div class="dev-logo">⇄</div>',
    '    <div><b>跨远程访问</b><span class="muted sm">局域网直连 · 不用服务器</span></div></div>',
    '  <nav class="dev-nav">',
    '    <button data-v="link" class="on"><i>◎</i>链接状态</button>',
    '    <button data-v="pin"><i>⚿</i>安全码</button>',
    '    <button data-v="set"><i>⚙</i>设置</button>',
    '  </nav>',
    '  <div class="dev-foot"><span class="dot" id="devDot"></span><span id="devState">未开启</span></div>',
    '</aside>',
    '<main class="dev-main">',
    '  <div class="dev-top"><h1 id="devTitle">链接状态</h1><span class="grow"></span>',
    '    <button class="btn ghost sm" id="devRefresh">刷新 / 体检</button>',
    '    <button class="btn ghost sm" id="devClose">返回主界面</button></div>',
    '  <section id="dv-link">',
    '    <div class="panel"><div class="panel-title">连接状态 <span class="muted sm">手机 / 另一台电脑连进来时看这里</span></div>',
    '      <div class="mini-stats"><div><span>服务</span><b id="dvOn">—</b></div>',
    '        <div><span>远程端口</span><b id="dvPort">—</b></div>',
    '        <div><span>安全码</span><b id="dvPin">—</b></div>',
    '        <div><span>防火墙</span><b id="dvFw">—</b></div></div></div>',
    '    <div class="panel"><div class="panel-title">可用地址 <span class="muted sm">带「推荐」的那条最稳;四种连接方式都会自动列出来</span></div>',
    '      <div id="dvRoutes" class="muted sm">点右上角「刷新 / 体检」开始检测。</div></div>',
    '    <div class="panel"><div class="panel-title">怎么连 <span class="muted sm">四种方式任选</span></div>',
    '      <p class="muted sm" id="dvTips" style="line-height:1.95"></p></div>',
    '  </section>',
    '  <section id="dv-pin" style="display:none">',
    '    <div class="panel"><div class="panel-title">安全码 <span class="muted sm">手机首次访问需要输入它</span></div>',
    '      <div class="dev-pin" id="dvPinBig">----</div>',
    '      <div class="row" style="justify-content:center;gap:10px">',
    '        <button class="btn" id="dvNewPin">换一个新码</button>',
    '        <button class="btn ghost" id="dvCopy">复制访问地址</button></div>',
    '      <p class="muted sm" style="margin-top:12px;line-height:1.95">手机输对一次会记住 30 天;换码后已连接的设备要重新输入。<br>',
    '        同一网络里的其他人不知道这个码,就打不开 Lyra。</p></div>',
    '  </section>',
    '  <section id="dv-set" style="display:none">',
    '    <div class="panel"><div class="panel-title">跨远程连接设置</div>',
    '      <div class="dev-set">',
    '        <div class="dev-line">远程端口 <span class="dev-lock" id="dvSetPort">—</span>',
    '          <span class="muted sm">固定端口,避免与其它软件冲突</span></div>',
    '        <label class="dev-line">启动时自动开启 <input type="checkbox" id="dvSetAuto">',
    '          <span class="muted sm">Lyra 每次启动都自动打开跨远程访问</span></label>',
    '        <label class="dev-line">允许电脑访问 <input type="checkbox" id="dvSetPc">',
    '          <span class="muted sm">另一台电脑用浏览器访问时显示桌面版界面(关闭则一律手机版)</span></label>',
    '        <label class="dev-line">允许远程改设置 <input type="checkbox" id="dvSetCtl">',
    '          <span class="muted sm">允许手机 / 另一台电脑改语音、主题等(关闭则只能看和朗读)</span></label>',
    '      </div></div>',
    '  </section>',
    '</main>',
  ].join('\n');
  document.body.appendChild(ov);
  OV = ov;

  ov.querySelectorAll('.dev-nav button').forEach((b) => { b.onclick = () => show(b.dataset.v); });
  $('devClose').onclick = close;
  $('devRefresh').onclick = () => pull(true);
  $('dvNewPin').onclick = async () => {
    const r = await post('/api/remote', { new_pin: true });
    toast(r.msg || '已换新安全码');
    pull(false);
  };
  $('dvCopy').onclick = async () => {
    const url = (STATE.best && STATE.best.url) || STATE.url || '';
    try { await navigator.clipboard.writeText(url); toast('已复制:' + url); }
    catch (e) { toast('地址:' + url); }
  };
  const bind = (id, key) => {
    const el = $(id);
    if (el) el.onchange = async () => {
      const r = await post('/api/remote', { [key]: el.checked });
      toast(r.ok === false ? (r.msg || '失败') : '已保存');
      pull(false);
    };
  };
  bind('dvSetAuto', 'auto');
  bind('dvSetPc', 'allow_pc');
  bind('dvSetCtl', 'allow_ctl');
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && isOpen()) close(); });
  return ov;
}

function isOpen() { return !!OV && OV.classList.contains('on'); }

function show(v) {
  ['link', 'pin', 'set'].forEach((k) => { const el = $('dv-' + k); if (el) el.style.display = (k === v) ? '' : 'none'; });
  OV.querySelectorAll('.dev-nav button').forEach((b) => b.classList.toggle('on', b.dataset.v === v));
  $('devTitle').textContent = ({ link: '链接状态', pin: '安全码', set: '设置' })[v] || '';
}

export function openDev() {
  build();
  OV.classList.remove('closing');
  OV.classList.add('on');
  show('link');
  pull(true);
}
export function closeDev() { close(); }
function close() {
  if (!OV) return;
  OV.classList.add('closing');
  setTimeout(() => OV.classList.remove('on', 'closing'), 220);
}

/* ---------------------------------------------------------------- 数据 */
async function pull(check) {
  try {
    const st = await post('/api/remote', {});
    STATE = st;
    const on = !!st.on;
    const sw = $('remoteOn');
    if (sw) sw.checked = on;
    const entry = $('remoteEntry');
    if (entry) entry.classList.toggle('hidden', !on);
    if (!OV) return;
    $('devDot').style.background = on ? 'var(--ok, #39c5a0)' : 'var(--muted)';
    $('devState').textContent = on ? '运行中' : '未开启';
    $('dvOn').innerHTML = on ? '<span style="color:#39c5a0">已开启</span>' : '未开启';
    $('dvPort').textContent = st.port || '—';
    $('dvPin').textContent = st.pin || '----';
    $('dvPinBig').textContent = st.pin || '----';
    $('dvSetPort').textContent = st.port || '—';
    $('dvSetAuto').checked = !!st.auto;
    $('dvSetPc').checked = st.allow_pc !== false;
    $('dvSetCtl').checked = !!st.allow_ctl;
    if (!on) {
      $('dvRoutes').innerHTML = '<span class="muted sm">还没开启 —— 到「设置 → 扩展模块」打开「跨远程访问」。</span>';
      $('dvFw').textContent = '—';
      return;
    }
    if (!check) return;
    $('dvRoutes').innerHTML = '<span class="muted sm">正在体检…</span>';
    const r = await post('/api/remote/check', {});
    STATE.best = r.best || {};
    const fw = r.firewall || {};
    $('dvFw').innerHTML = fw.ok ? '<span style="color:#39c5a0">已放行</span>'
      : '<span style="color:#e0a23a">未放行</span>';
    $('dvRoutes').innerHTML = ((r.routes || []).map((x) => '<div class="remote-row">'
      + '<div class="remote-k">' + (x.best ? '<b style="color:var(--accent)">推荐</b> ' : '')
      + esc(x.label) + (x.bound === true ? ' <span style="color:#39c5a0">✓ 连通</span>' : '') + '</div>'
      + '<div class="remote-u">' + esc(x.url) + '</div>'
      + '<div class="remote-h">' + esc(x.hint) + (x.iface ? ' · ' + esc(x.iface) : '') + '</div></div>').join('')
      || '<span class="muted sm">没找到可用地址,检查网络连接。</span>')
      + (fw.ok ? '' : '<div class="row" style="margin-top:10px"><button class="btn sm" id="dvFwBtn">点此放行防火墙</button>'
        + '<span class="muted sm" style="align-self:center">手机连不上多半是这一步没做</span></div>');
    const fb = $('dvFwBtn');
    if (fb) fb.onclick = async () => { const x = await post('/api/remote/firewall', {}); toast(x.msg || '已申请'); };
    $('dvTips').innerHTML = (r.tips || []).map((t) => '· ' + esc(t)).join('<br>');
  } catch (e) {
    if (OV && $('dvRoutes')) $('dvRoutes').innerHTML = '<span class="muted sm">读取失败:' + esc(String((e && e.message) || e)) + '</span>';
  }
}

/* ---------------------------------------------------------------- 入口 */
function ensureEntry() {
  if ($('remoteEntry')) return;
  const box = document.querySelector('.topbar .search') || document.querySelector('.search');
  if (!box || !box.parentNode) return;
  const b = document.createElement('button');
  b.className = 'btn ghost sm hidden';
  b.id = 'remoteEntry';
  b.title = '跨远程访问:连接状态 / 安全码 / 设置';
  b.innerHTML = '<i>⇄</i> 跨设备';
  b.onclick = openDev;
  box.parentNode.insertBefore(b, box.nextSibling);
}

export function installDevUI() {
  build();                    /* 页面先建好(隐藏),开关与入口随后绑定 */
  ensureEntry();
  const sw = $('remoteOn');
  if (sw) sw.onchange = async () => {
    const r = await post('/api/remote', { on: sw.checked });
    toast(r.msg || (sw.checked ? '已开启跨远程访问' : '已关闭'));
    pull(sw.checked);
  };
  pull(false);
  setInterval(() => pull(false), 20000);
}
