# -*- coding: utf-8 -*-
"""AI 辅助:把识别到的文字交给大模型润色 / 修补(OpenAI 兼容接口)。

只用标准库 urllib,不额外引入依赖。配置来自 config.json 的 ai:
    {enabled, repair, polish, strength, base_url, api_key, model, prompt}
"""
import json
import threading
import urllib.error
import urllib.request

TIMEOUT = 25

# 每次调用的 token 用量(线程内记录,供界面显示)
_local = threading.local()

# 累计用量(界面「AI 助手」里显示 token 与估算花费)
_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
_total_lock = threading.Lock()


def last_usage() -> dict:
    return dict(getattr(_local, "usage", {}) or {})


def total_usage() -> dict:
    """本次运行累计的 token 用量(重启程序清零)。"""
    with _total_lock:
        return dict(_total)


def reset_usage() -> dict:
    with _total_lock:
        for k in _total:
            _total[k] = 0
    return total_usage()


def estimate_cost(usage: dict, price_in: float = 2.0, price_out: float = 8.0) -> float:
    """按"元 / 百万 token"估算花费。

    单价由玩家在设置里填(各家、各时期价格都不一样,写死在代码里迟早过期),
    默认值只是给的 DeepSeek 常见档位。
    """
    u = usage or {}
    pin = max(0.0, float(price_in or 0))
    pout = max(0.0, float(price_out or 0))
    return (int(u.get("prompt_tokens") or 0) * pin
            + int(u.get("completion_tokens") or 0) * pout) / 1_000_000.0


SYSTEM_PROMPTS = {
    "repair": (
        "你是游戏文本纠错助手。用户给的是从游戏里取到的台词文本,常见问题是"
        "形近字(如 人/入、己/已、木/术)、漏字、多字、把图标识别成的怪字。"
        "请依据上下文修复这些错误,恢复成通顺的原文。"
        "只输出修复后的正文,不要解释,不要加引号。"
    ),
}

# 润色强度(按玩家定义):
#   1 轻微:字符层面优化 —— 长句断句、补标点、可加 ？ ！ ♥ ~ 之类情绪小符号,不换词
#   2 适中:台词太僵硬/翻译腔时改自然,并加上合适语气词
#   3 强:演出级改写 —— 重组节奏、拆并句、增强画面感与表现力
# 三档共同红线:**不得超出/改变原文的意思与事实**
POLISH_PROMPTS = {
    1: (
        "你是游戏字幕的排版与断句助手。你**只做这几件事**:\n"
        "· 断句:一长串连着说的话,在合适的位置加逗号/句号,拆成好读的短句\n"
        "· 标点:补全或修正标点(中文用全角),去掉 多出来的空格\n"
        "· 演出符号:原句有明显情绪(惊讶/疑问/呼喊/娇嗔)时,可以补 ？ ！ …… 或者 ♥ ～ 之类的小符号\n"
        "· 最多只允许补上被 游戏里漏掉的常用虚词(的、了、是、在),**不许换词、不许改语序、不许增删信息**\n"
        "示例:\n"
        "输入:但是，如果这是真的呢？ 从小就渴望成为骑士的我是不是真的有可能能够胜任呢\n"
        "输出:但是,如果这是真的呢?从小就渴望成为骑士的我,是不是真的有可能能够胜任呢?\n"
        "只输出正文,不要解释,不要加引号。"
    ),
    2: (
        "你是游戏台词的口吻润色助手。当角色说话**太僵硬、太像翻译腔**时,把它改成中文里真正会这么说的话:\n"
        "· 加上合适的语气词和口语节奏(吧、呢、啊、哦、嘛……),让语气活起来\n"
        "· 调整语序、拆开拗口的长句,让它顺口\n"
        "· 标点、断句、情绪符号(？ ！ ♥ ～)都可以用上\n"
        "**前提:不得改变原意;不得新增或删除任何剧情信息(谁做了什么、发生了什么),也不得改变人物性格**\n"
        "只输出正文,不要解释,不要加引号。"
    ),
    3: (
        "你是游戏剧情的演出级润色助手。在**完全不改变原意**的前提下,把这段文字改写成最有表现力的版本:\n"
        "· 大幅重组句子与节奏:长句拆短、短句并长,读起来有起伏\n"
        "· 用更有画面感的动词和形容,补足语气与停顿,善用 …… ！ ？ ♥ 等符号做演出\n"
        "· 去掉翻译腔和口水话,让它像中文原生的台词\n"
        "**红线:所有事实、人物、动作、因果都必须与原文一致;不许新增剧情事件或人物,不许改变谁说了什么**\n"
        "只输出正文,不要解释,不要加引号。"
    ),
}
STRENGTH_LABEL = {1: "轻微", 2: "适中", 3: "强"}


