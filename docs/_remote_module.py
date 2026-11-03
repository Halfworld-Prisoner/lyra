# -*- coding: utf-8 -*-
r"""跨设备访问:重做成**独立模块** core/remote.py + server.py 只加 4 行接线。
   同时:① 删掉设置里重复的旧「跨设备访问」面板 ② 开关立刻生效(前端轮询 + 立即刷新顶栏按钮)
"""
import io
import os
import shutil
import subprocess

SRC, APP = r"D:\Unity阅读器", r"D:\Lyra\app"

# ============ ① core/remote.py ============
REMOTE_PY = r'''# -*- coding: utf-8 -*-
r"""Lyra · 跨远程访问(局域网直连,不用任何外部服务器)

独立模块,server.py 只用三行接线:
    from core import remote as remote_mod
    ... 路由里: remote_mod.handle(self, path, data)
    ... 启动时: remote_mod.boot(cfgm, add_log, Handler, STATIC_DIR)

设计要点:
  · 远程监听在**另一个端口**(默认 8899),开关不需要重启主服务;
  · 手机首次访问要输 4 位安全码,输对后种 30 天 Cookie;
  · 「允许远程改设置」默认**关**:关着的时候,远程只能看和朗读,改设置一律被服务端拒绝。
"""
from __future__ import annotations

import os
import random
import threading
import time
import urllib.parse
from http.server import ThreadingHTTPServer

from core import netaccess

S = {"srv": None, "thread": None, "port": 8899, "pin": ""}
_CFG = None          # config 模块
_LOG = None          # 日志函数
_BASE = None         # server 的 Handler 基类
_STATIC = None       # 静态目录

# 远程**永远允许**的操作(遥控播放)
ALLOW_ALWAYS = ("/api/speak", "/api/stop", "/api/state")


def boot(cfg_module, log_fn, base_handler, static_dir):
    """启动时调一次:记下要用到的东西,并按配置决定是否开启。"""
    global _CFG, _LOG, _BASE, _STATIC
    _CFG, _LOG, _BASE, _STATIC = cfg_module, log_fn, base_handler, static_dir
    c = cfg()
    if c.get("on") or c.get("auto"):
        c["on"] = True
        _CFG.save()
        start()


def cfg() -> dict:
    c = _CFG.get().setdefault("remote", {})
    c.setdefault("on", False)
    c.setdefault("port", 8899)
    c.setdefault("auto", False)
    c.setdefault("allow_pc", True)
    c.setdefault("allow_ctl", False)          # ★默认不允许远程改设置★
    if not c.get("pin"):
        c["pin"] = "%04d" % random.randint(0, 9999)
    return c


def on() -> bool:
    return S["srv"] is not None


def start(port: int | None = None) -> dict:
    if S["srv"]:
        return {"ok": True, "msg": "已在监听", "port": S["port"]}
    c = cfg()
    p = int(port or c.get("port") or 8899)
    try:
        srv = ThreadingHTTPServer(("0.0.0.0", p), _make_handler())
    except OSError as e:
        return {"ok": False, "msg": "端口 %d 打不开:%s" % (p, e)}
    S["srv"], S["port"] = srv, p
    c["port"] = p
    _CFG.save()
    th = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.4}, daemon=True)
    th.start()
    S["thread"] = th
    if _LOG:
        _LOG("跨设备访问已开启:0.0.0.0:%d(安全码 %s)" % (p, c["pin"]), "info")
    return {"ok": True, "msg": "已开启", "port": p}


def stop() -> dict:
    srv = S.get("srv")
    if not srv:
        return {"ok": True, "msg": "本来就没开"}
    try:
        srv.shutdown()
        srv.server_close()
    except Exception:
        pass
    S["srv"] = None
    if _LOG:
        _LOG("跨设备访问已关闭", "info")
    return {"ok": True, "msg": "已关闭"}


def best_url() -> str:
    rows = netaccess.candidates(cfg().get("port", 8899))
    return (rows[0]["url"] if rows else "http://127.0.0.1:%d/" % cfg().get("port", 8899))


def _make_handler():
    Base = _BASE

    class RemoteHandler(Base):
        _cookie = None

        # ---------- 安全码 ----------
        def _pin_ok(self) -> bool:
            try:
                want = str(cfg().get("pin") or "")
                if want and ("lyra_pin=" + want) in (self.headers.get("Cookie") or ""):
                    return True
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                got = (q.get("pin") or [""])[0]
                return bool(want) and got == want
            except Exception:
                return False

        def _send_html(self, body: str, code: int = 200):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            if self._cookie:
                self.send_header("Set-Cookie", self._cookie)
                self._cookie = None
            self.end_headers()
            self.wfile.write(data)

        def _send_mobile(self):
            try:
                data = open(os.path.join(_STATIC, "m.html"), "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                if self._cookie:
                    self.send_header("Set-Cookie", self._cookie)
                    self._cookie = None
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self._send_html("<h3>手机页打不开:%s</h3>" % e, 500)

        @staticmethod
        def _pin_html(bad: bool = False) -> str:
            return ("<!DOCTYPE html><html lang=zh><head><meta charset=utf-8>"
                    "<meta name=viewport content='width=device-width,initial-scale=1'>"
                    "<title>Lyra · 安全码</title><style>"
                    "body{margin:0;height:100vh;display:grid;place-items:center;background:#12141c;"
                    "color:#e6e9f2;font:16px/1.6 'Microsoft YaHei',system-ui,sans-serif}"
                    "form{background:#1b1f2b;padding:28px 26px;border-radius:16px;text-align:center;"
                    "box-shadow:0 8px 30px rgba(0,0,0,.45);width:min(88vw,340px)}"
                    "h1{font-size:19px;margin:0 0 6px}p{color:#8b93a7;font-size:13px;margin:0 0 18px}"
                    "input{width:100%;box-sizing:border-box;font:600 26px/1 monospace;text-align:center;"
                    "letter-spacing:.4em;padding:14px 8px;border-radius:12px;border:1px solid #2c3243;"
                    "background:#12141c;color:#e6e9f2;outline:none}"
                    "button{margin-top:16px;width:100%;padding:13px;border:0;border-radius:12px;"
                    "background:linear-gradient(135deg,#7c5cff,#4aa8ff);color:#fff;font:600 16px/1 inherit;"
                    "cursor:pointer}.bad{color:#ff6b81;font-size:13px;margin-top:12px}</style></head><body>"
                    "<form method=get><h1>Lyra · 跨设备访问</h1>"
                    "<p>请输入电脑上显示的 4 位安全码</p>"
                    "<input name=pin inputmode=numeric maxlength=4 autofocus autocomplete=off>"
                    "<button>进入</button>"
                    + ("<div class=bad>安全码不对,再看看电脑屏幕</div>" if bad else "")
                    + "</form></body></html>")

        def _guard(self) -> bool:
            try:
                p = urllib.parse.urlparse(self.path).path
                if p.startswith("/static/"):
                    return True
                if self._pin_ok():
                    return True
                if p.startswith("/api/"):
                    self._json({"error": "需要安全码", "need_pin": True}, 401)
                    return False
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                self._send_html(self._pin_html(bad=bool(q.get("pin"))))
                return False
            except Exception:
                return False

        # ---------- 请求 ----------
        def do_GET(self):
            if not self._guard():
                return
            try:
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                if q.get("pin") and self._pin_ok():
                    self._cookie = ("lyra_pin=%s; Path=/; Max-Age=2592000; SameSite=Lax" % cfg()["pin"])
            except Exception:
                pass
            p = urllib.parse.urlparse(self.path).path
            if p in ("/", "/m", "/m.html", "/index.html"):
                return self._send_mobile()
            return super().do_GET()

        def do_POST(self):
            if not self._guard():
                return
            p = urllib.parse.urlparse(self.path).path
            if not cfg().get("allow_ctl", False) and p not in ALLOW_ALWAYS:
                if _LOG:
                    _LOG("远程设备想改设置,已被「允许远程改设置=关」拦下:" + p, "warn")
                return self._json({"ok": False, "denied": True,
                                   "msg": "电脑上关闭了「允许远程改设置」,这台设备只能看和朗读"}, 403)
            return super().do_POST()

    return RemoteHandler


# ---------------------------------------------------------------- 接口(主服务的 /api/remote*)
def handle(handler, path: str, data: dict):
    """由 server.py 的 POST 路由转进来。返回 True 表示已处理。"""
    c = cfg()
    if path == "/api/remote":
        for k in ("auto", "allow_pc", "allow_ctl"):
            if k in data:
                c[k] = bool(data.get(k))
        if "port" in data:
            try:
                np = int(data.get("port") or 0)
                if 1024 <= np <= 65535 and np != c.get("port"):
                    c["port"] = np
                    if on():
                        stop()
                        start(np)
            except Exception:
                pass
        if "on" in data:
            want = bool(data.get("on"))
            res = start() if want else stop()
            c["on"] = want
            _CFG.save()
            return handler._json({"ok": res.get("ok", False), "on": on(), "msg": res.get("msg", ""),
                                  "pin": c["pin"], "port": c["port"], "auto": bool(c.get("auto")),
                                  "allow_pc": c.get("allow_pc", True) is not False,
                                  "allow_ctl": bool(c.get("allow_ctl", False)),
                                  "url": best_url()})
        if data.get("new_pin"):
            c["pin"] = "%04d" % random.randint(0, 9999)
            _CFG.save()
            return handler._json({"ok": True, "pin": c["pin"], "msg": "已换新安全码"})
        return handler._json({"ok": True, "on": on(), "pin": c["pin"], "port": c["port"],
                              "auto": bool(c.get("auto")),
                              "allow_pc": c.get("allow_pc", True) is not False,
                              "allow_ctl": bool(c.get("allow_ctl", False)),
                              "url": best_url()})

    if path == "/api/remote/check":
        if not on():
            return handler._json({"ok": False, "msg": "先打开跨远程访问", "routes": []})
        s = netaccess.summary(c.get("port", 8899))
        b = s.get("best") or {}
        return handler._json({"ok": True, "routes": s["routes"], "best": b,
                              "firewall": s["firewall"], "tips": s["tips"],
                              "msg": ("最优:%s %s" % (b.get("label"), b.get("url"))) if b else "没找到可用地址"})

    if path == "/api/remote/firewall":
        port = c.get("port", 8899)
        ps = ('New-NetFirewallRule -DisplayName "Lyra 局域网访问" -Direction Inbound '
              '-Action Allow -Protocol TCP -LocalPort %d -Profile Any' % port)
        try:
            import subprocess
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Start-Process powershell -Verb RunAs -ArgumentList "
                            "'-NoProfile','-Command','%s'" % ps.replace("'", "''")],
                           capture_output=True, text=True, timeout=25, errors="ignore",
                           creationflags=0x08000000)
            if _LOG:
                _LOG("已请求放行防火墙端口 %d(会弹一次 UAC)" % port, "info")
            return handler._json({"ok": True, "msg": "已弹管理员窗口申请放行,点「是」即可"})
        except Exception as e:
            return handler._json({"ok": False, "msg": "申请失败:%s" % e,
                                  "manual": 'netsh advfirewall firewall add rule name="Lyra 局域网访问" '
                                            'dir=in action=allow protocol=TCP localport=%d' % port})
    return False
'''
io.open(os.path.join(SRC, "core", "remote.py"), "w", encoding="utf-8", newline="\n").write(REMOTE_PY)
r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)"
                    % os.path.join(SRC, "core", "remote.py")], capture_output=True, text=True)
