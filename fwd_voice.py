# -*- coding: utf-8 -*-
"""尾声那句"前进！前进！！不择手段地前进！！！"（H05）的配音：分三段单独合成，再按节拍拼成 build/tts/H05.wav + H05.json。

为什么不整句交给 edge-tts：整句合成时两个"前进"是一模一样的复制品（同样 0.64 秒、同样的音高曲线），前后间隔都是整整
1.2 秒，像节拍器；最后的"前进"音高和音量一路往下掉，整句越说越弱。用户反映"非常别扭僵硬"。

现在的做法（三段，响度逐级抬高，每段加一点饱和让声音更实）：
  · 第一声："前进。"——用句号合成，压得住；
  · 第二声：直接用第一声那一条录音，升 1.5 个半音、更响，落在第一声之后两拍的拍点上。
    单独合成的"前进！"结尾往上扬、像在发问，放在半拍上又像抢拍，用户反映"第二句前进还是很怪"；
    同一句命令升调加力再喊一遍，听起来才像一个人在越喊越急。其他做法留作试听（VARIANTS，python fwd_voice.py --audition）；
  · 第三段："不择手段地，前进！"整段一口气合成（逗号让最后的"前进"前面有一口气），放慢、最响，最后一个词单独再抬高。
拼好的 H05.json 与整句合成时的词表一一对应（前进 / 前进 / 不择手段 / 地 / 前进），timeline、cues 里 C["fwd"] 的卡点、
配乐的重击、尾声的字幕动画都照常从它取时间，不用改。

用法：make.py 的 tts 步骤在整片配音之后调用 build()；单独重做：python fwd_voice.py [--force]（--force 重新合成各段）；
python fwd_voice.py --audition 把第二声的几种做法各拼一版，放进 配音试听/前进/。"""
import asyncio, json, os, subprocess, sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample
from config import TTS_DIR, VOICE, BEAT, FFMPEG, REPO

PART_DIR = os.path.join(TTS_DIR, "fwd")
# 要合成的录音：名字 -> (合成文本, 语速, 音高)
TAKES = {
    "p1": ("前进。", "-8%", "-4Hz"),
    "p3": ("不择手段地，前进！", "-10%", "+4Hz"),
    "ctx": ("继续前进！", "-6%", "+4Hz"),          # 试听 B：从"继续前进！"里截出"前进"，语调由上下文带出来
    "slow": ("前进！", "-12%", "+0Hz"),            # 试听 C：单独合成、放慢
}
# 拼接的各段：dict(take=录音名, keep=从第几个词开始保留, shift=升几个半音, gain=增益 dB, drive=饱和度,
#                 at=起点（第一声之后多少拍）, last=段内最后一个词再抬高 dB)
P1 = dict(take="p1", keep=0, shift=0.0, gain=0.0, drive=1.2, at=0.0, last=0.0)
P3 = dict(take="p3", keep=0, shift=0.0, gain=4.0, drive=1.8, at=4.0, last=5.0)   # 最后的"前进"是顶点：句尾会收、单独再抬 5 dB
VARIANTS = {
    "A": dict(take="p1", keep=0, shift=1.5, gain=2.5, drive=1.6, at=2.0, last=0.0),
    "B": dict(take="ctx", keep=1, shift=0.0, gain=2.5, drive=1.6, at=2.0, last=0.0),
    "C": dict(take="slow", keep=0, shift=0.0, gain=2.5, drive=1.6, at=2.0, last=0.0),
}
SECOND = "C"                   # 成片用哪一种第二声（用户试听后选了 C）
LEAD = 0.1                     # 拼好的音频开头留的空白（与 edge-tts 整句合成时差不多）