def polish_prompt(strength: int) -> str:
    try:
        s = int(strength)
    except (TypeError, ValueError):
        s = 1
    return POLISH_PROMPTS.get(max(1, min(3, s)), POLISH_PROMPTS[1])


def _bare(s: str) -> str:
    """去掉所有标点/空白,只留字,用来判断"AI 是不是基本没改"。"""
    return "".join(ch for ch in (s or "") if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def _too_similar(src: str, out: str) -> bool:
    a, b = _bare(src), _bare(out)
    if not a or not b:
        return False
    if a == b:
        return True                                   # 只动了标点
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio() > 0.985


def available(cfg: dict) -> bool:
    return bool((cfg or {}).get("base_url") and (cfg or {}).get("api_key"))


def _endpoint(base_url: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    if not base:
        raise ValueError("没有填 AI 接口地址")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _call(system: str, text: str, cfg: dict, timeout: int, temperature: float = 0.3) -> str:
    """发一次请求,返回清理后的正文。"""
    key = (cfg.get("api_key") or "").strip()
    body = {
        "model": (cfg.get("model") or "deepseek-chat").strip(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        "temperature": temperature,
        "stream": False,
    }
    req = urllib.request.Request(
        _endpoint(cfg.get("base_url", "")),
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "ignore")[:200]
        except Exception:
            pass
        code = e.code
        if code in (401, 403):
            hint = "API Key 不对或没有权限 —— 请重新复制一次 Key(注意别带上空格),确认它属于这个接口"
        elif code == 404:
            hint = "接口地址不对 —— 地址要以 /v1/chat/completions 结尾(不是 /v1 或网页地址)"
        elif code == 429:
            hint = "调用太频繁或额度用完 —— 等一会儿再试,或去官网看余额"
        elif 500 <= code < 600:
            hint = "对方服务器暂时出错 —— 过几分钟再试"
        elif code == 400:
            hint = "请求被拒绝 —— 多半是模型名写错了(例如应为 deepseek-chat)"
        else:
            hint = "接口拒绝了这次请求"
        raise RuntimeError(f"{hint}(HTTP {code}{':' + detail if detail else ''})")
    except urllib.error.URLError as e:
        reason = str(getattr(e, "reason", e))
        if "timed out" in reason.lower() or "timeout" in reason.lower():
            raise RuntimeError("连接超时 —— 检查网络,或这台机器是否需要开代理才能访问 AI 接口")
        raise RuntimeError(f"连不上 AI 接口 —— 检查网络或代理设置({reason})")

    try:
        out = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("AI 返回格式不对:" + json.dumps(data, ensure_ascii=False)[:200])
    # 记下 token 用量(界面会显示)
    u = data.get("usage") or {}
    _local.usage = {
        "prompt_tokens": int(u.get("prompt_tokens") or 0),
        "completion_tokens": int(u.get("completion_tokens") or 0),
        "total_tokens": int(u.get("total_tokens") or 0),
        "model": data.get("model") or body["model"],
    }
    with _total_lock:
        _total["prompt_tokens"] += _local.usage["prompt_tokens"]
        _total["completion_tokens"] += _local.usage["completion_tokens"]
        _total["total_tokens"] += _local.usage["total_tokens"]
        _total["calls"] += 1
    return _clean(out)


_HALF2FULL = {",": "，", ".": "。", "?": "？", "!": "！", ":": "：", ";": "；",
              "(": "（", ")": "）", "<": "《", ">": "》"}


def light_clean(text: str) -> str:
    """轻微档的兜底:只用本地规则规范排版/标点,**一个字都不换**。

    模型经常不听"不要改词"的指令,所以轻微档最终以这里的结果为准。
    允许:半角→全角、去汉字间空格、... → ……、补句末标点与语气符号。
    """
    import re as _re
    s = "".join(_HALF2FULL.get(ch, ch) for ch in (text or ""))
    s = _re.sub(r"(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])", "", s)   # 去掉汉字之间的空隙
    s = s.replace("...", "……").replace("..", "……").replace("。。", "。")
    s = _re.sub(r"[ \t]{2,}", " ", s).strip()
    # 句末缺标点时补一个:有疑问/感叹语气词的给对应语气,否则补句号
    if s and s[-1] not in "。！？!?…、,，；;:：\"”」』":
        if _re.search(r"(吗|呢|么|吧)$", s) or _re.search(r"(什么|怎么|为什么|难道|岂|是不是|能不能|要不要)", s):
            s += "？"
        elif _re.search(r"(啊|呀|哇|啦|唉|哼|嘿)$", s):
            s += "！"
        else:
            s += "。"
    return s


def process(text: str, mode: str, cfg: dict, timeout: int = TIMEOUT) -> str:
    """把文字交给 AI 处理,返回处理后的文字。失败抛异常,由调用方兜底。

    润色模式带"强度":
      · 轻微(1):先让 AI 处理,但只要它改动了字(不只是标点),就用本地标点规整兜底,
        保证"轻微 = 只改标点、不换词"
      · 适中/强:AI 结果为准;如果基本原样返回(只动标点),自动升一档重试一次
    """
    text = (text or "").strip()
    if not text:
        return ""
    cfg = cfg or {}
    key = (cfg.get("api_key") or "").strip()
    if not key:
        raise ValueError("还没有填 API Key(在「AI 辅助」页填)")

    try:
        strength = max(1, min(3, int(cfg.get("strength", 1))))
    except (TypeError, ValueError):
        strength = 1
    extra = (cfg.get("prompt") or "").strip()

    system = SYSTEM_PROMPTS["repair"] if mode == "repair" else polish_prompt(strength)
    if extra:
        system = extra + "\n" + system

    out = _call(system, text, cfg, timeout)

    if mode != "repair" and strength == 1:
        # 轻微档:允许断句+补标点+情绪符号,也允许补一两个虚词;
        # 但只要改动过大(换词/改语序),就用本地标点规整兜底 —— 保证不超出原意
        if not out:
            return light_clean(text)
        from difflib import SequenceMatcher
        a, b = _bare(text), _bare(out)
        sim = SequenceMatcher(None, a, b).ratio() if (a and b) else 1.0
        if sim < 0.90:
            return light_clean(text)
        return out

    # 适中/强:"没润到位"时自动加力重试一次
    if mode != "repair" and out and _too_similar(text, out):
        system2 = (extra + "\n" if extra else "") + polish_prompt(min(3, strength + 1)) + (
            "\n注意:上一次的输出和原文几乎一模一样,这是不合格的。"
            "这次必须真正改写句子结构与用词,让它读起来更自然,不允许原样返回。"
        )
        try:
            out2 = _call(system2, text, cfg, timeout, temperature=0.6)
            if out2 and not _too_similar(text, out2):
                return out2
        except Exception:
            pass
    return out


def _clean(out: str) -> str:
    """去掉模型爱加的外层引号/前缀。"""
    s = (out or "").strip()
    for pre in ("处理后的正文:", "润色后:", "修复后:", "输出:"):
        if s.startswith(pre):
            s = s[len(pre):].strip()
    if len(s) >= 2 and s[0] in "\"“「" and s[-1] in "\"”」":
        s = s[1:-1].strip()
    return s


def test(cfg: dict) -> dict:
    """测一下能不能连通(顺便返回一段示例处理结果)。"""
    sample = "但是，如果这是真的呢？ 从小就渴望成为骑士的我"
    out = process(sample, "polish", cfg, timeout=20)
    return {"ok": True, "sample_in": sample, "sample_out": out}
