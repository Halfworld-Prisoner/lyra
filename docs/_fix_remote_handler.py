# -*- coding: utf-8 -*-
r"""修:RemoteHandler 在 Handler 类定义之前就被求值 → NameError → 后端起不来。
   改成把类放进 _make_handler() 里延迟创建(调用时 Handler 一定已存在)。"""
import io
import re
import subprocess

P = r"D:\Unity阅读器\webapp\server.py"
t = io.open(P, encoding="utf-8").read()

m = re.search(r"class RemoteHandler\(Handler\):\n(?:.*\n)*?(?=\ndef remote_start\()", t)
assert m, "找不到 RemoteHandler"
body = m.group(0)

# 取出类体,缩进 +4,包进工厂函数
inner = body.split("\n", 1)[1]
inner_ind = "\n".join(("    " + ln) if ln.strip() else ln for ln in inner.split("\n"))
factory = ("def _make_handler():\n"
           "    \"\"\"延迟创建远程处理器(此时 Handler 一定已定义)。\"\"\"\n\n"
           "    class RemoteHandler(Handler):\n" + inner_ind + "\n"
           "    return RemoteHandler\n\n\n")

t = t[:m.start()] + factory + t[m.end():]
t = t.replace('srv = ThreadingHTTPServer(("0.0.0.0", p), RemoteHandler)',
              'srv = ThreadingHTTPServer(("0.0.0.0", p), _make_handler())', 1)
io.open(P, "w", encoding="utf-8", newline="\n").write(t)

r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % P],
                   capture_output=True, text=True)
print("语法:", "通过" if r.returncode == 0 else (r.stderr or "")[:300])
print("含 _make_handler:", "def _make_handler" in t, "| 启动用工厂:", "_make_handler())" in t)

# 直接跑一次导入,确认不再 NameError
r2 = subprocess.run(["python", "-c",
                     "import sys; sys.path.insert(0, r'D:\\Unity阅读器');"
                     "import webapp.server as s; print('导入 OK, remote_on =', s.remote_on())"],
                    capture_output=True, text=True, timeout=90, errors="ignore")
print("导入测试:", (r2.stdout or "").strip() or (r2.stderr or "")[-200:])
