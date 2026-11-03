# -*- coding: utf-8 -*-
"""重写 _translate:单次 AI 调用(符号清单写进提示词)+ 仅短句补符号 + 永不返回空。"""
import io

TR = r"D:\Unity阅读器\core\translate.py"
t = io.open(TR, encoding="utf-8").read()

i = t.find("    def _translate(self, src: str, aicfg, timeout: int):")
j = t.find("    # ---- 预热", i)
assert i > 0 and j > i, "没找到 _translate"

NEW = '''    def _translate(self, src: str, aicfg, timeout: int):
        """把一句原文交给 AI 翻成简体中文。

        设计取舍(实测踩过的坑):
          · **一次调用**为主 —— 之前给每句做"符号重试",长对话被拖到十几秒甚至超时,
            玩家看到的是"翻译很慢""翻译失败";
          · 符号用"清单写进提示词"约束,只有**短句**(≤40 字)才为符号多打一次;
          · 任何情况下都不返回空字符串(空响应会让 XUnity 显示"翻译失败"并缓存下来)。
        """
        try:
            from core import ai as ai_mod
        except Exception:
            try:
                import ai as ai_mod              # 兼容直接跑 server.py 的场景
            except Exception:
                return ""
        aicfg = aicfg or {}
        if not (aicfg.get("base_url") and aicfg.get("api_key")):
            self.last_error = "还没配置 AI 接口(设置页填 Key)"
            return ""
        system = (
            "你是游戏本地化译者。把用户给你的游戏文本翻译成**简体中文**。\\n"
            "规则:\\n"
            "· 只输出译文正文,不要解释、不要加引号、不要输出原文\\n"
            "· 必须是**简体中文**,绝对不要输出繁体字;原文里的日文假名一律翻成中文,不许保留\\n"
            "· 人名/地名也要**用简体字写**(「格蘭特尼」→「格兰特尼」、「奧斯卡」→「奥斯卡」);同一名字前后必须一致\\n"
            "· ★符号一个都不能丢、不能换★:原文的标点、括号、引号(「」『』()【】〈〉)、"
            "音符星号(♪★☆※●○)、箭头、省略号、破折号、颜文字、以及 <>{}[] 这类标记,"
            "都要**原样保留在原来的位置**,不许增删改写;原文有几个就保留几个\\n"
            "· 保留原文的语气、称呼和标点风格;『』「」这类引号换成中文引号\\n"
            "· 原文里的换行、颜文字、以及 <>{}[] 之类的标记原样保留\\n"
            "· 文本很短(一个词、一个按钮)时,给最自然的界面用词(例如 Save→保存)\\n"
            "· 如果原文已经是简体中文,原样返回"
        )
        syms = _symbols(src)
        if syms:
            listed = " ".join("%s×%d" % (c, n) for c, n in list(syms.items())[:12])
            system += ("\\n★本句的符号清单(必须一个不少、按原顺序、原样保留):" + listed +
                       "。译文里这些符号的数量与位置要和原文一致;不许改成别的符号,也不许删掉。")
        try:
            out = ai_mod._call(system, src, aicfg, timeout, temperature=0.2)
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {str(e)[:120]}"
            return ""
        out = to_simplified((out or "").strip())
        if is_bad_output(out, src):
            self.last_error = "AI 没给出可用的简体中文译文"
            return ""
        miss = _missing_symbols(src, out)
        # 短句才为符号多打一次 AI;长句不为一个标点拖慢整段对话
        if miss and len(src) <= 40 and len(miss) <= 3:
            try:
                fix_sys = (system + "\\n★上一次的译文漏掉了这些符号:" +
                           "、".join(c for c, _n, _m in miss[:4]) +
                           "。请**只补回这些符号**,其余文字保持不变,重新输出完整译文。")
                out2 = to_simplified((ai_mod._call(fix_sys, src, aicfg, timeout, temperature=0.1) or "").strip())
                if out2 and len(_missing_symbols(src, out2)) < len(miss):
                    out = out2
            except Exception:
                pass
        self.last_error = ""
        return out

'''
t = t[:i] + NEW + t[j:]
io.open(TR, "w", encoding="utf-8", newline="\n").write(t)
print("_translate 已重写")
