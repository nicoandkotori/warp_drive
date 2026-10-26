# -*- coding: utf-8 -*-
"""《曲率引擎》配乐编排：E 小调，100 BPM。所有重音来自 cues.C（与画面共用同一张卡点表）。
转场只用低频：低通涌动 + 反向低音膨胀 + 次低频下潜，不使用高频"刷"声。
输出 build/music.wav（不含人声）和 build/beats.json（kicks / accents，给画面做泛光脉冲和震动）。

编排工具（put / pads / arps / drums ...）与 projects/three_body/music.py 同一套写法；
每段的和弦进行在 PROG 里，一段内循环使用；arrange() 按段落把乐器和重击排到卡点上。"""
import json, os, time
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly
from config import BUILD, BEAT, BAR, SHIP_AI
from opusvid.dsp import SR, RNG, mtof, lp, hp, bp, svf, sine, saw, pan_st, chorus, pingpong, make_ir, reverb, env_follow
from opusvid.instruments import (pad_note, organ_note, shimmer_note, pluck, bass_note, kick_s, tom_s, taiko_s, snare_s,
                                 sub_boom, braam, deep_whoosh, reverse_swell, bell, piano, riser)
from cues import C, AI, TL, SECS, ls, charge_phase

DUR = TL["duration"]
TAIL = 7.0
N = int((DUR + TAIL) * SR)
ORDER = [s["id"] for s in TL["sections"]]
STEP = BEAT / 4

BUS_NAMES = ["pad", "organ", "shimmer", "arp", "bass", "kick", "perc", "fx", "lead", "ai", "sfx"]
B = {k: np.zeros((N, 2), dtype=np.float32) for k in BUS_NAMES}


def put(bus, t, sig, gain=1.0, pan=0.0):
    if sig.ndim == 1:
        sig = pan_st(sig, pan)
    i = int(round(t * SR))
    if i < 0:
        sig = sig[-i:]
        i = 0
    j = min(N, i + sig.shape[0])
    if j > i:
        B[bus][i:j] += (sig[: j - i] * gain).astype(np.float32)


# (和弦音, 贝斯根音)
CH = {
    "Em": ([52, 59, 64, 66, 67], 40), "Em2": ([52, 59, 62, 66, 71], 40), "E": ([52, 59, 64, 68, 71], 40),
    "Esus": ([52, 59, 64, 69, 71], 40), "C": ([48, 55, 60, 64, 67], 36), "Cmaj7": ([48, 55, 59, 64, 67], 36),
    "G": ([43, 50, 59, 62, 67], 43), "D": ([50, 57, 62, 66, 69], 38), "Dsus": ([50, 57, 62, 67, 69], 38),
    "Am": ([45, 52, 57, 60, 64], 33), "Bsus": ([47, 54, 59, 64, 66], 35), "F": ([41, 48, 57, 60, 65], 41),
}
PROG = {
    "cold": [("Em", 2), ("C", 2), ("Am", 2), ("Em", 1)],
    # 跃迁：星图 Em -> 充能 F（弗里几亚的紧张感）-> 空间扭曲 Bsus -> 巡航 Em / C
    # 开场 23 小节：银河与导航 Em C Am | 充能 F Bsus | 空间扭曲 Bsus | 巡航 Em C | 减速 G D | 抵达 Cmaj7 | 片名 G Dsus
    "warp": [("Em", 4), ("C", 2), ("Am", 3), ("F", 2), ("Bsus", 1), ("Bsus", 1), ("Em", 2), ("C", 2), ("G", 1), ("D", 1),
             ("Cmaj7", 1), ("G", 2), ("Dsus", 1)],
    "arrive": [("Em", 2), ("C", 2), ("G", 1), ("Dsus", 1)],
    "ch1": [("Em", 2), ("C", 2), ("G", 2), ("D", 2), ("Am", 2), ("F", 1), ("Bsus", 1), ("Em", 1), ("C", 1)],
    "ch2": [("C", 2), ("G", 2), ("Em", 2), ("D", 2), ("C", 2), ("G", 2), ("Am", 1), ("Bsus", 2)],
    "ch3": [("Em2", 2), ("C", 2), ("G", 2), ("D", 2), ("Em", 2), ("C", 2), ("Am", 1), ("Bsus", 1), ("Em", 1)],
    "ch4": [("Em", 2), ("C", 2), ("G", 2), ("D", 2), ("Em", 2), ("C", 2), ("Am", 2), ("D", 1), ("Bsus", 2)],
    "ch5": [("Em", 2), ("F", 2), ("Em", 2), ("C", 2), ("Am", 2), ("F", 2), ("Em", 2), ("Bsus", 2)],
    "ch6": [("Em", 2), ("C", 2), ("G", 2), ("D", 2), ("C", 2), ("Am", 1), ("Bsus", 1), ("Em", 2), ("C", 1)],
    "outro": [("C", 2), ("G", 2), ("Em", 2), ("D", 2), ("C", 1), ("D", 1), ("Em", 1), ("C", 1), ("D", 1)],
    "end": [("Cmaj7", 2), ("Esus", 1), ("E", 2)],
}


def chord_timeline():
    out = []
    for sid in ORDER:
        s = SECS[sid]
        prog = PROG[sid]
        bar, k = 0, 0
        while bar < s["bars"]:
            name, nb = prog[k % len(prog)]
            nb = min(nb, s["bars"] - bar)
            out.append((s["start"] + bar * BAR, s["start"] + (bar + nb) * BAR, name, sid))
            bar += nb
            k += 1
    return out


CHORDS = chord_timeline()


def chord_at(t):
    for c in CHORDS:
        if c[0] <= t < c[1]:
            return c
    return CHORDS[-1]


class Auto:
    """分段线性的自动化曲线（音量、滤波截止频率）。"""

    def __init__(self, default):
        self.k = []
        self.default = default

    def add(self, t, v):
        self.k.append((t, v))

    def arr(self):
        if not self.k:
            return np.full(N, self.default, dtype=np.float32)
        k = sorted(self.k)
        grid = np.arange(0, N, 64) / SR
        g = np.interp(grid, [a for a, b in k], [b for a, b in k])
        return np.repeat(g, 64)[:N].astype(np.float32)

    def at(self, t):
        if not self.k:
            return self.default
        k = sorted(self.k)
        return float(np.interp(t, [a for a, b in k], [b for a, b in k]))


VOL = {k: Auto(1.0) for k in BUS_NAMES}
PAD_CUT = Auto(900)
ARP_CUT = Auto(1200)
KICKS, ACCENTS, DUCKS = [], [], []


def kick(t, g=1.0, duck=0.0):
    put("kick", t, KICK, 0.9 * g)
    KICKS.append((round(t, 4), g))
    if duck > 0:
        DUCKS.append((t, duck))


def accent(t, kind, size=1.0):
    ACCENTS.append(dict(t=round(t, 4), kind=kind, size=size))


def tick_s(f=1050.0):
    """有音高的"嗒"（不是噪声）：计数器/时钟的节拍。"""
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    s = sine(f, n) * np.exp(-t / 0.012) + 0.4 * sine(f * 0.5, n) * np.exp(-t / 0.02)
    return lp(s, 2500) * np.minimum(1, t / 0.0008)


def warp_growl(dur, m0=28, m1=40):
    """曲率场蓄能：两个失谐锯齿的低音滑音，低通滤波随时间打开（上限约 600 Hz，不刺耳）。"""
    n = int(dur * SR)
    x = np.arange(n) / n
    f = mtof(m0 + (m1 - m0) * x ** 1.5)
    s = saw(f, n) + saw(f * 1.007, n) + 0.6 * sine(f * 0.5, n)
    s = lp(s, 90 + 520 * x ** 2, 1.4)
    return pan_st(np.tanh(s * (0.3 + 0.9 * x)) * np.minimum(1, x * 8), 0) * 0.6


def vocoder(x, carrier, n_bands=14, lo=180.0, hi=6500.0):
    """通道声码器：把人声按频带的包络"印"到合成器载波上（舰载电脑那种电子味的来源）。"""
    out = np.zeros_like(x)
    att, rel = 1 - np.exp(-1 / (0.004 * SR)), 1 - np.exp(-1 / (0.03 * SR))
    for fc in np.geomspace(lo, hi, n_bands):
        envb = env_follow(np.abs(bp(x, fc, 5.0)), att, rel)
        out += bp(carrier, fc, 5.0) * envb
    return out


