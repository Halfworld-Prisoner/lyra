# -*- coding: utf-8 -*-
"""朗读:①微软 Edge 在线自然语音(最好听,需要联网) ②Windows 本机语音(离线)
   ③pyttsx3(SAPI5,兜底)。"""
import threading

from winrt.windows.media.core import MediaSource
from winrt.windows.media.playback import MediaPlayer
from winrt.windows.media.speechsynthesis import SpeechSynthesizer

_synth = None
_current_player = None   # 当前正在使用的播放器
_fallback_engine = None  # pyttsx3 引擎(回退用)
_voice = ""              # 当前选中的语音(可能是 Edge 的 xxxNeural)
_pitch = 0.0             # 声线调节:音高(半音,-12~+12)
_note = ""               # 最近一次的小提示(例如"联网失败,已用本机语音")
_cache = {}              # Edge 合成结果缓存 {(text, voice, rate): mp3}


def set_pitch(semitones) -> float:
    """设置声线音高(半音)。返回实际生效的值。"""
    global _pitch
    try:
        _pitch = max(-12.0, min(12.0, float(semitones)))
    except (TypeError, ValueError):
        _pitch = 0.0
    return _pitch

# Edge 自然语音(比系统自带的 SAPI5 语音自然很多;需要联网)
# ★只留男声★:女声(晓晓/晓伊/晓北/晓妮)已按玩家要求下架。
# 这份名单是**实测**的:用 edge_tts.list_voices() 拉过一遍,zh-CN 下男性只有这 4 个
# (曾经凭印象加过 Yunfeng/Yunze,实际不存在,点了必然失败)。
EDGE_VOICES = [
    ("zh-CN-YunxiNeural", "云希 · 男声(阳光少年)"),
    ("zh-CN-YunyangNeural", "云扬 · 男声(专业播报)"),
    ("zh-CN-YunjianNeural", "云健 · 男声(激情解说)"),
    ("zh-CN-YunxiaNeural", "云夏 · 男声(俏皮)"),
]
EDGE_LABELS = dict(EDGE_VOICES)


def _bare(name: str) -> str:
    """去掉界面加的 "edge:" 前缀。

    界面切语音时统一发 "kind:id",Edge 的 id 本身就是语音名(zh-CN-XiaoxiaoNeural),
    所以这里要把前缀削掉,否则会把 "edge:zh-CN-XiaoxiaoNeural" 当成语音名送去合成 → 失败。
    """
    n = name or ""
    return n.split(":", 1)[1] if n.lower().startswith("edge:") else n


def is_edge_voice(name: str) -> bool:
    n = _bare(name)
    return bool(n) and (n.endswith("Neural") or n.startswith("zh-"))


def is_sherpa_voice(name: str) -> bool:
    return bool(name) and name.startswith("sherpa:")


def is_sapi_voice(name: str) -> bool:
    return bool(name) and name.startswith("sapi:")


def sherpa_pack_of(name: str) -> str:
    """从 "sherpa:<pack>" / "sherpa:<pack>#<speaker>" 取出包 id。"""
    body = name.split(":", 1)[1] if ":" in name else name
    return body.split("#", 1)[0]


def sherpa_speaker_of(name: str) -> int:
    body = name.split(":", 1)[1] if ":" in name else name
    if "#" in body:
        try:
            return int(body.split("#", 1)[1])
        except ValueError:
            return 0
    return 0


def voice_label(name: str) -> str:
    """给界面显示的短标签。"""
    if is_sherpa_voice(name):
        from . import voices as vp
        pid = sherpa_pack_of(name)
        pack = vp.PACK_BY_ID.get(pid)
        spk = sherpa_speaker_of(name)
        base = pack["name"] if pack else pid
        if not spk and not (name.count("#")):
            return base
        g = vp.speaker_gender(pid, spk)
        tag = {"male": "男声", "female": "女声"}.get(g, "")
        return f"{base} · {tag} #{spk}" if tag else f"{base} #{spk}"
    if is_sapi_voice(name):
        return name.split(":", 1)[1]
    bare = _bare(name)
    return EDGE_LABELS.get(bare, bare)


