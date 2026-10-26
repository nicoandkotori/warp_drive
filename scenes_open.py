# -*- coding: utf-8 -*-
"""冷开场（飞船 -> 七万年 vs 四百年）与几个共用的镜头小工具。开场的跃迁过场、片名、抵达在 scenes_warp.py。"""
import math
import numpy as np
from opusvid.scene import Scene
from opusvid.gl import ease_in_out, ease_out_expo, smooth, lin, Camera
from cues import C
from wfx import CYAN, GOLD, AMBER, WHITE, DIM, ICE, space, bodies, stamp, brackets, hud_text, pulse, vis, lerp, streaks
from ship import ship, ship_frame, roll, relstars

SUN_DIR = (-0.7, 0.55, 0.35)
TARGET = np.array([0.5, 0.32, 400.0])          # 远方的半人马座 α（飞船 +z 方向）


def cam_lerp(t, t0, t1, eye0, eye1, tgt0, tgt1, fov=38.0, ease=ease_in_out):
    m = ease(lin(t0, t1, t))
    return Camera(tuple(lerp(eye0, eye1, m)), tuple(lerp(tgt0, tgt1, m)), fov=fov)


def screen_radius(cam, p, r):
    """世界空间半径 r 的球在屏幕上的像素半径（近似）。"""
    a = cam.project(p)
    eye = np.asarray(cam.eye, np.float64)
    f = np.asarray(cam.target, np.float64) - eye
    side = np.cross(f, (0, 1, 0))
    side /= np.linalg.norm(side)
    b = cam.project(tuple(np.asarray(p) + side * r))
    if a is None or b is None:
        return 0.0
    return math.hypot(a[0] - b[0], a[1] - b[1])