async def _synth(name, text, rate, pitch):
    import edge_tts                              # 只有重新合成时才需要（也只有这里需要联网）
    mp3, wav, js = (os.path.join(PART_DIR, name + ext) for ext in (".mp3", ".wav", ".json"))
    words = []
    com = edge_tts.Communicate(text, VOICE, rate=rate, pitch=pitch, boundary="WordBoundary")
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append(dict(text=ch["text"], start=ch["offset"] / 1e7, dur=ch["duration"] / 1e7))
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", mp3, "-ac", "1", "-ar", "24000", wav], check=True)
    json.dump(dict(text=text, words=words), open(js, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _load(name):
    sr, x = wavfile.read(os.path.join(PART_DIR, name + ".wav"))
    words = json.load(open(os.path.join(PART_DIR, name + ".json"), encoding="utf-8"))["words"]
    return sr, x.astype(np.float64) / 32768.0, words


def _segment(spec):
    """按 spec 切出一段、处理好，返回 (采样率, 音频, 词表（时间相对这段开头）)。"""
    sr, x, w = _load(spec["take"])
    w = [wd for wd in w[spec["keep"]:] if wd["text"].strip("，。！")]
    # 从第一个保留词的起音前 30 ms 切到最后一个词结束后 250 ms，两头 5 ms 淡入淡出
    a = max(int((w[0]["start"] - 0.03) * sr), 0)
    b = min(int((w[-1]["start"] + w[-1]["dur"] + 0.25) * sr), len(x))
    x = x[a:b].copy()
    w = [dict(wd, start=wd["start"] - a / sr) for wd in w]
    if spec["shift"]:
        # 升调：重采样（音高升 shift 个半音，时长相应缩短，词的时间同比例缩）
        r = 2 ** (spec["shift"] / 12)
        x = resample(x, int(len(x) / r))
        w = [dict(wd, start=wd["start"] / r, dur=wd["dur"] / r) for wd in w]
    f = int(0.005 * sr)
    x[:f] *= np.linspace(0, 1, f)
    x[-f:] *= np.linspace(1, 0, f)
    # 饱和：tanh 软削波让声音更实（按峰值归一后削，再还原响度），然后按增益抬高
    pk = np.abs(x).max() + 1e-9
    x = np.tanh(spec["drive"] * x / pk) / np.tanh(spec["drive"]) * pk * 10 ** (spec["gain"] / 20)
    if spec["last"]:
        # 最后一个词（起音前 30 ms 起，20 ms 渐变）单独抬高
        k = np.clip((np.arange(len(x)) / sr - (w[-1]["start"] - 0.03)) / 0.02, 0.0, 1.0)
        x *= 10 ** (spec["last"] * k / 20)
    return sr, x, w


def compose(second):
    """按 第一声 / 第二声（second 是 VARIANTS 里的一项）/ 第三段 拼好，返回 (采样率, 音频, 词表)。"""
    segs, words, sr = [], [], 24000
    for spec in (P1, second, P3):
        sr, x, w = _segment(spec)
        t0 = LEAD + spec["at"] * BEAT - w[0]["start"]            # 这一段在拼好的音频里的起点（第一个词落在拍上）
        segs.append((int(round(t0 * sr)), x))
        words += [dict(text=wd["text"], start=round(t0 + wd["start"], 6), dur=wd["dur"]) for wd in w]
    n = max(i + len(x) for i, x in segs) + int(0.3 * sr)
    out = np.zeros(n)
    for i, x in segs:
        out[i:i + len(x)] += x
    out *= 0.95 / max(np.abs(out).max(), 0.95)
    # 词表要和整句文本逐字对得上（timeline 按字定位）
    assert "".join(w["text"] for w in words) == "前进前进不择手段地前进", [w["text"] for w in words]
    return sr, out, words


def _write_wav(path, sr, x, out_sr):
    tmp = path + ".tmp.wav"
    wavfile.write(tmp, sr, (x * 32767).astype(np.int16))
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", tmp, "-ac", "1", "-ar", str(out_sr), path], check=True)
    os.remove(tmp)


def _ensure_takes(force):
    os.makedirs(PART_DIR, exist_ok=True)
    missing = [k for k in TAKES if force or not os.path.exists(os.path.join(PART_DIR, k + ".json"))]
    if missing:
        async def run():
            for k in missing:
                await _synth(k, *TAKES[k])
        asyncio.run(run())


def build(force=False):
    from opusvid.settings import SR
    _ensure_takes(force)
    sr, out, words = compose(VARIANTS[SECOND])
    _write_wav(os.path.join(TTS_DIR, "H05.wav"), sr, out, SR)
    json.dump(dict(text="前进！前进！！不择手段地前进！！！", words=words),
              open(os.path.join(TTS_DIR, "H05.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("H05 拼好（第二声 %s）：" % SECOND, " / ".join(f'{w["text"]}@{w["start"]:.2f}' for w in words))


def audition():
    """第二声的每种做法各拼一版干声，放进 配音试听/前进/，供用户挑。"""
    _ensure_takes(False)
    d = os.path.join(REPO, "配音试听", "前进")
    os.makedirs(d, exist_ok=True)
    for k, spec in VARIANTS.items():
        sr, out, _ = compose(spec)
        _write_wav(os.path.join(d, f"第二声_{k}.wav"), sr, out, 48000)
    print("试听已写到", d)


if __name__ == "__main__":
    if "--audition" in sys.argv:
        audition()
    else:
        build(force="--force" in sys.argv)