def voice_gender(name: str) -> str:
    """语音的性别(给界面上的男声/女声标签用)。"""
    if is_sherpa_voice(name):
        from . import voices as vp
        return vp.speaker_gender(sherpa_pack_of(name), sherpa_speaker_of(name))
    if is_edge_voice(name):
        return "male"                      # Edge 列表里只剩男声
    if is_sapi_voice(name):
        bare = name.split(":", 1)[1]
        try:
            for v in list(SpeechSynthesizer.all_voices):
                if v.display_name == bare:
                    return "male" if _winrt_male(v) else "female"
        except Exception:
            pass
    n = name.lower()
    if any(k in n for k in ("huihui", "yaoyao", "xiaoxiao", "xiaoyi", "hanhan", "zira", "hazel")):
        return "female"
    if "kangkang" in n:
        return "male"
    return ""


def last_note() -> str:
    return _note


def _get_synth() -> SpeechSynthesizer:
    global _synth
    if _synth is None:
        _synth = SpeechSynthesizer()
    return _synth


def list_voices() -> list:
    """返回 [(语音ID, 来源)]:离线声音包 → 本机 SAPI → Edge 在线。

    ★只列男声★(玩家要求「女声包全删」):离线包只列男声音色号,
    本机语音按 WinRT 给的 gender 过滤(0=男 1=女),Edge 只列 EDGE_VOICES(本身已全是男声)。
    """
    out = []
    try:
        from . import voices as vp
        for pid in vp.installed_ids():
            for sid in vp.male_speakers(pid):
                out.append((f"sherpa:{pid}#{sid}" if int(vp.PACK_BY_ID[pid].get("speakers") or 1) > 1
                            else f"sherpa:{pid}", "离线神经网络语音"))
    except Exception:
        pass
    try:
        voices = list(SpeechSynthesizer.all_voices)
        voices.sort(key=lambda v: 0 if v.language.lower().startswith("zh") else 1)
        # ★本机语音不再按性别过滤★:玩家要求把系统自带的女声(慧慧/瑶瑶)加回来。
        #   "只留男声"只针对我们自己提供的语音包与在线音色。
        out += [("sapi:" + v.display_name, v.language) for v in voices]
    except Exception as e:
        # 别静默吞掉!装机时曾因内嵌运行时少一个 WinRT 投影包(Foundation.Collections),
        # all_voices 直接抛异常 → 界面显示成"这台电脑没有本机语音",查了很久。
        # 现在把原因写进 note,界面上能看到。
        global _note
        if not _note:
            _note = "读不到本机语音(不影响离线/在线语音):%s %s" % (type(e).__name__, str(e)[:80])
    out += [(name, "在线语音(Edge)") for name, _label in EDGE_VOICES]
    return out


# WinRT VoiceGender: 0=Male 1=Female。老系统上个别语音可能没有这个属性,那就别拦(放行)。
def _winrt_male(v) -> bool:
    try:
        g = int(v.gender)
    except Exception:
        return True
    return g == 0


def _set_sapi_voice(name: str) -> str:
    """把本机(SAPI)合成器切到指定语音名,返回实际的 "sapi:名字"(找不到给中文默认)。"""
    synth = _get_synth()
    try:
        voices = list(SpeechSynthesizer.all_voices)
    except Exception as e:
        global _note
        if not _note:
            _note = "读不到本机语音(不影响离线/在线语音):%s %s" % (type(e).__name__, str(e)[:80])
        voices = []
    if name:
        for v in voices:
            if v.display_name == name:
                synth.voice = v
                return "sapi:" + v.display_name
    # 默认挑一个**男声**中文语音(产品只提供男声;以前会落到慧慧/瑶瑶这种女声上)
    zh = [v for v in voices if v.language.lower().startswith("zh")]
    for v in zh + voices:
        if _winrt_male(v):
            synth.voice = v
            return "sapi:" + v.display_name
    if voices:
        synth.voice = voices[0]
        return "sapi:" + voices[0].display_name
    return ""


