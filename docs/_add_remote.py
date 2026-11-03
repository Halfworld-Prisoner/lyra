# -*- coding: utf-8 -*-
r"""跨设备访问后端:
   ① netaccess:过滤虚拟网卡网段、修 PowerShell 输出编码
   ② server.py:
        · 配置项 remote = {on, port, pin}
        · 开关打开时,在 0.0.0.0:远程端口 上**再起一个** HTTP 服务(不用重启主服务)
        · 手机首次访问要求输入 4 位安全码(存在 Cookie 里)
        · 接口:/api/remote(状态/开关/换码)、/api/remote/check(自动体检)、/api/remote/firewall(申请放行)
"""
import io
import re
import subprocess

SRC = r"D:\Unity阅读器"
NET = SRC + r"\core\netaccess.py"
SV = SRC + r"\webapp\server.py"

# ---------------- ① netaccess 小修 ----------------
n = io.open(NET, encoding="utf-8").read()
n = n.replace('capture_output=True, text=True, timeout=12,',
              'capture_output=True, text=True, timeout=12, errors="ignore",')
n = n.replace('capture_output=True, text=True, timeout=15,',
              'capture_output=True, text=True, timeout=15, errors="ignore",')
n = n.replace('capture_output=True, text=True, timeout=12,\n                           creationflags=0x08000000)',
              'capture_output=True, text=True, timeout=12, errors="ignore",\n                           creationflags=0x08000000)')
if "198.18." not in n:
    n = n.replace('        if ip in seen or ip.startswith("127.") or ip.startswith("169.254."):\n'
                  '            continue                     # 169.254.x = 网卡没连上的自动地址,跳过',
                  '        if (ip in seen or ip.startswith("127.") or ip.startswith("169.254.")\n'
                  '                or ip.startswith("198.18.") or ip.startswith("198.19.")):\n'
                  '            continue      # 127/169.254=没连上;198.18/19=测速用虚拟网段,都跳过')
    print("① netaccess:已过滤虚拟网段 + 修输出编码")
io.open(NET, "w", encoding="utf-8", newline="\n").write(n)

# ---------------- ② server.py ----------------
t = io.open(SV, encoding="utf-8").read()

if "import netaccess" not in t:
    t = t.replace("from core import readstats, tts, voices",
                  "from core import readstats, tts, voices\nfrom core import netaccess", 1)
    print("② import netaccess ✓")

# --- 远程服务实现 ---
REMOTE = '''
# ---------------------------------------------------------------- 跨设备访问
REMOTE = {"srv": None, "port": 8899, "pin": "", "thread": None}


def _remote_cfg() -> dict:
    """远程访问配置(默认关闭 —— 开着等于把阅读器放到局域网上,得玩家自己开)。"""
    cfg = cfgm.get()
    r = cfg.setdefault("remote", {})
    r.setdefault("on", False)
    r.setdefault("port", 8899)
    if not r.get("pin"):
        r["pin"] = "%04d" % (int(time.time() * 7) % 10000)
    return r


def _new_pin() -> str:
    import random
    return "%04d" % random.randint(0, 9999)


class RemoteHandler(Handler):
    """手机/别的设备连进来的处理器:第一次要输安全码,之后靠 Cookie。"""

    def _pin_ok(self) -> bool:
        try:
            r = _remote_cfg()
            cookie = self.headers.get("Cookie") or ""
            m = re.search(r"lyra_pin=([0-9]{4})", cookie)
            if m and m.group(1) == str(r.get("pin") or ""):
                return True
            q = urllib.parse.urlparse(self.path).query
            got = urllib.parse.parse_qs(q).get("pin", [""])[0]
            if got and got == str(r.get("pin") or ""):
                return True
        except Exception:
            pass
        return False

    def _pin_page(self, bad: bool = False):
        body = ("<!DOCTYPE html><html lang=zh><head><meta charset=utf-8>"
                "<meta name=viewport content='width=device-width,initial-scale=1'>"
                "<title>Lyra · 输入安全码</title><style>"
                "body{margin:0;height:100vh;display:grid;place-items:center;background:#12141c;"
                "color:#e6e9f2;font:16px/1.6 'Microsoft YaHei',system-ui,sans-serif}"
                "form{background:#1b1f2b;padding:28px 26px;border-radius:16px;text-align:center;"
                "box-shadow:0 8px 30px rgba(0,0,0,.4);width:min(88vw,340px)}"
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
                "<button>进入</button>" + ("<div class=bad>安全码不对,再看看电脑屏幕</div>" if bad else "") +
                "</form></body></html>")
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _guard(self) -> bool:
        """没通过就返回 False(已自行响应)。"""
        try:
            if self.path.startswith("/static/") and self.path.endswith((".css", ".js", ".png", ".svg", ".ico")):
                return True                                   # 静态资源放行(页面要用)
            if self._pin_ok():
                return True
            if self.path.startswith("/api/"):
                self._json({"error": "需要安全码", "need_pin": True}, 401)
                return False
            self._pin_page(bad="pin" in (self.path or ""))
            return False
        except Exception:
            return False

    def do_GET(self):
        if not self._guard():
            return
        if self.path.startswith("/") and not self.path.startswith("/api/") \\
                and not self.path.startswith("/static/"):
            self.path = "/m"                                   # 手机上默认给精简版
        return super().do_GET()

    def do_POST(self):
        if not self._guard():
            return
        return super().do_POST()


def remote_start(port: int | None = None) -> dict:
    """开远程监听(0.0.0.0)。已经开着就返回现状。"""
    r = _remote_cfg()
    if REMOTE["srv"]:
        return {"ok": True, "msg": "已在监听", "port": r["port"]}
    p = int(port or r.get("port") or 8899)
    try:
        srv = ThreadingHTTPServer(("0.0.0.0", p), RemoteHandler)
    except OSError as e:
        return {"ok": False, "msg": "端口 %d 打不开:%s" % (p, e)}
    REMOTE["srv"] = srv
    REMOTE["port"] = p
    r["port"] = p
    cfgm.save()
    th = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.4}, daemon=True)
    th.start()
    REMOTE["thread"] = th
    add_log("跨设备访问已开启:0.0.0.0:%d(安全码 %s)" % (p, r["pin"]), "info")
    return {"ok": True, "msg": "已开启", "port": p}


def remote_stop() -> dict:
    srv = REMOTE.get("srv")
    if not srv:
        return {"ok": True, "msg": "本来就没开"}
    try:
        srv.shutdown()
        srv.server_close()
    except Exception:
        pass
    REMOTE["srv"] = None
    add_log("跨设备访问已关闭", "info")
    return {"ok": True, "msg": "已关闭"}


def remote_on() -> bool:
    return REMOTE.get("srv") is not None


'''
if "def remote_start(" not in t:
    t = t.replace("def metrics() -> dict:", REMOTE + "def metrics() -> dict:", 1)
    print("② 远程监听 + 安全码已加入")