def ai_voice(v):
    """舰载电脑的音色：清晰的原声为主，底下叠一层声码器（载波是 E 小调的锯齿和弦 + 一点噪声，保住辅音），
    再加 6 毫秒的梳状滤波（金属感）、轻微的电子颤动和 75 毫秒的短回声。音量统一到 RMS 0.1，
    最终响度由 main() 里 ai 总线的增益决定。"""
    n = len(v)
    t = np.arange(n) / SR
    x = lp(hp(v, 200, 0.7), 7000, 0.7)
    carrier = sum(saw(mtof(m), n) * g for m, g in ((52, 1.0), (59, 0.7), (64, 0.6), (71, 0.35)))
    carrier = carrier + 0.25 * RNG.standard_normal(n)
    voc = vocoder(x, carrier)
    voc *= np.sqrt(np.mean(x ** 2)) / (np.sqrt(np.mean(voc ** 2)) + 1e-9)
    y = 0.8 * x + 0.45 * voc
    d = int(0.006 * SR)
    y[d:] += 0.3 * y[:-d]                                   # 梳状滤波：金属腔体的共鸣
    y = y * (0.9 + 0.1 * np.sin(2 * np.pi * 70 * t))
    y = y + 0.2 * bp(y, 2600, 1.2)
    act = np.abs(y) > 1e-3
    y *= 0.1 / (np.sqrt(np.mean(y[act] ** 2)) + 1e-9)
    e = int(0.075 * SR)
    out = np.zeros(n + e)
    out[:n] += y
    out[e:] += 0.2 * lp(y, 3000)
    return pan_st(out, 0)


KICK = kick_s()
SNARE = snare_s()
TICK, TICK_LO = tick_s(), tick_s(620.0)
TOM_HI, TOM_LO, TAIKO = tom_s(140, 90), tom_s(105, 66), taiko_s()
IR_HALL = make_ir(3.6, predelay=0.03, bright=6000, dark=1100, seed=3)
IR_BIG = make_ir(7.5, predelay=0.05, bright=3800, dark=600, seed=5)


def impact(t, size=1.0, notes=(28, 40, 47, 52, 55), braam_dur=3.0, boom=True, br=True, kind="impact"):
    """重击：次低频下潜 + 低音铜管 + 太鼓。"""
    if boom:
        put("fx", t, pan_st(sub_boom(4.5), 0), 0.95 * size)
    if br:
        put("fx", t, braam(braam_dur, notes, peak=650 + 280 * size), 0.55 * size)
    put("perc", t, TAIKO, 0.7 * size)
    accent(t, kind, size)


def transition(t, size=1.0, notes=(40, 47, 52)):
    """段落转场：低频涌动 -> 强拍下潜（深邃、无高频）。"""
    w = deep_whoosh(1.9, 45, 360)
    put("fx", t - w.shape[0] / SR, w, 0.5 * size)
    rs = reverse_swell(notes, 2.4, IR_BIG)
    put("fx", t - rs.shape[0] / SR, rs, 0.5 * size)
    put("fx", t, pan_st(sub_boom(4.0), 0), 0.9 * size)
    accent(t, "transition", size)


def hit(t, size=0.5, f0=60, f1=28, bell_m=None, bell_g=0.06, kind="flash"):
    """小重音：短的次低频 + 可选的钟声点缀。"""
    put("fx", t, pan_st(sub_boom(2.5, f0, f1), 0), 0.6 * size)
    if bell_m is not None:
        put("lead", t, bell(bell_m, 3.5), bell_g)
    accent(t, kind, size)


def tom_fill(t_end, beats=1.0, g=0.6):
    n = int(beats * 4)
    for i in range(n):
        tt = t_end - (n - i) * STEP
        put("perc", tt, TOM_HI if i < n / 2 else TOM_LO, g * (0.6 + 0.4 * i / n), pan=0.4 - 0.8 * i / n)


def pads(t0, t1, gain=1.0, att=1.4, rel=2.4, octave=0):
    for c0, c1, name, sid in CHORDS:
        a, b = max(c0, t0), min(c1, t1)
        if b - a < 0.05:
            continue
        for m in CH[name][0]:
            put("pad", a, pad_note(m + octave, b - a, att, rel), gain * 0.16)


def organs(t0, t1, gain=1.0):
    for c0, c1, name, sid in CHORDS:
        a, b = max(c0, t0), min(c1, t1)
        if b - a < 0.05:
            continue
        notes, root = CH[name]
        for m in [m for m in notes if m >= 47] + [notes[-1] + 12]:
            put("organ", a, organ_note(m, b - a), gain * 0.22)
        put("organ", a, organ_note(root + 12, b - a), gain * 0.18)


def shimmers(t0, t1, gain=1.0):
    for c0, c1, name, sid in CHORDS:
        a, b = max(c0, t0), min(c1, t1)
        if b - a < 0.05:
            continue
        for m in CH[name][0][2:]:
            put("shimmer", a, shimmer_note(m + 12, b - a), gain * 0.09)


ARP_PATTERNS = {
    "up": [0, 1, 2, 3, 4, 3, 2, 1],
    "drive": [0, 2, 1, 3, 2, 4, 3, 1],
    "pulse": [0, 0, 2, 0, 1, 0, 3, 0],
    "box": [0, 2, 4, 2, 3, 1, 4, 2],
}


def chord_tones(t, lo, hi):
    notes, root = CH[chord_at(t + 1e-4)[2]]
    pcs = sorted(set(m % 12 for m in notes))
    return [m for m in range(lo, hi) if m % 12 in pcs]


