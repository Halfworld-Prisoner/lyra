# -*- coding: utf-8 -*-
"""把用户数据目录也改成英文名: %LOCALAPPDATA%\\LingYueReader -> %LOCALAPPDATA%\\Lyra
   带**兼容回退**:新目录不存在时仍然读老目录,并自动把老目录搬过去(不删原件)。"""
import io
import os

# ① voices.py:数据目录改名 + 兼容老目录
p = r"D:\Unity阅读器\core\voices.py"
t = io.open(p, encoding="utf-8").read()
old = '''def user_dir() -> Path:
    """玩家下载的包放在这里(不需要管理员权限)。"""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "LingYueReader" / "voices"'''
new = '''def user_dir() -> Path:
    """玩家下载的语音包放在这里(不需要管理员权限)。

    英文目录名(Lyra);以前叫 LingYueReader —— 新目录还不存在而老目录在时,
    **自动把老目录整体搬过来**(搬不动就继续用老目录,绝不丢玩家下载过的包)。
    """
    base = Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))
    new_dir = base / "Lyra" / "voices"
    old_dir = base / "LingYueReader" / "voices"
    if not new_dir.exists() and old_dir.is_dir():
        try:
            new_dir.parent.mkdir(parents=True, exist_ok=True)
            os.replace(str(old_dir), str(new_dir))       # 同盘:原子改名
        except Exception:
            try:
                import shutil as _sh
                _sh.copytree(old_dir, new_dir)
            except Exception:
                return old_dir                            # 实在不行就继续用老的
    return new_dir'''
assert old in t, "user_dir 没找到"
io.open(p, "w", encoding="utf-8", newline="\n").write(t.replace(old, new, 1))
print("voices.py:数据目录改为 %LOCALAPPDATA%\\Lyra\\voices(兼容老目录)")

# ② 其它引用 LingYueReader 的地方
for rel in ("core/games.py", "config.py", "webapp/server.py", "core/floatwin.py", "core/tts.py"):
    fp = os.path.join(r"D:\Unity阅读器", rel.replace("/", "\\"))
    if not os.path.isfile(fp):
        continue
    s = io.open(fp, encoding="utf-8").read()
    if "LingYueReader" in s:
        n = s.count("LingYueReader")
        s = s.replace("LingYueReader", "Lyra")
        io.open(fp, "w", encoding="utf-8", newline="\n").write(s)
        print("  %-18s 替换 %d 处" % (rel, n))
print("完成")