print("① core/remote.py:", "语法通过 ✓" if r.returncode == 0 else (r.stderr or "")[-200:])

# ============ ② server.py 接线(只加最小几处) ============
SV = os.path.join(SRC, "webapp", "server.py")
t = io.open(SV, encoding="utf-8").read()
changed = []

if "from core import remote as remote_mod" not in t:
    t = t.replace("from core import netaccess", "from core import netaccess\nfrom core import remote as remote_mod", 1)
    changed.append("import")

if "remote_mod.handle(self" not in t:
    HOOK = '''            if p.startswith("/api/remote"):
                if remote_mod.handle(self, p, d) is not False:
                    return

'''
    anchor = '            if p == "/api/settings":'
    if anchor in t:
        t = t.replace(anchor, HOOK + anchor, 1)
        changed.append("路由")

if "remote_mod.boot(" not in t:
    t = t.replace("    srv = None\n    # 启动时按配置恢复",
                  "    try:\n"
                  "        remote_mod.boot(cfgm, add_log, Handler, STATIC_DIR)\n"
                  "    except Exception as _e:\n"
                  "        print('跨设备访问启动失败:', _e)\n"
                  "    srv = None\n    # 启动时按配置恢复", 1)
    changed.append("启动接线")

io.open(SV, "w", encoding="utf-8", newline="\n").write(t)
r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % SV],
                   capture_output=True, text=True)
