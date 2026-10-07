# -*- coding: utf-8 -*-
"""LDC 引擎(剧情挂钩)—— 直接读游戏正在显示的剧情,不截图、不 OCR。

两条路线,自动按游戏类型选:
  · Unity **Mono** 游戏:装 BepInEx 5 + 我们自己写的 StoryHook 插件(挂 UTAGE / 自研剧本 / UI.Text / TMP)
  · Unity **IL2CPP** 游戏:装 BepInEx 6 + XUnity + 我们写的 StoryHookIl2Cpp 插件(挂 SetCharArray 等)

文本来源有两个,都会汇总到同一个过滤流水线:
  1. 插件写的日志 <游戏目录>\\BepInEx\\storyhook.log    (Mono 与 IL2CPP 插件都是这个格式)
  2. XUnity 发到本地服务 GET /translate?text=...        (IL2CPP 路线:xunity = True 时启用)

过滤流水线(自动学习,不用人工维护词表):
  · 界面词 / 版本号 / 参数名 / 载入标语 → 丢
  · 严格模式:没有对话标点的短句 → 当界面说明丢掉(游戏里的菜单说明往往一个标点都没有)
  · 说话人:短名字(带"角色"前缀或 2~4 字纯名)记为候选,由下一句真剧情确认
  · 打字机合并:同一句逐字变长只算一句(停止 1.5 秒才定稿)
  · 重复抑制:同一条 45 秒内重复出现不再显示
  · 自动学习:某个"说话人标签"连续 6 行都没有任何台词标点、且都是操作指示 → 判定为界面面板,以后忽略
"""
import json
import os
import re
import shutil
import struct
import subprocess
import threading
import time

# ---------------------------------------------------------------- 文本判定
DIALOG_PUNCT = "。！？!?…⋯‥⁙、，；：「」『』“”‘’—～·"      # 中文标点 + ASCII ? !
DIALOG_QUOTES = "「『“”" + chr(34) + chr(39)

UI_KEYWORDS = (
    "开启此选项", "此选项", "选项", "设置", "配置", "分辨率", "全屏", "窗口化",
    "音量", "语言", "存档", "读档", "跳过", "自动播放", "文字速度", "按键",
    "手柄", "鼠标", "键盘", "画质", "阴影", "抗锯齿", "垂直同步", "帧率",
    "游戏实况", "难度", "字幕", "音效", "背景音乐", "操作说明",
    "海拔", "正在保存", "请勿在此时关闭", "已快速存档", "教程", "点击继续",
    "无法连接", "请确认您", "请确认你", "已关联", "联网", "网络异常", "服务器维护",
    "别想太多", "前方", "加载中", "正在加载", "读取中", "loading",
    "抢先体验", "主菜单", "欢迎来到", "感谢您加入", "感谢你加入", "本游戏尚在",
    "尚未面世", "正在开发", "敬请期待", "版本更新", "更新公告", "工作室", "studio",
    "版权所有", "保留所有权利", "制作人员", "鸣谢", "反馈",
    "牌库", "购买英雄", "浏览英雄", "更换皮肤", "随游戏进度解锁", "卡牌及",
    "游戏物品", "商店", "购买", "浏览",
    "已记录", "已保存", "已解锁", "书签已", "从书签", "继续故事",
    "从头开始", "返回至", "您的进度", "你的进度", "不会被保存", "进度不会",
    "章节画面", "幕间休息",
)
MENU_WORDS = {
    "最新", "继续", "返回", "设置", "读取", "存档", "读档", "快速存档", "菜单",
    "交互", "新开始", "开始", "离开", "退出", "关闭", "确定", "取消", "关于我们",
    "操作说明", "对白记录", "自动", "跳过", "存档/读档", "下一章", "上一章",
    "系统", "标题", "回到标题", "退出游戏",
    "截取画面", "画面", "列表", "章节列表", "请输入名字", "回顾", "记录",
    "抢先体验", "主菜单", "公告", "更新", "版本", "制作者", "制作人员", "鸣谢",
    "画廊", "图鉴", "成就", "按键设置", "声音", "语言", "帮助",
}
UI_WORDS = {
    "start", "start game", "load", "save", "config", "setting", "settings", "option",
    "options", "quit", "exit", "back", "next", "close", "cancel", "ok", "yes", "no",
    "on", "off", "auto", "skip", "log", "title", "menu", "new game", "continue",
    "gallery", "extra", "version", "language", "volume", "resolution", "full screen",
    "windowed", "apply", "return", "item", "items", "status", "help", "about",
    "empty", "none", "free", "locked", "new", "del", "delete", "copy", "paste",
}

# ---------------------------------------------------------------- 游戏常用词
# 视觉小说 / ADV 里几乎每款游戏都会出现的界面词(玩家要求补充"游戏通常会用的一些词语")。
# 说明:这些词按**包含匹配**生效,所以只收"几乎不可能出现在台词里"的词 ——
# 像「名字」「时间」这种日常词绝不能放进来,否则会把正常对白一起吃掉。
# 这一组独占一个页签,玩家可以整组清空,不影响别的规则。
GAME_WORDS = (
    # 存档 / 读档
    "快速存档", "快速读档", "自动存档", "存档位", "存档栏", "读档位", "覆盖存档",
    "存档失败", "读取存档", "保存进度", "存档数据", "存档损坏", "云存档",
    # 菜单 / 系统
    "主菜单", "标题画面", "返回标题", "回到标题", "继续游戏", "开始新游戏",
    "新游戏", "载入游戏", "读取进度", "操作说明", "按键设置", "按键配置",
    "显示设置", "画面设置", "声音设置", "语言设置", "文本速度", "文字速度",
    "自动播放速度", "跳过已读", "已读文本", "快进", "回顾", "对白记录",
    "文本记录", "历史记录", "已解锁", "尚未解锁", "需要通关", "通关后",
    # 养成 / 收集
    "好感度", "亲密度", "羁绊", "信赖度", "角色信息", "角色资料", "人物资料",
    "人物介绍", "角色介绍", "图鉴", "画廊", "鉴赏", "回忆", "成就", "奖杯",
    "收集度", "收集进度", "解锁条件", "支线任务", "主线任务", "任务列表",
    # 章节 / 进度
    "序章", "终章", "尾声", "幕间", "下一章", "上一章", "章节选择", "章节列表",
    "进度保存", "游戏进度", "当前进度",
    # 演出 / 音画
    "立绘", "差分", "背景音乐", "音效音量", "语音音量", "字幕", "全屏显示",
    "窗口模式", "无边框", "垂直同步", "帧率上限", "画质", "抗锯齿", "分辨率",
    # 常见提示
    "确定要", "是否保存", "是否覆盖", "请稍候", "请稍等", "加载中", "读取中",
    "正在载入", "正在保存", "保存中", "请勿关闭", "请勿断电", "按任意键",
    "点击继续", "点击画面", "点击任意", "长按", "拖动", "键盘操作", "手柄操作",
)
NAME_PREFIXES = ("角色 ", "角色:", "角色：", "名字 ", "名字:", "名字：", "姓名 ", "姓名:")
NAME_BLACKLIST = (
    # 语气词/连接词:长得像短名字,其实不是
    "嗯", "哦", "啊", "哎", "唉", "哈", "哼", "呃", "咦", "诶", "喂",
    "应该", "可能", "大概", "或许", "于是", "然后", "但是", "不过", "所以","菜单", "体验", "设置", "列表", "公告", "版本", "画面", "记录",
                  "存档", "读档", "画廊", "图鉴", "成就", "帮助", "说明", "教程",
                  "关于", "系统", "选项", "退出", "返回", "开始", "继续", "标题",
                  "工作室", "制作", "官方", "提示", "章", "节", "话",
                  "牌库", "商店", "购买", "浏览", "卡牌", "皮肤", "解锁", "进度",
                  "通知", "幕间", "休息", "已完成", "已保存", "已记录", "章节",
                  "稍后", "长按", "点击", "拖动", "查看", "获得", "需要", "按下",
                  "设定", "立刻", "去吧", "试试", "开始游戏", "继续游戏")
RICH_TAG = re.compile(r"<[^<>]{1,80}>")

# 剧本引擎内部方法:它们的返回值是脚本参数/求值中间量,不是给人看的台词。
# 实测三相奇谈靠这些把日志刷到 2 万行,还把打字机半句打断,所以整类丢掉。
JUNK_METHODS = (
    "StatementToVal", "CalculateByOperator", "GetStatementValue", "StatementSplit",
    "StatementIsTrue", "IsStatementTrue", "IsNegativeSign", "GetParamStr", "GetParamBool",
    "GetParamInt", "GetParamFEx", "GetParam", "HasParam", "ExplainStory", "GetFlashColor",
    "GetVal", "SetVal", "GetVariable", "SetVariable", "GetFlag", "SetFlag",
)
JUNK_TEXT = {"pos", "fo", "ease", "size", "wait", "talker", "talkid", "default", "type",
             "speed", "color", "name", "text", "true", "false", "null", "none"}


