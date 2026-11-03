# -*- coding: utf-8 -*-
"""符号保护改为"绝不乱码"策略:
   · 不再用占位符/对齐插入(实测会插错位置 → 乱码,比丢符号更糟)
   · 提示词里带上**这一句实际出现的符号清单**,要求原样保留
   · 译文缺符号 → 带着"缺了哪个、几次"重试一次
   · 重试仍缺 → 这一句返回原文(玩家看到原文,不会看到乱码)"""
import io

TR = r"D:\Unity阅读器\core\translate.py"
t = io.open(TR, encoding="utf-8").read()

# ① 调用处:用原文直发 + 把符号清单写进系统提示
old = '''        prot, marks = _protect_symbols(src)          # 符号 → ⟦n⟧
        sys2 = system
        if marks:
            sys2 = (system + "\\n★这条文本里的 [[0]] [[1]] … 是**占位符**,代表原文的标点与符号。"
                             "你必须把它们**原样、按原顺序全部保留**在译文里(数量一个不少),"
                             "绝对不要翻译、删除、改动或新增这些记号。")
        try:
            out = ai_mod._call(sys2, prot, aicfg, timeout, temperature=0.2)
        except Exception as e:'''
new = '''        # 把这一句实际出现的符号列成清单写进提示词 —— 比笼统说"保留符号"有效得多
        syms = _symbols(src)
        sys2 = system
        if syms:
            listed = " ".join("%s×%d" % (c, n) for c, n in list(syms.items())[:14])
            sys2 = (system + "\\n★本句的符号清单(必须一个不少、按原顺序、原样保留):" + listed +
                    "。译文里这些符号的数量与位置要和原文一致;不许改成别的符号,也不许删掉。")
        try:
            out = ai_mod._call(sys2, src, aicfg, timeout, temperature=0.2)
        except Exception as e:'''
assert old in t, "调用处没找到"
t = t.replace(old, new, 1)

# ② 还原与"乱码判定"整段撤掉,改成:缺符号 → 重试 → 仍缺 → 返回原文
i = t.find("        out = _restore_symbols((out or \"\").strip(), marks, src)")
j = t.find("        if is_bad_output(out, src):")
assert i > 0 and j > i, "还原段没找到"
NEW = '''        out = to_simplified((out or "").strip())
        miss = _missing_symbols(src, out)
        if miss:
            # 缺符号 → 把"缺了哪个、原文几次、你给了几次"讲清楚,再要一次
            detail = "、".join("%s(原文 %d 个,你只给了 %d 个)" % (c, n, m) for c, n, m in miss[:6])
            fix_sys = (system + "\\n★上一次的译文漏掉/改动了这些符号:" + detail +
                       "。请**只补回这些符号**、其余文字保持不变,重新输出完整译文。")
            try:
                out2 = to_simplified((ai_mod._call(fix_sys, src, aicfg, timeout, temperature=0.1) or "").strip())
                if out2 and len(_missing_symbols(src, out2)) < len(miss):
                    out = out2
            except Exception:
                pass
        if _missing_symbols(src, out):
            # 还是对不上 → 这一句宁可显示原文,也绝不给乱码
            self.last_error = "译文符号与原文对不上,这一句按原文显示"
            return ""
'''
t = t[:i] + NEW + t[j:]

# ③ 清掉不再使用的 _looks_broken(留个说明,避免以后误用)
t = t.replace("def _looks_broken(out: str, src: str) -> bool:",
              "def _looks_broken(out: str, src: str) -> bool:   # 保留但不再使用:占位符方案已撤\n    # 曾经用它判"译文是否乱码",但会把合法的 ……—— 误判,因此改为"缺符号就退回原文"", 1)
io.open(TR, "w", encoding="utf-8", newline="\n").write(t)
print("已改为:符号清单提示 + 缺符号重试 + 仍缺则显示原文")
