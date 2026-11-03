# -*- coding: utf-8 -*-
"""把当前源码打成一个 zip 备份,放进桌面仓库的 _backup/ 里(不上传 GitHub)。

排除:installer/build(WebView2 SDK + 运行环境)、payload(第三方负载)、voices(语音包)、
      __pycache__、*.pyc、以及仓库自身。
"""
import os
import shutil
import time
import zipfile
from pathlib import Path

SRC = Path(r"D:\Unity阅读器")
REPO = Path(os.path.expanduser("~")) / "Desktop" / "Lyra"
BK = REPO / "_backup"
BK.mkdir(parents=True, exist_ok=True)

stamp = time.strftime("%Y%m%d-%H%M")
out = BK / f"Lyra-源码备份-{stamp}.zip"

SKIP_DIRS = {"build", "payload", "voices", "__pycache__", ".venv", "node_modules",
             ".git", "_backup", "dist", "obj", "bin"}
SKIP_EXT = {".pyc", ".pyo", ".zip", ".exe", ".onnx", ".o", ".obj", ".res", ".lib", ".pdb"}

n = 0
total = 0
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for root, dirs, files in os.walk(SRC):
        root_p = Path(root)
        # 顶层与 installer 下的重型目录直接跳过
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            p = root_p / f
            if p.suffix.lower() in SKIP_EXT:
                continue
            if p.stat().st_size > 12 * 1024 * 1024:      # 单个文件超过 12MB 不进备份
                continue
            rel = p.relative_to(SRC)
            try:
                z.write(p, str(rel))
                n += 1
                total += p.stat().st_size
            except Exception as e:
                print("  跳过", rel, e)

print("  备份完成:", out)
print("  文件数 %d,原始大小 %.1f MB,压缩后 %.1f MB" %
      (n, total / 1048576, out.stat().st_size / 1048576))

# 确保 .gitignore 里有 _backup/(zip 本来就被 *.zip 忽略,这里再明确一次)
gi = REPO / ".gitignore"
t = gi.read_text(encoding="utf-8")
if "_backup" not in t:
    gi.write_text(t.rstrip() + "\n\n# ---- 本地备份(不要上传)----\n_backup/\n", encoding="utf-8")
    print("  .gitignore 已加入 _backup/")
else:
    print("  .gitignore 已包含 _backup/")