def is_junk_line(method: str, text: str, typ: str = "") -> bool:
    """这行是不是引擎内部噪音(不是剧情)。

    typ: 日志第 1 段(声明类型)。★必须传进来★ —— 插件写的是「类型\\t方法\\t文本」,
    判断"是不是 XUnity 回写的译文"要看**类型**,以前只查方法名,那段判断其实从没生效过。
    """
    m = (method or "").strip()
    if m in EFF_JUNK_METHODS:
        return True
    if any(m.endswith(x) for x in EFF_JUNK_METHODS if x.endswith(("Param", "Val", "Flag"))):
        return True
    # XUnity 把译文回写文本框时也会走 set_text —— 那是译文,不是游戏原文。
    # 默认丢掉(面板里只留游戏本来显示的文字);开了「朗读译文」时由调用方放行。
    if is_xunity(typ, method):
        return True
    if any(m.endswith(x) for x in ("GetParamStr", "GetParamBool", "GetParamInt", "GetParamFEx")):
        return True
    t = (text or "").strip()
    # 注意:这里必须只认 ASCII —— Python 的 \w 是含中文的,
    # 用它会把手游/视觉小说里 2~4 个汉字的名字(净饭、三宝、皮月羞)当噪音丢掉。
    if len(t) <= 6 and (t in EFF.get("junk_text", ())
                        or re.fullmatch(r"[A-Za-z0-9_.$:<>\-]+", t or "")):
        return True
    return False


def is_xunity(typ: str, method: str = "") -> bool:
    """这一行是不是 XUnity.AutoTranslator 回写译文时产生的。

    日志格式是「类型\\t方法\\t文本」,所以要看**类型**(第 1 段);
    也接受老格式(把带前缀的名字写在方法段里)。
    """
    for s in ((typ or ""), (method or "")):
        if s.startswith("XUnity.") or s.startswith("XUnity"):
            return True
    return False

# ---------------------------------------------------------------- 过滤规则(可在界面上增删改)
# 玩家看到的规则分组:键名 -> (显示名, 说明)
#   simple=True 的组是"词表":命中包含关系就丢;名字/方法类各有自己的判定逻辑。
RULE_GROUPS = [
    ("ui_keywords",  "界面说明词",   "句子里含这些词就当界面文字丢掉(设置项、公告、商店说明等)"),
    ("game_words",   "游戏常用词",   "视觉小说里几乎都会出现的系统词(快速存档、好感度、立绘…);整组可清空"),
    ("menu_words",   "菜单按钮词",   "整句等于这些词的,是按钮,不读"),
    ("ui_words",     "英文界面词",   "英文菜单/按钮(start、save、options…),不读"),
    ("ui_phrases",   "第二人称操作词", "句子里同时有 你/您 + 这些词 → 判定为界面提示"),
    ("name_blacklist", "人名黑名单", "短文本里含这些词就不当角色名(通知/主菜单/已完成…)"),
    ("junk_methods", "引擎噪音方法", "日志里这些方法的返回是脚本内部值,整类丢掉"),
    ("junk_text",    "噪音碎片",     "等于这些短词的日志行直接丢(pos/ease/size…)"),
    ("ai_words",     "AI 添加的过滤词", "AI 评审时建议加的过滤词只进这里 —— 单独一栏,随时能逐条删掉"),
]

# 名单(玩家要求:日志里看到一行 → 弹窗选择拉黑还是放行)
LIST_GROUPS = [
    ("whitelist", "白名单", "含这些词的行**一定朗读**:跳过所有过滤与去重,直接念出来"),
    ("blacklist", "黑名单", "含这些词的行**彻底拉黑**:不显示、不朗读、不当角色名"),
]


def _as_list(v):
    return [str(x).strip() for x in (v or []) if str(x).strip()]


# 运行时可变的规则表(界面改了立刻生效)。★这里是"玩家能改的通用规则"★,
# 游戏专用规则在 GAME_PROFILES 里,运行时合并成 EFF 才是真正生效的那份。
RULES = {
    "ui_keywords": list(UI_KEYWORDS),
    "game_words": list(GAME_WORDS),
    "menu_words": sorted(MENU_WORDS),
    "ui_words": sorted(UI_WORDS),
    "ui_phrases": [
        "继续", "返回", "保存", "开始", "选择", "确认", "取消", "进度",
        "书签", "存档", "读档", "设置", "菜单", "退出", "跳过", "解锁"],
    "name_blacklist": list(NAME_BLACKLIST),
    "junk_methods": list(JUNK_METHODS),
    "junk_text": sorted(JUNK_TEXT),
    "ai_words": [],
    # 黑/白名单默认空 —— 由玩家在日志里点出来
    "blacklist": [],
    "whitelist": [],
}

DEFAULT_RULES = {k: list(v) for k, v in RULES.items()}


# ---------------------------------------------------------------- 已适配游戏的专用规则
# 每一条都来自**真实日志**(KnightsCollege 的 storyhook.log 里能直接看到这些词被当成台词
# 读出来过),不是凭空编的。界面上按游戏单独显示这一份内容,而不是把词倒进通用规则里。
#
# match_exe    : 游戏 exe 名里出现这些片段就认为匹配(小写比较)
# match_method : 日志里出现过这些方法片段也认为匹配(运行中学会,兜底)
# groups       : 只在匹配到这款游戏时才追加生效的规则(键名与 RULE_GROUPS 一致)
GAME_PROFILES = [
    {
        "key": "utage",
        "name": "UTAGE ADV(Knights College 1 / 2)",
        "note": "日式 ADV 引擎:台词走 AdvMessageWindow.set_Text,名字走 set_NameText / "
                "set_CharacterLabel(片假名原文),信息面板 AdvCharacterInfo 会塞 ？？？。",
        "match_exe": ("knights", "anados", "naitsukarejji"),
        "match_method": ("advmessagewindow", "advcharacterinfo", "utage."),
        "groups": {
            # 实测:这些是存档/信息面板上的固定文字,一个标点都没有,靠严格模式也能挡住,
            # 但明确列出来更稳(玩家关掉严格模式时仍然不读)。
            # 这款游戏的界面是**繁体**,所以简繁两种写法都收。
            "menu_words": [
                "交流", "场所", "人物", "信息", "好感度", "角色好感度", "查看截图",
                "截取画面", "唤出/收起菜单", "跳过剧情", "自动播放", "返回标题界面",
                "章节列表", "后日谈", "展示魅力", "骑士学院", "卡片",
                "場所", "資訊", "查看截圖", "截取畫面", "喚出/收起選單", "跳過劇情",
                "自動播放", "返回標題界面", "章節列表", "後日談", "騎士學院",
            ],
            "ui_keywords": [
                "角色好感度", "唤出/收起菜单", "查看截图", "截取画面", "返回标题界面",
                "跳过剧情", "自动播放", "好感度", "后日谈", "展示魅力",
                "查看截圖", "截取畫面", "跳過劇情", "自動播放", "後日談",
            ],
            # 名字框的内容有时走通用的 set_text:这些不是台词,也不能当角色名
            # ★后半段是实测从玩家存档里翻出来的★ —— 它们曾被当成"角色"收集:
            #   安全模式/跳過/快速/圖集/觀察/顯示/通常/交談/關閉/結束遊戲/致謝名單…
            "name_blacklist": ["CharaOff", "？？？", "后日谈", "骑士学院",
                               "安全模式", "跳過", "跳过", "快速", "圖集", "图集",
                               "觀察", "观察", "顯示", "显示", "通常", "交談", "交谈",
                               "關閉", "关闭", "結束遊戲", "结束游戏", "致謝名單", "致谢名单",
                               "快速存檔", "快速存档", "繼續", "继续", "開始", "开始",
                               "選項", "选项", "選單", "离开", "離開"],
            "junk_text": ["CharaOff", "？？？", "Cards", "Hearts", "Spades", "Diamonds", "Clubs"],
        },
    },
    {
        "key": "threefold",
        "name": "三相奇谈(自研剧本引擎)",
        "note": "剧本解释器把每一步求值都写进日志(两万行级别),还会把打字机半句打断;"
                "这些方法的返回值是脚本内部量,整类丢掉。",
        "match_exe": ("threefold", "三相奇谈", "recital"),
        "match_method": ("statementtoval", "explainstory", "getparam"),
        "groups": {
            "junk_methods": [
                "StatementToVal", "CalculateByOperator", "GetStatementValue", "StatementSplit",
                "StatementIsTrue", "IsStatementTrue", "IsNegativeSign", "GetParamStr",
                "GetParamBool", "GetParamInt", "GetParamFEx", "GetParam", "HasParam",
                "ExplainStory", "GetFlashColor",
            ],
            "junk_text": ["pos", "fo", "ease", "size", "wait", "talker", "talkid",
                          "default", "type", "speed", "color"],
        },
    },
    {
        "key": "astatos",
        "name": "Astatos(卡牌 ADV)",
        "note": "卡牌对战 + ADV:牌库 / 商店 / 皮肤这些界面词特别多,而且会整句走文本框。",
        "match_exe": ("astatos",),
        "match_method": (),
        "groups": {
            "ui_keywords": [
                "牌库", "购买英雄", "浏览英雄", "更换皮肤", "随游戏进度解锁", "卡牌及",
                "游戏物品", "牌组", "出牌", "回合结束", "法力", "水晶",
            ],
            "menu_words": ["牌库", "商店", "牌组", "卡组", "卡牌", "对战", "购买", "浏览"],
        },
    },
]