def apply_voice(v: str) -> str:
    """把"当前使用的声音"切成 v(不改玩家的全局选择,供角色配音临时切换)。

    v 的三种写法:sherpa:<包>[#音色] / sapi:<本机语音名> / <Edge 语音名> 或 edge:<...>。
    """
    global _voice
    v = (v or "").strip()
    if not v:
        return _voice
    if is_sherpa_voice(v):
        _voice = v
    elif is_sapi_voice(v):
        got = _set_sapi_voice(v.split(":", 1)[1])
        if got:
            _voice = got
    elif is_edge_voice(v):
        _voice = _bare(v)
    return _voice


def select_voice(pref: str = "") -> str:
    """选择语音:sherpa:<包> 走离线引擎;sapi:<名字> 走本机;xxxNeural 走 Edge。"""
    global _voice, _note
    _note = ""
    if is_edge_voice(pref):
        _voice = _bare(pref)          # 界面发来的 "edge:zh-CN-XxxNeural" 要削掉前缀
        return _voice
    if pref and is_sherpa_voice(pref):
        _voice = pref
        _warm_sherpa(_voice)          # 后台预热:首次加载模型要 2~5 秒,别让第一句台词干等
        return pref
    got = _set_sapi_voice(pref.split(":", 1)[1] if is_sapi_voice(pref) else pref)
    _voice = got
    return got


def _warm_sherpa(vid: str):
    """在后台把离线模型先加载好(不阻塞调用方)。"""
    def run():
        try:
            from . import voices as vp
            vp.warm(sherpa_pack_of(vid), sherpa_speaker_of(vid))
        except Exception:
            pass
    threading.Thread(target=run, daemon=True, name="ttswarm").start()


def _playback_state(player) -> int:
    """MediaPlaybackState: 0=NONE 1=OPENING 2=BUFFERING 3=PLAYING 4=PAUSED。取不到返回 -1。"""
    try:
        return int(player.playback_session.playback_state)
    except Exception:
        return -1


def _wait_until_done(player, text: str, rate: float, timeout: float = 180.0) -> None:
    """等这一段真的播完(或被 stop() 打断)再返回。

    以前这里不等 —— speak() 在 play() 之后就返回,导致调用方以为"已经读完",
    自动播放就会在朗读中途点到下一段剧情。
    """
    import time
    t0 = time.time()
    started = False
    for _ in range(40):                     # 等它真的开始播(最多 4 秒)
        st = _playback_state(player)
        if st in (2, 3, 4):                 # buffering / playing / paused 都算已开始
            started = True
            break
        if st == 0 and time.time() - t0 > 3.0:
            break
        time.sleep(0.1)
    if started:
        while time.time() - t0 < timeout:
            st = _playback_state(player)
            if st not in (2, 3):            # 停了/播完了/被 stop 了
                time.sleep(0.12)            # 再确认一下,避开状态抖动的瞬间
                if _playback_state(player) not in (2, 3):
                    return
            time.sleep(0.08)
        return
    # 拿不到播放状态(个别系统上 playback_session 不可用):按字数估时长兜底
    try:
        est = len(text) / (4.5 * max(0.5, float(rate)))
    except Exception:
        est = len(text) / 4.5
    end = t0 + min(60.0, max(0.8, est))
    while time.time() < end:
        time.sleep(0.08)


