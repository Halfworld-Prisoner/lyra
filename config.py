# -*- coding: utf-8 -*-
"""Lyra · 配置(全新实现,纯挂钩方案)

只保留挂钩路线需要的设置。开发调试时可用环境变量 LINGYUE_DATA 指定数据目录,
正常安装后数据就放在程序目录下。
"""
import json
import os
import threading
from pathlib import Path

_lock = threading.Lock()
_ROOT = Path(os.environ.get("LINGYUE_DATA") or Path(__file__).resolve().parent)
CFG_PATH = _ROOT / "config.json"

DEFAULTS = {
    "game": "",                      # 当前游戏的 exe 路径
    "games": [],                     # 游戏库 [{"name","path","dlp","info"}]
    "removed": [],                   # 玩家手动移除过的游戏(重新扫描也不再自动加回)

    # ---- 剧情挂钩 ----
    "hook": {
        "min_cjk": 4,                # 至少几个汉字才算剧情
        "strict": True,              # 严格模式:没有对话标点的短句当界面说明过滤
        "extra_words": [],           # 玩家自己加的过滤词
        "ignored_labels": [],        # 自动/手动学到的"界面面板"标签
        "ignored_texts": [],         # 手动标记过的具体句子
        "interrupt": True,           # 新剧情来了立刻打断上一句朗读
    },

    # ---- 语音 ----
    "voice": "sherpa:chaowen",       # 默认用离线声音包「超文」(男声,随程序自带)
    "rate": 1.0,                     # 语速
    "pitch": 0.0,                    # 声线(音高,半音)
    "volume": 1.0,                   # 音量
    "auto_say": False,               # 自动朗读(默认关,想听再开)
    "say_name": False,               # 朗读时是否念出角色名(【名字】),默认不念

    # ---- 自动下一句 ----
    # 剧情**朗读完**之后停一下,自动帮玩家点一下游戏画面,进入下一句。
    # 必须是剧情朗读(自动朗读开着、且这段确实念完了)才点;被打断/停止就不点。
    "auto_next": False,              # 默认关
    "auto_next_delay": 1.0,          # 读完停几秒再点
    "auto_next_point": "center",     # 点哪儿:center 窗口中央 / low 下方文字框 / bottom 最下面
    # ★静默推进★:让 LDC 插件在游戏**内部**伪造一次点击,真实鼠标一动不动。
    # 插件点不动个别游戏时,回执会说明原因,再由下面这个开关决定要不要退回"移动鼠标点一下"。
    "auto_next_silent": True,
    "auto_next_fallback": True,
    # 没有文字的过场剧情(画面上只有"点击继续"的指示,抓不到任何文本):
    # 等一会儿还是没有新台词,就再点一次,让自动朗读能continue下去。
    "auto_next_blank": True,         # 默认开(跟着自动下一句一起用)
    "auto_next_blank_wait": 2.5,     # 几秒没新台词就算"这一步没文字"
    "auto_next_blank_max": 6,        # 连续点几次还没有新台词就停手(防止在菜单/选项上乱点)

    # ---- 文本翻译(实时把游戏里的原文换成简体中文)----
    # 走 XUnity.AutoTranslator(CustomTranslate)→ 本机 /api/translate → AI 翻译
    "translate": {
        "on": False,                 # 是否已启用(启用=把翻译插件装进游戏目录)
        "say": False,                # 译文要不要**走朗读**(玩家自己选;关掉就只改画面不念)
        "wait": 1.0,                 # 朗读译文时,打字机多等几秒(等中文回写)
        "prefetch": True,            # 读到原文就顺手先翻好(下次同一句秒出)
    },

    # ---- 角色配音 ----
    # {角色名: {"voice": 语音id, "rate": 语速, "pitch": 声线}} —— 每个角色一套,可只改其中一项
    "cast_on": True,
    "cast": {},
    # 读到过的角色名(名字 → 出现次数)。存下来,重开程序也不会丢,
    # 界面上「剧情里出现过的角色」就有内容可点。
    "cast_seen": {},
    # 默认配音:① 没有角色名的台词(旁白)② 还没单独配音的新角色 都用它。
    # 留空 = 跟随「语音朗读」页选的全局语音(**推荐留空**:
    # 填个本机 SAPI 声音的话,旁白会变成机械音,容易误以为"换了语音包也没用")。
    "cast_default": "",

    # ---- AI 辅助 ----
    "ai": {
        "enabled": False,
        "base_url": "https://api.deepseek.com/v1/chat/completions",   # DeepSeek(可换别的兼容接口)
        "model": "deepseek-chat",
        "api_key": "",
        "fix": True,                 # 修复错字
        "polish": False,             # 润色文笔
        "strength": 1,               # 润色强度 1~3
        # 计费单价(元 / 百万 token),用来把 token 换算成"花了多少钱"。
        # 各家/各时期价格不同,所以做成可改的;默认给的是 DeepSeek 常见档位。
        "price_in": 2.0,
        "price_out": 8.0,
    },

    # ---- 界面 ----
    "theme": "dark",
    "on_top": True,
    "watch_game": True,               # 监控启动的游戏:游戏关了就退出本服务
    "auto_scan": True,                # 启动时自动扫描 Steam 里的 Unity 游戏并入游戏库
    # 注入代理:winhttp(默认) / version / winmm / auto。
    # 有的游戏被 winhttp.dll 顶替后联网会坏(实测 AnaDos),换成 version 即可。
    "hook_proxy": "auto",
    # IL2CPP 挂钩档位(写给插件):
    #   gameonly  只挂游戏自己的文本入口(默认 —— 实测唯一稳定的档:一碰 TMPro 就闪退)
    #   tmpro_setonly / tmpro / all  往上加 TMPro 覆盖,但实测必崩,只作排查用
    "hook_profile": "gameonly",
    "hook_args": "any",

    # ---- 悬浮窗(左上角常驻信息条) ----
    "float_on": True,                # 显示悬浮窗(默认未展开的小胶囊)
    "float_corner": 18,              # 圆角半径(px)
}


def _merge(base: dict, cur: dict) -> dict:
    out = dict(base)
    for k, v in (cur or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            out[k] = _merge(base[k], v)
        else:
            out[k] = v
    return out


def load() -> dict:
    try:
        # utf-8-sig:配置文件要是被记事本之类写进了 BOM,也能正常读
        # (否则 json 解析失败会**静默**回落成默认值 —— 玩家的设置全没了)
        with open(CFG_PATH, encoding="utf-8-sig") as f:
            return _merge(DEFAULTS, json.load(f))
    except Exception:
        return dict(DEFAULTS)


_cfg = load()


def get() -> dict:
    return _cfg


def save() -> None:
    """原子写(先写临时文件再替换),避免并发/掉电把配置写坏。"""
    with _lock:
        try:
            tmp = str(CFG_PATH) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(_cfg, f, ensure_ascii=False, indent=2)
            os.replace(tmp, CFG_PATH)
        except Exception as e:
            print("保存配置失败:", e)


def set_many(data: dict) -> None:
    """合并写入(支持嵌套 hook/ai)。"""
    for k, v in (data or {}).items():
        if isinstance(v, dict) and isinstance(_cfg.get(k), dict):
            _cfg[k].update(v)
        else:
            _cfg[k] = v
    save()
