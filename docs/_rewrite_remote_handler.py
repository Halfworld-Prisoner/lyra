# -*- coding: utf-8 -*-
r"""整段重写 _make_handler():之前把 do_GET 的缩进弄到类外了,导致它没生效 → 手机端 404。"""
import io
import shutil
import subprocess

P = r"D:\Unity阅读器\webapp\server.py"
t = io.open(P, encoding="utf-8").read()

i = t.find("def _make_handler():")
j = t.find("def remote_start(")
assert i > 0 and j > i, "找不到 _make_handler 段"

BLOCK = '''def _make_handler():
    """延迟创建远程处理器(此时 Handler 一定已定义)。

    手机上:第一次要输 4 位安全码,输对后种 Cookie;页面直接用 m.html。
    """

    class RemoteHandler(Handler):
        _cookie = None

        # ---- 鉴权 ----
        def _pin_ok(self) -> bool:
            try:
                r = _remote_cfg()
                want = str(r.get("pin") or "")
                cookie = self.headers.get("Cookie") or ""
                if want and ("lyra_pin=" + want) in cookie:
                    return True
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                got = (q.get("pin") or [""])[0]
                if got and got == want:
                    return True
            except Exception:
                pass
            return False

        def _html(self, body: str, code: int = 200):
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

        def _serve_mobile(self):
            """直接发 m.html 文件(不走路径路由,免得 404)。"""
            try:
                path = os.path.join(STATIC_DIR, "m.html")
                data = open(path, "rb").read()
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
                self._html("<h3>手机页打不开:%s</h3>" % e, 500)

        def _guard(self) -> bool:
            """没通过安全码就自行响应,返回 False。"""
            try:
                p = urllib.parse.urlparse(self.path).path
                if p.startswith("/static/"):
                    return True                       # 静态资源放行(页面要用)
                if self._pin_ok():
                    return True
                if p.startswith("/api/"):
                    self._json({"error": "需要安全码", "need_pin": True}, 401)
                    return False
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                self._html(self._pin_page_html(bad=bool(q.get("pin"))))
                return False
            except Exception:
                return False

        @staticmethod
        def _pin_page_html(bad: bool = False) -> str:
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

        # ---- 请求入口 ----
        def do_GET(self):
            if not self._guard():
                return
            try:
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                if q.get("pin") and self._pin_ok():
                    self._cookie = ("lyra_pin=%s; Path=/; Max-Age=2592000; SameSite=Lax"
                                    % _remote_cfg()["pin"])
            except Exception:
                pass
            p = urllib.parse.urlparse(self.path).path
            if p in ("/", "/m", "/m.html", "/index.html"):
                return self._serve_mobile()
            return super().do_GET()

        def do_POST(self):
            if not self._guard():
                return
            return super().do_POST()

    return RemoteHandler


'''
t = t[:i] + BLOCK + t[j:]
io.open(P, "w", encoding="utf-8", newline="\n").write(t)

r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % P],
                   capture_output=True, text=True)
print("语法:", "通过" if r.returncode == 0 else (r.stderr or "")[-300:])
if r.returncode == 0:
    shutil.copy2(P, r"D:\Lyra\app\webapp\server.py")
    print("已部署")
