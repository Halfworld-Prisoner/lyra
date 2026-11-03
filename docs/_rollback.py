# -*- coding: utf-8 -*-
r"""回滚:把项目恢复到 _backup 里的那份源码备份(自定义 UI 那批改动全部撤掉)。

  · 备份包:C:\Users\bgyLe\Desktop\Lyra\_backup\Lyra-源码备份-*.zip
  · 还原:解压覆盖 D:\Unity阅读器(installer/build、payload、voices 不在备份里,保持不动)
  · 删除:这次新增的文件(uilayout.py / chrome.js / widgets.js / board.js / designer.js /
          designer.css / designer.html)以及部署目录里的同名文件
  · 清理:config.json 里的 ui 配置块
  · 重启应用并验证
"""
import glob
import json
import os
import shutil
import subprocess
import zipfile

SRC = r"D:\Unity阅读器"
APP = r"D:\Lyra\app"
REPO = os.path.join(os.path.expanduser("~"), "Desktop", "Lyra")

NEW_FILES = [
    r"core\uilayout.py",
    r"webapp\static\designer.html",
    r"webapp\static\css\designer.css",
    r"webapp\static\js\ui\chrome.js",
    r"webapp\static\js\ui\widgets.js",
    r"webapp\static\js\views\board.js",
    r"webapp\static\js\views\designer.js",
]

# ① 停应用
for name in ("Lyra", "聆阅"):
    subprocess.run(["taskkill", "/F", "/IM", name + ".exe"], capture_output=True)
for p in ("pythonw",):
    subprocess.run(["taskkill", "/F", "/IM", p + ".exe"], capture_output=True)
import time
time.sleep(3)
print("① 已停止应用")

# ② 找最近的备份
zips = sorted(glob.glob(os.path.join(REPO, "_backup", "Lyra-源码备份-*.zip")))
assert zips, "没找到备份包"
bk = zips[-1]
print("② 使用备份:", os.path.basename(bk))

# ③ 解压覆盖
with zipfile.ZipFile(bk) as z:
    names = z.namelist()
    z.extractall(SRC)
print("   已还原 %d 个文件" % len(names))

# ④ 删除这次新增的文件(源码 + 部署目录都要删)
for rel in NEW_FILES:
    for base in (SRC, APP):
        p = os.path.join(base, rel)
        if os.path.isfile(p):
            os.remove(p)
            print("   删除", p)

# ⑤ 部署目录同步成还原后的源码(不删 config.json / server.port)
for rel in (r"webapp\server.py", r"config.py", r"webapp\static\index.html",
            r"webapp\static\js\boot.js", r"webapp\static\js\state.js",
            r"webapp\static\js\views\settings.js", r"core\storyhook.py"):
    s, d = os.path.join(SRC, rel), os.path.join(APP, rel)
    if os.path.isfile(s):
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)
print("⑤ 部署目录已同步")

# ⑥ config.json 去掉 ui 块
cfg_path = os.path.join(APP, "config.json")
try:
    d = json.load(open(cfg_path, encoding="utf-8-sig"))
    if "ui" in d:
        d.pop("ui")
        json.dump(d, open(cfg_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("⑥ 已从 config.json 移除 ui 配置")
    else:
        print("⑥ config.json 里没有 ui 配置")
except Exception as e:
    print("⑥ 配置处理失败:", e)

# ⑦ 重启应用
subprocess.Popen([r"D:\Lyra\Lyra.exe"])
print("⑦ 已重启应用")
