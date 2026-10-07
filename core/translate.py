# -*- coding: utf-8 -*-
r"""文本翻译(把游戏里的原文实时换成简体中文)。

流程(和「游戏一键汉化工具」同一个思路,只是翻译后端换成本机的 AI):
    游戏 set_text(日文) → XUnity.AutoTranslator 拦下 → GET 本机 /api/translate
    → 这里查缓存 / 调 AI → 返回**纯文本译文** → XUnity 把译文写回游戏文本框

几条硬要求(踩过才知道):
  · **响应体必须是纯文本译文本身** —— XUnity 的 CustomTranslate 不做任何解析,
    返回 JSON 它会把整串 JSON 当译文显示出来。
  · 出错必须**原样返回原文**(HTTP 200):返回非 200 会让插件记失败,连续 5 次它自己关掉。
  · 只输出简体中文:模型偶尔会把繁体/日文原样吐回来,这里做一次校验 + 兜底转简体。
  · 译文缓存要落盘:XUnity 自己也会把译文写进游戏的 Translation\ 目录,
    但我们这份缓存是给"阅读器"用的(离线预览、统计、朗读译文)。
"""
import json
import os
import io
import os
import re
import threading
import time
from pathlib import Path

# 出现这些 → 需要翻译(日文假名 / 韩文 / 纯英文单词)
_KANA = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff]")
_HANGUL = re.compile(r"[\uac00-\ud7af]")
_HAN = re.compile(r"[\u4e00-\u9fff]")
_ASCII_WORD = re.compile(r"[A-Za-z]{2,}")