PROFILE_BY_KEY = {p["key"]: p for p in GAME_PROFILES}
# 玩家整个停用某款游戏的专用规则(界面上一个开关)
PROFILE_OFF = set()
# 当前生效的 profile key(None = 没有匹配到已适配的游戏)
ACTIVE_PROFILE = None

# ★真正生效的规则★ = 通用规则 + 当前游戏专用规则。所有判定都读 EFF,不再直接读 RULES。
EFF = {}
EFF_WORDS = []          # ui_keywords + game_words + ai_words 合并好,免得每行都拼一遍
EFF_JUNK_METHODS = []


def rebuild_eff():
    """把通用规则和当前游戏的专用规则合并成生效规则(规则一改/换游戏就调一次)。"""
    global EFF, EFF_WORDS, EFF_JUNK_METHODS
    eff = {k: list(v) for k, v in RULES.items()}
    key = ACTIVE_PROFILE
    if key and key not in PROFILE_OFF:
        for gk, items in (PROFILE_BY_KEY[key].get("groups") or {}).items():
            bucket = eff.setdefault(gk, [])
            for x in items:
                if x not in bucket:
                    bucket.append(x)
    EFF = eff
    EFF_WORDS = eff.get("ui_keywords", []) + eff.get("game_words", []) + eff.get("ai_words", [])
    EFF_JUNK_METHODS = eff.get("junk_methods", [])


def set_active_profile(key):
    """切换当前游戏时调用:匹配到哪款已适配的游戏。返回实际生效的 key。"""
    global ACTIVE_PROFILE
    key = key if key in PROFILE_BY_KEY else None
    if key != ACTIVE_PROFILE:
        ACTIVE_PROFILE = key
        rebuild_eff()
    return ACTIVE_PROFILE


def match_profile(game_path: str, methods_seen=None):
    """按 exe 名 / 日志里出现过的方法名,判断当前游戏属于哪份专用规则。"""
    exe = os.path.basename(game_path or "").lower()
    seen = " ".join(sorted(methods_seen or [])).lower()
    for p in GAME_PROFILES:
        if exe and any(h in exe for h in p.get("match_exe") or ()):
            return p["key"]
    for p in GAME_PROFILES:
        if seen and any(h.lower() in seen for h in p.get("match_method") or ()):
            return p["key"]
    return None


def profile_dump() -> list:
    """给界面:每份游戏专用规则的内容 + 是否正在为当前游戏生效。"""
    out = []
    for p in GAME_PROFILES:
        out.append({
            "key": p["key"], "name": p["name"], "note": p["note"],
            "exe_hint": "、".join(p.get("match_exe") or ()),
            "groups": {k: list(v) for k, v in (p.get("groups") or {}).items()},
            "active": p["key"] == ACTIVE_PROFILE and p["key"] not in PROFILE_OFF,
            "off": p["key"] in PROFILE_OFF,
        })
    return out


rebuild_eff()          # 模块加载时先把生效规则算出来(EFF 不能是空的)


def dump_rules() -> dict:
    """玩家可改的通用规则(不含游戏专用部分)。"""
    return {k: list(v) for k, v in RULES.items()}


def load_rules(data: dict):
    """从配置里恢复规则(缺的用默认值补)。

    注意 `ai_words` / `blacklist` / `whitelist` 默认就是空表:
    配置里没有、或者是空表,都要保持"空"而不是回落成默认(默认本来就是空,所以没问题),
    但**绝不能用 `if data[k]` 判空跳过** —— 那会让玩家清空后的名单又"复活"。
    """
    for k in RULES:
        if not data or k not in data:
            continue
        v = data[k]
        if isinstance(v, list):
            RULES[k] = _as_list(v)
    rebuild_eff()


def set_rule_list(key: str, values) -> dict:
    if key not in RULES:
        return {"ok": False, "msg": "没有这个规则组"}
    RULES[key] = _as_list(values)
    rebuild_eff()
    return {"ok": True, "count": len(RULES[key])}


def add_rule(key: str, value: str) -> dict:
    v = (value or "").strip()
    if not v:
        return {"ok": False, "msg": "内容是空的"}
    if key not in RULES:
        return {"ok": False, "msg": "没有这个规则组"}
    if v not in RULES[key]:
        RULES[key].append(v)
    rebuild_eff()
    return {"ok": True, "count": len(RULES[key])}


def del_rule(key: str, value: str) -> dict:
    if key not in RULES:
        return {"ok": False, "msg": "没有这个规则组"}
    RULES[key] = [x for x in RULES[key] if x != value]
    rebuild_eff()
    return {"ok": True, "count": len(RULES[key])}


def reset_rules():
    for k, v in DEFAULT_RULES.items():
        RULES[k] = list(v)
    PROFILE_OFF.clear()
    rebuild_eff()
    return {"ok": True}


def strip_rich(text: str) -> str:
    """去掉富文本标签(<color=#FFDD78>、<sprite=29> 之类)与多余空白。"""
    if not text:
        return ""
    s = RICH_TAG.sub("", text)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
          .replace("&gt;", ">").replace("\\n", " "))
    s = re.sub(r"[ \t\u3000]{2,}", " ", s)
    return s.strip()


def as_speaker(text: str):
    """短文本是不是"角色名"?是则返回名字,否则 None。"""
    s = (text or "").strip()
    if not s or len(s) > 12:
        return None
    cjk = sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff")
    if cjk < 2:
        return None
    if any(ch in s for ch in "。！？…⋯，、；：!?,;「」『』“”"):
        return None
    if s in EFF.get("menu_words", ()) or s.lower() in EFF.get("ui_words", ()):
        return None
    for kw in EFF_WORDS:
        if kw and kw in s:
            return None
    for pre in NAME_PREFIXES:
        if s.startswith(pre):
            s = s[len(pre):].strip()
            return s or None
    for bad in EFF.get("name_blacklist", ()):
        if bad in s:
            return None
    if 2 <= cjk <= 4 and not re.search(r"[\s\dA-Za-z]", s) and \
       not any(ch in s for ch in
               "了着的在是我你他她它们个和与把被给到说看走"
               "捡按推拉开关闭使用查看选择获得需要完成进入离开购买装备"
               "稍后长按点击拖动双击左右上下前后真假有无多少大小"):
        return s
    return None


def is_story_text(text: str, min_cjk: int = 4, strict: bool = True):
    """这句是不是剧情/对白? 返回 (是否读, 原因)。"""
    s = (text or "").strip()
    if not s:
        return False, "空"
    low = s.lower().strip(" 　.。!！?？:：")
    cjk = sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff")
    if low in EFF.get("ui_words", ()):
        return False, "界面词"
    if cjk == 0:
        return False, "无中文"
    if re.fullmatch(r"(ver\.?\s*)?[\d.\s_vp]+", s, re.I):
        return False, "版本号"
    if re.fullmatch(r"(no|chapter|ep|act|stage)\.?\s*[\d.]+", s, re.I):
        return False, "编号"
    if re.fullmatch(r"[\d\s%:/.\-+]+", s):
        return False, "数字"
    for kw in EFF_WORDS:
        if kw and kw in s:
            return False, f"界面词({kw})"
    if (s[0] in "「『“" or s[-1] in "」』”") and cjk >= 1:
        return True, ""
    has_dialog_punct = any(ch in s for ch in DIALOG_PUNCT) or bool(re.search(r"\.{2,}$", s))
    if cjk < min_cjk and not has_dialog_punct:
        return False, f"中文少于 {min_cjk} 字"
    if len(s) <= 6 and not has_dialog_punct:
        return False, "短标签"
    if len(s) <= 10 and not has_dialog_punct:
        return False, "短提示"
    if any(p in s for p in ("你", "您")) and any(p in s for p in EFF.get("ui_phrases", ())):
        return False, "界面提示(第二人称操作指示)"
    if strict and not has_dialog_punct and len(s) < 18:
        return False, "没有对话标点(界面说明)"
    return True, ""


# ---------------------------------------------------------------- 过滤流水线
PLACEHOLDER = re.compile(r"\{\d+\}|%[sd]|\$\{[^}]+\}")


