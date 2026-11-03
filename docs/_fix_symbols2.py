# -*- coding: utf-8 -*-
"""符号保护重做:
   ① 记号换成 [[0]] 这种 ASCII 形式(模型丢记号的情况明显更少);
   ② 还原改成**按文字对齐**(difflib)插入 —— 不再"按比例瞎插"(实测会把句子插乱);
   ③ 兜底:还原后如果符号还是对不上、或译文乱七八糟,就**返回原文**,
      宁可这一句不翻,也绝不给玩家一串乱码。"""
import io

TR = r"D:\Unity阅读器\core\translate.py"
t = io.open(TR, encoding="utf-8").read()

i = t.find("# ★符号占位符★")
j = t.find("def local_convert(text: str) -> str:")
assert i > 0 and j > i, "没找到占位符那段"

NEW = '''# ★符号占位符★
# 光靠提示词约束 AI 是不够的(实测:标点、引号、破折号仍会被改写或吞掉)。
# 做法:把原文里的符号换成 [[0]] [[1]] … 这样的记号再交给 AI —— 记号是"单词",
# 模型不会去翻译它;拿回来按编号还原成原符号。这样符号**在机制上不可能丢**。
_TOK_RE = re.compile(r"\\[\\[(\\d+)\\]\\]")
_TOK_L, _TOK_R = "[[", "]]"


def _protect_symbols(text: str):
    """(带占位符的文本, [原符号, ...])"""
    out, marks = [], []
    for ch in text or "":
        if ch.isspace() or not _SYM_ONLY.match(ch):
            out.append(ch)
            continue
        marks.append(ch)
        out.append("%s%d%s" % (_TOK_L, len(marks) - 1, _TOK_R))
    return "".join(out), marks


def _plain(text: str) -> str:
    """只留"真正的字"(字母/数字/汉字/假名/韩文),用来做对齐。"""
    return "".join(ch for ch in (text or "") if not _SYM_ONLY.match(ch))


def _restore_symbols(text: str, marks: list) -> str:
    """把 [[n]] 还原成原符号。

    模型弄丢记号时,**按文字对齐**把它塞回正确位置(而不是按比例瞎插):
    以"去掉符号后的文字"为骨架做 difflib 对齐,找到第 k 个字在译文里的位置,
    符号就插在它前面 —— 这样插出来的句子仍然是通顺的。
    """
    if not marks:
        return text
    used = set()

    def _sub(m):
        i = int(m.group(1))
        if 0 <= i < len(marks):
            used.add(i)
            return marks[i]
        return ""                                  # 越界记号直接丢掉

    out = _TOK_RE.sub(_sub, text or "")
    lost = [k for k in range(len(marks)) if k not in used]
    if not lost:
        return out
    # 骨架对齐:src 里第 k 个符号前面的"字数"
    src_plain, before = "", []
    for ch in text or "":
        m = _TOK_RE.match(ch)
        before.append(len(src_plain))
        if not _SYM_ONLY.match(ch):
            src_plain += ch
    out_plain = _plain(out)
    # 找出 out_plain 的每个字符对应到 src_plain 的位置
    import difflib
    sm = difflib.SequenceMatcher(None, src_plain, out_plain, autojunk=False)
    mapping = {}
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            mapping[a + k] = b + k
    # 逐个补回丢失的符号:插在"它后面那个字"在译文里的位置之前
    for k in lost:
        pos = None
        for idx in range(k + 1, len(before)):
            p = mapping.get(before[idx])
            if p is not None:
                pos = p
                break
        if pos is None:
            pos = len(out)
        out = out[:pos] + marks[k] + out[pos:]
        for key in list(mapping.keys()):
            if mapping[key] >= pos:
                mapping[key] += 1
    return out


def _looks_broken(out: str, src: str) -> bool:
    """还原之后还是乱的吗?(符号比原文还多 / 文字几乎没了 / 出现成串符号)"""
    if not out:
        return True
    if len(_plain(out)) < max(1, len(_plain(src)) // 3):
        return True
    so, ss = _symbols(out), _symbols(src)
    if sum(so.values()) > sum(ss.values()) + 2:
        return True
    if re.search(r"[^\\w\\s][^\\w\\s]{4,}", out):
        return True
    return False


'''
t = t[:i] + NEW + t[j:]

# 调用处:还原 → 乱码就退回原文
t = t.replace('''        out = _restore_symbols((out or "").strip(), marks)      # ⟦n⟧ → 原符号
        out = to_simplified(out)
        miss = _missing_symbols(src, out)''',
              '''        out = _restore_symbols((out or "").strip(), marks)      # [[n]] → 原符号
        out = to_simplified(out)
        if _looks_broken(out, src):
            # 还原失败 → 用原文重来一次(不带占位符,纯提示词约束);再不行就返回原文
            self.last_error = "符号还原失败,已重试"
            try:
                out = to_simplified((ai_mod._call(system, src, aicfg, timeout, temperature=0.1) or "").strip())
            except Exception:
                out = ""
            if _looks_broken(out, src) or _missing_symbols(src, out):
                self.last_error = "译文与原文符号对不上,这一句按原文显示"
                return ""
        miss = _missing_symbols(src, out)''', 1)

# 提示词里记号写法同步
t = t.replace('"\\n★这条文本里的 ⟦0⟧ ⟦1⟧ … 是**占位符**',
              '"\\n★这条文本里的 [[0]] [[1]] … 是**占位符**')
io.open(TR, "w", encoding="utf-8", newline="\n").write(t)
print("符号保护已重做:ASCII 记号 + 对齐还原 + 乱码退回原文")
