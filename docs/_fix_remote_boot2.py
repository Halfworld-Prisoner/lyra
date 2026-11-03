# -*- coding: utf-8 -*-
r"""按行号修复启动段(不用正则,避免转义问题);若仍不通过 → 回退到仓库里 v1.4.0 的 server.py。"""
import io
import os
import shutil
import subprocess

SRC = r"D:\Unity阅读器"
P = os.path.join(SRC, "webapp", "server.py")
APP = r"D:\Lyra\app\webapp\server.py"

lines = io.open(P, encoding="utf-8").read().split("\n")

# 找到被改坏的起点:srv = None
i = None
for k, l in enumerate(lines):
    if l.strip() == "srv = None" and k > 1000:
        i = k
        break
print("  srv = None 在第", (i or -1) + 1, "行")

GOOD = '''    srv = None
    # 启动时按配置恢复"跨设备访问"(远程监听用另一个端口,和主服务互不影响)
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
            continue'''.split("\n")

if i is not None:
    # 找到这段的结束位置(遇到 "if not srv:" 为止)
    j = i
    while j < len(lines) and lines[j].strip() != "if not srv:":
        j += 1
    print("  替换 %d~%d 行" % (i + 1, j))
    lines = lines[:i] + GOOD + [""] + lines[j:]
    io.open(P, "w", encoding="utf-8", newline="\n").write("\n".join(lines))

r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % P],
                   capture_output=True, text=True)
if r.returncode == 0:
    print("  语法通过 ✓ → 部署")
    shutil.copy2(P, APP)
else:
    print("  语法仍失败 → 回退到仓库 v1.4.0 的 server.py")
    print((r.stderr or "")[-200:])
    shutil.copy2(os.path.join(os.path.expanduser("~"), "Desktop", "Lyra", "webapp", "server.py"), P)
    r2 = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % P],
                        capture_output=True, text=True)
    print("  回退后语法:", "通过 ✓" if r2.returncode == 0 else (r2.stderr or "")[-200:])
    if r2.returncode == 0:
        shutil.copy2(P, APP)
        print("  注意:回退版**没有**跨设备访问和浏览器自动跳转,是 v1.4.0 的原样")