def number_shape(text: str) -> str:
    """把所有数字换成 #,用来判断"只有数字在变"的同一句话。"""
    return re.sub(r"\d+(?:\.\d+)?", "#", text or "")


def similar(a: str, b: str) -> float:
    """很粗的相似度:共同前缀长度 / 较长者长度(够用了,而且快)。"""
    if not a or not b:
        return 0.0
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n / max(len(a), len(b))


# 存档/读档 这类"菜单界面"的文字特征。
# 为什么不能靠方法名:这些文字走的是通用的 UI.Text.set_text(实测 KnightsCollege),
# 和剧情台词同一条路,只能按"整行内容"认。
MENU_EXACT = {
    "存档", "存檔", "读档", "讀檔", "读取", "讀取", "保存", "设置", "設定", "返回",
    "菜单", "選單", "跳过剧情", "跳過劇情", "章节列表", "章節列表", "角色好感度",
    "查看截图", "查看截圖", "截取画面", "截取畫面", "唤出/收起菜单", "喚出/收起選單",
    "自动播放", "自動播放", "auto", "auto save", "save", "load", "セーブ", "ロード",
}
MENU_PAT = [
    re.compile(r"^No\.?\s*\d+$", re.I),                                  # No.  3
    re.compile(r"^\d{4}[/\-年]\d{1,2}[/\-月]\d{1,2}(\s+\d{1,2}:\d{2}(:\d{2})?)?$"),  # 2026/09/23 21:00:59
    re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$"),                             # 21:00
    re.compile(r"^(交流|信息|情報|场所|場所|人物|好感度|章节|章節|存档位|存檔位)\s*\d+$"),
]

# 菜单模式的时长(秒):
MENU_HOLD = 3.0        # 离最后一次菜单文字这么久之内 → 认为还在菜单里(暂停自动点击)
MENU_SWALLOW = 1.5     # 紧挨着菜单文字出现的其它文字也不读(槽位缩略里的台词)


# 这些来源虽然在"设名字",但那不是对话框上的名字,不能拿来当发言人:
#   角色信息面板(AdvCharacterInfo 会设成 ？？？ / <param=player_name>)
#   履历/回忆列表(AdvBacklog… 里是每一页记下来的旧名字)
NAME_SOURCE_IGNORE = ("info", "backlog", "history", "gallery", "select", "menu",
                      "title", "save", "load", "config", "setting", "caption")


def is_menu_line(text: str) -> bool:
    """这一行是不是"存档/读档/设置"这类菜单界面的文字。"""
    t = (text or "").strip()
    if not t or len(t) > 32:
        return False
    if t.lower() in MENU_EXACT:
        return True
    for p in MENU_PAT:
        if p.match(t):
            return True
    return False