# 常见繁体 → 简体兜底表(游戏菜单里最常出现的那批字)。
# 只当"AI 不小心回了繁体"时的保险,不指望它覆盖全部 —— 主体还是靠提示词。
# 注意:必须是**单字**映射(str.maketrans 的要求),多字词要拆成单字。
_T2S = {
    "設": "设", "選": "选", "單": "单", "讀": "读", "檔": "档", "開": "开", "關": "关",
    "閉": "闭", "確": "确", "認": "认", "繼": "继", "續": "续", "遊": "游", "戲": "戏",
    "畫": "画", "聲": "声", "語": "语", "說": "说", "幫": "帮", "記": "记", "錄": "录",
    "鑑": "鉴", "賞": "赏", "圖": "图", "進": "进", "節": "节", "結": "结", "項": "项",
    "變": "变", "顯": "显", "隱": "隐", "載": "载", "儲": "储", "蓋": "盖", "刪": "删",
    "資": "资", "訊": "讯", "態": "态", "經": "经", "驗": "验", "級": "级", "裝": "装",
    "備": "备", "敵": "敌", "戰": "战", "鬥": "斗", "勝": "胜", "敗": "败", "隊": "队",
    "員": "员", "夥": "伙", "們": "们", "個": "个", "為": "为", "會": "会", "來": "来",
    "時": "时", "間": "间", "現": "现", "這": "这", "裡": "里", "樣": "样", "麼": "么",
    "幾": "几", "點": "点", "種": "种", "還": "还", "讓": "让", "給": "给", "對": "对",
    "錯": "错", "過": "过", "應": "应", "該": "该", "無": "无", "愛": "爱", "願": "愿",
    "覺": "觉", "頭": "头", "腦": "脑", "體": "体", "臉": "脸", "髮": "发", "腳": "脚",
    "隻": "只", "雙": "双", "張": "张", "實": "实", "際": "际", "總": "总", "統": "统",
    "稱": "称", "號": "号", "碼": "码", "網": "网", "頁": "页", "連": "连", "線": "线",
    "絡": "络", "傳": "传", "額": "额", "價": "价", "錢": "钱", "幣": "币", "費": "费",
    "買": "买", "賣": "卖", "貴": "贵", "贈": "赠", "禮": "礼", "藥": "药", "醫": "医",
    "療": "疗", "傷": "伤", "癒": "愈", "復": "复", "甦": "苏", "靈": "灵", "龍": "龙",
    "鳳": "凤", "鷹": "鹰", "馬": "马", "鳥": "鸟", "魚": "鱼", "貓": "猫", "獅": "狮",
    "獸": "兽", "騎": "骑", "劍": "剑", "槍": "枪", "鎧": "铠", "書": "书", "寫": "写",
    "筆": "笔", "紙": "纸", "冊": "册", "課": "课", "業": "业", "學": "学", "師": "师",
    "長": "长", "國": "国", "軍": "军", "團": "团", "營": "营", "爭": "争", "條": "条",
    "約": "约", "規": "规", "則": "则", "權": "权", "責": "责", "務": "务", "職": "职",
    "類": "类", "別": "别", "報": "报", "聞": "闻", "許": "许", "論": "论", "談": "谈",
    "話": "话", "請": "请", "謝": "谢", "歡": "欢", "樂": "乐", "憂": "忧", "慘": "惨",
    "驚": "惊", "嚇": "吓", "懼": "惧", "罵": "骂", "騙": "骗", "謊": "谎", "誠": "诚",
    "證": "证", "據": "据", "標": "标", "準": "准", "檢": "检", "測": "测", "試": "试",
    "誤": "误", "廢": "废", "棄": "弃", "丟": "丢", "尋": "寻", "覓": "觅", "鄉": "乡",
    "遙": "遥", "遠": "远", "邊": "边", "處": "处", "區": "区", "場": "场", "層": "层",
    "階": "阶", "樓": "楼", "門": "门", "牆": "墙", "頂": "顶", "橋": "桥", "車": "车",
    "輪": "轮", "機": "机", "飲": "饮", "飯": "饭", "麵": "面", "湯": "汤", "菸": "烟",
    "煙": "烟", "襪": "袜", "褲": "裤", "鏡": "镜", "鐘": "钟", "錶": "表", "鍵": "键",
    "盤": "盘", "螢": "萤", "餘": "余", "儘": "尽", "盡": "尽", "纔": "才", "姊": "姐",
    "妳": "你", "牠": "它", "壞": "坏", "丟": "丢", "剎": "刹", "劍": "剑", "勁": "劲",
    "動": "动", "務": "务", "厲": "厉", "厭": "厌", "廳": "厅", "嚮": "向", "嚴": "严",
    "囑": "嘱", "團": "团", "圓": "圆", "聖": "圣", "塵": "尘", "墊": "垫", "墳": "坟",
    "奮": "奋", "妝": "妆", "婦": "妇", "嬰": "婴", "孫": "孙", "寬": "宽", "寶": "宝",
    "對": "对", "導": "导", "屆": "届", "嶺": "岭", "巖": "岩", "巔": "巅", "帥": "帅",
    "師": "师", "帳": "帐", "帶": "带", "幀": "帧", "幾": "几", "庫": "库", "廠": "厂",
    "廢": "废", "廟": "庙", "廳": "厅", "彈": "弹", "徑": "径", "徹": "彻", "恆": "恒",
    "態": "态", "憲": "宪", "懷": "怀", "懸": "悬", "戲": "戏", "戶": "户", "掃": "扫",
    "掛": "挂", "採": "采", "揀": "拣", "換": "换", "揮": "挥", "損": "损", "搶": "抢",
    "搖": "摇", "撐": "撑", "撥": "拨", "撓": "挠", "擔": "担", "據": "据", "擴": "扩",
    "攝": "摄", "攜": "携", "敗": "败", "敘": "叙", "斷": "断", "曆": "历", "書": "书",
    "術": "术", "樣": "样", "樹": "树", "機": "机", "橫": "横", "檢": "检", "權": "权",
    "歎": "叹", "歲": "岁", "歷": "历", "歸": "归", "殺": "杀", "殘": "残", "殺": "杀",
    "氣": "气", "決": "决", "沒": "没", "沖": "冲", "淨": "净", "湊": "凑", "準": "准",
    "溝": "沟", "滅": "灭", "滯": "滞", "滿": "满", "漸": "渐", "漲": "涨", "潑": "泼",
    "潔": "洁", "濁": "浊", "濃": "浓", "濤": "涛", "瀉": "泻", "瀋": "沈", "爛": "烂",
    "爭": "争", "爾": "尔", "牆": "墙", "獨": "独", "獲": "获", "獻": "献", "獸": "兽",
    "現": "现", "環": "环", "瑪": "玛", "甦": "苏", "產": "产", "畫": "画", "療": "疗",
    "盡": "尽", "監": "监", "蓋": "盖", "盤": "盘", "眾": "众", "瞭": "了", "矯": "矫",
    "礦": "矿", "碼": "码", "礎": "础", "礙": "碍", "禮": "礼", "禱": "祷", "離": "离",
    "種": "种", "積": "积", "穩": "稳", "窮": "穷", "竄": "窜", "競": "竞", "筆": "笔",
    "節": "节", "範": "范", "築": "筑", "簡": "简", "簽": "签", "籃": "篮", "籌": "筹",
    "籠": "笼", "粵": "粤", "精": "精", "緊": "紧", "糾": "纠", "紅": "红", "紋": "纹",
    "納": "纳", "純": "纯", "紙": "纸", "級": "级", "素": "素", "索": "索", "紫": "紫",
    "累": "累", "細": "细", "終": "终", "組": "组", "結": "结", "絕": "绝", "統": "统",
    "絲": "丝", "綁": "绑", "經": "经", "綠": "绿", "維": "维", "綱": "纲", "網": "网",
    "緊": "紧", "緒": "绪", "線": "线", "練": "练", "緩": "缓", "編": "编", "緣": "缘",
    "縮": "缩", "總": "总", "績": "绩", "繁": "繁", "織": "织", "繡": "绣", "繼": "继",
    "續": "续", "纏": "缠", "罰": "罚", "罷": "罢", "羅": "罗", "聖": "圣", "聞": "闻",
    "聯": "联", "聰": "聪", "聲": "声", "職": "职", "聽": "听", "肅": "肃", "脅": "胁",
    "脈": "脉", "腳": "脚", "脫": "脱", "臉": "脸", "臨": "临", "舉": "举", "舊": "旧",
    "艙": "舱", "藝": "艺", "節": "节", "薦": "荐", "藍": "蓝", "藥": "药", "處": "处",
    "號": "号", "蟲": "虫", "衝": "冲", "補": "补", "裝": "装", "見": "见", "觀": "观",
    "規": "规", "視": "视", "覺": "觉", "覽": "览", "觀": "观", "觸": "触", "訂": "订",
    "計": "计", "訊": "讯", "討": "讨", "訓": "训", "記": "记", "訪": "访", "設": "设",
    "許": "许", "訴": "诉", "診": "诊", "註": "注", "評": "评", "詞": "词", "試": "试",
    "詩": "诗", "話": "话", "詳": "详", "認": "认", "誌": "志", "語": "语", "誠": "诚",
    "誤": "误", "說": "说", "誰": "谁", "課": "课", "調": "调", "談": "谈", "請": "请",
    "論": "论", "諒": "谅", "誼": "谊", "謝": "谢", "證": "证", "識": "识", "譜": "谱",
    "警": "警", "議": "议", "護": "护", "讀": "读", "變": "变", "讓": "让", "讚": "赞",
    "貝": "贝", "負": "负", "財": "财", "貢": "贡", "貧": "贫", "貨": "货", "販": "贩",
    "貪": "贪", "責": "责", "貴": "贵", "買": "买", "貸": "贷", "費": "费", "貼": "贴",
    "賀": "贺", "賊": "贼", "資": "资", "賈": "贾", "賓": "宾", "賜": "赐", "賞": "赏",
    "賠": "赔", "賢": "贤", "賣": "卖", "質": "质", "賬": "账", "賭": "赌", "購": "购",
    "賽": "赛", "贈": "赠", "贊": "赞", "贏": "赢", "贖": "赎", "赫": "赫", "趙": "赵",
    "趨": "趋", "躍": "跃", "軌": "轨", "軍": "军", "軒": "轩", "軟": "软", "較": "较",
    "載": "载", "輔": "辅", "輕": "轻", "輛": "辆", "輝": "辉", "輩": "辈", "輪": "轮",
    "輯": "辑", "輸": "输", "轄": "辖", "轉": "转", "轟": "轰", "辦": "办", "辭": "辞",
    "農": "农", "迴": "回", "迴": "回", "迺": "乃", "進": "进", "遠": "远", "違": "违",
    "遞": "递", "適": "适", "選": "选", "遺": "遗", "遼": "辽", "邁": "迈", "還": "还",
    "邊": "边", "邏": "逻", "鄉": "乡", "鄧": "邓", "鄭": "郑", "醫": "医", "釋": "释",
    "鐘": "钟", "鋼": "钢", "錄": "录", "錘": "锤", "錢": "钱", "錦": "锦", "鍵": "键",
    "鏈": "链", "鎖": "锁", "鍋": "锅", "鎮": "镇", "鏡": "镜", "鐘": "钟", "鐵": "铁",
    "鑄": "铸", "鑑": "鉴", "長": "长", "閉": "闭", "問": "问", "閒": "闲", "間": "间",
    "閏": "闰", "閘": "闸", "閣": "阁", "閱": "阅", "闆": "板", "闊": "阔", "關": "关",
    "欄": "栏", "陽": "阳", "陰": "阴", "陣": "阵", "階": "阶", "際": "际", "陸": "陆",
    "隊": "队", "隨": "随", "險": "险", "隱": "隐", "雖": "虽", "雙": "双", "雜": "杂",
    "雞": "鸡", "離": "离", "難": "难", "雲": "云", "電": "电", "霧": "雾", "靈": "灵",
    "靜": "静", "非": "非", "面": "面", "鞏": "巩", "韋": "韦", "韓": "韩", "頁": "页",
    "頂": "顶", "項": "项", "順": "顺", "須": "须", "預": "预", "頑": "顽", "頒": "颁",
    "頓": "顿", "頗": "颇", "領": "领", "頭": "头", "頰": "颊", "頸": "颈", "頻": "频",
    "顆": "颗", "題": "题", "額": "额", "顏": "颜", "願": "愿", "類": "类", "顧": "顾",
    "顯": "显", "風": "风", "飛": "飞", "飯": "饭", "飲": "饮", "飾": "饰", "飽": "饱",
    "養": "养", "餐": "餐", "館": "馆", "饋": "馈", "首": "首", "香": "香", "馬": "马",
    "駕": "驾", "駒": "驹", "駛": "驶", "騎": "骑", "驗": "验", "驚": "惊", "骨": "骨",
    "體": "体", "高": "高", "髮": "发", "鬥": "斗", "魂": "魂", "魚": "鱼", "鳥": "鸟",
    "鳴": "鸣", "鴉": "鸦", "鵝": "鹅", "鷹": "鹰", "麗": "丽", "麥": "麦", "黃": "黄",
    "點": "点", "黨": "党", "齊": "齐", "齒": "齿", "龍": "龙", "龜": "龟",
}
T2S = str.maketrans(_T2S)