# --- 接口 ---
if '"/api/remote"' not in t:
    ROUTES = '''            if p == "/api/remote":
                r = _remote_cfg()
                if "on" in d:
                    want = bool(d.get("on"))
                    res = remote_start() if want else remote_stop()
                    r["on"] = want
                    cfgm.save()
                    return self._json({"ok": res.get("ok", False), "on": remote_on(),
                                       "msg": res.get("msg", ""), "pin": r["pin"],
                                       "port": r["port"]})
                if d.get("new_pin"):
                    r["pin"] = _new_pin()
                    cfgm.save()
                    return self._json({"ok": True, "pin": r["pin"], "msg": "已换新安全码"})
                return self._json({"ok": True, "on": remote_on(), "pin": r["pin"],
                                   "port": r["port"], "url": "http://%s:%d/" % (
                                       (netaccess.candidates(r["port"])[:1] or [{"ip": "127.0.0.1"}])[0]["ip"],
                                       r["port"])})

            if p == "/api/remote/check":
                r = _remote_cfg()
                if not remote_on():
                    return self._json({"ok": False, "msg": "先打开「跨设备访问」", "routes": []})
                s = netaccess.summary(r["port"])
                best = s.get("best") or {}
                return self._json({"ok": True, "routes": s["routes"], "best": best,
                                   "firewall": s["firewall"], "tips": s["tips"],
                                   "msg": ("最优:%s %s" % (best.get("label"), best.get("url")))
                                          if best else "没找到可用地址(检查网络连接)"})

            if p == "/api/remote/firewall":
                # 申请放行(需要管理员;失败就告诉玩家手动命令)
                port = _remote_cfg()["port"]
                ps = ('New-NetFirewallRule -DisplayName "Lyra 局域网访问" -Direction Inbound '
                      '-Action Allow -Protocol TCP -LocalPort %d -Profile Any' % port)
                try:
                    rr = subprocess.run(["powershell", "-NoProfile", "-Command",
                                         "Start-Process powershell -Verb RunAs -ArgumentList "
                                         "'-NoProfile','-Command','%s'" % ps.replace("'", "''")],
                                        capture_output=True, text=True, timeout=25, errors="ignore",
                                        creationflags=0x08000000)
                    add_log("已请求放行防火墙端口 %d(会弹一次 UAC)" % port, "info")
                    return self._json({"ok": True, "msg": "已弹管理员窗口申请放行,点「是」即可"})
                except Exception as e:
                    return self._json({"ok": False, "msg": "申请失败:%s" % e,
                                       "manual": 'netsh advfirewall firewall add rule name="Lyra 局域网访问" dir=in action=allow protocol=TCP localport=%d' % port})

'''
    anchor = '            if p == "/api/stats":'
    if anchor in t:
        t = t.replace(anchor, ROUTES + anchor, 1)
        print("② /api/remote* 三个接口已加")
    else:
        print("② !! 找不到 POST 插入点")

# 启动时按配置恢复监听
if "remote_start()" in t and "启动时按配置恢复" not in t:
    t = t.replace("    srv = Server((\"127.0.0.1\", port), Handler)",
                  "    # 启动时按配置恢复\"跨设备访问\"\n"
                  "    try:\n"
                  "        if _remote_cfg().get(\"on\"):\n"
                  "            remote_start()\n"
                  "    except Exception:\n"
                  "        pass\n"
                  "    srv = Server((\"127.0.0.1\", port), Handler)", 1)
    print("② 启动时按配置自动恢复监听 ✓")

io.open(SV, "w", encoding="utf-8", newline="\n").write(t)
for f in (NET, SV):
    r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % f],
                       capture_output=True, text=True)
    print("   语法 %-14s %s" % (f.split("\\")[-1], "通过" if r.returncode == 0 else (r.stderr or "")[:220]))