class StoryFilter:
    """把游戏送来的文本过滤成"只有剧情",并自动学习界面面板。"""

    def __init__(self, min_cjk=4, strict=True, extra_words=None,
                 ignored_labels=None, ignored_texts=None, on_learn=None, on_filtered=None):
        self.min_cjk = min_cjk
        self.strict = strict
        self.extra_words = list(extra_words or [])
        self.ignored_labels = set(ignored_labels or [])
        self.ignored_texts = set(ignored_texts or [])
        self.label_stats = {}
        self.speaker = ""
        self.speaker_t = 0.0                # 游戏最后一次给名字(含"清空")的时刻
        self.menu_t = 0.0                   # 最近一次看到"菜单界面文字"的时刻
        self.pending_speaker = ""
        self.pending_speaker_t = 0.0
        self.pending = ""
        self.pending_time = 0.0
        self.settle = 0.45                  # 打字机"不再变长"多久算定稿(开了翻译会调大)
        self.last_text = ""
        self.last_committed = ""
        self.recent = []
        self.filtered = 0
        self.last_reason = ""
        self.on_learn = on_learn
        self.on_filtered = on_filtered      # 被丢掉时回调(界面用它显示"为什么没读")
        self.on_replay = None               # 判定为"回存档重读"时回调(界面提示一句)
        self.keep_quotes = False          # True=连界面文本也留着(调试)
        # 回存档重读的识别:连续几句"各不相同、但都见过"→ 是玩家回去重读,
        # 不是界面刷屏(界面刷屏是同一句反复出现)
        self._dup_run = 0
        self._dup_text = ""
        self.replays = 0

    # -- 忽略规则 --
    def _name_event(self, method: str, text: str):
        """处理一次"设置名字"事件。

        这一版是踩出来的(实测 KnightsCollege,日志顺序):
            AdvMessageWindow.set_Text           「啊!抱、抱歉。」   ← 台词
            AdvMessageWindow.set_NameText       奥斯卡               ← 中文名
            AdvMessageWindow.set_CharacterLabel オスカー             ← 同一个名字的日文原文
            AdvCharacterInfo.set_NameText       ？？？ / <param=player_name>  ← 信息面板,不是对话框
        所以:
          · **空值** = 名字框被清空 → 这一句是旁白 → 清掉发言人(这是有用的信号)
          · 非空但不可用(片假名原文 / <param=…> 占位符 / 太长)→ **忽略,绝不能清空**
            (以前一律清空,于是刚记下的中文名立刻被那句片假名冲掉,一个名字都显示不出来)
          · 来源是信息面板/履历列表 → 整个不理(里面的名字不一定是当前说话人)
        """
        m = (method or "").lower()
        if any(h in m for h in NAME_SOURCE_IGNORE):
            return
        t = (text or "").strip()
        # 兜底:万一文本字段又变成方法名(日志格式问题),绝不能当角色名
        if t and (t == (method or "").split(".")[-1] or "set_" in t and t.endswith("NameText")):
            return
        if not t:
            self.speaker = ""
            self.pending_speaker = ""
            self.speaker_t = time.time()
            return
        if len(t) > 16 or t.startswith("<") or re.search(r"[\u3040-\u30ff]", t):
            return                              # 不可用,但**不要**清掉已记住的名字
        self.speaker = t
        self.speaker_t = time.time()

    def menu_active(self) -> bool:
        """现在是不是在存档/读档这类菜单界面里(自动点击据此停手)。"""
        return bool(self.menu_t) and (time.time() - self.menu_t) < MENU_HOLD

    def _drop(self, text: str, why: str):
        """丢掉一行并**说明原因**(界面日志的「已过滤」页签就靠它)。"""
        self.filtered += 1
        self.last_reason = why
        if self.on_filtered:
            try:
                self.on_filtered(text, why)
            except Exception:
                pass

    def is_ignored(self, text: str) -> bool:
        if text in self.ignored_texts:
            return True
        m = re.match(r"^【([^】]{1,12})】", text)
        return bool(m and m.group(1) in self.ignored_labels)

    # -- 黑名单 / 白名单(玩家在「日志」里点出来的) --
    # 写法:普通文字 = 含这个词就命中;前面加 "=" = 整句一模一样才命中。
    def list_verdict(self, text: str) -> str:
        """返回 "block"(黑名单)/ "allow"(白名单)/ ""(没命中)。黑名单优先。"""
        t = text or ""
        for w in EFF.get("blacklist", ()):
            if not w:
                continue
            if w[0] == "=":
                if t.strip() == w[1:].strip():
                    return "block"
            elif w in t:
                return "block"
        for w in EFF.get("whitelist", ()):
            if not w:
                continue
            if w[0] == "=":
                if t.strip() == w[1:].strip():
                    return "allow"
            elif w in t:
                return "allow"
        return ""

    def is_whitelisted(self, text: str) -> bool:
        return self.list_verdict(text) == "allow"

    def blocked_by_user(self, text: str):
        for w in self.extra_words:
            if w and w in text:
                return w
        return None

    def mark_not_story(self, text: str):
        """把一行标成"不是剧情":自动学出它的标签。返回学到的标签。"""
        m = re.match(r"^\[[^\]]*\]\s*(.*)$", text or "")
        body = m.group(1) if m else (text or "")
        if not body:
            return ""
        self.ignored_texts.add(body)
        lab = re.match(r"^【([^】]{1,12})】", body)
        label = lab.group(1) if lab else ""
        if label:
            self.ignored_labels.add(label)
        if self.on_learn:
            self.on_learn(label, body)
        return label

    # -- 主流程 --
    def feed(self, text: str, method: str = "", typ: str = "") -> list:
        """喂一句进来。返回这次"应该显示"的行(通常 0 或 1 行)。

        typ 是日志第 1 段(声明类型),用来判断"来源是不是信息面板/履历列表"
        —— 只看方法名(set_NameText)是分不出 AdvCharacterInfo 和对话框的。
        """
        out = []
        method = method or ""
        text = strip_rich(text or "").strip()
        # 游戏给出的角色名(UTAGE 的 set_NameText / set_CharacterLabel)。
        # ★必须在"空文本直接丢掉"之前处理★ —— 空值本身就是一个信号(名字框清空 = 旁白)。
        if "NameText" in method or "CharacterLabel" in method or "NameLabel" in method:
            self._name_event((typ + "." + method) if typ else method, text)
            return out
        if not text or len(text) < 2:
            return out
        # ── 黑名单 / 白名单(玩家在日志里点出来的)──
        verdict = self.list_verdict(text)
        if verdict == "block":
            self._drop(text, "黑名单(你拉黑的)")
            return out
        allowed = verdict == "allow"
        if not allowed:
            # ── 存档/读档 这类菜单界面:一律不读 ──
            # 这种界面上会出现"存档里的最后一句"(槽位预览),以前会被当成剧情念出来;
            # 而且自动点击在这里乱点可能**覆盖存档**,所以菜单期间连点击也要停(见 menu_active)。
            now = time.time()
            if is_menu_line(text):
                self.menu_t = now
                self._drop(text, "存档/读档等菜单界面")
                return out
            if self.menu_t and (now - self.menu_t) < MENU_SWALLOW:
                # 紧挨着菜单行出现的文字(槽位缩略里的那句台词)也不读
                self._drop(text, "存档界面里的缩略文字")
                return out
            if re.match(r"^[A-Za-z_][A-Za-z0-9_.]*(\.[A-Za-z0-9_]+)* \(", text):
                self._drop(text, "引擎对象名")
                return out
            if is_junk_line(method, text, typ):
                self._drop(text, "引擎内部文本")
                return out
            if PLACEHOLDER.search(text):          # 「海拔 {0} 尺…」这种格式串
                self._drop(text, "格式串(占位符)")
                return out
            if self.blocked_by_user(text):
                self._drop(text, "你加的过滤词")
                return out
            if self.is_ignored(text):
                self._drop(text, "学到的忽略规则")
                return out
            if text == self.last_text:
                self._drop(text, "和上一行一样")
                return out
            self.last_text = text
            # 短名字 → 候选说话人(等下一句真剧情确认)
            sp = as_speaker(text)
            if sp:
                self.pending_speaker = sp
                self.pending_speaker_t = time.time()
                self._drop(text, "当成角色名")
                return out
        else:
            self.last_text = text
        # 打字机合并
        if self.pending and (text.startswith(self.pending) or self.pending.startswith(text)):
            if len(text) >= len(self.pending):
                self.pending = text
            self.pending_time = time.time()
            return out
        committed = self.commit(force=allowed)
        if committed:
            out.append(committed)
        self.pending = text
        self.pending_time = time.time()
        return out

    def tick(self) -> list:
        """定期调用:把"已经不再变长"的那句定稿(打字机结束)。

        噪音行已在读取端丢掉,打字机步进是连续的,所以 0.45 秒没再变长就可以定稿,
        不必等 1.5 秒 —— 这是"显示慢"的主要来源。
        开了「朗读译文」时 settle 会调大到 ~1.5 秒:等 XUnity 把译文送回来顶掉原文,
        否则会先把日文原文念一遍、再念一遍中文。

        ★白名单也必须在**这条路径**上放行★:绝大多数句子是在这里定稿的
        (feed 里那次 commit 只在"下一句来了"时发生),只在 feed 里放行等于没放行。
        """
        if self.pending and time.time() - self.pending_time > self.settle:
            c = self.commit(force=self.is_whitelisted(self.pending))
            return [c] if c else []
        return []

    def replace_pending(self, text: str):
        """用**译文**顶掉还没定稿的原文(XUnity 回写译文时调用)。

        原文同时记进 recent:万一游戏又把同一句日文设一遍,不会重复朗读。
        """
        if not text:
            return
        old, self.pending = self.pending, text
        if old and old != text:
            self.recent.append((old, time.time()))
        self.pending_time = time.time()

    def commit(self, force: bool = False) -> str:
        """把 pending 定稿。force=True = 白名单放行:跳过界面文字判定,直接当剧情读。

        去重那一关**照旧保留**(不然游戏把同一句设两遍就会念两遍)。
        """
        text, self.pending = self.pending, ""
        if not text:
            return ""
        # ---- 先过去重这关,但要能认出"回存档重读" ----
        kind = self._dup_kind(text)
        if kind:
            if self._looks_like_replay(text, kind):
                # 连续几句各不相同的旧句子 → 玩家在读档重读:清空记忆,放行
                self.forget_recent()
                self.replays += 1
                if self.on_replay:
                    try:
                        self.on_replay()
                    except Exception:
                        pass
            else:
                self.recent = [(a, b) for a, b in self.recent if time.time() - b < 120]
                return ""
        if text == self.last_committed:        # 兜底(理论上已被上面拦住)
            return ""
        self.last_committed = text
        if not force and self.is_ignored(text):
            self.filtered += 1
            return ""
        # 自动学习:统计每个标签带出来的行像不像台词(必须在过滤之前统计)
        lab = self.speaker or ""
        if lab and not force:
            like = any(ch in text for ch in DIALOG_QUOTES) or \
                any(ch in text for ch in "。！？?？!！…⋯")
            st = self.label_stats.get(lab, [0, 0])
            st[0] += 1
            if like:
                st[1] += 1
            self.label_stats[lab] = st
            instruction = any(w in text for w in ("你", "您", "请", "点击", "选择", "返回", "保存", "继续"))
            if st[0] >= 6 and st[1] == 0 and instruction and lab not in self.ignored_labels:
                self.ignored_labels.add(lab)
                if self.on_learn:
                    self.on_learn(lab, "")
                self.filtered += 1
                return ""
        if not self.keep_quotes and not force:
            keep, why = is_story_text(text, self.min_cjk, self.strict)
            if not keep:
                self.filtered += 1
                self.last_reason = why
                if self.on_filtered:
                    try:
                        self.on_filtered(text, why)
                    except Exception:
                        pass
                return ""
        if self.pending_speaker and time.time() - self.pending_speaker_t < 25:
            # 打字机的第一小段(比如"好大一")也会被当成短文本;
            # 如果候选正好是这句的开头,那它就是碎片,不是名字。
            #
            # 但如果游戏刚刚明确给过名字(名字框刚更新过,哪怕是**清空**),
            # 就以游戏为准,不要用这个猜出来的候选盖掉它 ——
            # 否则旁白(名字被清空)会被上一句猜出来的名字污染。
            fresh = self.speaker_t and (time.time() - self.speaker_t) < 8.0
            if not fresh and not text.startswith(self.pending_speaker):
                self.speaker = self.pending_speaker
            self.pending_speaker = ""
        now = time.time()
        self.recent = [(a, b) for a, b in self.recent if now - b < 120]
        self.recent.append((text, now))
        if len(self.recent) > 200:
            self.recent = self.recent[-120:]
        return (f"【{self.speaker}】{text}" if self.speaker else text)

    # -- 去重判定 / 回存档重读识别 --
    def _dup_kind(self, text: str) -> str:
        """这句话是不是"刚见过"?

        返回 ""(没见过)/ "last"(就是上一句)/ "same"(45 秒内一模一样)/
        "shape"(30 秒内只有数字不同)/ "similar"(20 秒内高度相似,打字机残留)。
        """
        if text == self.last_committed:
            return "last"
        now = time.time()
        shape = number_shape(text)
        for t, ts in self.recent:
            if now - ts >= 120:
                continue
            if t == text and now - ts < 45:
                return "same"
            if now - ts < 30 and len(shape) >= 4 and number_shape(t) == shape:
                return "shape"
            if now - ts < 20 and similar(t, text) >= 0.9 and abs(len(t) - len(text)) <= 4:
                return "similar"
        return ""

    def _looks_like_replay(self, text: str, kind: str) -> bool:
        """判断"连续见到旧句子"是**玩家回存档重读**,还是界面在刷屏。

        重读的特征:一句接一句、**彼此各不相同**、但都见过(A→B→C…)。
        刷屏的特征:同一句反复出现(A→A→A)。
        所以只有"连续 2 句各不相同的旧句子"才算重读;相似度那类(打字机残留)不算。

        误判也不要紧:放行后还有 is_story_text 严格模式把关,界面说明照样会被滤掉。
        """
        if kind == "similar":
            return False
        if text != self._dup_text:
            self._dup_run += 1
        else:
            self._dup_run = 0                  # 同一句反复出现 → 刷屏,不算重读
        self._dup_text = text
        return self._dup_run >= 2

    def forget_recent(self):
        """清空去重记忆 = 允许把刚才读过的剧情再读一遍(玩家点「允许重读」也走这里)。"""
        self.recent = []
        self.last_committed = ""
        self.last_text = ""
        self._dup_run = 0
        self._dup_text = ""

    def clear_learned(self):
        self.ignored_labels.clear()
        self.ignored_texts.clear()
        self.label_stats.clear()

    def dump(self) -> dict:
        return {"ignored_labels": sorted(self.ignored_labels),
                "ignored_texts": sorted(self.ignored_texts)[-300:],
                "filtered": self.filtered, "speaker": self.speaker,
                "label_stats": self.label_stats,
                "last_reason": self.last_reason}