def _edge_mp3(text: str, voice: str, rate: float, volume: float) -> bytes:
    """用 Edge 在线语音合成,返回 MP3 字节(带缓存)。音高用接口自带的 pitch 参数。"""
    global _note
    pitch = float(_pitch or 0)
    key = (text, voice, round(float(rate), 2), round(pitch, 1))
    hit = _cache.get(key)
    if hit:
        return hit
    import asyncio
    import edge_tts
    rate_pct = int(round((float(rate) - 1.0) * 100))
    rate_pct = max(-50, min(100, rate_pct))
    pitch_hz = int(round(pitch * 6))            # 1 半音 ≈ 6Hz(中等音域近似)
    async def run() -> bytes:
        kw = {"rate": f"{rate_pct:+d}%"}
        if pitch_hz:
            kw["pitch"] = f"{pitch_hz:+d}Hz"
        comm = edge_tts.Communicate(text, voice, **kw)
        buf = bytearray()
        async for chunk in comm.stream():
            if chunk.get("type") == "audio":
                buf.extend(chunk["data"])
        return bytes(buf)
    data = asyncio.run(run())
    if not data:
        raise RuntimeError("在线语音没有返回音频")
    if len(_cache) > 80:                     # 小缓存,避免越攒越多
        _cache.clear()
    _cache[key] = data
    return data


def _play_bytes(data: bytes, content_type: str, rate: float, volume: float, text: str) -> None:
    """播放内存里的音频(MP3),等它播完。"""
    global _current_player
    from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter

    prev = _current_player
    if prev is not None:
        try:
            prev.stop()
        except Exception:
            pass
        try:
            prev.source = None
        except Exception:
            pass

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream.get_output_stream_at(0))
    writer.write_bytes(data)
    writer.store_async().get()
    stream.seek(0)

    player = MediaPlayer()
    player.volume = max(0.0, min(1.0, float(volume)))
    player.source = MediaSource.create_from_stream(stream, content_type)
    player.play()
    _current_player = player
    _wait_until_done(player, text, rate)


def _speak_edge(text: str, rate: float, volume: float) -> None:
    """Edge 在线语音;失败自动退回本机语音(并记一条提示)。"""
    global _note, _voice                      # 注意:这里会赋值 _voice,必须声明 global
    want = _voice
    try:
        data = _edge_mp3(text, want, rate, volume)
        _play_bytes(data, "audio/mpeg", rate, volume, text)
    except Exception:
        _note = "在线语音不可用,已改用本机语音"
        select_voice("")                     # 退回本机中文语音
        try:
            _speak_windows(text, rate, volume)
        finally:
            _voice = want                    # 记住玩家的选择,下次再试在线


def _stream_bytes(stream) -> bytes:
    """把 WinRT 的 IRandomAccessStream 读成 bytes(用于做声线调节)。"""
    from winrt.windows.storage.streams import DataReader
    size = int(stream.size)
    reader = DataReader(stream.get_input_stream_at(0))
    reader.load_async(size).get()
    buf = reader.read_buffer(size)
    return bytes(memoryview(buf))


def _speak_windows(text: str, rate: float, volume: float) -> None:
    global _current_player
    synth = _get_synth()
    try:
        synth.options.speaking_rate = max(0.5, min(6.0, float(rate)))
    except Exception:
        pass

    # 停掉上一段并解除音源。
    # 注意:不能复用同一个 MediaPlayer —— stop() 之后再设新音源 play() 会静音,
    # 因此每次朗读都新建一个播放器(等于每次都“第一次播放”)。
    prev = _current_player
    if prev is not None:
        try:
            prev.stop()
        except Exception:
            pass
        try:
            prev.source = None
        except Exception:
            pass

    stream = synth.synthesize_text_to_stream_async(text).get()

    # 有声线调节时:把合成结果读出来 → 变调 → 用内存播放(音质/时长都不变)
    pitch = float(_pitch or 0)
    if abs(pitch) >= 0.05:
        from . import voicefx
        try:
            wav = _stream_bytes(stream)
            shifted, sr = voicefx.shift_wav(wav, pitch)
            if sr:
                _play_bytes(shifted, "audio/wav", rate, volume, text)
                return
        except Exception:
            pass                                    # 失败就退回原样播放

    player = MediaPlayer()
    player.volume = max(0.0, min(1.0, float(volume)))
    player.source = MediaSource.create_from_stream(stream, stream.content_type)
    player.play()
    _current_player = player
    _wait_until_done(player, text, rate)     # ← 关键:播完才返回


