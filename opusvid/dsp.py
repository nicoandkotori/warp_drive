# -*- coding: utf-8 -*-
"""opusvid.dsp — 基础音频合成工具：振荡器、滤波器、包络、混响、限幅器。"""
import numpy as np
from numba import njit
from scipy import signal

SR = 48000
RNG = np.random.default_rng(7)


def mtof(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=np.float64) - 69.0) / 12.0)


@njit(cache=True)
def svf(x, cutoff, q, mode):
    """TPT 状态变量滤波器。cutoff 为逐样本数组。mode 0=低通 1=带通 2=高通"""
    n = x.shape[0]
    y = np.empty(n)
    ic1 = 0.0
    ic2 = 0.0
    k = 1.0 / q
    for i in range(n):
        fc = cutoff[i]
        if fc > 20000.0:
            fc = 20000.0
        if fc < 10.0:
            fc = 10.0
        g = np.tan(np.pi * fc / 48000.0)
        a1 = 1.0 / (1.0 + g * (g + k))
        a2 = g * a1
        a3 = g * a2
        v3 = x[i] - ic2
        v1 = a1 * ic1 + a2 * v3
        v2 = ic2 + a2 * ic1 + a3 * v3
        ic1 = 2.0 * v1 - ic1
        ic2 = 2.0 * v2 - ic2
        if mode == 0:
            y[i] = v2
        elif mode == 1:
            y[i] = v1
        else:
            y[i] = x[i] - k * v1 - v2
    return y


@njit(cache=True)
def saw_blep(freq, phase0):
    n = freq.shape[0]
    y = np.empty(n)
    p = phase0
    for i in range(n):
        dt = freq[i] / 48000.0
        p += dt
        if p >= 1.0:
            p -= 1.0
        v = 2.0 * p - 1.0
        if p < dt:
            t = p / dt
            v -= t + t - t * t - 1.0
        elif p > 1.0 - dt:
            t = (p - 1.0) / dt
            v -= t * t + t + t + 1.0
        y[i] = v
    return y


@njit(cache=True)
def onepole_lp(x, a):
    y = np.empty_like(x)
    s = 0.0
    for i in range(x.shape[0]):
        s += a * (x[i] - s)
        y[i] = s
    return y


@njit(cache=True)
def env_follow(x, att, rel):
    y = np.empty_like(x)
    s = 0.0
    for i in range(x.shape[0]):
        v = abs(x[i])
        if v > s:
            s += att * (v - s)
        else:
            s += rel * (v - s)
        y[i] = s
    return y


@njit(cache=True)
def limiter_gain(peak, thr, look, rel):
    n = peak.shape[0]
    gt = np.empty(n)
    for i in range(n):
        gt[i] = 1.0 if peak[i] <= thr else thr / peak[i]
    out = np.empty(n)
    g = 1.0
    att = 4.0 / look
    for i in range(n):
        m = 1.0
        j_end = min(n, i + look)
        for j in range(i, j_end):
            if gt[j] < m:
                m = gt[j]
        if m < g:
            g += (m - g) * att
        else:
            g += (m - g) * rel
        out[i] = g
    return out


def limit(st, thr=0.89, look_ms=4.0, rel_ms=120.0):
    peak = np.max(np.abs(st), axis=1)
    g = limiter_gain(np.ascontiguousarray(peak), thr, int(look_ms * SR / 1000), 1.0 / (rel_ms * SR / 1000))
    y = st * g[:, None]
    return np.tanh(y / thr) * thr


def sine(freq, n, phase=0.0):
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (n,))
    ph = np.cumsum(f) / SR + phase
    return np.sin(2 * np.pi * ph)


def saw(freq, n, phase=None):
    f = np.ascontiguousarray(np.broadcast_to(np.asarray(freq, dtype=np.float64), (n,)))
    return saw_blep(f, RNG.random() if phase is None else phase)


def lp(x, fc, q=0.707):
    c = np.ascontiguousarray(np.broadcast_to(np.asarray(fc, dtype=np.float64), x.shape))
    return svf(np.ascontiguousarray(x, dtype=np.float64), c, q, 0)


