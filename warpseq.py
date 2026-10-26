# -*- coding: utf-8 -*-
"""开场用到的两个公用小件（导航 HUD 在 navhud.py，充能 -> 跃迁 -> 抵达的一镜到底在 warpshot.py）。

  tunnel_z(τ)     尾声“前进”段曲率隧道的行程
  ai_caption(...) 飞船 AI 说话时的中英字幕 + 声纹条

所有函数只依赖传入的时刻，可任意跳帧。"""
import math
from opusvid.gl import smooth, W, H
from wfx import WHITE

HOLO = (0.35, 0.85, 1.0)


# ---------------------------------------------------------------------- 尾声“前进”段的隧道行程
def tunnel_z(tau):
    """隧道行程 = 速度 v(τ)=3.2·(1-e^(-τ/0.45)) 的积分（解析式，只依赖时间）。"""
    return 3.2 * (tau - 0.45 * (1 - math.exp(-tau / 0.45)))


# ---------------------------------------------------------------------- 飞船 AI 字幕
def ai_caption(e, t, lines, t_end):
    """飞船 AI 说话时，在画面下方显示英文原话（逐字打出）+ 中文字幕，左侧一组随语音跳动的声纹条。
    lines 为 cues.AI。t_end 之前淡出（字幕在清晰文字层，不参与转场）。"""
    for L in lines:
        if not (L["t"] - 0.1 <= t <= L["end"] + 0.6):
            continue
        a = smooth(L["t"] - 0.1, L["t"] + 0.08, t) * (1 - smooth(L["end"] + 0.3, L["end"] + 0.6, t)) * (1 - smooth(t_end - 0.2, t_end, t))
        if a <= 0.001:
            continue
        y = H - 128
        en = L["en"].upper()
        n = int(len(en) * min(1.0, (t - L["t"]) / max(L["end"] - L["t"], 0.3) * 1.15)) + 1
        w = e.text(en[:n], W / 2 + 18, y, 30, "latin_m", HOLO, a, "mm", 0.12, 1.5)
        e.text(L["zh"], W / 2, y + 44, 30, "sans_m", WHITE, 0.92 * a, "mm", 0.08, 1.1)
        # 声纹条：说话时跳动
        speaking = L["t"] <= t <= L["end"]
        x0 = W / 2 - w / 2 - 40
        for k in range(5):
            hgt = 4 + (14 * abs(math.sin(t * (13 + 5 * k) + k)) if speaking else 0)
            e.rect(x0 + k * 7, y - hgt / 2, 4, hgt, 1, fill=HOLO, fill_a=a, intensity=2.0)