# ---------------------------------------------------------------- 游戏识别 / 挂钩安装
# Doorstop 的注入代理是同一个 DLL 换个名字,系统加载谁它就顶替谁。
# winhttp.dll 覆盖了游戏的联网模块 → 有的游戏(实测 AnaDos)会报"网络不稳/无法连线";
# 换成 version.dll / winmm.dll 就两全其美:LDC 照常,联网照常。
PROXY_NAMES = ["winhttp.dll", "version.dll", "winmm.dll"]
HOOK_ROOT = PROXY_NAMES + ["doorstop_config.ini", ".doorstop_version", "BepInEx", "dotnet"]
MANIFEST = "_聆阅_已安装清单.json"
# 静默推进:App 往游戏目录写这个文件(内容=请求序号),插件轮询到就伪造一次点击并删掉它。
# 用文件而不是网络:插件线程里做 HTTP 会拖住游戏主线程,文件读一下几乎不要钱。
CLICK_FILE = "_聆阅_点击请求.txt"
# 反过来:插件把"我这边静默点击成功了/失败了"写在这个文件里,App 读来显示状态。
CLICK_ACK = "_聆阅_点击回执.txt"

# 记住每台机器上"这个游戏用哪个代理是好的",下次装自动沿用
PROXY_MEMO = "_聆阅_注入代理.json"


def pick_proxy(game: dict, want: str = "auto") -> str:
    """want: auto / winhttp / version / winmm。auto 时优先用上次验证过的。

    注意:这里返回的是**裸名**(winhttp),不带 .dll —— 只用来做标识/存配置。
    真要往游戏目录里放文件,必须过一道 proxy_file() 补上 .dll,
    否则会装出一个名叫 "winhttp" 的怪文件,Windows 根本不会加载它当代理
    (LDC 等于没装,而且按钮一直显示"安装 LDC")。
    """
    want = (want or "auto").lower().replace(".dll", "")
    if want in ("winhttp", "version", "winmm"):
        return want
    try:
        m = json.load(open(os.path.join(game["dir"], PROXY_MEMO), encoding="utf-8"))
        p = str(m.get("proxy", "")).lower().replace(".dll", "")
        if p in ("winhttp", "version", "winmm"):
            return p
    except Exception:
        pass
    return "winhttp"


def proxy_file(proxy: str) -> str:
    """裸名 → 真正的文件名(winhttp → winhttp.dll)。"""
    n = (proxy or "").strip().lower().replace(".dll", "")
    return (n + ".dll") if n in ("winhttp", "version", "winmm") else "winhttp.dll"


