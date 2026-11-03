# -*- coding: utf-8 -*-
"""① 翻译接口绝不返回空(空了 XUnity 就报"翻译失败");
   ② 符号重试只在短句上做,且失败也返回译文(不再多打 AI、不再拖慢);
   ③ 配置自动备份/恢复:重装程序后设置不会丢。"""
import io
import os

SRV = r"D:\Unity阅读器\webapp\server.py"
TR = r"D:\Unity阅读器\core\translate.py"

# ---------------- ① 接口不返回空 ----------------
t = io.open(SRV, encoding="utf-8").read()
old = '''                try:
                    out = TRANSLATOR.get(src, cfgm.get().get("ai") or {})
                except Exception:
                    out = src
                _note_req(src, out)
                return self._text(out)'''
new = '''                try:
                    out = TRANSLATOR.get(src, cfgm.get().get("ai") or {})
                except Exception:
                    out = src
                if not (out or "").strip():
                    # ★绝不能返回空体★:XUnity 收到空响应就判定"翻译失败"并写进缓存。
                    # 翻不出来就原样返回原文 —— 玩家看到原文,而不是一串"翻译失败"。
                    out = src
                _note_req(src, out)
                return self._text(out)'''
assert old in t
t = t.replace(old, new, 1)

# ---------------- ③ 配置备份 / 恢复 ----------------
if "def cfg_backup" not in t:
    t = t.replace("def data_dir(",
'''def cfg_backup() -> str:
    """配置的备份文件路径。"""
    import os as _os
    return _os.path.join(_os.path.dirname(CFG_PATH), "config.json.bak")


def cfg_snapshot() -> None:
    """每次保存配置时留一份备份(重装程序/误清空时可以恢复)。"""
    try:
        import shutil as _sh
        if os.path.isfile(CFG_PATH):
            _sh.copy2(CFG_PATH, cfg_backup())
    except Exception:
        pass


def cfg_restore_if_lost() -> list:
    """启动时:如果配置明显不完整(比备份小很多),就用备份恢复。

    场景:玩家用安装程序「重新安装」,payload 覆盖 app 目录时把 config.json 冲掉,
    于是游戏库/角色配音/规则/开关状态全没了。有了备份就能自动救回来。
    """
    notes = []
    bak = cfg_backup()
    try:
        if not os.path.isfile(CFG_PATH):
            if os.path.isfile(bak):
                shutil.copy2(bak, CFG_PATH)
                notes.append("配置丢失,已从备份恢复")
            return notes
        if os.path.isfile(bak) and os.path.getsize(bak) > os.path.getsize(CFG_PATH) * 2 + 512:
            shutil.copy2(CFG_PATH, CFG_PATH + ".small")
            shutil.copy2(bak, CFG_PATH)
            notes.append("配置像是被清空了,已用备份恢复(旧的小配置存为 config.json.small)")
    except Exception as e:
        notes.append("配置恢复失败:%s" % e)
    return notes


def data_dir(''', 1)

    # 保存时留备份
    t = t.replace("    def save(self", "    def save(self", 1)
    t = t.replace('''            with open(CFG_PATH, "w", encoding="utf-8") as f:''',
                  '''            cfg_snapshot()                      # 先留一份备份,再写新配置
            with open(CFG_PATH, "w", encoding="utf-8") as f:''', 1)

    # 启动时恢复
    t = t.replace("apply_translate_cfg()\ntry:\n    write_xunity_cfg()",
                  "for _n in cfg_restore_if_lost():\n    add_log(_n, \"info\")\napply_translate_cfg()\ntry:\n    write_xunity_cfg()", 1)
    io.open(SRV, "w", encoding="utf-8", newline="\n").write(t)
    print("① 接口不返回空 ③ 配置备份/恢复 已加入 server.py")
else:
    print("①③ 已存在")

# ---------------- ② 符号重试限流 ----------------
u = io.open(TR, encoding="utf-8").read()
old2 = '''        miss = _missing_symbols(src, out)
        if miss:'''
new2 = '''        miss = _missing_symbols(src, out)
        # ★只有短句才为符号多打一次 AI★:长句多打一次会超时,玩家看到的是"翻译很慢"
        #   甚至"翻译失败"。长句就接受它,别为了一个标点拖慢整段对话。
        if miss and len(src) <= 40 and len(miss) <= 3:'''
assert old2 in u
u = u.replace(old2, new2, 1)

# 仍然缺符号也不要返回空 —— 返回译文
old3 = '''        if _missing_symbols(src, out):
            # 还是对不上 → 这一句宁可显示原文,也绝不给乱码
            self.last_error = "译文符号与原文对不上,这一句按原文显示"
            return ""'''
new3 = '''        if _missing_symbols(src, out):
            # 短句还是对不上 → 按原文显示(短句无伤大雅,而且避免标点错乱)
            if len(src) <= 40:
                self.last_error = "译文符号与原文对不上,这一句按原文显示"
                return ""
            # 长句:符号差一两个就接受,绝不因为一个标点让整段对话"翻译失败"
            self.last_error = ""'''
assert old3 in u
u = u.replace(old3, new3, 1)
io.open(TR, "w", encoding="utf-8", newline="\n").write(u)
print("② 符号重试已限流(仅短句),长句不再多打 AI")
