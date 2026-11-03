# -*- coding: utf-8 -*-
r"""让 core/remote.py 能**自己初始化**(不依赖 server.py 的启动接线):
   · 加 ensure(cfg_module, log_fn, base_handler, static_dir) —— 幂等,首次调用时记下依赖
   · server.py 的 /api/remote 路由里先调 ensure(...) 再 handle(...)
   这样即使启动钩子没插上,接口第一次被调用时也能正常работать。
"""
import io
import os
import shutil
import subprocess
import time

SRC, APP = r"D:\Unity阅读器", r"D:\Lyra\app"
RP = os.path.join(SRC, "core", "remote.py")
SV = os.path.join(SRC, "webapp", "server.py")

# ---------- ① core/remote.py 加 ensure ----------
t = io.open(RP, encoding="utf-8").read()
if "def ensure(" not in t:
    t = t.replace("def boot(cfg_module, log_fn, base_handler, static_dir):",
                  '''def ensure(cfg_module=None, log_fn=None, base_handler=None, static_dir=None):
    """幂等初始化:谁先调都行(启动钩子或接口第一次被访问)。"""
    global _CFG, _LOG, _BASE, _STATIC
    if cfg_module is not None:
        _CFG = cfg_module
    if log_fn is not None:
        _LOG = log_fn
    if base_handler is not None:
        _BASE = base_handler
    if static_dir is not None:
        _STATIC = static_dir
    return _CFG is not None and _BASE is not None


def boot(cfg_module, log_fn, base_handler, static_dir):''', 1)
    io.open(RP, "w", encoding="utf-8", newline="\n").write(t)
    print("① core/remote.py 已加 ensure()")

# ---------- ② 路由里先 ensure ----------
s = io.open(SV, encoding="utf-8").read()
if "remote_mod.ensure(" not in s:
    s = s.replace('''            if p.startswith("/api/remote"):
                if remote_mod.handle(self, p, d) is not False:
                    return''',
                  '''            if p.startswith("/api/remote"):
                # 幂等初始化(万一启动钩子没跑起来,这里补上)
                remote_mod.ensure(cfgm, add_log, Handler, STATIC_DIR)
                if remote_mod.handle(self, p, d) is not False:
                    return''', 1)
    io.open(SV, "w", encoding="utf-8", newline="\n").write(s)
    print("② 路由已先 ensure")

for f in (RP, SV):
    r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % f],
                       capture_output=True, text=True)
    print("   语法 %-12s %s" % (os.path.basename(f), "通过 ✓" if r.returncode == 0 else (r.stderr or "")[-200:]))

for rel in ("core/remote.py", "webapp/server.py"):
    shutil.copy2(os.path.join(SRC, rel.replace("/", os.sep)), os.path.join(APP, rel.replace("/", os.sep)))
print("   已同步")

# ---------- ③ 重启 + 验证 ----------
subprocess.run(["taskkill", "/F", "/IM", "Lyra.exe"], capture_output=True)
subprocess.run(["taskkill", "/F", "/IM", "pythonw.exe"], capture_output=True)
time.sleep(4)
subprocess.Popen([r"D:\Lyra\Lyra.exe"])
for _ in range(20):
    time.sleep(2)
    try:
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:8890/api/state", timeout=5)
        break
    except Exception:
        pass

import json
import urllib.error
import urllib.request


def call(p, o=None, base="http://127.0.0.1:8890", cookie=None):
    hd = {"Content-Type": "application/json"}
    if cookie:
        hd["Cookie"] = cookie
    data = json.dumps(o).encode() if o is not None else None
    r = urllib.request.Request(base + p, data=data, headers=hd, method=("POST" if o is not None else "GET"))
    try:
        return urllib.request.urlopen(r, timeout=30).read().decode()
    except urllib.error.HTTPError as e:
        return "HTTP %d %s" % (e.code, e.read().decode()[:80])
    except Exception as e:
        return "ERR " + str(e)[:50]


print("③ 验证:")
st = call("/api/remote", {})
print("   /api/remote →", st[:100] if (st.startswith("HTTP") or st.startswith("ERR")) else "200 ✓ " + st[:90])
if not st.startswith(("HTTP", "ERR")):
    d = json.loads(st)
    if not d.get("on"):
        d = json.loads(call("/api/remote", {"on": True}))
    print("   已开启: port=%s pin=%s" % (d.get("port"), d.get("pin")))
    print("   体检:", json.loads(call("/api/remote/check", {})).get("msg", "")[:70])
    R = "http://127.0.0.1:%d" % d["port"]
    try:
        ck = (urllib.request.urlopen(R + "/?pin=" + d["pin"], timeout=8).headers.get("Set-Cookie") or "").split(";")[0]
        print("   手机页+验证码 ✓ Cookie:", ck)
        print("   权限关闭时改设置 →", call("/api/settings", {"auto_say": True}, base=R, cookie=ck)[:70])
        call("/api/remote", {"allow_ctl": False})
    except Exception as e:
        print("   手机端测试失败:", str(e)[:60])
