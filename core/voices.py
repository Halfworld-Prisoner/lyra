# -*- coding: utf-8 -*-
r"""声音包管理:离线神经网络语音(sherpa-onnx)。

以后加新声音只要往 CATALOG 里加一条(名称/体积/下载地址/模型文件),界面会自动出现,
不需要改前端 —— 这就是把"引擎"和"声音包"分开的目的。

- 已内置(安装包里带着)的包放在 <安装目录>\app\voices\<包目录>
- 玩家自己下载的包放在 %LOCALAPPDATA%\LingYueReader\voices\<包目录>
- 两个位置都会找;下载用标准库 tarfile 解 bz2,不需要额外依赖
"""
import os
import shutil
import tarfile
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # 安装目录下的 app\
BUNDLED_DIR = ROOT / "voices"                          # 随安装包带的包

GH = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"

# 每个包: id / 名字 / 性别 / 说明 / 体积 / 下载地址 / 解压出的目录。
# 模型文件名不再硬编码 —— 解压后自动扫描 *.onnx(区分声学模型与声码器),
# 所以换包/换版本都不用改代码。
#
# ★ 只保留男声 ★(玩家要求):女声包全部下架,连随安装包自带的小雅也删了。
#    这个列表就是产品里仅有的声音来源,加包只要往这里加一条。
CATALOG = [
    # ---------- 自带(随安装程序,不下载就能用) ----------
    {
        "id": "chaowen", "name": "超文", "gender": "male",
        "note": "自带男声,体积最小、速度最快(0.6 秒/句),先从这个开始",
        "size_mb": 13.4, "url": GH + "vits-piper-zh_CN-chaowen-medium-int8.tar.bz2",
        "dir": "vits-piper-zh_CN-chaowen-medium-int8", "speakers": 1, "bundled": True,
    },
    # ---------- 男声(下载) ----------
    {
        "id": "chaowen_hq", "name": "超文 · 高音质", "gender": "male",
        "note": "同一个男声的高音质版,语气更自然、体积大一些",
        "size_mb": 57.6, "url": GH + "vits-piper-zh_CN-chaowen-medium.tar.bz2",
        "dir": "vits-piper-zh_CN-chaowen-medium-hq", "speakers": 1, "bundled": False,
    },
    {
        "id": "fanchen_wnj", "name": "沉稳男声 · 文", "gender": "male",
        "note": "官方文档里唯一明确标「Chinese / 1 male」的男声;实测基频 118Hz,是这批里最快的(单句约 2 秒)",
        "size_mb": 113.6, "url": GH + "vits-zh-hf-fanchen-wnj.tar.bz2",
        "dir": "vits-zh-hf-fanchen-wnj", "speakers": 1, "bundled": False,
    },
    {
        "id": "fanchen_unity", "name": "UNITY · 男声", "gender": "male",
        "note": "这批里最低沉、语调起伏最大的男声(基频 112Hz),适合有表现力的剧情对白",
        "size_mb": 113.6, "url": GH + "vits-zh-hf-fanchen-unity.tar.bz2",
        "dir": "vits-zh-hf-fanchen-unity", "speakers": 1, "bundled": False,
    },
    {
        "id": "fanchen_laozhe", "name": "智慧老者", "gender": "male",
        "note": "成熟老者男声(基频 117Hz),语速平稳,最适合旁白和长段落",
        "size_mb": 113.9, "url": GH + "vits-zh-hf-fanchen-ZhiHuiLaoZhe.tar.bz2",
        "dir": "vits-zh-hf-fanchen-ZhiHuiLaoZhe", "speakers": 1, "bundled": False,
    },
    {
        "id": "fanchen_laozhe2", "name": "智慧老者 · 新版", "gender": "male",
        "note": "同系列重导出的老者男声(基频起伏更大),情绪比上一版明显",
        "size_mb": 113.9, "url": GH + "vits-zh-hf-fanchen-ZhiHuiLaoZhe_new.tar.bz2",
        "dir": "vits-zh-hf-fanchen-ZhiHuiLaoZhe_new", "speakers": 1, "bundled": False,
    },
    {
        # 5 个音色里 3 个男声 —— 默认 sid=0 是**女声**,必须靠 male_speakers() 只列 #1/#3/#4
        # (实测 sid0=266.7Hz 女、sid1=97.6 男、sid3=161.6 男、sid4=104.9 男)
        "id": "zh_ll", "name": "五音色 · 三男声", "gender": "male",
        "note": "一个包里 5 个音色(已挑出 3 个男声:低沉 / 青年 / 中低),适合一部戏里配不同角色",
        "size_mb": 113.3, "url": GH + "sherpa-onnx-vits-zh-ll.tar.bz2",
        "dir": "sherpa-onnx-vits-zh-ll", "speakers": 5, "bundled": False,
        "speaker_gender": {1: "male", 3: "male", 4: "male"},
    },
    # ---------- 多音色(只列男声) ----------
    {
        "id": "aishell3", "name": "AISHELL3 · 男声组", "gender": "male",
        "note": "一个包里 174 个音色,已逐个实测基频挑出 23 个男声;想要不同角色不同嗓子就装它",
        "size_mb": 140.1, "url": GH + "vits-zh-aishell3.tar.bz2",
        "dir": "vits-zh-aishell3", "speakers": 174, "bundled": False,
        # ★逐个实测基频得到的男声(F0 < 165Hz)★
        #   这份表修过三次错:去掉 72/136/156(实测 172/207/169Hz,其实是女声)、
        #   去掉 98/102(151/163Hz,临界,换个句长就飘到女声范围)、补上漏掉的 52/100。
        "speaker_gender": {
            10: "male", 15: "male", 21: "male", 25: "male", 40: "male", 46: "male",
            52: "male", 58: "male", 60: "male", 69: "male", 74: "male", 75: "male",
            76: "male", 95: "male", 100: "male", 107: "male", 110: "male", 119: "male",
            124: "male", 143: "male", 163: "male", 167: "male", 171: "male",
        },
    },
]


