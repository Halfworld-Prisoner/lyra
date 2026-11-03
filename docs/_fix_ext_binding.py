# -*- coding: utf-8 -*-
r"""修三处(小步,做完立刻验证):
   ① **根因**:device.js 找不到控制台页面就 return → 开关没绑事件 → 点了没用、重启还是关的
      → 改成"绑定与页面无关":开关、顶栏入口按钮独立处理
   ② 顶栏搜索框旁边的入口按钮:**没有就自己创建**,点了跳到 设置→扩展模块
   ③ 「扩展模块」面板挪到设置页**最上面**,并加一行状态:**安全码 / 端口 / 地址 / 重新体检**
   ④ 设置页窄窗口适配:两列挤在一起 → 窄屏自动单列
"""
import io
import os
import shutil
import subprocess

SRC, APP = r"D:\Unity阅读器", r"D:\Lyra\app"
IDX = os.path.join(SRC, "webapp", "static", "index.html")
JS = os.path.join(SRC, "webapp", "static", "js", "views", "device.js")
CSS = os.path.join(SRC, "webapp", "static", "css", "extra.css")

# ---------- ① index.html:面板挪到设置页最上面 + 加状态行 ----------
h = io.open(IDX, encoding="utf-8").read()
start = h.find('\n      <div class="panel" id="extPanel">')
if start > 0:
    end = h.find('\n      </div>\n', start) + len('\n      </div>\n')
    h = h[:start] + h[end:]
    print("① 已把旧面板摘出")
PANEL = '''
      <div class="panel" id="extPanel">
        <div class="panel-title">扩展模块 <span class="muted sm">额外能力,按需开启</span></div>
        <div class="ext-row">
          <div class="ext-info">
            <b>跨远程访问</b>
            <span class="muted sm">手机 / 另一台电脑在同一个网络里打开 Lyra(不用服务器)。
              开启后,顶栏搜索框旁边会出现「⇄ 跨设备」入口。</span>
          </div>
          <label class="switch" title="开启/关闭跨远程访问"><input id="remoteOn" type="checkbox"><i></i></label>
        </div>
        <div class="ext-stat" id="remoteStat">
          <div><span>状态</span><b id="extState">未开启</b></div>
          <div><span>安全码</span><b id="extPin">----</b></div>
          <div><span>端口</span><b id="extPort">—</b></div>
          <div class="ext-url"><span>手机访问</span><b id="extUrl">—</b></div>
          <button class="btn ghost sm" id="extCheck">重新体检</button>
        </div>
        <p class="muted sm" id="extTip" style="margin:8px 0 0">打开开关后,手机上用上面的地址访问,首次输入安全码。</p>
      </div>
'''
i = h.find('<section class="view" id="view-settings">')
j = h.find('>', i) + 1
h = h[:j] + PANEL + h[j:]
io.open(IDX, "w", encoding="utf-8", newline="\n").write(h)
print("① 面板已挪到设置页最上面(含状态行)")