_FULL_T2S = None


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
    return s.translate(T2S)


def needs_translation(text: str) -> bool:
    """这句要不要翻?(已经是简体中文的就不用,免得 AI 把中文又改一遍)"""
    t = (text or "").strip()
    if not t or len(t) < 2:
        return False
    if _KANA.search(t) or _HANGUL.search(t):
        return True                      # 日文/韩文 → 必翻
    if not _HAN.search(t):
        return bool(_ASCII_WORD.search(t))    # 没有汉字:英文才翻
    # 有汉字:看有没有繁体字(转一遍不相等就说明含繁体)
    return to_simplified(t) != t


# 所有"非文字"字符都算符号:标点、括号、引号、音符星号、颜文字零件、拉丁字母与数字**不算**
_SYM_ONLY = re.compile(r"[^\w\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", re.UNICODE)


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


# ★符号占位符★
# 光靠提示词约束 AI 是不够的(实测:标点、引号、破折号仍会被改写或吞掉)。
# 做法:把原文里的符号换成 [[0]] [[1]] … 这样的记号再交给 AI —— 记号是"单词",
# 模型不会去翻译它;拿回来按编号还原成原符号。这样符号**在机制上不可能丢**。
_TOK_RE = re.compile(r"\[\[(\d+)\]\]")
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


