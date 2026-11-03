# -*- coding: utf-8 -*-
"""① 用 OpenCC 权威表补齐简繁转换;② 提示词改为"名字也要转简体" + 符号必须原样保留;
   ③ 加本地转换快路径(短名字不问 AI);④ 译文漏符号时自动重试一次。"""
import base64
import io
import os

SRC = r"D:\Unity阅读器"
TR = os.path.join(SRC, "core", "translate.py")
DATA = os.path.join(SRC, "core", "data", "t2s.txt")

# ---------- ① 生成完整简繁表 ----------
raw_path = os.path.expandvars(r"%TEMP%\t2s_raw.txt")
if os.path.isfile(raw_path) and os.path.getsize(raw_path) > 20000:
    pairs = {}
    for ln in io.open(raw_path, encoding="utf-8", errors="ignore"):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        parts = ln.split()
        if len(parts) >= 2:
            pairs[parts[0]] = parts[1]        # 繁体 -> 第一个简体写法
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    io.open(DATA, "w", encoding="utf-8", newline="\n").write(
        "\n".join("%s %s" % (k, v) for k, v in sorted(pairs.items())))
    print("① 完整简繁表已生成:%d 条 -> core/data/t2s.txt (%.1f KB)"
          % (len(pairs), os.path.getsize(DATA) / 1024))
else:
    print("!! 没找到下载好的 OpenCC 表,跳过", raw_path)

# ---------- ② 改 translate.py ----------
t = io.open(TR, encoding="utf-8").read()

# 2.1 to_simplified:优先用完整表
OLD_T2S_START = "def to_simplified(s: str) -> str:"
i = t.find(OLD_T2S_START)
j = t.find("\n\n", i)
NEW_T2S = '''_FULL_T2S = None


def _load_full_t2s():
    """加载 OpenCC 的完整简繁表(core/data/t2s.txt)。

    只带一张内置小表是不够的 —— 实测「格蘭特尼」「奧斯卡」这种名字会漏转,
    因为表里没有 蘭/奧。完整表 3000+ 条,覆盖常用繁体字。
    """
    global _FULL_T2S
    if _FULL_T2S is not None:
        return _FULL_T2S
    table = {}
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "data", "t2s.txt")
        if os.path.isfile(path):
            for ln in io.open(path, encoding="utf-8"):
                parts = ln.split()
                if len(parts) >= 2:
                    table[parts[0]] = parts[1]
    except Exception:
        table = {}
    _FULL_T2S = table
    return table


def to_simplified(s: str) -> str:
    """繁体 → 简体(优先完整表,失败退回内置小表)。"""
    if not s:
        return s or ""
    full = _load_full_t2s()
    if full:
        return "".join(full.get(ch, T2S.get(ch, ch)) for ch in s)
    return s.translate(T2S)'''
t = t[:i] + NEW_T2S + t[j:]

# 需要 io / os
if "\nimport io\n" not in t:
    t = t.replace("import re\n", "import io\nimport os\nimport re\n", 1)

# 2.2 符号体检 + 本地快路径
if "_missing_symbols" not in t:
    t = t.replace("def is_bad_output(out: str, src: str) -> bool:",
'''# 所有"非文字"字符都算符号:标点、括号、引号、音符星号、颜文字零件、拉丁字母与数字**不算**
_SYM_ONLY = re.compile(r"[^\\w\\u4e00-\\u9fff\\u3040-\\u30ff\\uac00-\\ud7af]", re.UNICODE)


def _symbols(text: str) -> dict:
    """统计一句里的符号(去掉空白),用于校验译文有没有丢符号。"""
    out = {}
    for ch in (text or ""):
        if ch.isspace():
            continue
        if _SYM_ONLY.match(ch):
            out[ch] = out.get(ch, 0) + 1
    return out


def _missing_symbols(src: str, out: str) -> list:
    """译文里少了 / 少了几次的符号。返回 [(符号, 原次数, 译次数), ...]"""
    a, b = _symbols(src), _symbols(out)
    bad = []
    for ch, n in a.items():
        m = b.get(ch, 0)
        if m < n:
            bad.append((ch, n, m))
    return bad


def local_convert(text: str) -> str:
    """短名字 / 界面词:直接用简繁表转,不问 AI。

    好处:① 不花 token、不等待;② 比模型更准(模型会"贴心地"保留繁体名字);
    只处理"纯汉字 + 符号"且很短(<= 14 字)的串,长句仍交给 AI 翻译。
    """
    s = (text or "").strip()
    if not s or len(s) > 14:
        return ""
    if _KANA.search(s) or _HANGUL.search(s) or _ASCII_WORD.search(s):
        return ""
    if not _HAN.search(s):
        return ""
    conv = to_simplified(s)
    return conv if conv != s else ""


def is_bad_output(out: str, src: str) -> bool:''', 1)

# 2.3 get() 里先走本地快路径
t = t.replace('''        if not needs_translation(src):
''',
'''        _local = local_convert(src)          # 短名字/界面词:本地转,不问 AI
        if _local:
            with self.lock:
                self.cache[src] = _local
                self.stat["hit_local"] = self.stat.get("hit_local", 0) + 1
            self._dirty = True
            return _local
        if not needs_translation(src):
''', 1)

# 2.4 提示词:名字也转简体 + 符号必须原样保留
t = t.replace('''            "· 人名/地名保留原文的汉字写法(日文汉字照抄),专有名词前后一致\\n"''',
              '''            "· 人名/地名也要**用简体字写**(「格蘭特尼」→「格兰特尼」、「奧斯卡」→「奥斯卡」);同一名字前后必须一致\\n"
            "· ★符号一个都不能丢、不能换★:原文的标点、括号、引号(「」『』()【】〈〉)、"
            "音符星号(♪★☆※●○)、箭头、省略号、破折号、颜文字、以及 <>{}[] 这类标记,"
            "都要**原样保留在原来的位置**,不许增删改写;原文有几个就保留几个\\n"''', 1)

# 2.5 漏符号时带证据重试一次
t = t.replace('''        out = to_simplified((out or "").strip())
        if is_bad_output(out, src):''',
'''        out = to_simplified((out or "").strip())
        miss = _missing_symbols(src, out)
        if miss and out:
            # 漏了符号 → 把"哪个符号、原文几次、你只给了几次"讲清楚,再要一次
            detail = "、".join("%s(原文 %d 个,你只给了 %d 个)" % (c, n, m) for c, n, m in miss[:6])
            fix_sys = (system + "\\n★上一次的译文漏掉了符号:" + detail +
                       "。请**只补回这些符号**、其余文字保持不变,重新输出完整译文。")
            try:
                out2 = to_simplified((ai_mod._call(fix_sys, src, aicfg, timeout, temperature=0.1) or "").strip())
                if out2 and len(_missing_symbols(src, out2)) < len(miss):
                    out = out2
            except Exception:
                pass
        if is_bad_output(out, src):''', 1)

io.open(TR, "w", encoding="utf-8", newline="\n").write(t)
print("② translate.py 已改:完整表 + 本地快路径 + 提示词 + 符号校验重试")