def remember_proxy(game: dict, proxy: str):
    try:
        with open(os.path.join(game["dir"], PROXY_MEMO), "w", encoding="utf-8") as f:
            json.dump({"proxy": proxy}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def find_unity_dir(root: str, depth: int = 3):
    try:
        entries = os.listdir(root)
    except Exception:
        return None
    if any(d.endswith("_Data") for d in entries) or os.path.exists(os.path.join(root, "GameAssembly.dll")):
        return root
    if depth <= 0:
        return None
    for sub in entries:
        sp = os.path.join(root, sub)
        if os.path.isdir(sp) and sub.lower() not in ("redist", "directx", "dotnet", "_commonredist"):
            r = find_unity_dir(sp, depth - 1)
            if r:
                return r
    return None


def detect_game(exe_path: str) -> dict:
    """判断位数与 Mono/IL2CPP。任何情况都返回完整字段。"""
    info = {"exe": exe_path, "dir": os.path.dirname(exe_path), "bits": 0,
            "backend": "?", "payload": "mono_x64", "error": ""}
    try:
        with open(exe_path, "rb") as f:
            head = f.read(0x400)
        pe = struct.unpack_from("<I", head, 0x3C)[0]
        machine = struct.unpack_from("<H", head, pe + 4)[0]
        info["bits"] = 64 if machine == 0x8664 else (32 if machine == 0x14C else 0)
    except Exception as e:
        info["error"] = f"读取 exe 失败: {e}"
        return info
    udir = find_unity_dir(info["dir"], 3)
    if udir:
        info["dir"] = udir
        datas = [d for d in os.listdir(udir) if d.endswith("_Data")]
        if os.path.exists(os.path.join(udir, "GameAssembly.dll")):
            info["backend"] = "IL2CPP"
        elif any(os.path.isdir(os.path.join(udir, d, "Managed")) for d in datas):
            info["backend"] = "Mono"
        elif datas:
            info["backend"] = "Mono(推测)"
    else:
        info["backend"] = "非 Unity"
    mono = "Mono" in info["backend"]
    info["payload"] = (("mono_x64" if info["bits"] == 64 else "mono_x86") if mono
                       else ("il2cpp_x64" if info["bits"] == 64 else "il2cpp_x86"))
    return info


def steam_appid(exe_path: str) -> str:
    """Steam 游戏优先用 Steam 启动(否则游戏拿不到 Steam 会话会自己退出)。"""
    try:
        gdir = os.path.dirname(exe_path)
        apps = os.path.dirname(os.path.dirname(gdir))
        for f in os.listdir(apps):
            if not (f.startswith("appmanifest_") and f.endswith(".acf")):
                continue
            txt = open(os.path.join(apps, f), encoding="utf-8", errors="ignore").read()
            m = re.search(r'"installdir"\s+"([^"]+)"', txt)
            if m and os.path.basename(os.path.normpath(gdir)).lower() == m.group(1).lower():
                return f[len("appmanifest_"):-len(".acf")]
    except Exception:
        pass
    return ""


class HookManager:
    """装/卸 LDC、启动游戏、把插件的剧情日志喂给 StoryFilter。"""

    def __init__(self, payload_dir: str, hooks_dir: str, on_line=None, on_status=None):
        self.payload_dir = payload_dir          # <程序目录>\payload
        self.hooks_dir = hooks_dir              # <程序目录>\hooks
        self.on_line = on_line or (lambda text: None)
        self.on_status = on_status or (lambda msg: None)
        self.on_skipped = None                  # 被当噪音跳过时回调(界面「跳过噪音」页签用)
        self.filter = StoryFilter()
        self.game = None
        self.log_path = ""
        self.log_pos = 0
        self.started = False
        self._thread = None
        self._running = False
        self.skipped = 0        # 被丢掉的引擎噪音行数
        self.profile = "gameonly"  # IL2CPP LDC 档位:gameonly / tmpro_setonly / tmpro / all
        self.profile_args = "any"   # any(含字符数组,抓得多)/ string(只要字符串参数)
        self._behind = ""       # 上一轮读不完时提示落后多少行
        self._stall = 0         # 连续多少轮"文件在长但位置没动"
        self._round = 0         # 轮次(心跳用)
        # ---- 文本翻译 ----
        self.say_translation = False   # 朗读译文(XUnity 回写的中文)而不是游戏原文
        # ---- 静默推进(不控制鼠标的自动点击)----
        self.silent_click = True       # 用插件在游戏内伪造点击;False 时退回"移动鼠标点一下"
        self._click_seq = 0            # 请求序号(插件按序号去重)
        self._methods_seen = set()     # 日志里出现过的方法名 → 用来认游戏引擎(专用规则)
        self.keep_xunity = False       # True = 装 LDC 时不要清理 XUnity(翻译功能在用)

    # ---- LDC 包路径 ----
    def pack_dir(self, game: dict) -> str:
        for cand in (os.path.join(self.payload_dir, game["payload"]),):
            if os.path.isdir(cand):
                return cand
        return ""

    def installed(self, game: dict) -> bool:
        """LDC 装好了吗?

        ★必须检查带 .dll 的文件名★:老版本 bug 会装出一个名叫 "winhttp" 的文件,
        那种文件 Windows 不会当代理加载,LDC 其实是死的 —— 不能算"已安装"。
        """
        g = game["dir"]
        proxy = any(os.path.isfile(os.path.join(g, n)) for n in PROXY_NAMES)
        return proxy and all(os.path.exists(os.path.join(g, n))
                             for n in ("doorstop_config.ini", os.path.join("BepInEx", "core")))

    def install(self, game: dict, proxy: str = "auto") -> dict:
        """把 LDC 装进游戏目录。已装过就跳过复制(IL2CPP 那套 150MB,复制很慢)。"""
        pack = self.pack_dir(game)
        if not pack:
            return {"ok": False, "msg": f"缺少 LDC 包 {game['payload']}"}
        gdir = game["dir"]
        il2cpp = "IL2CPP" in game["backend"]
        proxy = pick_proxy(game, proxy)
        manifest = {"copied": [], "backup": {}, "pack": pack, "proxy": proxy,
                    "time": time.strftime("%Y-%m-%d %H:%M:%S")}
        if self.installed(game):
            self.on_status("LDC 文件已存在,跳过复制(只更新配置)")
        else:
            for name in HOOK_ROOT:
                if name in PROXY_NAMES:          # 注入代理单独处理:换个名字而已
                    continue
                src = os.path.join(pack, name)
                if not os.path.exists(src):
                    continue
                dst = os.path.join(gdir, name)
                if os.path.isfile(dst):                     # 只备份文件,目录跳过(否则 copy2 报错)
                    bak = dst + ".bak_聆阅"
                    if not os.path.exists(bak):
                        try:
                            shutil.copy2(dst, bak)
                        except Exception:
                            pass
                    # ★不管备份是不是这次新建的,都要记进清单★
                    # 否则(上一次装留下的 .bak 还在时)卸载就不知道有这个备份,
                    # 结果 .bak_聆阅 永远留在游戏目录里(玩家实测的"卸载残留")。
                    if os.path.exists(bak):
                        manifest["backup"][name] = bak
                try:
                    if os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src, dst)
                    manifest["copied"].append(name)
                except Exception as e:
                    return {"ok": False, "msg": f"复制 {name} 失败:{e}(游戏可能还开着)"}
            # 注入代理:同一个 DLL,按选定的名字放进去(★文件名必须带 .dll★)
            src_proxy = os.path.join(pack, "winhttp.dll")
            if not os.path.exists(src_proxy):
                for n in PROXY_NAMES:
                    if os.path.exists(os.path.join(pack, n)):
                        src_proxy = os.path.join(pack, n)
                        break
            pfile = proxy_file(proxy)
            try:
                shutil.copy2(src_proxy, os.path.join(gdir, pfile))
                manifest["copied"].append(pfile)
            except Exception as e:
                return {"ok": False, "msg": f"放置注入代理 {pfile} 失败:{e}(游戏可能还开着)"}
        # 只留选定的那个代理名,其它两个名字清掉(否则会双重注入)
        keep = proxy_file(proxy)
        for n in PROXY_NAMES:
            if n == keep:
                continue
            p = os.path.join(gdir, n)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                    self.on_status(f"已移除多余注入代理 {n}")
                except Exception:
                    pass
        # 清掉老版本 bug 留下的"没有扩展名"的代理文件(winhttp / version / winmm):
        # 那种文件 Windows 不会加载,LDC 等于没装,界面却以为装过。
        for n in ("winhttp", "version", "winmm"):
            p = os.path.join(gdir, n)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                    self.on_status(f"已清理无扩展名的残留代理文件 {n}")
                except Exception:
                    pass
        remember_proxy(game, proxy)
        # 清掉旧版留下的 XUnity:它自己也会钩 Text.set_text,端点半死不活时会把游戏
        # 拖崩/拖慢,而且我们的插件已经能独立挂钩,不再需要它(AnaDos 实测)。
        # ★但现在「文本翻译」功能正是靠 XUnity 把 AI 译文写回游戏的★ ——
        #   所以只有在翻译没开的时候才清理它,否则一装 LDC 就把翻译插件删了。
        if not self.keep_xunity:
            for pdir0 in (os.path.join(gdir, "BepInEx", "plugins"),
                          os.path.join(gdir, "BepInEx", "patchers")):
                for name in (os.listdir(pdir0) if os.path.isdir(pdir0) else []):
                    if name.lower().startswith("xunity"):
                        try:
                            p = os.path.join(pdir0, name)
                            shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
                            self.on_status("已清理旧版残留的 XUnity 翻译插件")
                        except Exception:
                            pass
        # IL2CPP:把LDC 档位写给插件(插件读 <游戏>\BepInEx\storyhook_mode.txt)。
        # 默认 gameonly —— 只挂游戏自己的文本入口,不碰引擎内部方法(实测LDC 挂引擎内部方法会闪退)。
        if il2cpp:
            try:
                pdir = os.path.join(gdir, "BepInEx")
                os.makedirs(pdir, exist_ok=True)
                mpath = os.path.join(pdir, "storyhook_mode.txt")
                want = f"profile={self.profile}\nargs={self.profile_args}\n"
                old = ""
                if os.path.exists(mpath):
                    old = open(mpath, encoding="utf-8", errors="ignore").read()
                if old != want:
                    with open(mpath, "w", encoding="utf-8", newline="\n") as f:
                        f.write(want)
                    manifest["copied"].append("BepInEx/storyhook_mode.txt")
            except Exception:
                pass
        # Mono 游戏要额外放我们的剧情插件。
        # 这一段要在"已装就跳过复制"之外 —— 插件升级后必须能覆盖进去。
        if not il2cpp:
            plug = os.path.join(self.hooks_dir, "mono", "StoryHook.dll")
            if os.path.exists(plug):
                pdir = os.path.join(gdir, "BepInEx", "plugins")
                os.makedirs(pdir, exist_ok=True)
                try:
                    shutil.copy2(plug, os.path.join(pdir, "StoryHook.dll"))
                    manifest["copied"].append("BepInEx/plugins/StoryHook.dll")
                except Exception as e:
                    return {"ok": False, "msg": f"更新剧情插件失败:{e}(游戏还开着的话先关掉游戏再装)"}
        try:
            with open(os.path.join(gdir, MANIFEST), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        self.on_status("LDC 安装完成")
        return {"ok": True, "msg": "LDC 已安装", "il2cpp": il2cpp, "pack": pack, "proxy": proxy}

    def uninstall(self, game: dict) -> dict:
        """卸载 LDC:把LDC 从游戏里**彻底**撤掉。

        删:winhttp.dll / doorstop_config.ini / .doorstop_version / BepInEx / dotnet
            + 我们自己的插件(BepInEx\\plugins\\StoryHook.dll 等)
        有备份的话把玩家原本的文件还原回去。
        """
        gdir = game["dir"]
        mpath = os.path.join(gdir, MANIFEST)
        # 先读清单(里面记着:我们装了什么、备份过什么)
        try:
            man = json.load(open(mpath, encoding="utf-8"))
        except Exception:
            man = {}
        restored = set((man.get("backup") or {}).keys())   # 这些是"还原回来的游戏原文件",不算残留
        # 1) 先删我们自己的插件(无论有没有清单)
        for rel in ("BepInEx/plugins/StoryHook.dll", "BepInEx/plugins/StoryHookIl2Cpp.dll",
                    "BepInEx/plugins/StoryHook2.dll"):
            try:
                os.remove(os.path.join(gdir, *rel.split("/")))
            except Exception:
                pass
        # 2) 清单里有记录就按记录删,没记录就按标准LDC 文件删
        try:
            m = json.load(open(mpath, encoding="utf-8"))
            names = m.get("copied") or (HOOK_ROOT + ["BepInEx/plugins/StoryHook.dll"])
        except Exception:
            names = HOOK_ROOT + ["BepInEx/plugins/StoryHook.dll"]
        # 标准LDC 文件一律补上,保证"彻底"
        for n in HOOK_ROOT:
            if n not in names:
                names.append(n)
        # 老版本 bug 留下的无扩展名代理也一并清掉
        for n in ("winhttp", "version", "winmm"):
            if n not in names:
                names.append(n)
        failed = []
        for n in names:
            p = os.path.join(gdir, *str(n).split("/"))
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
                    if os.path.exists(p):
                        failed.append(n)
                elif os.path.isfile(p):
                    os.remove(p)
            except Exception as e:
                failed.append(f"{n}({e})")
        # 3) 还原被我们备份过的原文件
        try:
            m = json.load(open(mpath, encoding="utf-8"))
            for name, bak in (m.get("backup") or {}).items():
                if os.path.exists(bak):
                    shutil.copy2(bak, os.path.join(gdir, name))
                    os.remove(bak)
        except Exception:
            pass
        # 3b) 兜底清扫:凡是 .bak_聆阅 备份、注入代理记事本、清单本身,
        #     一律扫干净 —— 老版本清单里可能没记全,不能靠清单。
        import glob as _glob
        for pat in ("*.bak_聆阅", PROXY_MEMO, MANIFEST):
            for p in _glob.glob(os.path.join(gdir, pat)):
                try:
                    os.remove(p)
                except Exception:
                    pass
        # 3c) 空目录也顺手收掉(有些游戏原本没有 BepInEx 目录)
        for sub in ("BepInEx", "dotnet"):
            p = os.path.join(gdir, sub)
            try:
                if os.path.isdir(p) and not os.listdir(p):
                    os.rmdir(p)
            except Exception:
                pass
        try:
            os.remove(mpath)
        except Exception:
            pass
        # 4) 复查:我们装进去的东西必须都没了
        #    (备份还原回来的游戏原文件当然还在 —— 那是玩家自己的,不算残留)
        left = [x for x in (PROXY_NAMES + ["winhttp", "version", "winmm",
                                           "doorstop_config.ini", ".doorstop_version",
                                           "BepInEx", "dotnet", PROXY_MEMO, MANIFEST])
                if os.path.exists(os.path.join(gdir, x)) and x not in restored]
        if left:
            self.on_status("LDC卸载不完整:" + "、".join(left))
            return {"ok": False, "msg": "卸载不完整,还剩下:" + "、".join(left)
                                          + "(可能是游戏还开着,关掉游戏再试)"}
        self.on_status("LDC已从游戏里彻底撤掉")
        return {"ok": True, "msg": "已卸载 LDC(LDC 已彻底撤掉,游戏恢复原版,不留残留文件)"}

    def launch(self, game: dict) -> dict:
        exe = game["exe"]
        appid = steam_appid(exe)
        started = False
        if appid:
            try:
                os.startfile(f"steam://rungameid/{appid}")
                started = True
            except Exception:
                started = False
        if not started:
            try:
                subprocess.Popen([exe], cwd=game["dir"])
            except Exception as e:
                return {"ok": False, "msg": f"启动失败:{e}"}
        return {"ok": True, "msg": f"已启动{'（通过 Steam）' if appid else ''}", "appid": appid}

    # ---- 剧情日志 ----
    def set_game(self, game: dict):
        self.game = game
        self.log_path = os.path.join(game["dir"], "BepInEx", "storyhook.log")
        self.log_pos = 0
        self.started = False
        self._methods_seen = set()
        # 换上这款游戏的专用过滤规则(按 exe 名先匹配一次,后面还能按日志里的方法名补)
        set_active_profile(match_profile(game.get("exe") or game.get("dir") or "", self._methods_seen))
        old = self.filter
        self.filter = StoryFilter(min_cjk=old.min_cjk, strict=old.strict,
                                  extra_words=old.extra_words,
                                  ignored_labels=old.ignored_labels,
                                  ignored_texts=old.ignored_texts,
                                  on_learn=old.on_learn)
        # ★回调必须一并带过去★:以前只带了 on_learn,于是换过一次游戏之后
        # on_filtered / on_replay 全丢(界面「已过滤」页签、读档重读提示都记不出来)。
        self.filter.on_filtered = old.on_filtered
        self.filter.on_replay = old.on_replay
        self.filter.settle = old.settle

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            time.sleep(0.2)           # 轮询间隔:越小越跟手
            try:
                for line in self.filter.tick():
                    self.on_line(line)
                if not self.log_path or not os.path.exists(self.log_path):
                    continue
                size = os.path.getsize(self.log_path)
                if size < self.log_pos:
                    self.log_pos = 0
                if not self.started:
                    self.started = True
                    self.log_pos = size          # 只读接上之后的新剧情
                    self.on_status("已接上 LDC,从现在起显示新出现的剧情")
                    continue
                # ★卡住自动恢复★
                # 现象:读到一半就不读了,重启程序又能读(玩家实测)。
                # 这里把"重启"自动化:文件明明在长、位置却连续多轮不动 → 就地重新对齐。
                if size > self.log_pos and self.log_pos == getattr(self, "_last_pos", -1):
                    self._stall += 1
                else:
                    self._stall = 0
                self._last_pos = self.log_pos
                if self._stall >= 10:                     # ≈2.5 秒没进展
                    self.log_pos = size
                    self.filter.pending = ""
                    self.filter.recent = []
                    self._stall = 0
                    self.filter.filtered += 0
                    self.on_status("读取卡住,已自动重新对齐到最新进度(等价于重启程序)")
                    self._resync = getattr(self, "_resync", 0) + 1
                    continue

                # 心跳:不再每 60 轮刷一条状态(状态会被写进日志面板,玩家反馈太吵)。
                # 这些数字在「日志」页顶部的实时面板里一直能看到(/api/state 的 metrics)。
                # 只有"积压/追上"这种**状态变化**才提示一次。
                self._round += 1
                behind_now = (size - self.log_pos) > 64 * 1024
                if behind_now != getattr(self, "_was_behind", False):
                    self._was_behind = behind_now
                    self.on_status("正在追赶积压的剧情…(会自动追上)" if behind_now
                                   else "已追上最新进度")

                if size == self.log_pos:
                    continue
                # 积压太多(游戏一瞬间刷了几百 KB)就直接跳到末尾:
                # 宁可丢掉已经过去的旧句,也不要永远落后、越读越慢。
                if size - self.log_pos > 300 * 1024:
                    self.log_pos = size
                    self.filter.pending = ""
                    self.on_status("积压过多,已跳到最新进度(旧句略过)")
                    continue
                # ★关键修复★ 必须用二进制方式读写位置。
                # 旧代码用文本模式读、再用 UTF-8 字节数去减 f.tell() ——
                # 而文本模式的 tell() 是"不透明 cookie",不是字节偏移,
                # 一旦某行含中文(游戏文本当然是中文),相减结果就是垃圾值,
                # 于是下一次 seek 到错误位置 → 后面的剧情永远读不到。
                # 现象:一轮里积压超过 800 行(噪音一多就超)之后,就再也读不到 ——
                # 正好对应"跳过噪音数一到 100 多就读不了";重启程序(位置归零)又能读。
                with open(self.log_path, "rb") as f:
                    f.seek(self.log_pos)
                    data = f.read(512 * 1024)
                    self.log_pos = f.tell()          # 二进制模式:确确实实是字节偏移
                if data:
                    cut = data.rfind(b"\n")
                    if cut >= 0:                     # 只处理到最后一个完整行为止
                        self.log_pos -= (len(data) - cut - 1)
                        data = data[:cut + 1]
                chunk = data.decode("utf-8", "ignore")
                # (积压提示已经由上面的"状态变化"统一处理,这里不再每轮刷状态)
                for raw in chunk.splitlines():
                    # ★只去掉行尾的换行,不要 strip 整行★
                    # 插件上报"名字框被清空"时写的是 "类型\t方法\t"(末尾是空字段);
                    # 一旦 strip 掉那个制表符,split 之后 parts[-1] 就变成了**方法名**
                    # (实测被当成角色名 "set_NameText" 记了下来,名字全乱)。
                    raw = raw.rstrip("\r\n")
                    if not raw or raw.lstrip().startswith("#"):
                        continue
                    parts = raw.split("\t")
                    typ = parts[0] if parts else ""
                    method = parts[1] if len(parts) >= 2 else ""
                    # 明确取第 3 段:缺了就是空文本(空文本对"名字框清空"是有意义的信号)
                    text = parts[2] if len(parts) >= 3 else ""
                    # 记下出现过的方法名:用来认这款游戏属于哪份"专用规则"
                    if method and method not in self._methods_seen:
                        self._methods_seen.add(method)
                        if len(self._methods_seen) in (1, 4, 12, 40):
                            self._sync_profile()
                    # ── XUnity 回写的**译文** ──
                    # 开了「朗读译文」就把译文顶到待定稿的位置(原文不再念);
                    # 没开就照旧丢掉,只读游戏原文。★判据是类型段,不是方法段★
                    if is_xunity(typ, method):
                        if self.say_translation and text:
                            self.filter.replace_pending(strip_rich(text))
                        continue
                    # 白名单里的行连"引擎噪音"这一关都要放行(玩家在日志里明确点了"要读")
                    if is_junk_line(method, text, typ) and not self.filter.is_whitelisted(strip_rich(text)):
                        self.skipped += 1          # 引擎内部噪音,直接丢
                        if self.on_skipped:
                            try:
                                self.on_skipped(method, text)
                            except Exception:
                                pass
                        continue
                    for out in self.filter.feed(text, method, typ):
                        self.on_line(out)
            except Exception as e:
                self.on_status(f"读取剧情出错:{e}")

    def _sync_profile(self):
        """按"当前游戏 + 日志里见过的方法名"重算专用规则。"""
        try:
            g = self.game or {}
            key = match_profile(g.get("exe") or g.get("dir") or "", self._methods_seen)
            if key != ACTIVE_PROFILE:
                set_active_profile(key)
                if key:
                    self.on_status("已识别到「%s」,启用它的专用过滤规则"
                                   % PROFILE_BY_KEY[key]["name"])
        except Exception:
            pass

    # ---- 静默推进(自动点击的"不动鼠标"版本)----
    def silent_advance(self) -> dict:
        """让游戏**自己在内部**点一下"下一句"(真实鼠标一动不动)。

        实现:往游戏目录写一个请求文件,插件那边轮询到就伪造一次点击
        (UTAGE 里等价于 AdvPage.InputSendMessage + UiManager.IsInputTrig),
        写完请求就交给插件删除,避免重复触发。
        """
        g = self.game or {}
        d = g.get("dir") or ""
        if not d:
            return {"ok": False, "msg": "还没选游戏"}
        self._click_seq += 1
        p = os.path.join(d, "BepInEx", CLICK_FILE)
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(str(self._click_seq))
            return {"ok": True, "msg": "已让游戏自己点了一下(鼠标没动)"}
        except Exception as e:
            return {"ok": False, "msg": f"写入请求失败:{e}"}

