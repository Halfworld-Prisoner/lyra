# -*- coding: utf-8 -*-
r"""修复被上一个补丁改坏的启动段:
   应该是 —— 先按配置恢复远程监听,再进 for 循环找可用端口。"""
import io
import re
import subprocess

P = r"D:\Unity阅读器\webapp\server.py"
t = io.open(P, encoding="utf-8").read()

bad = re.search(
    r"    srv = None\n"
    r"    for port in range\(PORT, PORT \+ 20\):\n"
    r"        try:\n"
    r"            # 启动时按配置恢复\"跨设备访问\"\n"
    r"    try:\n"
    r"        if _remote_cfg\(\)\.get\(\"on\"\):\n"
    r"            remote_start\(\)\n"
    r"    except Exception:\n"
    r"        pass\n"
    r"    srv = Server\(\\(\"127\.0\.0\.1\", port\\), Handler\)\n"
    r"            PORT_USED = port\n"
    r"            break\n"
    r"        except OSError:\n"
    r"            continue\n", t)
assert bad, "没匹配到被改坏的那段"

good = '''    srv = None
    # 启动时按配置恢复"跨设备访问"(远程监听是另一个端口,和主服务互不影响)
    try:
        if _remote_cfg().get("on"):
            remote_start()
    except Exception:
        pass
    for port in range(PORT, PORT + 20):
        try:
            srv = Server(("127.0.0.1", port), Handler)
            PORT_USED = port
            break
        except OSError:
            continue
'''
t = t[:bad.start()] + good + t[bad.end():]
io.open(P, "w", encoding="utf-8", newline="\n").write(t)

r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % P],
                   capture_output=True, text=True)
ok = r.returncode == 0
print("语法:", "通过" if ok else (r.stderr or "")[-300:])

if ok:
    import shutil
    shutil.copy2(P, r"D:\Lyra\app\webapp\server.py")
    print("已部署")