def bp(x, fc, q=1.0):
    c = np.ascontiguousarray(np.broadcast_to(np.asarray(fc, dtype=np.float64), x.shape))
    return svf(np.ascontiguousarray(x, dtype=np.float64), c, q, 1)


def hp(x, fc, q=0.707):
    c = np.ascontiguousarray(np.broadcast_to(np.asarray(fc, dtype=np.float64), x.shape))
    return svf(np.ascontiguousarray(x, dtype=np.float64), c, q, 2)


def adsr(n, a, d, s, r, hold):
    """hold：从开始到释放的秒数。返回长度 n 的包络。"""
    t = np.arange(n) / SR
    e = np.empty(n)
    a = max(a, 1e-4)
    d = max(d, 1e-4)
    e = np.where(t < a, t / a, s + (1 - s) * np.exp(-(t - a) / d * 3.0))
    if hold is not None:
        rel_lvl = np.interp(hold, t, e) if hold < t[-1] else e[-1]
        e = np.where(t < hold, e, rel_lvl * np.exp(-(t - hold) / max(r, 1e-4) * 4.0))
    return e


def exp_sweep(f0, f1, n, tau=None):
    t = np.arange(n) / SR
    if tau is None:
        return f0 * (f1 / f0) ** (t / (n / SR))
    return f1 + (f0 - f1) * np.exp(-t / tau)


def make_ir(rt60=3.5, dur=None, predelay=0.025, bright=7000, dark=900, width=1.0, seed=1):
    dur = dur or rt60 * 1.3
    n = int(dur * SR)
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    env = 10 ** (-3 * t / rt60)
    cut = dark + (bright - dark) * np.exp(-t / (rt60 * 0.25))
    out = np.zeros((n + int(predelay * SR), 2))
    for ch in range(2):
        noise = rng.standard_normal(n) * env
        noise = lp(noise, cut, 0.6)
        out[int(predelay * SR):, ch] = noise
    # 立体声宽度
    mid = (out[:, 0] + out[:, 1]) / 2
    side = (out[:, 0] - out[:, 1]) / 2 * width
    out[:, 0], out[:, 1] = mid + side, mid - side
    # 淡入防止咔嗒
    fade = min(len(out), int(0.004 * SR))
    out[:fade] *= np.linspace(0, 1, fade)[:, None]
    out /= np.sqrt(np.sum(out ** 2) / 2)
    return out


def reverb(x, ir):
    """x: (n,2) 干信号，返回 (n,2) 湿信号（截断到 n）。"""
    n = x.shape[0]
    y = np.zeros_like(x)
    for ch in range(2):
        y[:, ch] = signal.oaconvolve(x[:, ch], ir[:, ch], mode="full")[:n]
    return y


def pan_st(mono, pan=0.0):
    """等功率声像。pan -1..1"""
    a = (pan + 1) * np.pi / 4
    return np.stack([mono * np.cos(a), mono * np.sin(a)], axis=1)


def pingpong(st, delay_s, fb=0.45, n_echo=6, lp_fc=2500):
    n = st.shape[0]
    out = np.zeros_like(st)
    mono = (st[:, 0] + st[:, 1]) * 0.5
    d = int(delay_s * SR)
    cur = mono.copy()
    g = 1.0
    for k in range(1, n_echo + 1):
        g *= fb
        cur = lp(cur, lp_fc, 0.5)
        sh = k * d
        if sh >= n:
            break
        out[sh:, k % 2] += g * cur[: n - sh]
    return out


def chorus(st, depth_ms=6.0, rate=0.25, mix=0.5):
    n = st.shape[0]
    t = np.arange(n) / SR
    out = st.copy()
    for ch, ph in ((0, 0.0), (1, np.pi / 2)):
        d = (depth_ms * 0.5 * (1 + np.sin(2 * np.pi * rate * t + ph)) + 8.0) * SR / 1000.0
        idx = np.arange(n) - d
        idx = np.clip(idx, 0, n - 1)
        i0 = np.floor(idx).astype(np.int64)
        fr = idx - i0
        i1 = np.minimum(i0 + 1, n - 1)
        src = st[:, ch]
        out[:, ch] = st[:, ch] * (1 - mix) + (src[i0] * (1 - fr) + src[i1] * fr) * mix
    return out
