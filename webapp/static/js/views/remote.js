/* remote.js —— 设置页的「跨设备访问」面板
   开关 → 自动体检 → 列出所有可用地址(电脑热点 / 手机热点 / USB / 同一 WiFi)并标出最优 */
import { $, esc, post, toast } from '../core.js';

let DATA = null;

function rowHtml(r) {
  const badge = r.best ? '<b style="color:var(--accent)">推荐</b> ' : '';
  const ok = r.bound === true ? '<span style="color:#39c5a0">✓ 连通</span>'
           : (r.bound === false ? '<span style="color:#e0a23a">未监听</span>' : '');
  return '<div class="remote-row">'
    + '<div class="remote-k">' + badge + esc(r.label) + ok + '</div>'
    + '<div class="remote-u">' + esc(r.url) + '</div>'
    + '<div class="remote-h">' + esc(r.hint) + (r.iface ? ' · ' + esc(r.iface) : '') + '</div>'
    + '</div>';
}

async function refresh(check) {
  const box = $('remoteBox');
  if (!box) return;
  try {
    const st = await post('/api/remote', {});
    DATA = st;
    if ($('remoteOn')) $('remoteOn').checked = !!st.on;
    if ($('remotePin')) $('remotePin').textContent = st.pin || '----';
    if ($('remotePort')) $('remotePort').textContent = st.port || '';
    if (!st.on) {
      box.innerHTML = '<p class="muted sm">打开后,手机会在下面这些地址里选一个访问(同一网络下)。</p>';
      return;
    }
    box.innerHTML = '<p class="muted sm">正在体检…</p>';
    const r = await post('/api/remote/check', {});
    if (!r.ok) { box.innerHTML = '<p class="muted sm">' + esc(r.msg || '检测失败') + '</p>'; return; }
    const fw = (r.firewall || {}).ok
      ? '<span style="color:#39c5a0">防火墙已放行 ✓</span>'
      : '<span style="color:#e0a23a">防火墙还没放行</span> <button class="btn ghost sm" id="remoteFw">点此放行</button>';
    box.innerHTML = '<div class="muted sm" style="margin:4px 0 8px">' + rw(fw) + '</div>'
      + (r.routes || []).map(rowHtml).join('')
      + '<p class="muted sm" style="margin:10px 0 0">' + esc((r.best && ('最优: ' + r.best.label + ' ' + r.best.url)) || r.msg || '') + '</p>'
      + '<p class="muted sm" style="margin:6px 0 0">' + (r.tips || []).map((t) => '· ' + esc(t)).join('<br>') + '</p>';
    const f = $('remoteFw');
    if (f) f.onclick = async () => {
      const x = await post('/api/remote/firewall', {});
      toast(x.msg || '已申请');
    };
  } catch (e) {
    box.innerHTML = '<p class="muted sm">读取失败:' + esc(String(e && e.message || e)) + '</p>';
  }
}
function rw(s) { return s; }

export function installRemoteUI() {
  const sw = $('remoteOn');
  if (sw) sw.onchange = async () => {
    const r = await post('/api/remote', { on: sw.checked });
    toast(r.msg || (sw.checked ? '已开启' : '已关闭'));
    refresh(true);
  };
  const np = $('remotePinBtn');
  if (np) np.onclick = async () => {
    const r = await post('/api/remote', { new_pin: true });
    if ($('remotePin')) $('remotePin').textContent = r.pin || '';
    toast(r.msg || '已换新安全码');
  };
  const ck = $('remoteCheck');
  if (ck) ck.onclick = () => refresh(true);
  refresh(false);
}