# ---------- ② device.js:绑定与页面无关 ----------
s = io.open(JS, encoding="utf-8").read()
NEW_TAIL = '''
/* ---------------- 与"有没有控制台页面"无关的绑定 ----------------
   之前这里没找到 #devOverlay 就直接 return ✗ → 开关点不动、也不保存 ✗ */
function paintExt(st) {
  const on = !!(st && st.on);
  if ($('remoteOn')) $('remoteOn').checked = on;
  if ($('extState')) $('extState').innerHTML = on
    ? '<span style="color:#39c5a0">运行中</span>' : '未开启';
  if ($('extPin')) $('extPin').textContent = (st && st.pin) || '----';
  if ($('extPort')) $('extPort').textContent = (st && st.port) || '—';
  if ($('extUrl')) $('extUrl').textContent = (st && st.url) || '—';
  const b = $('remoteEntry');
  if (b) b.classList.toggle('hidden', !on);
}

async function pullExt(check) {
  try {
    const st = await post('/api/remote', {});
    paintExt(st);
    if (check && st.on) {
      const r = await post('/api/remote/check', {});
      const best = r.best || {};
      if (best.url && $('extUrl')) $('extUrl').textContent = best.url;
      if ($('extTip')) {
        $('extTip').innerHTML = (r.firewall && r.firewall.ok ? '防火墙已放行 ✓ · ' : '⚠ 防火墙还没放行(手机可能连不上)· ')
          + '最优路线:' + esc(best.label || '-') + ' —— 手机浏览器打开上面的地址,首次输入安全码。';
      }
      if (r.firewall && !r.firewall.ok && $('extCheck')) {
        $('extCheck').textContent = '点此放行防火墙';
        $('extCheck').onclick = async () => { const x = await post('/api/remote/firewall', {}); toast(x.msg || '已申请'); };
      } else if ($('extCheck')) {
        $('extCheck').textContent = '重新体检';
        $('extCheck').onclick = () => pullExt(true);
      }
    }
  } catch (e) { /* 后端没开也不报错 */ }
}

/* 顶栏入口按钮:没有就自己造一个,插在搜索框后面 */
function ensureEntry() {
  if ($('remoteEntry')) return;
  const box = document.querySelector('.topbar .search') || document.querySelector('.search');
  if (!box) return;
  const b = document.createElement('button');
  b.className = 'btn ghost sm hidden';
  b.id = 'remoteEntry';
  b.title = '跨远程访问:看安全码、地址与连接状态';
  b.innerHTML = '<i>⇄</i> 跨设备';
  b.onclick = () => {
    const nav = document.querySelector('.nav-item[data-view="settings"]');
    if (nav) nav.click();
    setTimeout(() => {
      const p = $('extPanel');
      if (p) { p.scrollIntoView({ behavior: 'smooth', block: 'center' });
        p.style.transition = 'box-shadow .3s'; p.style.boxShadow = '0 0 0 2px var(--accent)';
        setTimeout(() => { p.style.boxShadow = ''; }, 1200); }
    }, 260);
  };
  box.parentNode.insertBefore(b, box.nextSibling);
}

export function installDevUI() {
  ensureEntry();
  const sw = $('remoteOn');
  if (sw) sw.onchange = async () => {
    const r = await post('/api/remote', { on: sw.checked });
    toast(r.msg || (sw.checked ? '已开启跨远程访问' : '已关闭'));
    await pullExt(sw.checked);
  };
  if ($('extCheck')) $('extCheck').onclick = () => pullExt(true);
  pullExt(true);
  setInterval(() => pullExt(false), 20000);
}
'''
cut = s.find("export function installDevUI()")
s = s[:cut] + NEW_TAIL.lstrip("\n") if cut > 0 else s + NEW_TAIL
io.open(JS, "w", encoding="utf-8", newline="\n").write(s)
print("② device.js 已改为「绑定与页面无关」+ 自动创建顶栏入口")
r = subprocess.run(["node", "--check", JS], capture_output=True, text=True)
print("   语法:", "通过 ✓" if r.returncode == 0 else r.stderr[:200])

# ---------- ③ CSS:状态行 + 窄屏适配 ----------
c = io.open(CSS, encoding="utf-8").read()
if ".ext-stat" not in c:
    c += '''

/* 扩展模块:状态行 + 适配 */
.ext-stat { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px;
  align-items: center; margin-top: 12px; }
.ext-stat > div { background: var(--soft); border: 1px solid var(--line); border-radius: 10px; padding: 8px 12px; }
.ext-stat span { display: block; font-size: 11.5px; color: var(--muted); }
.ext-stat b { font-size: 14.5px; font-family: Consolas, monospace; user-select: all; }
.ext-stat .ext-url b { font-size: 13px; }
.ext-stat .btn { align-self: center; }

/* 设置页窄窗口:两列挤 → 自动单列 */
@media (max-width: 1080px) {
  #view-settings .settings-grid, #view-settings .cols, #view-settings .panel-row { grid-template-columns: 1fr !important; }
  #view-settings .panel { padding: 14px; }
}
@media (max-width: 720px) {
  .ext-row { flex-direction: column; align-items: flex-start; }
  .ext-stat { grid-template-columns: 1fr 1fr; }
}
'''
    io.open(CSS, "w", encoding="utf-8", newline="\n").write(c)
    print("③ 样式(状态行 + 窄屏适配)已加")

for rel in ("webapp/static/index.html", "webapp/static/js/views/device.js", "webapp/static/css/extra.css"):
    shutil.copy2(os.path.join(SRC, rel.replace("/", os.sep)), os.path.join(APP, rel.replace("/", os.sep)))
print("已部署")