def speaker_gender(pack_id: str, sid: int) -> str:
    """某个说话人的性别(male/female/'' 未知)。"""
    p = PACK_BY_ID.get(pack_id) or {}
    table = p.get("speaker_gender") or {}
    if not table:
        return p.get("gender") if p.get("gender") in ("male", "female") else ""
    return table.get(int(sid), "female")      # 表里没标的一律按女声(检测阈值偏保守)


def male_speakers(pack_id: str) -> list:
    """多音色包里的男声音色号(单音色包返回 [0])。

    产品只提供男声,所以列表/界面一律以这个为准 ——
    以前 AISHELL3 会把 174 个音色里前 8 个没标性别的(其实是女声)也列出来,
    玩家点进去就听到女声,和"只留男声"矛盾。
    """
    p = PACK_BY_ID.get(pack_id) or {}
    n = int(p.get("speakers") or 1)
    if n <= 1:
        return [0]
    table = p.get("speaker_gender") or {}
    return [s for s in sorted(table) if table[s] == "male"]

PACK_BY_ID = {p["id"]: p for p in CATALOG}


def user_dir() -> Path:
    """玩家下载的语音包放在这里(不需要管理员权限)。

    英文目录名(Lyra);以前叫 LingYueReader —— 新目录还不存在而老目录在时,
    **自动把老目录整体搬过来**(搬不动就继续用老目录,绝不丢玩家下载过的包)。
    """
    base = Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))
    new_dir = base / "Lyra" / "voices"
    old_dir = base / "LingYueReader" / "voices"
    if not new_dir.exists() and old_dir.is_dir():
        try:
            new_dir.parent.mkdir(parents=True, exist_ok=True)
            os.replace(str(old_dir), str(new_dir))       # 同盘:原子改名
        except Exception:
            try:
                import shutil as _sh
                _sh.copytree(old_dir, new_dir)
            except Exception:
                return old_dir                            # 实在不行就继续用老的
    return new_dir


VOCODER_URL = GH + "vocos-22khz-univ.onnx"
VOCODER_FILE = "vocos-22khz-univ.onnx"
VOCODER_MB = 50.0


