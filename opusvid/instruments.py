# -*- coding: utf-8 -*-
"""opusvid.instruments — 合成乐器与音效：铺底、管风琴、闪光铺底、拨弦、贝斯、鼓组、
次低频下潜、低音铜管 braam、低频涌动转场、反向混响、钟、钢琴、上行音。
所有转场类音效都只保留低频，深邃不刺耳。"""
import numpy as np
from scipy import signal
from .dsp import *

def pad_note(m, dur, att=1.2, rel=2.2, voices=3, det=0.11, bright=1.0):
    n = int((dur + rel + 0.2) * SR)
    env = adsr(n, att, 1.0, 0.85, rel, dur)
    out = np.zeros((n, 2))
    f = mtof(m)
    for v in range(voices):
        d = (v - (voices - 1) / 2) * det
        s = saw(f * 2 ** (d / 12), n)
        out += pan_st(s, (v - (voices - 1) / 2) * 0.7)
    return out * env[:, None] / voices


def organ_note(m, dur, att=0.6, rel=2.5):
    n = int((dur + rel + 0.2) * SR)
    t = np.arange(n) / SR
    env = adsr(n, att, 1.0, 0.9, rel, dur)
    f = mtof(m) * (1 + 0.0012 * np.sin(2 * np.pi * 5.1 * t + RNG.random() * 6))
    sig = np.zeros(n)
    for h, a in ((1, 1.0), (2, 0.55), (3, 0.22), (4, 0.2), (6, 0.07), (8, 0.06)):
        sig += a * sine(f * h, n, RNG.random())
    return pan_st(sig * env * 0.35, RNG.uniform(-0.3, 0.3))


def shimmer_note(m, dur):
    n = int((dur + 3.0) * SR)
    t = np.arange(n) / SR
    env = adsr(n, 1.8, 1.0, 0.9, 3.0, dur)
    trem = 0.7 + 0.3 * np.sin(2 * np.pi * RNG.uniform(0.15, 0.4) * t + RNG.random() * 6)
    sig = sine(mtof(m), n) + 0.25 * sine(mtof(m + 12) * 1.001, n)
    return pan_st(sig * env * trem, RNG.uniform(-0.8, 0.8))


def pluck(m, cut, vel=1.0, length=0.42):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = mtof(m)
    s = saw(f, n) * 0.7 + saw(f * 1.004, n) * 0.5
    fc = cut * (1 + 5 * np.exp(-t / 0.05))
    s = lp(s, fc, 1.1)
    env = np.exp(-t / 0.16) * np.minimum(1, t / 0.002)
    return s * env * vel


def bass_note(m, dur, cut=260, pluck_mode=False):
    n = int((dur + 0.3) * SR)
    t = np.arange(n) / SR
    f = mtof(m)
    s = sine(f, n) + 0.35 * saw(f, n)
    if pluck_mode:
        s = lp(s, cut * (1 + 3 * np.exp(-t / 0.05)), 0.9)
        env = np.exp(-t / max(dur * 0.6, 0.05)) * np.minimum(1, t / 0.004)
    else:
        s = lp(s, cut, 0.8)
        env = adsr(n, 0.08, 1, 0.9, 0.3, dur)
    return np.tanh(s * env * 1.4)


def kick_s(f0=150, f1=44, decay=0.42, click=0.25):
    n = int(1.0 * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / 0.032)
    body = np.tanh(sine(f, n) * np.exp(-t / decay) * 1.8)
    clk = lp(RNG.standard_normal(n) * np.exp(-t / 0.003), 1600) * click
    return body + clk


def tom_s(f0=120, f1=72, decay=0.38):
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / 0.07)
    body = sine(f, n) * np.exp(-t / decay)
    nz = lp(RNG.standard_normal(n), 700) * np.exp(-t / 0.04) * 0.5
    return np.tanh((body + nz) * 1.5)


def taiko_s():
    return tom_s(90, 52, 0.7) * 1.1


def snare_s():
    n = int(0.8 * SR)
    t = np.arange(n) / SR
    body = sine(185 + 30 * np.exp(-t / 0.02), n) * np.exp(-t / 0.09)
    nz = bp(RNG.standard_normal(n), 1400, 0.6) * np.exp(-t / 0.16)
    nz = lp(nz, 5000)
    return np.tanh((body * 0.8 + nz * 0.9) * 1.3)


