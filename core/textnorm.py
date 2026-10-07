# -*- coding: utf-8 -*-
"""文本规整:离线声音包(词典型 VITS)遇到阿拉伯数字会直接跳过("Ignore OOV '7'"),
所以合成前先把数字/常见符号转成中文读法。别的引擎(Edge/本机语音)自己会读数字,
只在离线路径上调用即可。
"""
import re

_DIGITS = "零一二三四五六七八九"
_UNITS = ["", "十", "百", "千"]


def _four(n: int) -> str:
    """0~9999 转中文(不含"万"以上)。"""
    if n == 0:
        return ""
    out = []
    zero = False
    s = str(n)
    ln = len(s)
    for i, ch in enumerate(s):
        d = int(ch)
        pos = ln - i - 1
        if d == 0:
            zero = True
            continue
        if zero and out:
            out.append("零")
        zero = False
        if not (d == 1 and pos == 1 and not out):        # 十几 读"十几"不读"一十几"
            out.append(_DIGITS[d])
        out.append(_UNITS[pos])
    return "".join(out)


def number_to_chinese(n: int) -> str:
    if n == 0:
        return "零"
    neg = n < 0
    n = abs(n)
    parts = []
    for unit, base in (("亿", 100000000), ("万", 10000)):
        if n >= base:
            parts.append(_four(n // base) + unit)
            n %= base
    if n:
        if parts and n < 1000:
            parts.append("零")
        parts.append(_four(n))
    return ("负" if neg else "") + "".join(parts)


def _digits_one_by_one(s: str) -> str:
    return "".join(_DIGITS[int(c)] for c in s)


_SYM = {"%": "百分之", "℃": "摄氏度", "°": "度", "&": "和", "@": "艾特", "#": "号"}


def normalize(text: str) -> str:
    """把数字与几个常见符号转成中文读法。"""
    if not text:
        return text
    s = text

    # 百分比:50% → 百分之五十
    s = re.sub(r"(\d+(?:\.\d+)?)%", lambda m: "百分之" + _num(m.group(1)), s)
    # 小数点:3.14 → 三点一四
    s = re.sub(r"\d+\.\d+", lambda m: _decimal(m.group(0)), s)
    # 长数字串(电话/编号那种)按位读 —— 必须放在普通整数之前,否则会被当成大数
    s = re.sub(r"\d{8,}", lambda m: _digits_one_by_one(m.group(0)), s)
    # 普通整数(1~7 位)
    s = re.sub(r"\d{1,7}", lambda m: number_to_chinese(int(m.group(0))), s)
    for k, v in _SYM.items():
        s = s.replace(k, v)
    return s


def _decimal(x: str) -> str:
    a, b = x.split(".", 1)
    return number_to_chinese(int(a)) + "点" + _digits_one_by_one(b)


def _num(x: str) -> str:
    if "." in x:
        return _decimal(x)
    return number_to_chinese(int(x))
