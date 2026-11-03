# -*- coding: utf-8 -*-
r"""修三处:
   ① **权限真正生效**:「允许远程改设置」关闭时,远程端**改不了**任何设置 ——
      服务端直接拦(不靠前端藏按钮);默认关闭。
   ② 端口:第一次进入就显示(从接口回填),不再空白。
   ③ 端口显示改成**只读锁死文本**,去掉可输入的上下拖动条。
"""
import io
import os
import shutil
import subprocess

SRC, APP = r"D:\Unity阅读器", r"D:\Lyra\app"
SV = os.path.join(SRC, "webapp", "server.py")
t = io.open(SV, encoding="utf-8").read()

# ---------- ① 配置默认值 + 接口字段 ----------
if "allow_ctl" not in t:
    t = t.replace('''    r.setdefault("on", False)
    r.setdefault("port", 8899)''',
                  '''    r.setdefault("on", False)
    r.setdefault("port", 8899)
    r.setdefault("auto", False)          # 启动时自动开启
    r.setdefault("allow_pc", True)       # 允许电脑端用桌面版界面
    r.setdefault("allow_ctl", False)     # ★默认不允许远程改设置★''', 1)
    print("① 配置项 auto/allow_pc/allow_ctl(默认关)已加")

# 服务端拦截:远程来的写操作
if "def _remote_deny" not in t:
    t = t.replace("class RemoteHandler(Handler):" if "class RemoteHandler(Handler):" in t else "    class RemoteHandler(Handler):",
                  "    class RemoteHandler(Handler):", 1)
    # 在 do_POST 里加拦截
    old_post = '''        def do_POST(self):
            if not self._guard():
                return
            return super().do_POST()'''
    new_post = '''        # 这些是"遥控播放",任何时候都允许
        _ALLOW_ALWAYS = ("/api/speak", "/api/stop")

        def do_POST(self):
            if not self._guard():
                return
            p = urllib.parse.urlparse(self.path).path
            cfg = _remote_cfg()
            if not cfg.get("allow_ctl", False) and p not in self._ALLOW_ALWAYS:
                add_log("远程设备尝试修改设置,已被「允许远程改设置=关」拦下:" + p, "warn")
                return self._json({"ok": False, "denied": True,
                                   "msg": "电脑上关闭了「允许远程改设置」,当前只能看和朗读"}, 403)
            return super().do_POST()'''
    if old_post in t:
        t = t.replace(old_post, new_post, 1)
        print("① do_POST 已加权限拦截(默认拒绝)")
    else:
        print("① !! 没找到 do_POST")

# 接口支持改这些字段 + 返回值里带上
if '"allow_ctl": bool(' not in t:
    t = t.replace('''                if "on" in d:
                    want = bool(d.get("on"))''',
                  '''                for k in ("auto", "allow_pc", "allow_ctl"):
                    if k in d:
                        r[k] = bool(d.get(k))
                if "port" in d:
                    try:
                        np = int(d.get("port") or 0)
                        if 1024 <= np <= 65535 and np != r.get("port"):
                            r["port"] = np
                            if remote_on():
                                remote_stop()
                                remote_start(np)
                    except Exception:
                        pass
                if "on" in d:
                    want = bool(d.get("on"))''', 1)
    t = t.replace('''                return self._json({"ok": True, "on": remote_on(), "pin": r["pin"],
                                   "port": r["port"], "url": "http://%s:%d/" % (''',
                  '''                return self._json({"ok": True, "on": remote_on(), "pin": r["pin"],
                                   "port": r["port"], "auto": bool(r.get("auto")),
                                   "allow_pc": r.get("allow_pc", True) is not False,
                                   "allow_ctl": bool(r.get("allow_ctl", False)),
                                   "url": "http://%s:%d/" % (''', 1)
    print("① 接口已支持 port/auto/allow_pc/allow_ctl")

# 启动时按 auto 自动开启
t = t.replace('        if _remote_cfg().get("on"):\n            remote_start()',
              '        _rc = _remote_cfg()\n'
              '        if _rc.get("on") or _rc.get("auto"):\n'
              '            _rc["on"] = True\n'
              '            cfgm.save()\n'
              '            remote_start()', 1)

io.open(SV, "w", encoding="utf-8", newline="\n").write(t)
r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % SV],
                   capture_output=True, text=True)
print("   server.py 语法:", "通过" if r.returncode == 0 else (r.stderr or "")[-200:])

# ---------- ② 端口改成只读显示 ----------
P = os.path.join(SRC, "webapp", "static", "index.html")
h = io.open(P, encoding="utf-8").read()
old = '''          <label class="dev-line">远程端口
            <input class="input" id="dvSetPort" type="number" min="1024" max="65535" style="width:110px">
            <span class="muted sm">改端口后需要重新开启一次</span></label>'''
new = '''          <div class="dev-line">远程端口
            <span class="dev-lock" id="dvSetPort">—</span>
            <span class="muted sm">固定端口(避免和其它软件冲突)</span></div>'''