def _resolve(d: Path) -> dict:
    """扫描一个已解压的声音包目录,自动辨认声学模型/声码器/tokens/lexicon。

    不再硬编码文件名 —— 各个包的模型文件名千奇百怪(model.onnx / *_medium.onnx /
    model-steps-3.onnx …),硬编码就会出现"包结构不对,没找到模型文件"。
    """
    if not d or not d.is_dir():
        return {}
    onnx = sorted(p for p in d.rglob("*.onnx"))
    if not onnx:
        return {}
    voc_keys = ("vocos", "hifigan", "vocoder", "voc.")
    vocoders = [p for p in onnx if any(k in p.name.lower() for k in voc_keys)]
    acoustic = [p for p in onnx if p not in vocoders] or onnx
    # Matcha 架构:文件名带 steps / matcha
    is_matcha = any(("steps" in p.name.lower()) or ("matcha" in p.name.lower()) for p in acoustic)
    model = None
    # 优先 int8 量化版:体积小、内存低、速度快,音质差别很小
    for pref in ("model.int8.onnx",):
        for p in acoustic:
            if p.name.lower() == pref:
                model = p
                break
        if model:
            break
    if model is None:
        int8s = [p for p in acoustic if ".int8." in p.name.lower()]
        if int8s:
            model = max(int8s, key=lambda p: p.stat().st_size)
    if model is None:
        for pref in ("model.onnx", "model-steps-3.onnx", "model-steps-2.onnx"):
            for p in acoustic:
                if p.name.lower() == pref:
                    model = p
                    break
            if model:
                break
    if model is None and len(acoustic) == 1:
        # 只有一个 onnx:那它就是声学模型(vits-zh-hf-* 家族的模型文件是按角色命名的,
        # 比如 zenyatta.onnx / vits-zh-hf-fanchen-wnj.onnx,根本不叫 model.onnx)
        model = acoustic[0]
    if model is None:
        # 再有多个才按"名字和包目录同名"挑,最后才退化成"最大的那个"
        same = [p for p in acoustic if p.stem.lower() in (d.name.lower(), d.parent.name.lower())]
        model = same[0] if same else None
    if model is None:                       # 退而求其次:最大的那个 onnx
        model = max(acoustic, key=lambda p: p.stat().st_size)
    tokens = next((p for p in d.rglob("tokens.txt")), None)
    lexicon = next((p for p in d.rglob("lexicon.txt")), None)
    # Piper 类是"音素"模型,要么给 lexicon,要么给 espeak-ng-data(有的包里带着)
    data_dir = next((p for p in d.rglob("espeak-ng-data") if p.is_dir()), None)
    vocoder = None
    if is_matcha:
        vocoder = (vocoders[0] if vocoders else None)
    return {
        "model": model, "tokens": tokens, "lexicon": lexicon, "data_dir": data_dir,
        "vocoder": vocoder, "matcha": is_matcha, "dir": d,
    }


def pack_path(pack_id: str):
    """返回已安装包的目录(内置优先),没装返回 None。"""
    p = PACK_BY_ID.get(pack_id)
    if not p:
        return None
    for base in (BUNDLED_DIR, user_dir()):
        d = base / p["dir"]
        if d.is_dir() and any(d.rglob("*.onnx")):
            return d
    return None


def is_installed(pack_id: str) -> bool:
    return pack_path(pack_id) is not None


def is_bundled(pack_id: str) -> bool:
    """包是不是"随安装程序自带"(在 app\\voices 里),用来在界面上打「自带」标签。"""
    p = PACK_BY_ID.get(pack_id)
    if not p:
        return False
    d = BUNDLED_DIR / p["dir"]
    try:
        return d.is_dir() and any(d.rglob("*.onnx"))
    except Exception:
        return False


def installed_ids() -> list:
    return [p["id"] for p in CATALOG if is_installed(p["id"])]


def catalog() -> list:
    """给界面用的列表(带"是否已安装"和性别,便于分组)。"""
    out = []
    for p in CATALOG:
        item = {k: p[k] for k in ("id", "name", "note", "size_mb", "speakers", "bundled", "gender")}
        item["installed"] = is_installed(p["id"])
        item["kind"] = "sherpa"
        out.append(item)
    return out