class Cold(Scene):
    def setup(self):
        self.tB = C["voyager"]

    # ------------------------------------------------ A 飞船英雄镜头 + 目标锁定
    def phase_a(self, t):
        e = self.eng
        cam = cam_lerp(t, self.t0, self.tB, (-5.6, 1.8, -8.0), (-4.6, 1.45, -6.6), (-0.4, 0.35, 3.0), (-0.2, 0.4, 3.4), fov=36.0)
        relstars(e, cam, stars=1.0, neb=0.55, gal=(0.25, 0.9, -0.3))
        tp = cam.project(tuple(TARGET))
        g = pulse(t, C["target"], 0.6)
        if tp:
            bodies(e, [(tp[0], tp[1], 3.0 + 3 * g, 1.2 + 2.5 * g, (1.0, 0.92, 0.75), 0.9)])
        ship(e, cam, (0, 0, 0), roll(ship_frame((0, 0, 1)), 0.25 + 0.02 * t), 1.0, ring=0.9 + 0.2 * math.sin(t * 2),
             phase=t * 1.2, engine=0.5, sun=SUN_DIR)
        # 目标锁定框 + HUD
        a = vis(t, C["target"], self.tB, 0.3, 0.3)
        if tp and a > 0:
            s = 70 * (1 + 2.5 * (1 - ease_out_expo(lin(C["target"], C["target"] + 0.5, t))))
            brackets(e, tp[0] - s / 2, tp[1] - s / 2, s, s, a, CYAN, L=14, width=1.6, intensity=1.8)
            e.text("α CEN", tp[0] + s / 2 + 14, tp[1] - s / 2 + 6, 20, "latin_m", CYAN, a, "lm", 0.15, 1.4)
        t0 = self.t0
        ha = vis(t, t0 + 1.2, self.tB, 0.5, 0.3)
        hud_text(e, t, t0 + 1.2, "曲率试验舰 · 待命", 90, 96, 26, ICE, ha, font="sans_m")
        hud_text(e, t, t0 + 1.6, "WARP TEST VESSEL  /  STANDBY", 92, 134, 21, DIM, ha)
        e.line([(92, 156), (92 + 300 * ease_out_expo(lin(t0 + 1.6, t0 + 2.6, t)), 156)], 1.0, CYAN, 0.6 * ha)
        hud_text(e, t, C["target"], "目标  半人马座 α  ·  三体人的故乡", 92, 190, 24, WHITE, vis(t, C["target"], self.tB, 0.2, 0.3),
                 font="sans_m")
        # 距离大字
        da = vis(t, C["dist"], self.tB, 0.25, 0.3)
        if da > 0:
            sc = stamp(t, C["dist"], 0.4, 1.25)
            e.text("4.37", 92, 800, 150, "latin_b", WHITE, da, "lm", 0.02, 1.5, scale=sc)
            e.text("光年", 92 + 330 * sc, 822, 52, "sans_b", GOLD, da, "lm", 0.1, 1.5, t=t, start=C["dist"] + 0.15, dur=0.4)
            e.text("LIGHT-YEARS  ·  4.1 × 10¹³ KM", 96, 902, 21, "latin_m", DIM, da, "lm", 0.25, 1.2, t=t,
                   start=C["dist"] + 0.3, dur=0.5, stagger=0.01, kind="spread")

    # ------------------------------------------------ B 距离示意：旅行者一号 vs 三体舰队
    def phase_b(self, t):
        e = self.eng
        lt = t - self.tB
        a = smooth(self.tB, self.tB + 0.25, t)
        space(e, neb=0.12, stars=0.7 * a, c1=(0.04, 0.08, 0.25), c2=(0.16, 0.05, 0.22), c3=(0.2, 0.25, 0.5), off=(lt * 10, 0), seed=5.0)
        xs, xa, y = 300.0, 1620.0, 520.0
        bodies(e, [(xs, y, 14, 1.6 * a, (1.0, 0.85, 0.55), 0.7),
                   (xa - 10, y - 8, 9, 1.4 * a, (1.0, 0.9, 0.7), 0.5), (xa + 18, y + 10, 7, 1.2 * a, (1.0, 0.7, 0.4), 0.4),
                   (xa - 60, y + 110, 3.5, 0.8 * a, (1.0, 0.35, 0.2), 0.2)])
        e.line([(xs + 40, y), (xa - 45, y)], 1.0, DIM, 0.35 * a, dash=14.0)
        la = vis(t, self.tB, self.t1, 0.3, 0.35)
        e.text("太阳系", xs, y + 82, 30, "sans_m", WHITE, la, "mm", 0.2, 1.1)
        e.text("半人马座 α", xa, y + 82, 30, "sans_m", WHITE, la, "mm", 0.15, 1.1)
        e.text("4.37 光年", (xs + xa) / 2, y - 46, 30, "sans_m", GOLD, la, "mm", 0.1, 1.3)
        # 旅行者一号：计数器飞快地跑到 7 万多年，探测器只挪了一点点 —— 表现"慢"
        ta, tb = self.tB + 0.25, C["fleet"] - 0.6
        yrs = 77000 * ease_in_out(lin(ta, tb, t))
        px = xs + 40 + (xa - 45 - xs - 40) * (yrs / 77000) * 0.12
        va = vis(t, self.tB + 0.1, self.t1, 0.3, 0.35)
        streaks(e, [dict(tail=(xs + 40, y + 2), head=(px, y + 2), color=ICE, a=1.2 * va, width=3.0, taper=0.3, spark=1.4)])
        e.text("旅行者一号  17 km/s", px, y + 40, 22, "sans_m", ICE, va, "mm", 0.06, 1.2)
        g = pulse(t, C["fleet"] - 1.3, 0.4)
        e.text(f"{int(yrs):,}", 820, 760, 96, "latin_b", ICE, va, "rm", 0.02, 1.4 + g, scale=1 + 0.15 * g)
        e.text("年", 840, 772, 44, "sans_b", ICE, va, "lm", 0.0, 1.3)
        e.text("VOYAGER 1", 826, 830, 18, "latin_m", DIM, va, "rm", 0.3, 1.1)
        # 三体舰队：一队琥珀色"水滴"从右往左
        if t > C["fleet"] - 0.1:
            p = ease_in_out(lin(C["fleet"], self.t1 - 0.5, t))
            fa = vis(t, C["fleet"], self.t1, 0.25, 0.35)
            fx0 = xa - 45 - (xa - 45 - xs - 40) * p
            for k in range(13):
                row, col = divmod(k, 5)
                ox = abs(col - 2) * 26 + row * 40
                oy = (col - 2) * 22 + (row % 2) * 8
                e.circle(fx0 + ox, y - 2 + oy, 3.0, fill=AMBER, fill_a=fa, glow=2, intensity=1.4)
            streaks(e, [dict(tail=(xa - 45, y - 2), head=(fx0, y - 2), color=AMBER, a=0.9 * fa, width=3.0, taper=0.3)])
            yrs2 = 450 * p
            e.text(f"{int(yrs2)}", 1240, 760, 96, "latin_b", AMBER, fa, "rm", 0.02, 1.5)
            e.text("年", 1260, 772, 44, "sans_b", AMBER, fa, "lm", 0.0, 1.3)
            e.text("三体舰队", 1246, 830, 22, "sans_m", AMBER, fa, "rm", 0.1, 1.1)

    def render(self, t):
        if t < self.tB:
            self.phase_a(t)
        else:
            self.phase_b(t)

    def post(self, t):
        if t < self.tB:
            return dict(uBloomAmt=0.5, uVignette=0.75, uGrain=0.035, uCA=0.006)
        return dict(uBloomAmt=0.55, uVignette=0.6)
