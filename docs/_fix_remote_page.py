# -*- coding: utf-8 -*-
r"""修手机端两处:
   ① 输码后跳到的 /m 服务器不认识 → {"error":"not found"}
      改成:直接把 m.html 这个文件发出去(不再依赖路径路由)
   ② 输码成功后**没有种 Cookie** → 页面接着请求 /api/state 又会 401
      改成:验证通过就 Set-Cookie(30 天),后续请求自动带上
"""
import io
import shutil
import subprocess

P = r"D:\Unity阅读器\webapp\server.py"
t = io.open(P, encoding="utf-8").read()

OLD = '''    def do_GET(self):
        if not self._guard():
            return
        if self.path.startswith("/") and not self.path.startswith("/api/") \\
                and not self.path.startswith("/static/"):
            self.path = "/m"                                   # 手机上默认给精简版
        return super().do_GET()'''

NEW = '''    def _serve_mobile(self):
        """把手机精简页(m.html)直接发出去 —— 不走路径路由,免得 404。"""
        try:
            self._file("m.html")
        except Exception as e:
            body = ("<h3>m.html 打不开:%s</h3>" % e).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def do_GET(self):
        if not self._guard():
            return
        try:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("pin") and self._pin_ok():
                # ★验证通过就种 Cookie★,否则页面接着请求接口还是 401
                self._cookie = "lyra_pin=%s; Path=/; Max-Age=2592000; SameSite=Lax" % _remote_cfg()["pin"]
        except Exception:
            pass
        p = urllib.parse.urlparse(self.path).path
        if p in ("/", "/m", "/m.html", "/index.html"):
            return self._serve_mobile()
        return super().do_GET()'''

if OLD in t:
    t = t.replace(OLD, NEW, 1)
    print("① do_GET 已改为直接发 m.html + 种 Cookie")
else:
    print("① !! 没匹配到 do_GET,打印现状:")
    i = t.find("class RemoteHandler")
    print(t[i:i+80] if i > 0 else "(没有 RemoteHandler)")
    j = t.find("def do_GET(self):", t.find("def _make_handler"))
    print(t[j:j+420])

# 让 _json / _file 能带上 Set-Cookie
if "self._cookie" in t and "_cookie" not in t.split("class Handler")[0]:
    # 在 Handler 的响应方法里挂上 Cookie(如果 base 类没有这个机制)
    for marker in ('    def _json(self', '    def _file(self'):
        i = t.find(marker)
        if i > 0 and "self._cookie" not in t[i:i + 600]:
            # 在方法体开头插入 Cookie 下发
            k = t.find("\n", t.find(":", i))
            ins = ('\n        if getattr(self, "_cookie", None):\n'
                   '            try:\n'
                   '                self.send_header("Set-Cookie", self._cookie)\n'
                   '                self._cookie = None\n'
                   '            except Exception:\n'
                   '                pass\n')
            # send_header 必须在 send_response 之后 → 插到方法里第一次 send_response 之后
            m = t.find("send_response", i)
            if m > 0:
                e = t.find("\n", m)
                t = t[:e + 1] + ins + t[e + 1:]
                print("② 已在 %s 里挂上 Set-Cookie 下发" % marker.strip())
            break

io.open(P, "w", encoding="utf-8", newline="\n").write(t)
r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % P],
                   capture_output=True, text=True)
print("   语法:", "通过" if r.returncode == 0 else (r.stderr or "")[-250:])
if r.returncode == 0:
    shutil.copy2(P, r"D:\Lyra\app\webapp\server.py")
    print("   已部署")
