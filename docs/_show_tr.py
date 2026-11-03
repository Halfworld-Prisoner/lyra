# -*- coding: utf-8 -*-
"""② 的稳妥改法:直接在当前文本上做(不依赖旧字符串)。"""
import io
import re

TR = r"D:\Unity阅读器\core\translate.py"
t = io.open(TR, encoding="utf-8").read()

# 打印当前相关片段,便于确认
i = t.find("miss = _missing_symbols")
print("---- 当前片段 ----")
print(t[i - 200:i + 900])
print("---- 结束 ----")
