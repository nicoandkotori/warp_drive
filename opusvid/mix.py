# -*- coding: utf-8 -*-
"""opusvid.mix — 人声处理 + 与配乐混合（人声出现时配乐自动避让）。"""
import json, os
import numpy as np
from scipy.io import wavfile
from .dsp import SR, hp, lp, bp, env_follow, make_ir, reverb, limit


def mix(timeline_path, tts_dir, music_path, out_path, voice_db=-17.0, music_db=-21.5, duck_depth=0.42,
        voice_reverb=0.0):
    """voice_reverb：人声混响的湿声比例。默认 0（干声）——用户明确不喜欢旁白带混响，
    停顿处的尾音会让人声发闷；只有确实需要空间感的项目才打开（0.05~0.1）。"""
    TL = json.load(open(timeline_path, encoding="utf-8"))
    sr, music = wavfile.read(music_path)
    music = music.astype(np.float64)
    N = music.shape[0]
    voice = np.zeros(N)
    for s in TL["sections"]:
        for L in s["lines"]:
            _, v = wavfile.read(os.path.join(tts_dir, L["id"] + ".wav"))
            v = v.astype(np.float64) / 32768.0
            i = int(round(L["place"] * SR))
            j = min(N, i + len(v))
            voice[i:j] += v[: j - i]
    # EQ：去低频浑浊、加一点胸腔温暖和清晰度
    voice = hp(voice, 85, 0.7)
    voice = voice + 0.25 * bp(voice, 180, 0.9) + 0.3 * bp(voice, 3200, 0.8) - 0.15 * bp(voice, 7500, 1.0)
    # 压缩
    env = env_follow(voice, 1 - np.exp(-1 / (0.008 * SR)), 1 - np.exp(-1 / (0.15 * SR)))
    thr = np.percentile(env[env > 1e-3], 60)
    ratio = 3.0
    g = np.where(env > thr, (np.maximum(env, 1e-9) / thr) ** (1 / ratio - 1), 1.0)
    voice = voice * g
    act = env > 1e-3
    rms = np.sqrt(np.mean(voice[act] ** 2))
    voice *= 10 ** (voice_db / 20) / rms
    vst = np.stack([voice, voice], 1)
    if voice_reverb > 0:
        ir = make_ir(1.3, predelay=0.018, bright=5000, dark=1500, width=0.8, seed=11)
        vst = vst + reverb(vst, ir) * voice_reverb
    # 闪避
    venv = env_follow(np.abs(voice), 1 - np.exp(-1 / (0.03 * SR)), 1 - np.exp(-1 / (0.5 * SR)))
    duck = np.clip(venv / (np.max(venv) * 0.12), 0, 1)
    duck = lp(lp(duck, 4.0), 4.0)
    mrms = np.sqrt(np.mean(music ** 2))
    music = music * (10 ** (music_db / 20) / mrms)
    music = music * (1 - duck_depth * duck)[:, None]
    mix = music + vst
    act_v = venv > np.max(venv) * 0.05
    rv = 20 * np.log10(np.sqrt(np.mean(voice[act_v] ** 2)) + 1e-12)
    rm = 20 * np.log10(np.sqrt(np.mean(music[act_v] ** 2)) + 1e-12)
    rq = 20 * np.log10(np.sqrt(np.mean(music[~act_v] ** 2)) + 1e-12)
    print(f"voice {rv:.1f} dB | music under voice {rm:.1f} dB | music alone {rq:.1f} dB")
    mix = limit(mix * 1.5, thr=0.89)
    print("mix rms dB", 20 * np.log10(np.sqrt(np.mean(mix ** 2))), "peak", np.max(np.abs(mix)))
    wavfile.write(out_path, SR, mix.astype(np.float32))

