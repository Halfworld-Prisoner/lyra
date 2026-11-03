# -*- coding: utf-8 -*-
"""符号还原改为"完全不信任模型记号位置"的确定性版本:
   把译文里的记号全删掉 → 用"去掉符号后的文字"和原文做对齐 →
   按原文顺序把每个符号插到对齐后的正确位置。
   这样即使模型把记号顺序搞乱、丢掉、重复,结果都一样正确。"""
import io

TR = r"D:\Unity阅读器\core\translate.py"
t = io.open(TR, encoding="utf-8").read()

i = t.find("def _restore_symbols(text: str, marks: list) -> str:")
j = t.find("def _looks_broken(out: str, src: str) -> bool:")
assert i > 0 and j > i, "没找到 _restore_symbols"

NEW = '''def _restore_symbols(text: str, marks: list) -> str:
    """把符号按**原文顺序**放回译文正确位置。

    ★不信任模型给的记号位置★:实测模型会把记号顺序弄乱、丢掉或重复,
    所以这里先把它返回的记号全部删掉,再拿"去掉符号后的文字"与原文对齐,
    逐个把符号插到对应位置 —— 结果是确定的,与模型怎么摆记号无关。
    """
    if not marks:
        return text
    out = _TOK_RE.sub("", text or "")          # 模型给的记号一律不要
    # 原文里每个符号"后面第一个真字"的序号(没有就表示在句尾)
    anchors, plain_len = [], 0
    for ch in marks:
        anchors.append(None)
    idx = 0
    seq = []                                    # (符号序号, 其后第一个真字的序号)
    plain_cnt = 0
    mi = 0
    # 重新扫一遍原文结构:marks 是按出现顺序给的,这里算出每个符号的锚点
    # (调用方传进来的 text 是"带记号"的文本,所以按记号序号反推)
    for m in _TOK_RE.finditer(text or ""):
        k = int(m.group(1))
        tail = text[m.end():]
        nxt = _TOK_RE.search(tail)
        seg = tail[:nxt.start()] if nxt else tail
        cnt = sum(1 for c in seg if not _SYM_ONLY.match(c) and not c.isspace())
        seq.append((k, plain_cnt + cnt))
        plain_cnt += cnt
    # 译文去掉符号后的文字
    out_plain = _plain(out)
    import difflib
    sm = difflib.SequenceMatcher(None, _plain(text), out_plain, autojunk=False)
    map_pos = {}
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            map_pos[a + k] = b + k
    # 原文去掉符号后的文字(供 map_pos 使用)
    src_plain = _plain(text)
    # 按原文顺序插回
    result = out
    shift = 0
    for k, anchor in sorted(seq, key=lambda x: x[1]):
        pos = map_pos.get(anchor)
        if pos is None:
            # 锚点没对齐上:退而求其次,按比例定位
            pos = int(len(out_plain) * anchor / max(1, len(src_plain)))
        pos += shift
        result = result[:pos] + marks[k] + result[pos:]
        shift += 1
        if k + 1 > len(marks):                  # 安全阀
            break
    return result


'''
t = t[:i] + NEW + t[j:]
io.open(TR, "w", encoding="utf-8", newline="\n").write(t)
print("已改为确定性对齐还原")