def _speak_fallback(text: str) -> None:
    """pyttsx3 回退方案(Windows SAPI5)。"""
    global _fallback_engine
    try:
        import pyttsx3
    except Exception as e:
        raise RuntimeError(f"TTS 回退不可用: {e}") from e
    if _fallback_engine is None:
        _fallback_engine = pyttsx3.init()
        for v in _fallback_engine.getProperty("voices"):
            langs = v.languages or []
            if langs and str(langs[0]).lower().startswith("zh"):
                _fallback_engine.setProperty("voice", v.id)
                break
    _fallback_engine.say(text)
    _fallback_engine.runAndWait()


def is_playing() -> bool:
    """现在是否正在播放(供"读完才点下一段"判断)。"""
    p = _current_player
    if p is None:
        return False
    return _playback_state(p) in (1, 2, 3)


def _speak_sherpa(text: str, rate: float, volume: float) -> None:
    """离线神经网络语音(sherpa-onnx):本地合成 WAV → 声线调节 → 播放,不联网。"""
    global _note, _voice                      # 注意:下面会赋值 _voice,必须声明 global
    from . import voices as vp
    from . import voicefx
    want = _voice
    pack = sherpa_pack_of(want)
    spk = sherpa_speaker_of(want)
    try:
        from . import textnorm
        spoken = textnorm.normalize(text)          # 离线模型不认阿拉伯数字,先转成中文
        wav = vp.synth_wav(pack, spoken, speed=float(rate), speaker=spk)
        pitch = float(_pitch or 0)
        if abs(pitch) >= 0.05:
            shifted, sr = voicefx.shift_wav(wav, pitch)
            if sr:
                wav = shifted
        _play_bytes(wav, "audio/wav", rate, volume, text)
    except Exception:
        _note = "离线语音不可用,已改用本机语音"
        select_voice("")
        try:
            _speak_windows(text, rate, volume)
        finally:
            _voice = want


def speak(text: str, rate: float = 1.0, volume: float = 1.0,
          voice: str = "", pitch=None) -> None:
    """朗读文本:离线神经网络 → Edge 在线 → 本机语音(按当前选中的语音自动分发)。

    voice / pitch 传了就**只对这一段生效**(角色配音用),读完自动还原全局选择。
    注意:三条路径都会**等这段播完才返回**(自动播放依赖这个语义)。
    """
    if not text:
        return
    global _voice, _pitch
    keep_v, keep_p = _voice, _pitch
    try:
        if voice and voice != _voice:
            apply_voice(voice)
        if pitch is not None:
            try:
                _pitch = max(-12.0, min(12.0, float(pitch)))
            except (TypeError, ValueError):
                pass
        if is_sherpa_voice(_voice):
            _speak_sherpa(text, rate, volume)
        elif is_edge_voice(_voice):
            _speak_edge(text, rate, volume)
        else:
            try:
                _speak_windows(text, rate, volume)
            except Exception:
                _speak_fallback(text)
    finally:
        # 还原:下一句可能换成别的角色,也可能回到全局语音
        if _voice != keep_v:
            apply_voice(keep_v) if keep_v else None
            if not keep_v:
                _voice = ""
        _pitch = keep_p


def stop() -> None:
    """停止当前朗读。"""
    global _current_player, _fallback_engine
    if _current_player is not None:
        try:
            _current_player.stop()
        except Exception:
            pass
        try:
            _current_player.source = None
        except Exception:
            pass
        _current_player = None
    if _fallback_engine is not None:
        try:
            _fallback_engine.stop()
        except Exception:
            pass
