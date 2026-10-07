# -*- coding: utf-8 -*-
"""声线调节:对合成好的音频做本地后处理,让玩家用滑块自己调声线。

目前提供**音高(半音)**:用相位声码器做变调 —— 不改变时长,只把基频整体上/下移,
所以同一个声音可以调得更"低沉"或更"清亮"。不联网、纯 numpy 实现。

(想更彻底地改"音色"需要共振峰弯折/声音克隆,那是另一类模型,这里不做。)
"""
import numpy as np

_FFT = 2048                     # 频率分辨率高一点,变调伪影少一些
_HOP_IN = _FFT // 4


def _stft(x: np.ndarray):
    win = np.hanning(_FFT + 1)[: _FFT].astype(np.float32)
    frames = []
    for start in range(0, max(1, len(x) - _FFT), _HOP_IN):
        seg = x[start:start + _FFT]
        if len(seg) < _FFT:
            seg = np.pad(seg, (0, _FFT - len(seg)))
        frames.append(np.fft.rfft(seg * win))
    return np.array(frames) if frames else np.zeros((0, _FFT // 2 + 1), dtype=complex), win


def _istft(frames: np.ndarray, win: np.ndarray, hop: int, length: int) -> np.ndarray:
    out = np.zeros(length + _FFT * 2, dtype=np.float32)
    wsum = np.zeros_like(out)
    for i, fr in enumerate(frames):
        seg = np.fft.irfft(fr, n=_FFT).astype(np.float32) * win
        start = i * hop
        out[start:start + _FFT] += seg
        wsum[start:start + _FFT] += win ** 2
    nz = wsum > 1e-6
    out[nz] /= wsum[nz]
    return out[:length]


def time_stretch(x: np.ndarray, rate: float) -> np.ndarray:
    """变速不变调(rate>1 变快、时长变短)。标准相位声码器。"""
    if abs(rate - 1.0) < 1e-3 or len(x) < _FFT * 2:
        return x
    frames, win = _stft(x)
    if not len(frames):
        return x
    n_bins = frames.shape[1]
    hop_out = int(round(_HOP_IN / rate))
    hop_out = max(1, hop_out)
    omega = 2 * np.pi * np.arange(n_bins) * _HOP_IN / _FFT        # 每个 bin 的期望相位步进
    out = np.zeros((len(frames), n_bins), dtype=complex)
    phase = np.angle(frames[0])
    out[0] = frames[0]
    for t in range(1, len(frames)):
        mag = np.abs(frames[t])
        dphi = np.angle(frames[t]) - np.angle(frames[t - 1]) - omega
        dphi = np.mod(dphi + np.pi, 2 * np.pi) - np.pi            # 卷绕到 [-pi,pi)
        true_adv = omega + dphi
        phase = phase + true_adv * (hop_out / _HOP_IN)
        out[t] = mag * np.exp(1j * phase)
    y = _istft(out, win, hop_out, int(len(x) / rate) + _FFT)
    return y.astype(np.float32)


def _resample(x: np.ndarray, n_out: int) -> np.ndarray:
    if n_out <= 0 or len(x) == 0:
        return x
    idx = np.linspace(0, len(x) - 1, n_out)
    return np.interp(idx, np.arange(len(x)), x).astype(np.float32)


def pitch_shift(x: np.ndarray, semitones: float) -> np.ndarray:
    """变调不变速:semitones 为半音数(+12 = 高一个八度)。"""
    if abs(semitones) < 0.05 or len(x) < _FFT * 2:
        return x
    r = 2.0 ** (float(semitones) / 12.0)
    # 先按 1/r 变速(变长 r 倍),再重采样回原长度 → 音高 ×r
    stretched = time_stretch(x, 1.0 / r)
    return _resample(stretched, len(x))


def shift_pcm16(pcm: bytes, sample_rate: int, semitones: float) -> bytes:
    """16bit 单声道 PCM 变调,返回同样格式的 bytes。"""
    if abs(semitones) < 0.05:
        return pcm
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
    y = pitch_shift(x, semitones)
    return (np.clip(y, -1.0, 1.0) * 32767).astype("<i2").tobytes()


def shift_wav(wav: bytes, semitones: float):
    """WAV 变调;返回 (新 WAV bytes, 采样率)。音频很短就直接原样返回。"""
    import io
    import wave

    if abs(semitones) < 0.05:
        return wav, 0
    with wave.open(io.BytesIO(wav), "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        n = w.getnframes()
        pcm = w.readframes(n)
    if ch != 1 or sw != 2 or n < _FFT * 2:
        return wav, 0                                  # 只处理单声道 16bit
    out = shift_pcm16(pcm, sr, semitones)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(out)
    return buf.getvalue(), sr