def _restore_symbols(text: str, marks: list, src: str = "") -> str:
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


def _looks_broken(out: str, src: str) -> bool:
    """还原之后还是乱的吗?(符号比原文还多 / 文字几乎没了 / 出现成串符号)"""
    if not out:
        return True
    if len(_plain(out)) < max(1, len(_plain(src)) // 3):
        return True
    so, ss = _symbols(out), _symbols(src)
    if sum(so.values()) > sum(ss.values()) + 2:
        return True
    # (这里曾经有一条"连续 5 个以上符号就算乱码"的规则 —— 实测会把
    #  「原來如此……」他說道——是這樣嗎? 这种**合法**写法误判成乱码,
    #  导致整句退回原文。已删除。)
    return False


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


def is_bad_output(out: str, src: str) -> bool:
    """译文是不是"不可用"?(空 / 原样返回 / 还是日文)"""
    o = (out or "").strip()
    if not o or len(o) < 1:
        return True
    if _KANA.search(o):
        return True                      # 还是假名 → 没翻
    if o == (src or "").strip():
        return True                      # 原样返回
    return False


class Translator:
    """带落盘缓存的翻译器(线程安全)。

    预热用**一条常驻后台线程 + 队列**,不是每来一句就 `Thread(...)`:
    后者在读得快的时候会瞬间开出一堆线程(每句一个),白耗资源。
    """

    def __init__(self, cache_path):
        self.path = Path(cache_path)
        self.lock = threading.Lock()
        self.cache = {}
        self.stat = {"hit": 0, "miss": 0, "fail": 0, "skip": 0, "chars": 0}
        self.last_error = ""
        self._dirty = False
        self._last_save = 0.0
        self._q = None            # 预热队列(第一次用到才建)
        self._q_thread = None
        self._aicfg = None
        self.load()

    # ---- 缓存 ----
    def load(self):
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.cache = {k: v for k, v in (data.get("cache") or {}).items() if v}
        except Exception:
            self.cache = {}

    def save(self, force=False):
        with self.lock:
            if not self._dirty:
                return
            if not force and time.time() - self._last_save < 5:
                return
            self._last_save = time.time()
            self._dirty = False
            try:
                tmp = str(self.path) + ".tmp"
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump({"cache": self.cache, "at": time.time()}, f, ensure_ascii=False)
                os.replace(tmp, self.path)
            except Exception:
                pass

    def clear(self):
        with self.lock:
            self.cache = {}
            self.stat = {"hit": 0, "miss": 0, "fail": 0, "skip": 0, "chars": 0}
            self._dirty = True
        self.save(force=True)

    def stats(self) -> dict:
        with self.lock:
            n = len(self.cache)
            return dict(self.stat, cached=n, last_error=self.last_error)

    # ---- 主流程 ----
    def get(self, text: str, aicfg=None, timeout: int = 12) -> str:
        """拿译文。**永远不会抛异常** —— 出错就把原文还回去(游戏照原样显示)。"""
        src = (text or "").strip()
        if not src:
            return text or ""
        _local = local_convert(src)          # 短名字/界面词:本地转,不问 AI
        if _local:
            with self.lock:
                self.cache[src] = _local
                self.stat["hit_local"] = self.stat.get("hit_local", 0) + 1
            self._dirty = True
            return _local
        if not needs_translation(src):
            with self.lock:
                self.stat["skip"] += 1
            return src
        with self.lock:
            hit = self.cache.get(src)
            if hit:
                self.stat["hit"] += 1
                return hit
            self.stat["miss"] += 1
        out = self._translate(src, aicfg, timeout)
        if out:
            with self.lock:
                self.cache[src] = out
                self.stat["chars"] += len(src)
                self._dirty = True
                if len(self.cache) > 60000:            # 上限保护
                    for k in list(self.cache)[:10000]:
                        self.cache.pop(k, None)
            self.save()
            return out
        with self.lock:
            self.stat["fail"] += 1
        return src

    def _translate(self, src: str, aicfg, timeout: int):
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
            "你是游戏本地化译者。把用户给你的游戏文本翻译成**简体中文**。\n"
            "规则:\n"
            "· 只输出译文正文,不要解释、不要加引号、不要输出原文\n"
            "· 必须是**简体中文**,绝对不要输出繁体字;原文里的日文假名一律翻成中文,不许保留\n"
            "· 人名/地名也要**用简体字写**(「格蘭特尼」→「格兰特尼」、「奧斯卡」→「奥斯卡」);同一名字前后必须一致\n"
            "· ★符号一个都不能丢、不能换★:原文的标点、括号、引号(「」『』()【】〈〉)、"
            "音符星号(♪★☆※●○)、箭头、省略号、破折号、颜文字、以及 <>{}[] 这类标记,"
            "都要**原样保留在原来的位置**,不许增删改写;原文有几个就保留几个\n"
            "· 保留原文的语气、称呼和标点风格;『』「」这类引号换成中文引号\n"
            "· 原文里的换行、颜文字、以及 <>{}[] 之类的标记原样保留\n"
            "· 文本很短(一个词、一个按钮)时,给最自然的界面用词(例如 Save→保存)\n"
            "· 如果原文已经是简体中文,原样返回"
        )
        prot, marks = _protect_symbols(src)          # 符号 → ⟦n⟧
        sys2 = system
        if marks:
            sys2 = (system + "\n★这条文本里的 [[0]] [[1]] … 是**占位符**,代表原文的标点与符号。"
                             "你必须把它们**原样、按原顺序全部保留**在译文里(数量一个不少),"
                             "绝对不要翻译、删除、改动或新增这些记号。")
        try:
            out = ai_mod._call(sys2, prot, aicfg, timeout, temperature=0.2)
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {str(e)[:120]}"
            return ""
        out = _restore_symbols((out or "").strip(), marks, src)   # [[n]] → 原符号(按原文对齐)
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
        miss = _missing_symbols(src, out)
        if miss and out:
            # 漏了符号 → 把"哪个符号、原文几次、你只给了几次"讲清楚,再要一次
            detail = "、".join("%s(原文 %d 个,你只给了 %d 个)" % (c, n, m) for c, n, m in miss[:6])
            fix_sys = (system + "\n★上一次的译文漏掉了符号:" + detail +
                       "。请**只补回这些符号**、其余文字保持不变,重新输出完整译文。")
            try:
                out2 = _restore_symbols((ai_mod._call(fix_sys, prot, aicfg, timeout, temperature=0.1) or "").strip(), marks, src)
                out2 = to_simplified(out2)
                if out2 and len(_missing_symbols(src, out2)) < len(miss):
                    out = out2
            except Exception:
                pass
        if is_bad_output(out, src):
            self.last_error = "AI 没给出可用的简体中文译文"
            return ""
        self.last_error = ""
        return out

    # ---- 预热:把读到的新原文提前翻好(阅读器用) ----
    def prefetch(self, texts, aicfg=None):
        """把还没翻过的原文丢进队列,后台慢慢翻(绝不阻塞调用方)。"""
        import queue
        with self.lock:
            if self._q is None:
                self._q = queue.Queue(maxsize=400)
                self._q_thread = threading.Thread(target=self._q_loop, daemon=True,
                                                  name="transprefetch")
                self._q_thread.start()
            self._aicfg = aicfg or self._aicfg
            n = 0
            for t in texts:
                t = (t or "").strip()
                if not t or not needs_translation(t) or t in self.cache:
                    continue
                try:
                    self._q.put_nowait(t)
                    n += 1
                except Exception:
                    break                    # 队列满了就丢掉,别拖累读数
            return n

    def _q_loop(self):
        while True:
            try:
                t = self._q.get()
            except Exception:
                return
            try:
                self.get(t, self._aicfg, timeout=15)
            except Exception:
                pass
