# -*- coding: utf-8 -*-
"""符号还原(最终版):锚点从**原文**算,位置靠**对齐**定,模型给的记号全部丢弃。"""
import io

TR = r"D:\Unity阅读器\core\translate.py"
t = io.open(TR, encoding="utf-8").read()

i = t.find("def _restore_symbols(text: str, marks: list) -> str:")
j = t.find("def _looks_broken(out: str, src: str) -> bool:")
assert i > 0 and j > i

NEW = '''def _restore_symbols(text: str, marks: list, src: str = "") -> str:
    """把符号按**原文顺序**放回译文正确位置(text=模型返回的译文, src=原文)。

    ★丢弃模型给的记号位置★:实测模型会把记号弄乱、丢掉或重复,
    所以先把它返回的记号全删掉,再用"去掉符号后的文字"与原文做对齐(锚点取自原文),
    逐个把符号插回去 —— 结果确定,与模型怎么摆记号无关。
    """
    if not marks:
        return text
    out = _TOK_RE.sub("", text or "")
    base = src or ""
    if not base:
        return out + "".join(marks)
    # ① 锚点:原文里每个符号的"前面有多少个真字"
    src_plain, anchors = [], []
    for ch in base:
        if ch.isspace():
            continue
        if _SYM_ONLY.match(ch):
            anchors.append(len(src_plain))
        else:
            src_plain.append(ch)
    if len(anchors) != len(marks):          # 极端情况下按少的来,避免错位
        anchors = anchors[:len(marks)] + [len(src_plain)] * max(0, len(marks) - len(anchors))
    # ② 对齐:原文骨架 ↔ 译文骨架
    out_plain = _plain(out)
    import difflib
    sm = difflib.SequenceMatcher(None, "".join(src_plain), out_plain, autojunk=False)
    pos_of = {}
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            pos_of[a + k] = b + k
    # ③ 按顺序插回(带偏移)
    res, shift = out, 0
    for i2, anc in enumerate(anchors):
        p = pos_of.get(anc)
        if p is None:
            p = int(len(out_plain) * anc / max(1, len(src_plain)))
        p = max(0, min(len(res), p + shift))
        res = res[:p] + marks[i2] + res[p:]
        shift += 1
    return res


'''
t = t[:i] + NEW + t[j:]

# 两处调用都补上原文参数
t = t.replace("out = _restore_symbols((out or \"\").strip(), marks)      # [[n]] → 原符号",
              "out = _restore_symbols((out or \"\").strip(), marks, src)   # [[n]] → 原符号(按原文对齐)")
t = t.replace("out2 = _restore_symbols((ai_mod._call(fix_sys, prot, aicfg, timeout, temperature=0.1) or \"\").strip(), marks)",
              "out2 = _restore_symbols((ai_mod._call(fix_sys, prot, aicfg, timeout, temperature=0.1) or \"\").strip(), marks, src)")
io.open(TR, "w", encoding="utf-8", newline="\n").write(t)
print("已修正:锚点取自原文 + 调用传原文")