def sub_boom(dur=4.0, f0=62, f1=27, drive=1.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / 0.45)
    s = sine(f, n) * np.exp(-t / 1.25) * np.minimum(1, t / 0.006)
    s = np.tanh(s * drive) / np.tanh(drive)
    thump = lp(RNG.standard_normal(n), 160, 0.7) * np.exp(-t / 0.16) * 1.4
    tom = sine(78 * np.exp(-t / 0.5) + 40, n) * np.exp(-t / 0.5) * 0.6
    return s + thump + tom


def braam(dur=3.2, notes=(26, 38, 45, 50, 53), peak=950, gain=1.0):
    n = int((dur + 1.5) * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for m in notes:
        for v in range(4):
            d = (v - 1.5) * 0.14
            out += pan_st(saw(mtof(m) * 2 ** (d / 12), n), (v - 1.5) * 0.5)
    cut = 140 + (peak - 140) * (1 - np.exp(-t / 0.09)) * np.exp(-t / (dur * 0.45))
    for ch in range(2):
        out[:, ch] = lp(out[:, ch], cut, 1.3)
    env = adsr(n, 0.025, 0.6, 0.55, 1.2, dur)
    out = np.tanh(out * env[:, None] * 0.55) * gain
    return out


def deep_whoosh(dur=1.9, f_lo=55, f_hi=420):
    """低频涌动：低通噪声 + 共鸣扫频 + 次低频上行。结束于 t=dur。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = t / dur
    cut = f_lo * (f_hi / f_lo) ** (x ** 1.6)
    out = np.zeros((n, 2))
    for ch in range(2):
        nz = RNG.standard_normal(n)
        a = lp(nz, cut, 2.2)
        a = lp(a, cut * 1.5, 0.7)
        out[:, ch] = a
    env = x ** 2.6 * (1 - np.clip((x - 0.985) / 0.015, 0, 1))
    rumble = sine(32 + 38 * x ** 2, n) * x ** 2 * 0.5
    out = out * env[:, None] * 2.2 + pan_st(rumble, 0)
    return out


def reverse_swell(notes=(38, 45, 50), dur=2.2, ir=None):
    n = int(0.6 * SR)
    dry = np.zeros((n, 2))
    for m in notes:
        dry += pan_st(lp(saw(mtof(m), n), 500) * np.exp(-np.arange(n) / SR / 0.15), RNG.uniform(-.5, .5))
    wet = np.zeros((n + ir.shape[0] - 1, 2))
    for ch in range(2):
        wet[:, ch] = signal.oaconvolve(dry[:, ch], ir[:, ch], mode="full")[: wet.shape[0]]
    wet = wet[::-1]
    m = int(dur * SR)
    wet = wet[-m:]
    wet *= np.linspace(0, 1, m)[:, None] ** 1.5
    return wet


def bell(m, dur=4.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = mtof(m)
    s = np.zeros(n)
    for r, a, d in ((1, 1, 2.8), (2.756, 0.38, 1.4), (5.404, 0.16, 0.7), (8.93, 0.06, 0.35)):
        s += a * sine(f * r, n) * np.exp(-t / d)
    return s * np.minimum(1, t / 0.003)


def piano(m, dur=3.0, vel=1.0):
    n = int((dur + 1) * SR)
    t = np.arange(n) / SR
    f = mtof(m)
    s = np.zeros(n)
    for h in range(1, 8):
        s += (0.6 ** (h - 1)) * sine(f * h * (1 + 0.0004 * h * h), n) * np.exp(-t / (2.2 / h ** 0.7))
    s += 0.5 * sine(f * 1.002, n) * np.exp(-t / 2.0)
    env = np.minimum(1, t / 0.004) * np.where(t < dur, 1, np.exp(-(t - dur) / 0.3))
    return s * env * vel * 0.4


def riser(dur=4.0, notes=(38, 45, 50, 57), top=1100):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = t / dur
    out = np.zeros((n, 2))
    for m in notes:
        f = mtof(m) * 2 ** (x ** 2 * 1.0)
        for v in range(2):
            out += pan_st(saw(f * (1 + (v - .5) * 0.006), n), (v - .5) * 1.2)
    cut = 150 + (top - 150) * x ** 2
    for ch in range(2):
        out[:, ch] = lp(lp(out[:, ch], cut, 1.2), cut * 1.4, 0.7)
    env = x ** 2.2 * (1 - np.clip((x - 0.99) / 0.01, 0, 1))
    return out * env[:, None] * 0.35