def _download(url: str, dest: Path, on_progress=None) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "LingYueReader"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
        total = int(resp.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = resp.read(262144)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if on_progress and total:
                on_progress(got, total)


def install_pack(pack_id: str, on_status=None, on_progress=None) -> dict:
    """下载并解压一个声音包(阻塞;调用方放在后台线程里)。"""
    p = PACK_BY_ID.get(pack_id)
    if not p:
        return {"ok": False, "error": "没有这个声音包"}
    if is_installed(pack_id):
        return {"ok": True, "already": True, "note": f"{p['name']} 已经装好了"}

    dest_root = user_dir()
    dest_root.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="gtr_voice_"))
    try:
        if on_status:
            on_status(f"正在下载「{p['name']}」({p['size_mb']} MB)…")
        tar_path = tmp / "pack.tar.bz2"
        _download(p["url"], tar_path, on_progress)
        if on_status:
            on_status("正在解压…")
        with tarfile.open(tar_path, "r:bz2") as tf:
            tf.extractall(tmp)                      # 包里通常是一层同名目录
        info = _resolve(tmp / p["dir"]) or {}
        if not info:
            # 有的包会多套一层:在整个临时目录里找
            for cand in tmp.iterdir():
                if cand.is_dir():
                    info = _resolve(cand) or {}
                    if info:
                        break
        if not info:
            return {"ok": False, "error": "包结构不对,没找到模型文件"}
        src = Path(info["dir"])
        if src.name != p["dir"]:
            # 归一到标准目录名,免得以后找不到
            moved = tmp / p["dir"]
            if not moved.exists():
                try:
                    src.rename(moved)
                    src = moved
                    info = _resolve(src) or info
                except Exception:
                    pass

        # Matcha 类需要声码器:包里没带就下载一个
        if info.get("matcha") and not info.get("vocoder"):
            if on_status:
                on_status(f"正在下载声码器({VOCODER_MB} MB)…")
            _download(VOCODER_URL, src / VOCODER_FILE, on_progress)
            info = _resolve(src) or info

        target = dest_root / p["dir"]
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        shutil.move(str(src), str(target))
        if on_status:
            on_status(f"「{p['name']}」安装完成")
        return {"ok": True, "path": str(target)}
    except Exception as e:
        return {"ok": False, "error": f"安装失败: {e}"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def remove_pack(pack_id: str) -> dict:
    """删除下载的包(内置的删不掉)。"""
    p = PACK_BY_ID.get(pack_id)
    if not p:
        return {"ok": False, "error": "没有这个声音包"}
    target = user_dir() / p["dir"]
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
        return {"ok": True}
    if (BUNDLED_DIR / p["dir"]).exists():
        return {"ok": False, "error": "这是随程序自带的声音包,删不掉"}
    return {"ok": False, "error": "这个包还没装"}


# ---------------- 引擎缓存(加载一次模型要 2 秒左右) ----------------
_engines = {}
_lock = threading.Lock()


def clear_cache() -> None:
    """清掉已加载的模型(手动往目录里放了新包时用「重载引擎」)。"""
    with _lock:
        _engines.clear()


def get_engine(pack_id: str):
    """拿到(并缓存)一个包的 OfflineTts 引擎;没装返回 None。"""
    import sherpa_onnx

    p = PACK_BY_ID.get(pack_id)
    if not p:
        return None
    d = pack_path(pack_id)
    if not d:
        return None
    key = str(d)
    with _lock:
        hit = _engines.get(key)
        if hit is not None:
            return hit
    info = _resolve(d)
    if not info or not info.get("model"):
        return None
    tokens = info.get("tokens")
    lexicon = info.get("lexicon")
    data_dir = info.get("data_dir")
    try:
        if info.get("matcha"):
            voc = info.get("vocoder")
            if voc is None:
                return None
            model_cfg = sherpa_onnx.OfflineTtsModelConfig(
                matcha=sherpa_onnx.OfflineTtsMatchaModelConfig(
                    acoustic_model=str(info["model"]), vocoder=str(voc),
                    tokens=str(tokens) if tokens else "",
                    lexicon=str(lexicon) if lexicon else "",
                    data_dir=str(data_dir) if data_dir else "",
                ),
                num_threads=2, provider="cpu",
            )
        else:
            model_cfg = sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=str(info["model"]),
                    tokens=str(tokens) if tokens else "",
                    lexicon=str(lexicon) if lexicon else "",
                    data_dir=str(data_dir) if data_dir else "",
                ),
                num_threads=2, provider="cpu",
            )
        cfg = sherpa_onnx.OfflineTtsConfig(model=model_cfg, max_num_sentences=1)
        eng = sherpa_onnx.OfflineTts(cfg)
    except Exception:
        return None
    with _lock:
        _engines[key] = eng
    return eng


_WAV_CACHE = {}          # {(包, 文本, 语速, 音色): wav}  —— 重复的句子直接秒出
_WAV_CACHE_MAX = 48


def warm(pack_id: str, speaker: int = 0):
    """预热:先把模型加载好(首次要 2~5 秒),别让第一句台词干等。"""
    try:
        synth_wav(pack_id, "你好。", 1.0, speaker)
    except Exception:
        pass


def synth_wav(pack_id: str, text: str, speed: float = 1.0, speaker: int = 0) -> bytes:
    """合成一段 16-bit PCM WAV(离线,不联网)。

    带一层小缓存:同一句(同一包/语速/音色)第二次直接返回,不用再合成
    —— 界面文字、重复台词、点两次试听这种情况很常见。
    """
    import wave
    import numpy as np

    key = (pack_id, text, round(float(speed), 3), int(speaker))
    hit = _WAV_CACHE.get(key)
    if hit is not None:
        return hit

    eng = get_engine(pack_id)
    if eng is None:
        raise RuntimeError("这个声音包还没安装")
    t0 = time.time()
    audio = eng.generate(text, sid=int(speaker), speed=float(speed))
    samples = np.array(audio.samples, dtype=np.float32)
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    import io as _io
    buf = _io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(audio.sample_rate))
        w.writeframes(pcm)
    data = buf.getvalue()
    if len(_WAV_CACHE) >= _WAV_CACHE_MAX:          # 简单淘汰:清掉一半
        for k in list(_WAV_CACHE)[: _WAV_CACHE_MAX // 2]:
            _WAV_CACHE.pop(k, None)
    _WAV_CACHE[key] = data
    return data