if old in h:
    h = h.replace(old, new, 1)
    print("② 端口已改为只读显示")
elif 'id="dvSetPort"' in h:
    print("② 端口已是只读(或结构不同)")
io.open(P, "w", encoding="utf-8", newline="\n").write(h)

# 只读样式
CSS = os.path.join(SRC, "webapp", "static", "css", "extra.css")
c = io.open(CSS, encoding="utf-8").read()
if ".dev-lock" not in c:
    c += '''

/* 只读数值(锁死显示,不带输入框)*/
.dev-lock { font: 600 15px/1 Consolas, monospace; color: var(--accent); background: var(--soft);
  border: 1px solid var(--line); border-radius: 8px; padding: 7px 14px; user-select: all; }
.dev-lock::before { content: "🔒 "; font-size: 12px; opacity: .8; }
'''
    io.open(CSS, "w", encoding="utf-8", newline="\n").write(c)
    print("② 只读样式已加")

# ---------- ③ device.js:回填端口 + 接上三个开关 ----------
JS = os.path.join(SRC, "webapp", "static", "js", "views", "device.js")
s = io.open(JS, encoding="utf-8").read()
if "dvSetPort'" in s and "textContent = CUR.port" not in s:
    s = s.replace("  if ($('dvPinBig')) $('dvPinBig').textContent = CUR.pin || '----';",
                  "  if ($('dvPinBig')) $('dvPinBig').textContent = CUR.pin || '----';\n"
                  "  if ($('dvSetPort')) $('dvSetPort').textContent = CUR.port || '—';\n"
                  "  if ($('dvSetAuto')) $('dvSetAuto').checked = !!CUR.auto;\n"
                  "  if ($('dvSetPc')) $('dvSetPc').checked = CUR.allow_pc !== false;\n"
                  "  if ($('dvSetCtl')) $('dvSetCtl').checked = !!CUR.allow_ctl;", 1)
    print("③ 端口/开关回填已加")
if "dvSetCtl" in s and "dvSetCtl').onchange" not in s:
    s = s.replace("  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDev(); });",
                  "  const bind = (id, key, msg) => {\n"
                  "    const el = $(id);\n"
                  "    if (el) el.onchange = async () => {\n"
                  "      const r = await post('/api/remote', { [key]: el.checked });\n"
                  "      toast(r.msg || msg);\n"
                  "      refresh(false);\n"
                  "    };\n"
                  "  };\n"
                  "  bind('dvSetAuto', 'auto', '已保存');\n"
                  "  bind('dvSetPc', 'allow_pc', '已保存');\n"
                  "  bind('dvSetCtl', 'allow_ctl', '已保存');\n"
                  "  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDev(); });", 1)
    print("③ 三个开关已接后端")
io.open(JS, "w", encoding="utf-8", newline="\n").write(s)
r = subprocess.run(["node", "--check", JS], capture_output=True, text=True)
print("   device.js 语法:", "通过" if r.returncode == 0 else r.stderr[:180])

# ---------- ④ m.html:远程端按权限锁定设置页 ----------
M = os.path.join(SRC, "webapp", "static", "m.html")
m = io.open(M, encoding="utf-8").read()
if "allow_ctl" not in m:
    m = m.replace("let S = {}, RM = {}, shown = '';", "let S = {}, RM = {}, shown = '', CAN_CTL = true;")
    m = m.replace("""    RM = await api('/api/remote');
    $('pin').textContent = RM.pin || '----';""",
                  """    RM = await api('/api/remote');
    CAN_CTL = RM.allow_ctl !== false;              /* 电脑上关掉"允许远程改设置" → 本页只读 */
    const lock = $('lockNote');
    if (lock) lock.style.display = CAN_CTL ? 'none' : '';
    document.querySelectorAll('#v-set button, #v-set select').forEach((el) => {
      el.disabled = !CAN_CTL; el.style.opacity = CAN_CTL ? '' : '.5';
    });
    $('pin').textContent = RM.pin || '----';""", 1)
    m = m.replace('<section id="v-set" style="display:none">',
                  '<section id="v-set" style="display:none">\n      <div class="card" id="lockNote" style="display:none;border-color:var(--warn)">\n'
                  '        <b style="color:var(--warn)">只读模式</b>\n'
                  '        <p class="tips" style="margin:6px 0 0">电脑上关闭了「允许远程改设置」,这台设备当前只能查看和朗读。</p>\n'
                  '      </div>', 1)
    io.open(M, "w", encoding="utf-8", newline="\n").write(m)
    print("④ 远程端已按权限锁定设置页")

for rel in ("webapp/server.py", "webapp/static/index.html", "webapp/static/css/extra.css",
            "webapp/static/js/views/device.js", "webapp/static/m.html"):
    s2 = os.path.join(SRC, rel.replace("/", os.sep)); d2 = os.path.join(APP, rel.replace("/", os.sep))
    if os.path.isfile(s2):
        shutil.copy2(s2, d2)
print("已部署")
