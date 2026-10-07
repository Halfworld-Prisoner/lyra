# -*- coding: utf-8 -*-
"""实测 vits-zh-hf-* 系列男声包能不能用(下载 → 解压 → _resolve → get_engine → 合成)。

用法: python docs/_vtest.py zenyatta [doom abyssinvoker ...]
结果写到 docs/_vtest.json,并把每个包的诊断打印出来。
"""
import json
import os
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, r"D:\Unity阅读器")
from core import voices as V          # noqa: E402

GH = V.GH
OUT = Path(r"D:\Unity阅读器\docs\_vtest.json")
TMP = Path(os.environ.get("TEMP", r"C:\Windows\Temp")) / "lingyue_vtest"


def log(*a):
    print(*a, flush=True)


def fetch(pack_id: str) -> dict:
    r = {"id": pack_id}
    url = GH + f"vits-zh-hf-{pack_id}.tar.bz2"
    dest = TMP / pack_id
    dest.mkdir(parents=True, exist_ok=True)
    tar = dest / "pack.tar.bz2"
    if not tar.exists() or tar.stat().st_size < 1024:
        t0 = time.time()
        log(f"[{pack_id}] 下载 {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "LingYueReader"})
        with urllib.request.urlopen(req, timeout=300) as resp, open(tar, "wb") as f:
            total = int(resp.headers.get("Content-Length") or 0)
            got = 0
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
        r["header_size_mb"] = round(total / 1048576, 1)
        r["download_s"] = round(time.time() - t0, 1)
    r["tar_mb"] = round(tar.stat().st_size / 1048576, 1)
    # 列出包内文件(不全部解压,先看结构)
    with tarfile.open(tar, "r:bz2") as tf:
        names = tf.getnames()
        r["entries"] = names[:60]
        r["entry_count"] = len(names)
        top = sorted({n.split("/")[0] for n in names})
        r["top_dirs"] = top
        # 包内 onnx / tokens / lexicon 的位置
        r["has"] = {
            "onnx": [n for n in names if n.endswith(".onnx")],
            "tokens": [n for n in names if n.endswith("tokens.txt")],
            "lexicon": [n for n in names if n.endswith("lexicon.txt")],
            "espeak": [n for n in names if "espeak-ng-data" in n][:5],
            "dict_dir": [n for n in names if n.endswith("dict")],
        }
        if not (dest / "x").exists():
            tf.extractall(dest / "x")
    root = dest / "x"
    info = V._resolve(root / pack_id) or V._resolve(root)
    # _resolve 可能返回 __ 包内一层目录
    if not info:
        for cand in sorted(root.iterdir()):
            if cand.is_dir():
                info = V._resolve(cand)
                if info:
                    break
    r["resolve"] = {k: str(v) for k, v in (info or {}).items()}
    if not info:
        r["ok"] = False
        r["why"] = "包结构不对,没找到模型文件"
        return r
    # 直接把引擎搭起来(绕过 pack_path:临时把这个包登记进目录里)
    try:
        import sherpa_onnx
        import numpy as np
        real = f"vits-zh-hf-{pack_id}"
        entry = {"id": real, "name": real, "gender": "male", "note": "",
                 "size_mb": 0, "url": "", "dir": real, "speakers": 1, "bundled": False}
        if real not in V.PACK_BY_ID:
            V.CATALOG.append(entry)
            V.PACK_BY_ID[real] = entry
        bp = V.BUNDLED_DIR
        target = bp / real
        if not target.exists():
            import shutil
            shutil.copytree(Path(info["dir"]) / real, target) if (Path(info["dir"]) / real).is_dir() \
                else shutil.copytree(Path(info["dir"]), target)
            r["copied_to"] = str(target)
        V.clear_cache()
        t0 = time.time()
        wav = V.synth_wav(real, "这是一段测试语音,用来检查这个声音包是否正常。", 1.0, 0)
        r["first_synth_s"] = round(time.time() - t0, 2)
        t0 = time.time()
        V.synth_wav(real, "第二句测试,看看速度。", 1.0, 0)
        r["warm_synth_s"] = round(time.time() - t0, 2)
        r["wav_bytes"] = len(wav)
        # 存一份试听文件,人耳可判断
        out = Path(r"D:\Unity阅读器\docs") / f"_vtest_{pack_id}.wav"
        out.write_bytes(wav)
        r["wav_out"] = str(out)
        # 采样统计:全静音/全噪声说明模型坏了
        import wave as _w
        import io as _io
        with _w.open(_io.BytesIO(wav)) as w:
            fr = w.getframerate()
            pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("f4")
        r["sample_rate"] = fr
        r["seconds"] = round(len(pcm) / max(fr, 1), 2)
        r["peak"] = int(abs(pcm).max()) if len(pcm) else 0
        r["rms"] = int((pcm ** 2).mean() ** 0.5) if len(pcm) else 0
        r["ok"] = bool(len(pcm) > 1000 and abs(pcm).max() > 500)
    except Exception as e:
        r["ok"] = False
        r["why"] = f"{type(e).__name__}: {e}"
    return r


def main():
    ids = sys.argv[1:] or ["zenyatta"]
    allr = []
    for pid in ids:
        try:
            allr.append(fetch(pid))
        except Exception as e:
            allr.append({"id": pid, "ok": False, "why": f"外层失败 {type(e).__name__}: {e}"})
        log("---- 结果 ----")
        log(json.dumps(allr[-1], ensure_ascii=False, indent=1)[:2500])
    OUT.write_text(json.dumps(allr, ensure_ascii=False, indent=1), encoding="utf-8")
    log("已写入", OUT)


if __name__ == "__main__":
    main()