def arps(t0, t1, gain=1.0, rate=4, pattern="drive", lo=64, hi=88, accent_every=4, pan_w=0.35, bus="arp"):
    step = BEAT / rate
    k0 = int(np.ceil((t0 - 1e-6) / step))
    k = k0
    pat = ARP_PATTERNS[pattern]
    while k * step < t1 - 1e-6:
        t = k * step
        tones = chord_tones(t, lo, hi)
        idx = pat[(k - k0) % len(pat)] + (((k - k0) // (len(pat) * 2)) % 2) * 2
        m = tones[min(idx, len(tones) - 1)]
        vel = 1.0 if ((k - k0) % accent_every) == 0 else 0.6
        put(bus, t, pluck(m, ARP_CUT.at(t), vel), gain * 0.22, pan=pan_w * np.sin(k * 0.9))
        k += 1


def music_box(t0, t1, gain=1.0):
    """童话段落的八音盒：高音区的钟声琶音（每拍两个音）。"""
    step = BEAT / 2
    k = int(np.ceil((t0 - 1e-6) / step))
    i = 0
    while k * step < t1 - 1e-6:
        t = k * step
        tones = chord_tones(t, 76, 96)
        m = tones[ARP_PATTERNS["box"][i % 8] % len(tones)]
        put("lead", t, bell(m, 2.5), gain * 0.045, pan=0.5 * np.sin(i * 1.3))
        k += 1
        i += 1


def bassline(t0, t1, gain=1.0, mode="sustain", cut=240):
    for c0, c1, name, sid in CHORDS:
        a, b = max(c0, t0), min(c1, t1)
        if b - a < 0.05:
            continue
        root = CH[name][1]
        if mode == "sustain":
            put("bass", a, bass_note(root, b - a, cut), gain * 0.5)
        else:
            step = BEAT / (2 if mode == "8th" else 4)
            k = int(np.ceil((a - 1e-6) / step))
            while k * step < b - 1e-6:
                tt = k * step
                oct_ = 12 if (mode == "16th" and k % 4 == 2) else 0
                put("bass", tt, bass_note(root + oct_, step * 0.9, cut, True), gain * 0.5)
                k += 1


def drums(t0, t1, pattern, g=1.0, duck=0.0, snare_g=0.0):
    PAT = {"pulse": [0, 8], "half": [0, 10], "four": [0, 4, 8, 12], "drive": [0, 3, 8, 10], "one": [0],
           "heart": [0, 3]}
    SN = {"half": [8], "four": [4, 12], "drive": [4, 12]}
    b = int(np.ceil((t0 - 1e-6) / BAR))
    while b * BAR < t1 - 1e-6:
        for s in PAT[pattern]:
            tt = b * BAR + s * STEP
            if t0 - 1e-6 <= tt < t1 - 1e-6:
                kick(tt, g, duck)
        if snare_g > 0:
            for s in SN.get(pattern, []):
                tt = b * BAR + s * STEP
                if t0 - 1e-6 <= tt < t1 - 1e-6:
                    put("perc", tt, SNARE, snare_g * 0.45)
        b += 1


def ticks(t0, t1, every=0.5, g=0.12, lo=False):
    step = BEAT * every
    k = int(np.ceil((t0 - 1e-6) / step))
    while k * step < t1 - 1e-6:
        tt = k * step
        put("perc", tt, TICK_LO if (lo or k % 2) else TICK, g * (1.0 if k % 4 == 0 else 0.65), pan=0.25 if k % 2 else -0.25)
        k += 1


def drone(t0, t1, notes=(28, 40), g=0.16):
    n = int((t1 - t0) * SR)
    tt = np.arange(n) / SR
    s = sum(sine(mtof(m), n) * (0.6 if i == 0 else 0.35) for i, m in enumerate(notes))
    env = np.minimum(1, tt / 2.0) * np.minimum(1, (t1 - t0 - tt) / 1.5)
    put("pad", t0, pan_st(s * env * g, 0), 1)


def silence(t0, t1, buses=("pad", "organ", "shimmer", "arp", "bass")):
    """t0..t1 之间把这些总线压到静音（重拍前的"吸气"）。"""
    for k in buses:
        VOL[k].add(t0 - 0.05, VOL[k].at(t0 - 0.05))
        VOL[k].add(t0, 0.0)
        VOL[k].add(t1 - 0.01, 0.0)
        VOL[k].add(t1, 1.0)


def power_down(dur):
    """减速：两个失谐锯齿从高往低滑落，低通一路收窄（结束时只剩次低频）。"""
    n = int(dur * SR)
    x = np.arange(n) / n
    f = mtof(43 - 17 * x ** 0.7)
    s_ = saw(f, n) + saw(f * 1.006, n) + 0.7 * sine(f * 0.5, n)
    s_ = lp(s_, 650 - 560 * x ** 0.6, 1.2)
    env = np.minimum(1, x * 20) * (1 - x) ** 0.6
    return pan_st(np.tanh(s_ * env * 0.9), 0) * 0.6


# 用户提供的跃迁引擎音效（9 秒）：0-2 秒渐强的蓄能声，约 2.12 秒一记巨大的低频轰响，之后 6 秒多的 40-50 Hz 低沉轰鸣。
# 它是跃迁这一下的主角：走单独的 sfx 总线（不受跃迁前"吸气"静音的影响，蓄能声要一直铺到重击；不进混响），
# 跃迁时别的乐器只留太鼓和一层减弱的"拳头"给起音加力度，铜管、次低频都不叠，免得把它盖住。
ENGINE_SFX = "跃迁引擎音效_3.wav"
ENGINE_HIT = 2.12             # 文件里轰响起音的时刻（秒），对准 C["warpjump"]
ENGINE_PRE_DB = 5.0           # 蓄能段（轰响之前）原本比轰响低 30 dB 左右，混进配乐后几乎听不见，单独抬高
ENGINE_PRE_LP = 700.0         # 蓄能段带一层 2-8 kHz 的尖啸，用户嫌刺耳：轰响之前的部分低通到这里（转场声只留低频）
ENGINE_DIP = 0.35             # 跃迁前慢动作那 0.3 秒里把蓄能声收到这么轻：先"静"下来，轰响（用户要的那记强脉冲）才冲得出来


def read_sfx(path):
    """读入用户提供的音效：转成立体声、浮点、重采样到 SR。"""
    sr, x = wavfile.read(path)
    x = x.astype(np.float64) / (32768.0 if x.dtype == np.int16 else 1.0)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    g = np.gcd(SR, sr)
    return resample_poly(x, SR // g, sr // g, axis=0)


def engine_sfx():
    x = read_sfx(ENGINE_SFX)
    # 蓄能段：低通到 ENGINE_PRE_LP、抬高 ENGINE_PRE_DB；轰响前 0.45 -> 0.12 秒收到 ENGINE_DIP（和画面的慢动作、
    # 配乐的静音同一段）；轰响起音前 10 毫秒交还原声，轰响和后面的轰鸣本身不动
    tr = np.arange(len(x)) / SR - ENGINE_HIT
    soft = np.stack([lp(lp(x[:, ch], ENGINE_PRE_LP, 0.7), ENGINE_PRE_LP, 0.7) for ch in range(2)], 1)
    w = np.clip((tr + 0.06) / 0.05, 0.0, 1.0)[:, None]        # 0 = 用滤过的蓄能声，1 = 原声
    x = soft * (1 - w) + x * w
    lift = 10 ** (ENGINE_PRE_DB / 20)
    gain = np.interp(tr, [-0.45, -0.12, -0.05, -0.01], [lift, ENGINE_DIP, ENGINE_DIP, 1.0])
    return x * gain[:, None]


# 用户提供的跃迁结束音效（6.5 秒）：0-3.4 秒越来越紧的低频轰鸣，3.39-3.51 秒短暂收住，约 3.53 秒一记很重的"咚"，
# 之后 2 秒多的次低频余震。用户要这一记"咚"在跃迁结束（急停）的瞬间：对准 C["dropout"]，蓄势段正好从镜头绕向船头时铺进来。
# 和跃迁的引擎音效一样走 sfx 总线、是这一下的主角，急停处别的乐器只补太鼓和一层减弱的"拳头"。
ARRIVE_SFX = "跃迁结束音效.wav"
ARRIVE_HIT = 3.53             # 文件里"咚"起音的时刻（秒）
ARRIVE_PRE_LP = 700.0         # 蓄势段带一层 2 kHz 以上的嘶声：和引擎音效一样低通掉（转场声只留低频）
ARRIVE_PRE_DB = -5.0          # 蓄势段原样放太响（急停前 1 秒混音已到 -9 dB），"咚"只比它高 1 dB、冲不出来：压低这么多
ARRIVE_GAIN = 0.65            # 整体再收一点，跃迁仍是开场最响的一下


def arrive_sfx():
    x = read_sfx(ARRIVE_SFX)
    tr = np.arange(len(x)) / SR - ARRIVE_HIT
    soft = np.stack([lp(lp(x[:, ch], ARRIVE_PRE_LP, 0.7), ARRIVE_PRE_LP, 0.7) for ch in range(2)], 1)
    w = np.clip((tr + 0.06) / 0.05, 0.0, 1.0)[:, None]        # 0 = 用滤过、压低的蓄势声，1 = 原声；"咚"和余震本身不动
    return (soft * 10 ** (ARRIVE_PRE_DB / 20) * (1 - w) + x * w) * ARRIVE_GAIN


def charge_spinup(t0, t1):
    """曲率环充能（t0 -> t1）：越来越快、越来越响。节拍按 cues.charge_phase，与画面上环槽的搏动、卷进环的微粒同拍。三层：
      · 脉冲重击：每个整数相位一下"咚"（正弦从 160 Hz 滑到 55 Hz）加一点 300-600 Hz 的"叩"。笔记本扬声器放不出
        150 Hz 以下，只有低频的话脉冲听起来很小（旧版 74% 能量在 150 Hz 以下，用户反映响度太低）。
        脉冲越密每下越短，最后连成一片滚奏。
      · 嗡鸣：锯齿叠音，基频 55 -> 110 Hz，共振低通从 350 Hz 打开到 1.4 kHz，跟着脉冲一下一下涌。
      · 涡轮上行音：正弦从 180 Hz 升到 620 Hz（用户偏好：上行音压在 700 Hz 以下，不要尖）。
    充满之后保持最快的脉冲、音量先收一点；C["distort"]（空间扭曲）起越压越紧：音量抬回来并超过充满时，
    嗡鸣再升 5 个半音、涡轮音升到约 690 Hz，一直推到跃迁前的吸气。"""
    n = int((t1 - t0) * SR)
    tt = t0 + np.arange(n) / SR
    u = np.clip((tt - C["charge_on"]) / (C["charge_full"] - C["charge_on"]), 0.0, 1.0)
    ph = charge_phase(tt)
    pulse = (0.5 + 0.5 * np.cos(2 * np.pi * ph)) ** 4
    rise = np.clip((tt - C["distort"]) / (C["freeze"] - C["distort"]), 0.0, 1.0) ** 1.5
    f0 = mtof(33 + 12 * u ** 1.2 + 5 * rise)
    hum = saw(f0, n) + saw(f0 * 1.006, n) + 0.5 * saw(f0 * 2.003, n)
    hum = lp(hum, 350 + 1050 * u ** 1.5, 2.0) * (0.4 + 0.6 * pulse)
    fw = 180.0 * (620.0 / 180.0) ** (u ** 1.1) * 2 ** (0.15 * rise)
    whine = (sine(fw, n) + 0.3 * sine(fw * 2.0, n)) * u ** 1.5
    thump = np.zeros(n)
    rate = np.gradient(ph) * SR
    for k in range(int(np.ceil(ph[0])), int(np.floor(ph[-1])) + 1):
        i = int(np.searchsorted(ph, k))
        dec = min(0.09, 0.8 / max(rate[i], 1.0))
        x = np.arange(min(int(dec * 6 * SR), n - i)) / SR
        body = np.sin(2 * np.pi * np.cumsum(55.0 + 105.0 * np.exp(-x / 0.025)) / SR) * np.exp(-x / dec)
        knock = bp(RNG.standard_normal(len(x)), 420.0, 1.8) * np.exp(-x / 0.012)
        thump[i:i + len(x)] += (body + 0.9 * knock) * (0.4 + 0.6 * u[i])
    full = (tt >= C["charge_full"]).astype(np.float64)
    env = ((0.35 + 0.65 * u ** 1.2) * (1 - 0.25 * full + 0.65 * rise) * np.minimum(1, (tt - t0) / 0.3)
           * np.clip((t1 - tt) / 0.05, 0.0, 1.0))
    return pan_st(np.tanh((0.8 * hum + 0.35 * whine + thump) * env * 1.4), 0) * 0.7


def slam(dur=1.2):
    """重击的"拳头"：音高从 180 Hz 猛降到 38 Hz 的过载底鼓 + 一小团低通噪声（起音的冲击感，最高约 900 Hz）。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    body = sine(38.0 + 142.0 * np.exp(-t / 0.03), n) * np.exp(-t / 0.35)
    knock = lp(RNG.standard_normal(n), 900.0, 0.7) * np.exp(-t / 0.025)
    return pan_st(np.tanh(2.5 * (body + 0.6 * knock)), 0) * 0.8


def suck(dur):
    """重击前的"吸"：一记次低频轰鸣倒过来放，结尾正好顶到重击上（只有低频）。"""
    b = sub_boom(dur + 0.3, 60, 26)[: int(dur * SR)][::-1]
    return pan_st(lp(b, 300.0, 0.7) * np.linspace(0.0, 1.0, len(b)) ** 1.5, 0)


def arrange():
    S, c = SECS, C
    # ================= 开场（24 小节）
    s = S["warp"]
    t0, t1 = s["start"], s["end"]
    # 银河：浮现时一记低沉的重击，之后铺底和闪光铺底慢慢涌上来；"我们在这里"一声钟；
    # 缩放潜入太阳邻域时一道低频涌动 + 反向膨胀，到达邻域时一记重击
    impact(t0, 0.95, notes=(28, 40, 47, 52), braam_dur=2.5)
    drone(t0, c["charge"], (28, 35, 40), 0.14)
    pads(t0, c["charge"], 0.75)
    PAD_CUT.add(t0, 500); PAD_CUT.add(c["sun_mark"], 900); PAD_CUT.add(c["local"], 700); PAD_CUT.add(c["charge"], 1100)
    shimmers(t0 + BEAT, c["zoom"] + BAR, 1.1)
    hit(c["sun_mark"], 0.5, 60, 30, bell_m=79)
    put("fx", c["zoom"], deep_whoosh(c["local"] - c["zoom"], 40, 360), 0.6)
    rs = reverse_swell((40, 47, 52), 1.0, IR_BIG)
    put("fx", c["local"] - rs.shape[0] / SR, rs, 0.4)
    impact(c["local"], 0.75, notes=(28, 40, 47), braam_dur=1.4)
    # 导航：光标每停一颗候选星一声提示音；选中、规划航线、锁定各一记重音
    ticks(c["local"], c["switch"], 0.5, 0.06, lo=True)
    for k, tt in enumerate(c["cands"]):
        put("lead", tt, bell((71, 74, 76)[k], 2.0), 0.05)
        put("fx", tt, pan_st(sub_boom(1.2, 70, 40), 0), 0.2)
        accent(tt, "flash", 0.25)
    impact(c["select"], 0.6, notes=(28, 40, 47), braam_dur=1.0, br=False)
    put("lead", c["select"], bell(83, 3.0), 0.07)
    w = deep_whoosh(c["lock"] - c["switch"], 40, 260)               # 规划航线：镜头拉开看到太阳和半人马座 α
    put("fx", c["switch"], w, 0.45)
    impact(c["lock"], 0.85, notes=(28, 40, 47), braam_dur=1.4)
    put("lead", c["lock"], bell(88, 3.0), 0.07)
    ARP_CUT.add(c["lock"], 900); ARP_CUT.add(c["engage"], 1600)
    arps(c["lock"], c["engage"], 0.55, 4, "pulse", 59, 83)
    ticks(c["lock"], c["engage"], 0.25, 0.07)
    hit(c["eta"], 0.45, bell_m=83)
    put("fx", c["engage"] - 0.6, reverse_swell((40, 47, 52), 0.6, IR_BIG), 0.4)
    impact(c["engage"], 0.8, br=False)
    # 星图收起、镜头从舰桥拉开：一道低沉的下行音 + 拉开时的低频涌动
    put("fx", c["collapse"], power_down(c["handoff"] - c["collapse"] + 0.4), 0.35)
    w = deep_whoosh(c["charge"] + 1.8 - c["handoff"], 38, 240)
    put("fx", c["handoff"], w, 0.4)

    # 充能（3 小节）：一串越来越快越来越强的脉冲（与画面上环槽的搏动同拍），到跃迁前的慢动作为止；
    # 底下一条低音蓄能长音一路升到跃迁；曲率环 32 格每亮一格一声低沉的"嗒"，音高随充能升高
    put("fx", c["charge_on"], charge_spinup(c["charge_on"], c["freeze"]), 2.1)
    put("fx", c["charge"], warp_growl(c["warpjump"] - c["charge"], 24, 40), 0.5)
    pads(c["charge"], c["distort"], 0.7)
    PAD_CUT.add(c["charge"], 700); PAD_CUT.add(c["charge_full"], 1300)
    for k in range(32):
        tt = c["charge_on"] + (c["charge_full"] - c["charge_on"]) * k / 32
        put("perc", tt, tick_s(260.0 + 12.0 * k), 0.07 + 0.003 * k, pan=0.3 if k % 2 else -0.3)
    drums(c["charge"] + BAR, c["charge_full"], "heart", 0.6, duck=0.3)
    bassline(c["charge"], c["distort"], 0.55, "8th", 200)
    put("fx", c["charge_full"] - 1.0, reverse_swell((40, 47, 52, 59), 1.0, IR_BIG), 0.5)
    impact(c["charge_full"], 0.9, notes=(28, 40, 47, 52), braam_dur=1.6)
    put("lead", c["charge_full"], bell(83, 3.5), 0.07)

    # 空间扭曲（1 小节，取代倒数）：曲率场成形的一记低沉重击，随后一道低频涌动一路压到跃迁前的吸气
    # （涌动的上行压在 300 Hz 以下），反向膨胀接进跃迁
    drone(c["charge_full"], c["warpjump"], (28, 35, 40, 47), 0.16)
    impact(c["distort"], 0.9, notes=(28, 40, 47), braam_dur=2.0)
    put("fx", c["distort"], deep_whoosh(c["freeze"] - c["distort"], 40, 300), 1.2)
    put("fx", c["warpjump"] - 1.2, reverse_swell((40, 47, 52, 59), 1.2, IR_BIG), 0.6)
    # 慢动作窗口：其余声音全部抽空，只剩一记倒放的次低频"吸"进重击
    silence(c["freeze"], c["warpjump"], ("pad", "organ", "shimmer", "arp", "bass", "fx"))
    put("perc", c["freeze"], suck(c["warpjump"] - c["freeze"]), 0.5)

    # 跃迁分镜：主角是用户的引擎音效——蓄能声从约 2 秒前铺进来，轰响对准跃迁，长长的低频轰鸣一直拖到巡航。
    # 只在起音处补一层减弱的"拳头"和三连太鼓（给画面的弹射一个清楚的起点），铜管、次低频都不叠；
    # 冲击波扫过镜头时一下轻的太鼓和次低频；镜头追上去时一道低频涌动正好收在 C["catch"]，再一记重击，鼓、琶音和低音进来
    put("sfx", c["warpjump"] - ENGINE_HIT, engine_sfx(), 1.0)
    impact(c["warpjump"], 1.0, boom=False, br=False, kind="transition")
    put("fx", c["warpjump"], slam(), 0.45)
    for dl, g, pn in ((0.035, 0.6, -0.3), (0.07, 0.5, 0.3)):          # 主太鼓（impact 里）之后再补两下，成一串
        put("perc", c["warpjump"] + dl, TAIKO, g, pan=pn)
    put("fx", c["shockhit"], pan_st(sub_boom(4.0, 58, 20, drive=2.4), 0), 0.35)
    put("perc", c["shockhit"], TAIKO, 0.45)
    accent(c["shockhit"], "impact", 0.9)
    drone(c["warpjump"], c["catch"] + 0.5, (28, 35, 40), 0.07)
    put("fx", c["chase"], deep_whoosh(c["catch"] - c["chase"], 40, 520), 0.8)
    rs = reverse_swell((40, 47, 52, 59), 1.2, IR_BIG)
    put("fx", c["catch"] - rs.shape[0] / SR, rs, 0.5)
    impact(c["catch"], 1.15, notes=(28, 40, 47, 52, 55), braam_dur=2.5)
    pads(c["warpjump"], c["arrive"], 0.85)
    PAD_CUT.add(c["warpjump"], 1300); PAD_CUT.add(c["approach"], 700); PAD_CUT.add(c["arrive"], 1000)
    # 巡航：鼓、琶音、16 分音符低音在切到目的地（C["approach"]）时一起停住
    ARP_CUT.add(c["catch"], 1600); ARP_CUT.add(c["approach"] - BEAT, 3000)
    arps(c["catch"], c["approach"], 0.9, 4, "drive", 64, 88)
    bassline(c["catch"], c["approach"], 0.95, "16th", 320)
    drums(c["catch"], c["approach"], "four", 1.0, duck=0.7, snare_g=0.55)
    # 穿过星云：铺底和闪光铺底涌上来
    shimmers(c["nebula"] - BAR, c["nebula"] + 2 * BAR, 1.4)
    put("fx", c["nebula"] - 1.4, reverse_swell((43, 47, 52, 59), 1.4, IR_BIG), 0.45)
    hit(c["nebula"], 0.6, 55, 28, bell_m=86)
    # 恒星一颗颗擦身而过：每颗一道低频涌动收在最近点，再一记次低频（声像跟着恒星在左/右）
    for k, tt in enumerate(c["flybys"]):
        side = -0.6 if k % 2 == 0 else 0.6
        w = deep_whoosh(1.2, 40, 320)
        put("fx", tt - w.shape[0] / SR, w * np.array([1 - side, 1 + side]) * 0.5, 0.65)
        put("fx", tt, pan_st(sub_boom(2.5, 60, 26), side * 0.5), 0.55)
        accent(tt, "impact", 0.55)
    # 抵达：最后一冲时鼓点停下，只剩低音长音；蓄势、急停那一记"咚"和之后的余震都交给用户的跃迁结束音效
    # （它自己带蓄势和起音前的一下收住，原来叠的低频涌动、反向膨胀、吸气、铜管、次低频、轰鸣都撤掉，免得把它盖住）。
    # 急停只补太鼓和一层减弱的"拳头"给起音加力度；冲击波扫过镜头（C["arr_hit"]）时一下轻的太鼓；镜头绕行时鼓点滚进抵达的大和弦
    drone(c["approach"], c["arrive"] + 0.5, (28, 35, 40), 0.18)
    silence(c["dropout"] - 0.15, c["dropout"], ("pad", "organ", "shimmer", "arp", "bass", "fx"))
    put("sfx", c["dropout"] - ARRIVE_HIT, arrive_sfx(), 1.0)
    impact(c["dropout"], 1.0, boom=False, br=False, kind="transition")
    put("fx", c["dropout"], slam(), 0.45)
    put("perc", c["arr_hit"], TAIKO, 0.4)
    tom_fill(c["arrive"], 1.0, 0.45)

    # 抵达：明亮的大和弦（AI 报"已抵达"时配乐让开）
    impact(c["arrive"], 1.1, notes=(24, 36, 43, 48, 52), braam_dur=3.0, br=True)
    organs(c["arrive"], t1 + 0.5, 0.6)
    pads(c["arrive"], t1, 1.0)
    shimmers(c["arrive"], t1, 1.2)
    bassline(c["arrive"], t1, 0.65, "sustain", 160)
    PAD_CUT.add(c["title"], 1500); PAD_CUT.add(t1, 900)
    # 片名
    impact(c["title"], 1.45, notes=(24, 36, 43, 48, 52, 55), braam_dur=5.0, kind="transition")
    put("perc", c["title"] + BAR, TAIKO, 0.5)
    for i, m in enumerate([67, 74, 79, 83, 81]):
        put("lead", c["title"] + BEAT * (2 + i * 1.5), piano(m, 3.0), 0.3)

    # ================= 冷开场：飞船 -> 七万年 vs 四百年
    s = S["cold"]
    t0, t1 = s["start"], s["end"]
    transition(t0, 0.6)
    drone(t0, t1 + 0.5, (28, 40), 0.15)
    pads(t0 + 0.5, c["voyager"], 0.6, att=2.5)
    PAD_CUT.add(t0, 400); PAD_CUT.add(c["voyager"], 800)
    for b in range(1, 4):                                      # 心跳
        tb = t0 + b * BAR
        for off, gg in ((0, 1.0), (0.36, 0.6)):
            put("kick", tb + off, kick_s(95, 40, 0.3, 0.0), 0.4 * gg)
            KICKS.append((round(tb + off, 4), 0.3 * gg))
    hit(c["target"], 0.5, bell_m=76, bell_g=0.07)
    impact(c["dist"], 0.6, br=False)
    # 旅行者一号：计数器的滴答 + 低音脉冲；三体舰队：琥珀色的低音铜管
    ticks(c["voyager"], c["fleet"] - 0.3, 0.25, 0.09)
    pads(c["voyager"], t1, 0.7)
    ARP_CUT.add(c["voyager"], 900)
    arps(c["voyager"], t1 - BEAT, 0.55, 2, "pulse", 59, 83)
    drums(c["voyager"], t1 - BEAT, "pulse", 0.65, duck=0.3)
    hit(c["fleet"] - 1.3, 0.6, bell_m=83)
    put("fx", c["fleet"], braam(2.5, (28, 40, 47), peak=650), 0.35)
    accent(c["fleet"], "impact", 0.5)
    ticks(c["fleet"], t1 - 0.3, 0.5, 0.09, lo=True)

    # ================= 回到半人马座 α：而它只需要几个月 -> 曲率驱动 -> 爱因斯坦方程
    s = S["arrive"]
    t0, t1 = s["start"], s["end"]
    transition(t0, 0.9)
    organs(t0 + BAR, t1, 0.75)
    pads(t0, t1, 0.9)
    shimmers(t0, t1, 1.2)
    bassline(t0, t1, 0.6, "sustain", 180)
    PAD_CUT.add(t0, 1200); PAD_CUT.add(c["name"], 1700)
    drums(t0 + BAR, t1 - BEAT, "pulse", 0.7, duck=0.4)
    impact(c["months"], 0.85, br=False)
    put("lead", c["months"], bell(83, 3.0), 0.07)
    impact(c["name"], 0.9, notes=(24, 36, 43, 48), braam_dur=2.5)
    hit(c["einstein"], 0.5, bell_m=79)
    impact(c["eq"], 0.8, br=False)
    for k, m in enumerate((67, 71, 74, 79)):
        put("lead", c["eq"] + k * BEAT / 2, bell(m, 3.0), 0.06)
    tom_fill(t1, 1.0, 0.5)

    # ================= 飞船 AI 语音（英文），配乐在它说话时让开（config.SHIP_AI 关掉时是无人声版）
    for L in AI if SHIP_AI else ():
        sr_, v = wavfile.read(os.path.join(BUILD, "ai", L["id"] + ".wav"))
        put("ai", L["place"], ai_voice(v.astype(np.float64) / 32768.0), 1.0)

    # ================= 第一章：光速之墙
    s = S["ch1"]
    t0, t1 = s["start"], s["end"]
    transition(t0, 1.0)
    pads(t0, c["wall"], 0.75)
    PAD_CUT.add(t0, 700); PAD_CUT.add(c["climit"], 1400)
    ARP_CUT.add(c["why"], 700); ARP_CUT.add(c["climit"], 2600)
    arps(c["why"], c["curve"] - BEAT, 0.75, 4, "up", 64, 88)        # 越来越快：滤波一路打开
    bassline(c["why"], c["curve"], 0.7, "8th", 260)
    drums(c["why"], c["law"], "pulse", 0.7, duck=0.4)
    drums(c["law"], c["curve"] - BEAT, "four", 0.9, duck=0.6, snare_g=0.4)
    impact(c["law"], 0.9, notes=(28, 40, 47, 52))
    impact(c["climit"], 1.0, notes=(28, 40, 46, 52), braam_dur=2.0)
    ticks(c["curve"], c["inf"], 0.5, 0.1)
    drums(c["curve"], c["inf"] - BEAT, "half", 0.8, duck=0.5, snare_g=0.3)
    hit(c["harder"], 0.5, bell_m=83)
    put("fx", c["inf"] - 2.4, riser(2.4, (40, 46, 52, 58), 900), 0.7)
    impact(c["inf"], 1.15, notes=(28, 40, 46, 52, 55), braam_dur=2.5)
    silence(c["wall"] - 0.2, c["wall"])
    impact(c["wall"], 1.4, notes=(24, 36, 42, 48, 51), braam_dur=4.0)
    drone(c["wall"], c["loophole"] + 1.0, (28, 34, 40), 0.16)
    put("fx", c["trapped"], pan_st(sub_boom(3.0, 50, 25), 0), 0.5)
    accent(c["trapped"], "impact", 0.5)
    # 缝隙：神秘的钟声，裂开时一道反向膨胀
    pads(c["loophole"], t1, 0.7)
    PAD_CUT.add(c["loophole"], 700); PAD_CUT.add(c["space_itself"], 2000)
    for k, m in enumerate((71, 74, 79, 83)):
        put("lead", c["loophole"] + 0.3 + k * BEAT, bell(m, 4.0), 0.05)
    put("fx", c["gap"] - 1.4, reverse_swell((40, 47, 52, 59), 1.4, IR_BIG), 0.5)
    impact(c["gap"], 0.8, br=False)
    shimmers(c["gap"], t1, 1.3)
    ARP_CUT.add(ls("A06"), 1400)
    arps(ls("A06"), t1 - BEAT, 0.7, 4, "drive", 64, 88)
    bassline(ls("A06"), t1, 0.7, "8th", 240)
    drums(ls("A06"), c["space_itself"] - BEAT, "pulse", 0.8, duck=0.4)
    hit(c["motion"], 0.5)
    put("fx", c["space_itself"] - BAR, riser(BAR, (40, 47, 52, 59), 1000), 0.7)
    silence(c["space_itself"] - 0.2, c["space_itself"])
    impact(c["space_itself"], 1.3, notes=(24, 36, 43, 48, 52), braam_dur=3.0)
    drums(c["space_itself"], t1 - BEAT, "four", 1.0, duck=0.7, snare_g=0.5)
    tom_fill(t1, 1.0, 0.5)

    # ================= 第二章：空间本身
    s = S["ch2"]
    t0, t1 = s["start"], s["end"]
    transition(t0, 1.0, (36, 43, 48))
    pads(t0, c["expand"], 0.8)
    shimmers(t0, c["mass"], 1.1)
    PAD_CUT.add(t0, 1000); PAD_CUT.add(c["stage"], 1600)
    ARP_CUT.add(t0, 1500)
    arps(t0 + BAR, c["mass"] - BEAT, 0.6, 2, "up", 64, 88)
    hit(c["bend"], 0.5, bell_m=84)
    hit(c["stretch"], 0.5, bell_m=86)
    put("fx", c["mass"] - 1.2, reverse_swell((36, 43, 48), 1.2, IR_BIG), 0.4)
    put("fx", c["mass"], pan_st(sub_boom(4.0, 45, 22), 0), 0.7)
    accent(c["mass"], "impact", 0.6)
    impact(c["dent"], 0.9, notes=(24, 36, 43, 48), braam_dur=2.0)
    hit(c["gravity"], 0.5, bell_m=79)
    # 宇宙膨胀：鼓组进来，越来越宽
    impact(c["expand"], 0.9, br=False)
    pads(c["expand"], t1, 0.85)
    organs(c["expand"], c["ride_q"], 0.55)
    PAD_CUT.add(c["expand"], 1200); PAD_CUT.add(c["between"], 2000)
    ARP_CUT.add(c["expand"], 1500); ARP_CUT.add(c["between"], 2800)
    arps(c["expand"], c["ride_q"] - BEAT, 0.8, 4, "drive", 64, 88)
    bassline(c["expand"], c["ride_q"], 0.8, "8th", 260)
    drums(c["expand"] + BEAT, c["galaxies"], "half", 0.85, duck=0.5, snare_g=0.3)
    drums(c["galaxies"], c["notviol"] - BEAT, "four", 1.0, duck=0.7, snare_g=0.5)
    hit(c["galaxies"], 0.5, bell_m=83)
    put("fx", c["ftl"] - 1.6, riser(1.6, (40, 47, 52, 59), 900), 0.6)
    impact(c["ftl"], 1.1, notes=(28, 40, 47, 52, 55))
    drums(c["notviol"], c["ride_q"] - BEAT, "drive", 0.9, duck=0.6, snare_g=0.4)
    put("fx", c["between"] - 1.2, reverse_swell((40, 47, 52), 1.2, IR_BIG), 0.4)
    impact(c["between"], 0.8, br=False)
    # 顺风车？
    silence(c["ride_q"] - 0.15, c["ride_q"] + 0.01, ("arp", "bass", "organ"))
    pads(c["ride_q"], t1, 0.6)
    put("lead", c["ride_q"] + 0.1, piano(71, 2.0), 0.3)
    put("lead", c["ride"], bell(83, 4.0), 0.08)
    accent(c["ride"], "flash", 0.6)
    put("fx", t1 - BAR, riser(BAR, (40, 47, 52, 59), 800), 0.6)

    # ================= 第三章：肥皂船（童话：八音盒 + 柔和的拨弦）
    s = S["ch3"]
    t0, t1 = s["start"], s["end"]
    transition(t0, 0.8, (40, 47, 52))
    VOL["pad"].add(t0, 1.0)
    pads(t0, c["decode"], 0.7, att=2.0)
    shimmers(t0, c["boat"], 1.2)
    PAD_CUT.add(t0, 700); PAD_CUT.add(c["boat"], 1100)
    music_box(t0 + BAR * 0.5, c["sail"], 1.0)
    hit(c["fairy"], 0.5, bell_m=88, bell_g=0.08)
    hit(c["boat"], 0.4)
    for k, m in enumerate((76, 79, 83, 88, 91)):          # 抹肥皂：一串上行的亮晶晶
        put("lead", c["soap"] + k * BEAT / 4, bell(m, 2.5), 0.05)
    accent(c["soap"], "flash", 0.5)
    impact(c["sail"], 0.7, br=False)
    ARP_CUT.add(c["sail"], 1300); ARP_CUT.add(c["decode"], 2000)
    arps(c["sail"], c["decode"] - BEAT, 0.65, 2, "up", 64, 88)
    bassline(c["sail"], c["decode"], 0.6, "8th", 220)
    drums(c["sail"], c["decode"] - BEAT, "half", 0.7, duck=0.4, snare_g=0.25)
    hit(c["tension"], 0.5, 55, 28)
    hit(c["front_water"], 0.6, 70, 30, bell_m=83)
    impact(c["pull"], 0.85, notes=(28, 40, 47, 52), braam_dur=1.8)
    # 解码：水面变成时空膜
    transition(c["decode"], 0.6)
    pads(c["decode"], t1, 0.85)
    organs(c["decode"], c["curvature"] - BEAT, 0.6)
    PAD_CUT.add(c["decode"], 900); PAD_CUT.add(c["curvature"], 1800)
    ARP_CUT.add(c["decode"], 1200); ARP_CUT.add(c["curvature"], 2600)
    arps(c["decode"] + BEAT, c["curvature"] - BEAT, 0.75, 4, "drive", 64, 88)
    bassline(c["decode"], c["curvature"], 0.75, "8th", 240)
    drums(c["decode"] + BAR, c["pullship"], "half", 0.85, duck=0.5, snare_g=0.35)
    put("fx", c["iron"] - 0.6, deep_whoosh(0.6, 45, 300), 0.5)
    impact(c["iron"], 0.8, br=False)
    impact(c["curved"], 0.9, notes=(28, 40, 47, 52), braam_dur=1.5)
    drums(c["pullship"], c["curvature"] - BEAT, "four", 1.0, duck=0.7, snare_g=0.5)
    put("fx", c["curvature"] - 2.0, riser(2.0, (40, 47, 52, 59), 1000), 0.8)
    tom_fill(c["curvature"], 1.0, 0.6)
    silence(c["curvature"] - 0.2, c["curvature"])
    impact(c["curvature"], 1.4, notes=(28, 40, 47, 52, 55, 59), braam_dur=3.0)
    shimmers(c["curvature"], t1, 1.2)
    drone(c["curvature"], t1 + 0.5, (28, 40), 0.15)

    # ================= 第四章：曲率泡
    s = S["ch4"]
    t0, t1 = s["start"], s["end"]
    transition(t0, 1.0)
    pads(t0, c["inside"], 0.8)
    PAD_CUT.add(t0, 800); PAD_CUT.add(c["year"], 1300)
    ARP_CUT.add(t0, 1000)
    arps(c["coincide"], c["year"] - BEAT, 0.55, 2, "pulse", 59, 83)
    drums(c["coincide"], c["year"] - BEAT, "pulse", 0.6, duck=0.3)
    impact(c["year"], 0.9, notes=(28, 40, 47, 52))
    ticks(c["year"], c["contract"], 0.5, 0.09)
    hit(c["alc"], 0.5, bell_m=79)
    hit(c["solution"], 0.7, 65, 30, bell_m=83, bell_g=0.08)
    organs(c["contract"] - BEAT, c["inside"], 0.6)
    impact(c["contract"], 1.0, notes=(28, 40, 47), braam_dur=1.5)        # 收缩：低
    impact(c["expand2"], 1.0, notes=(31, 43, 50, 55), braam_dur=1.5)     # 膨胀：高一点
    shimmers(c["bubble"], c["inside"], 1.2)
    hit(c["bubble"], 0.6, bell_m=86)
    ARP_CUT.add(c["contract"], 1400); ARP_CUT.add(c["inside"], 2800)
    arps(c["contract"], c["inside"] - BEAT, 0.8, 4, "drive", 64, 88)
    bassline(c["contract"], c["inside"], 0.85, "16th", 300)
    drums(c["contract"], c["surf"] - BEAT, "half", 0.9, duck=0.6, snare_g=0.4)
    impact(c["surf"], 1.0, br=False)
    drums(c["surf"], c["inside"] - BEAT, "four", 1.0, duck=0.7, snare_g=0.55)
    put("fx", c["pushed"] - 1.0, reverse_swell((40, 47, 52), 1.0, IR_BIG), 0.4)
    hit(c["pushed"], 0.6)
    tom_fill(c["inside"], 1.0, 0.5)
    # 泡内：一切安静下来，只剩钟表
    silence(c["inside"] - 0.15, c["inside"] + 0.01, ("arp", "bass", "organ"))
    pads(c["inside"], t1, 0.7)
    PAD_CUT.add(c["inside"], 900)
    ticks(c["inside"], c["ftl2"] - BAR, 0.5, 0.12)
    hit(c["accel"], 0.6, bell_m=76)
    for k in range(int((c["ftl2"] - BAR - c["clock"]) / BEAT)):
        put("lead", c["clock"] + k * BEAT, bell(88, 1.5), 0.025, pan=0.4 if k % 2 else -0.4)
    put("fx", c["ftl2"] - BAR * 1.5, riser(BAR * 1.5, (40, 47, 52, 59), 1100), 0.8)
    ARP_CUT.add(ls("E06"), 1500); ARP_CUT.add(c["ftl2"], 3000)
    arps(ls("E06"), t1 - BEAT, 0.85, 4, "drive", 64, 88)
    bassline(ls("E06"), t1, 0.85, "16th", 320)
    tom_fill(c["ftl2"], 1.0, 0.6)
    silence(c["ftl2"] - 0.2, c["ftl2"])
    impact(c["ftl2"], 1.45, notes=(28, 40, 47, 52, 55, 59), braam_dur=3.0)
    drums(c["ftl2"], t1 - BEAT, "four", 1.0, duck=0.7, snare_g=0.6)
    shimmers(c["ftl2"], t1, 1.2)

    # ================= 第五章：代价（暗：弗里几亚的 F）
    s = S["ch5"]
    t0, t1 = s["start"], s["end"]
    transition(t0, 1.0, (40, 41, 47))
    pads(t0, c["est"], 0.8)
    PAD_CUT.add(t0, 600); PAD_CUT.add(c["neg"], 1000)
    drone(t0, c["est"], (28, 29, 40), 0.14)
    impact(c["ticket"], 0.9, notes=(28, 40, 46), braam_dur=1.8)
    drums(ls("F02"), c["est"] - BEAT, "heart", 0.6, duck=0.3)
    put("fx", c["neg"] - 1.6, reverse_swell((40, 41, 47), 1.6, IR_BIG), 0.5)
    impact(c["neg"], 1.2, notes=(24, 29, 36, 41, 48), braam_dur=3.0)
    hit(c["vacuum"], 0.6, 50, 22)
    # 数量级：一下比一下狠，然后一级级落下来
    pads(c["est"], c["casimir_q"], 0.8)
    ARP_CUT.add(c["est"], 1000); ARP_CUT.add(c["bigger_u"], 2400)
    arps(c["est"], c["casimir_q"] - BEAT, 0.7, 4, "pulse", 59, 83)
    bassline(c["est"], c["casimir_q"], 0.8, "8th", 240)
    drums(c["est"], c["bigger_u"] - BEAT, "half", 0.85, duck=0.5, snare_g=0.35)
    impact(c["universe"], 0.9, notes=(28, 40, 47))
    put("fx", c["bigger_u"] - 1.2, riser(1.2, (40, 46, 52), 900), 0.6)
    silence(c["bigger_u"] - 0.15, c["bigger_u"])
    impact(c["bigger_u"], 1.4, notes=(24, 29, 36, 41, 48), braam_dur=3.0)
    drums(c["bigger_u"], c["casimir_q"] - BEAT, "four", 0.95, duck=0.6, snare_g=0.45)
    impact(c["suns"], 0.9, notes=(26, 38, 45), braam_dur=1.5)
    impact(c["probe"], 0.75, notes=(23, 35, 42), braam_dur=1.5)
    # 卡西米尔：安静，量子涨落的细碎钟声
    silence(c["casimir_q"] - 0.15, c["casimir_q"] + 0.01, ("arp", "bass"))
    pads(c["casimir_q"], c["horizon"], 0.7)
    shimmers(c["casimir_q"], c["horizon"], 1.3)
    PAD_CUT.add(c["casimir_q"], 900)
    music_box(c["casimir_q"] + BEAT, c["horizon"] - BEAT, 0.8)
    hit(c["casimir"], 0.6, bell_m=83)
    impact(c["exists"], 0.85, br=False)
    hit(c["tiny"], 0.4, bell_m=95, bell_g=0.04)
    # 因果视界 -> 关不掉 -> 高能粒子
    pads(c["horizon"], t1, 0.8)
    PAD_CUT.add(c["horizon"], 900); PAD_CUT.add(c["stop"], 1800)
    ARP_CUT.add(c["horizon"], 1200); ARP_CUT.add(c["stop"], 3000)
    arps(c["horizon"], c["stop"] - BEAT, 0.8, 4, "drive", 64, 88)
    bassline(c["horizon"], c["stop"], 0.85, "16th", 300)
    drums(c["horizon"], c["superluminal"], "pulse", 0.75, duck=0.4)
    drums(c["superluminal"], c["stop"] - BEAT, "four", 1.0, duck=0.7, snare_g=0.5)
    impact(c["superluminal"], 0.9, br=False)
    impact(c["causal"], 1.0, notes=(28, 40, 46, 52))
    impact(c["noswitch"], 1.0, notes=(28, 40, 46), braam_dur=1.5)
    put("fx", c["sweep"], warp_growl(c["stop"] - c["sweep"], 28, 40), 0.7)
    put("fx", c["stop"] - 2.0, riser(2.0, (40, 46, 52, 58), 1000), 0.7)
    silence(c["stop"] - 0.05, c["burst"] - 0.05, ("pad", "organ", "shimmer", "arp", "bass"))
    impact(c["stop"], 1.0, notes=(28, 40), braam_dur=0.8)
    put("fx", c["burst"] - 0.6, reverse_swell((40, 46, 52), 0.6, IR_BIG), 0.6)
    impact(c["burst"], 1.1, notes=(28, 40, 46, 52))
    silence(c["destroy"] - 0.12, c["destroy"])
    impact(c["destroy"], 1.6, notes=(23, 24, 35, 36, 42), braam_dur=5.0)
    put("fx", c["destroy"], pan_st(sub_boom(6.0, 80, 20, 2.2), 0), 0.9)
    drone(c["destroy"], t1 + 1.0, (28, 29, 40), 0.16)

    # ================= 第六章：航迹（《三体》：史诗、悲壮）
    s = S["ch6"]
    t0, t1 = s["start"], s["end"]
    transition(t0, 0.9)
    VOL["pad"].add(t0, 1.0)
    pads(t0, c["foil"], 0.75)
    shimmers(t0, c["foil"], 1.1)
    PAD_CUT.add(t0, 800)
    for i, m in enumerate([64, 71, 76, 74, 71]):
        put("lead", t0 + BAR + i * BEAT * 1.5, piano(m, 3.0), 0.3)
    impact(c["built"], 0.8, br=False)
    put("lead", c["built"], bell(83, 4.0), 0.07)
    # 二向箔：沉重的管风琴 + 每颗行星落下一记重击
    drone(c["foil"], c["halo"], (28, 35, 40), 0.18)
    organs(c["foil"], c["trail"], 0.8)
    pads(c["foil"], c["trail"], 0.9)
    PAD_CUT.add(c["foil"], 1000); PAD_CUT.add(c["painting"], 1800)
    impact(c["foil"] + 0.3, 0.7, notes=(28, 40, 47))
    silence(c["flatten"] - 0.15, c["flatten"], ("pad", "organ"))
    impact(c["flatten"], 1.35, notes=(24, 36, 43, 48, 52), braam_dur=3.5)
    for k, m in enumerate((79, 83, 86, 91)):
        put("lead", c["painting"] + k * BEAT / 2, bell(m, 3.5), 0.06)
    accent(c["painting"], "flash", 0.6)
    # 星环号点火
    put("fx", c["halo"], warp_growl(c["ignite"] - c["halo"], 28, 43), 0.7)
    ARP_CUT.add(c["halo"], 1000); ARP_CUT.add(c["ignite"], 2200)
    arps(c["halo"], c["ignite"] - BEAT, 0.7, 4, "pulse", 59, 83)
    drums(c["halo"], c["ignite"] - BEAT, "heart", 0.8, duck=0.4)
    put("fx", c["ignite"] - 1.0, reverse_swell((40, 47, 52, 59), 1.0, IR_BIG), 0.6)
    silence(c["ignite"] - 0.15, c["ignite"])
    impact(c["ignite"], 1.4, notes=(28, 40, 47, 52, 55, 59), braam_dur=3.0, kind="transition")
    arps(c["ignite"], c["slowlight"] - BEAT, 0.8, 4, "drive", 64, 88)
    bassline(c["ignite"], c["slowlight"], 0.85, "16th", 300)
    drums(c["ignite"], c["trail"] + BAR, "four", 1.0, duck=0.7, snare_g=0.5)
    shimmers(c["trail"], c["slowlight"], 1.3)
    impact(c["long_trail"], 0.9, br=False)
    # 光速变慢：音乐也"变慢"——琶音降到每拍一个，钟声拉长
    pads(c["trail"], t1, 0.85)
    PAD_CUT.add(c["slowlight"], 900)
    silence(c["slowlight"] - 0.1, c["slowlight"] + 0.01, ("arp", "bass"))
    for k, m in enumerate((83, 79, 76, 71, 67)):
        put("lead", c["slowlight"] + k * BEAT * (1 + 0.35 * k), bell(m, 4.0), 0.06)
    hit(c["slowlight"], 0.6, 50, 24)
    for k in range(23):                                     # 航迹一道道叠上来：越来越密的低音嗒嗒
        tt = c["stack"] - 0.2 + k * 0.11
        put("perc", tt, TICK_LO, 0.1 + 0.006 * k, pan=np.sin(k * 1.7) * 0.6)
    put("fx", c["blackdomain"] - 2.4, riser(2.4, (40, 41, 47, 52), 800), 0.7)
    silence(c["blackdomain"] - 0.2, c["blackdomain"])
    impact(c["blackdomain"], 1.45, notes=(23, 24, 35, 36, 41), braam_dur=4.5)
    drone(c["blackdomain"], t1 + 0.5, (28, 29, 40), 0.18)
    put("lead", c["cage"], piano(40, 4.0), 0.4)
    put("lead", c["cage"], piano(52, 4.0), 0.3)
    accent(c["cage"], "flash", 0.4)

    # ================= 尾声：希望 -> 前进！
    s = S["outro"]
    t0, t1 = s["start"], s["end"]
    transition(t0, 0.8, (36, 43, 48))
    VOL["pad"].add(t0, 1.0)
    pads(t0, c["fwd"][0], 0.85)
    shimmers(t0, c["maybe"], 1.0)
    PAD_CUT.add(t0, 1100); PAD_CUT.add(c["positive"], 1800)
    put("lead", c["paper"], piano(72, 3.0), 0.3)
    for k in range(6):                                      # 时间线上每个节点一声
        tt = c["paper"] + 0.6 + k * 2 * BEAT
        put("lead", tt, bell((72, 76, 79, 83, 84, 88)[k], 3.0), 0.06)
        accent(tt, "flash", 0.3)
    ARP_CUT.add(c["paper"], 1400); ARP_CUT.add(c["positive"], 2400)
    arps(c["paper"] + BAR, c["maybe"] - BEAT, 0.7, 2, "up", 64, 88)
    bassline(c["paper"], c["maybe"], 0.6, "sustain", 200)
    drums(c["paper"] + BAR, c["maybe"] - BEAT, "pulse", 0.75, duck=0.4)
    impact(c["positive"], 1.0, notes=(24, 36, 43, 48, 52), braam_dur=2.5, br=True)
    hit(c["slower"], 0.6, 55, 28, bell_m=76)
    # 也许永远无法实现：只剩钢琴
    silence(c["maybe"] - 0.1, c["maybe"] + 0.01, ("arp", "bass", "shimmer"))
    mel = [(0, 76, 2), (2, 74, 1), (3, 71, 1), (4, 72, 2), (6, 71, 2), (8, 67, 3)]
    for b_, m, d in mel:
        tt = c["maybe"] + b_ * BEAT
        if tt < ls("H04"):
            put("lead", tt, piano(m, d * BEAT + 0.6), 0.45)
    # 维德的话：蓄能
    put("fx", ls("H04"), warp_growl(c["fwd"][0] - ls("H04"), 28, 45), 0.8)
    put("fx", c["fwd"][0] - 2.4, riser(2.4, (40, 47, 52, 59), 1000), 0.8)
    tom_fill(c["fwd"][0], 1.0, 0.7)
    silence(c["fwd"][0] - 0.25, c["fwd"][0], ("pad", "organ", "shimmer", "arp", "bass", "fx"))
    for k, tt in enumerate(c["fwd"]):
        impact(tt, 1.1 + 0.2 * k, notes=((28, 40, 47, 52), (31, 43, 50, 55), (24, 36, 43, 48, 52, 55))[k],
               braam_dur=1.2 if k < 2 else 4.5, kind="transition" if k == 2 else "impact")
    # 最后那个"前进"是整句的顶点（fwd_voice 让它前面留了一口气），原来没有任何重音、落空了：补太鼓 + 一记重音
    put("perc", c["fwd_last"], TAIKO, 0.85)
    accent(c["fwd_last"], "impact", 1.1)
    t_tun = c["fwd"][2]
    organs(t_tun, t1, 0.9)
    pads(t_tun, t1, 1.0)
    shimmers(t_tun, t1, 1.3)
    ARP_CUT.add(t_tun, 2000); ARP_CUT.add(t1, 3500)
    arps(t_tun + BEAT, t1 - BEAT, 1.0, 4, "drive", 64, 88)
    bassline(t_tun, t1, 1.0, "16th", 340)
    drums(t_tun + BEAT, t1 - BEAT, "four", 1.1, duck=0.8, snare_g=0.7)
    tt = t_tun + BAR
    while tt < t1 - 1e-6:
        put("perc", tt, SNARE, 0.2 + 0.3 * (tt - t_tun) / (t1 - t_tun))
        tt += BEAT / (2 if tt < t1 - BAR else 4)
    put("fx", t1 - 2.4, riser(2.4, (40, 47, 52, 59), 1100), 0.9)

    # ================= 片尾：落在 E 大调
    s = S["end"]
    t0, t1 = s["start"], s["end"]
    impact(t0, 1.3, notes=(28, 40, 47, 52, 56, 59), braam_dur=5.0)
    transition(t0, 0.5)
    organs(t0, t1 - 1, 0.9)
    pads(t0, t1 - 1.5, 0.9, rel=4.0)
    shimmers(t0, t1 - 2, 1.0)
    put("pad", t0, pan_st(bass_note(28, t1 - t0 - 2, 120), 0), 0.5)
    for i, m in enumerate([64, 71, 76, 78, 80]):
        put("lead", t0 + BAR + i * BEAT * 1.5, piano(m, 4), 0.4)
    PAD_CUT.add(t0, 1500); PAD_CUT.add(t1, 300)
    for k in BUS_NAMES:
        VOL[k].add(t1 - 3.0, VOL[k].at(t1 - 3.0))
        VOL[k].add(t1 + TAIL, 0.0)

    for sid in ORDER:
        ACCENTS.append(dict(t=SECS[sid]["start"], kind="section", size=1.0, id=sid))


def duck_env():
    """底鼓触发的侧链压缩包络。"""
    d = np.zeros(N, dtype=np.float32)
    L = int(0.45 * SR)
    t = np.arange(L) / SR
    shape = (np.exp(-t / 0.13) * np.minimum(1, t / 0.006)).astype(np.float32)
    for tk, depth in DUCKS:
        i = int(tk * SR)
        j = min(N, i + L)
        if j > i:
            np.maximum(d[i:j], shape[: j - i] * depth, out=d[i:j])
    return d


AI_GAIN = 2.6          # 飞船 AI 语音的总线增益（最终混音里与中文旁白响度相当）


def main():
    t_start = time.time()
    arrange()
    print("arranged", round(time.time() - t_start, 1), "s")
    duck = duck_env()
    pc = PAD_CUT.arr().astype(np.float64) * 1.35
    for ch in range(2):
        B["pad"][:, ch] = hp(svf(B["pad"][:, ch].astype(np.float64), pc, 0.8, 0), 95, 0.7).astype(np.float32)
    B["pad"] = chorus(B["pad"].astype(np.float64), 5.0, 0.18, 0.4).astype(np.float32)
    B["organ"] = chorus(B["organ"].astype(np.float64), 3.0, 0.3, 0.3).astype(np.float32)
    B["arp"] = (B["arp"] + pingpong(B["arp"].astype(np.float64), BEAT * 0.75, 0.4, 6, 2000)).astype(np.float32)
    for k, depth in (("pad", 0.45), ("bass", 0.7), ("arp", 0.3), ("organ", 0.25), ("shimmer", 0.15)):
        B[k] *= (1 - depth * duck)[:, None]
    # 飞船 AI 说话时，其余乐器整体让开约 6 dB
    aenv = env_follow(np.abs(B["ai"][:, 0].astype(np.float64)), 1 - np.exp(-1 / (0.03 * SR)), 1 - np.exp(-1 / (0.4 * SR)))
    aduck = lp(lp(np.clip(aenv / 0.02, 0, 1), 4.0), 4.0)
    for k in BUS_NAMES:
        if k not in ("ai", "kick"):
            B[k] *= (1 - 0.6 * aduck)[:, None].astype(np.float32)
    for k in BUS_NAMES:
        B[k] *= VOL[k].arr()[:, None]
    print("processed", round(time.time() - t_start, 1), "s")
    gains = dict(pad=2.0, organ=1.3, shimmer=1.4, arp=1.3, bass=0.38, kick=0.3, perc=0.55, fx=0.62, lead=1.3, ai=AI_GAIN,
                 sfx=3.2)
    hall_send = dict(pad=0.35, organ=0.5, shimmer=0.6, arp=0.3, bass=0.0, kick=0.06, perc=0.35, fx=0.25, lead=0.45, ai=0.06,
                     sfx=0.0)
    big_send = dict(pad=0.15, organ=0.25, shimmer=0.6, arp=0.1, bass=0.0, kick=0.0, perc=0.2, fx=0.35, lead=0.25, ai=0.0,
                    sfx=0.0)
    dry = np.zeros((N, 2))
    hall_in = np.zeros((N, 2))
    big_in = np.zeros((N, 2))
    for k in BUS_NAMES:
        x = B[k].astype(np.float64) * gains[k]
        if k == "ai":
            ai_stem = x + reverb(x * hall_send[k], IR_HALL) * 0.55
        dry += x
        hall_in += x * hall_send[k]
        big_in += x * big_send[k]
    B.clear()
    wet = reverb(hall_in, IR_HALL) * 0.55 + reverb(big_in, IR_BIG) * 0.5
    mix = dry + wet
    for ch in range(2):
        x = hp(mix[:, ch], 24, 0.7)
        # 温和的高频收束：整体更深沉，不刺耳
        x = x - 0.3 * lp(x, 55, 0.7) + 0.2 * hp(x, 3200, 0.7) - 0.25 * hp(x, 7000, 0.7)
        mix[:, ch] = x
    peak = np.max(np.abs(mix))
    mix = mix / peak * 0.7
    # 单独导出 AI 语音分轨（与 music.wav 同一缩放），用来检查它在配乐里是否听得清
    wavfile.write(os.path.join(BUILD, "stem_ai.wav"), SR, (ai_stem / peak * 0.7).astype(np.float32))
    print("rendered", round(time.time() - t_start, 1), "s  peak", round(float(peak), 3))
    wavfile.write(os.path.join(BUILD, "music.wav"), SR, mix.astype(np.float32))
    json.dump(dict(kicks=KICKS, accents=sorted(ACCENTS, key=lambda a: a["t"]),
                   chords=[(a, b, c_) for a, b, c_, d in CHORDS]),
              open(os.path.join(BUILD, "beats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
