# -*- coding: utf-8 -*-
"""把 cfg_backup / cfg_snapshot / cfg_restore_if_lost 三个函数挪到文件前部(定义要在调用之前)。"""
import io

SRV = r"D:\Unity阅读器\webapp\server.py"
t = io.open(SRV, encoding="utf-8").read()

i = t.find("def cfg_backup() -> str:")
j = t.find("def data_dir(", i)
assert i > 0 and j > i, "没找到那三个函数"
block = t[i:j]
t = t[:i] + t[j:]                                  # 先摘出来

# 插到 CFG_PATH 定义之后(那里最早、且 CFG_PATH 已存在)
anchor = None
for cand in ("CFG_PATH = ", "CFG_PATH=", "ROOT = "):
    k = t.find(cand)
    if k > 0:
        anchor = t.find("\n", k) + 1
        break
assert anchor, "找不到插入点"
t = t[:anchor] + "\n" + block + "\n" + t[anchor:]
io.open(SRV, "w", encoding="utf-8", newline="\n").write(t)
print("已把三个配置函数挪到前部")
# 自检
import py_compile
py_compile.compile(SRV, doraise=True)
print("语法通过")