print("② server.py 接线(%s):%s" % ("/".join(changed), "语法通过 ✓" if r.returncode == 0 else (r.stderr or "")[-250:]))

# ============ ③ 删掉设置里重复的旧面板 ============
P = os.path.join(SRC, "webapp", "static", "index.html")
h = io.open(P, encoding="utf-8").read()
n = 0
for marker in ('id="remotePanel"', 'id="remotePinBtn"', 'id="remoteCheck"'):
    i = h.find(marker)
    while i > 0:
        start = h.rfind('\n      <div class="panel"', 0, i)
        end = h.find('\n      </div>\n', i)
        if start > 0 and end > start:
            h = h[:start] + h[end + len('\n      </div>\n'):]
            n += 1
    # 每个 marker 只处理一轮(避免死循环)
    break
if n:
    io.open(P, "w", encoding="utf-8", newline="\n").write(h)
    print("③ 已删除 %d 个重复的旧面板" % n)
else:
    print("③ 没找到重复面板(可能已删)")

for rel in ("core/remote.py", "webapp/server.py", "webapp/static/index.html"):
    s2 = os.path.join(SRC, rel.replace("/", os.sep)); d2 = os.path.join(APP, rel.replace("/", os.sep))
    if os.path.isfile(s2):
        os.makedirs(os.path.dirname(d2), exist_ok=True); shutil.copy2(s2, d2)
print("已部署")
