# -*- coding: utf-8 -*-
"""尾声：研究时间线（1994 -> 2024，不需要负能量但仍慢于光）-> 也许永远无法实现
-> "前进！前进！！不择手段地前进！！！"三连跃迁 -> 片尾（飞向远方的恒星 + 参考文献）。"""
import math
from opusvid.scene import Scene
from opusvid.gl import ease_out, ease_in_out, ease_out_expo, smooth, lin, W, Camera
from config import BEAT
from cues import C, ls
from wfx import (CYAN, GOLD, AMBER, WHITE, DIM, ICE, VIOLET, bodies, flat, darkspot, glitch_text, stamp, pulse, vis,
                 mix3, lerp)
from ship import ship, ship_frame, roll, relstars, tunnel
from warpseq import tunnel_z

# 研究时间线：(年份, 名字, 一句话, 颜色)
PAPERS = [
    ("1994", "阿库别瑞", "曲率泡度规", CYAN),
    ("1997", "芬宁 & 福特", "需要的负能量远超宇宙", VIOLET),
    ("1999", "范登布鲁克", "降到几个太阳质量", VIOLET),
    ("2012", "怀特（NASA）", "乐观估计：探测器质量", VIOLET),
    ("2021", "博布里克 & 马蒂尔", "不需要负能量的曲率泡", (0.45, 1.0, 0.6)),
    ("2024", "费尔 等", "首个“物理”曲率泡解", (0.45, 1.0, 0.6)),
]


class Outro(Scene):
    def setup(self):
        self.tM, self.tQ, self.tF = ls("H03"), ls("H04"), C["fwd"][0]

    # ------------------------------------------------ 研究时间线
    def phase_papers(self, t):
        e = self.eng
        lt = t - self.t0
        cam = Camera((0, 0, 0), (0.15 * math.sin(lt * 0.05), 0.05, 1.0), fov=55)
        a = smooth(self.t0, self.t0 + 0.6, t) * (1 - smooth(self.tM - 0.15, self.tM, t))
        relstars(e, cam, stars=0.8 * a, neb=0.45 * a, gal=(0.4, 0.85, 0.2))
        x0, x1, y = 190, 1730, 560
        p = ease_out_expo(lin(C["paper"], C["paper"] + 1.2, t))
        e.line([(x0 - 40, y), (x0 - 40 + (x1 - x0 + 80) * p, y)], 1.5, DIM, 0.8 * a, intensity=1.2)    # 时间轴：不加光晕，免得晕成灯管
        pos_hi = smooth(C["positive"] - 0.2, C["positive"] + 0.3, t)
        for k, (yr, nm, note, col) in enumerate(PAPERS):
            st = C["paper"] + 0.6 + k * 2 * BEAT
            if t < st:
                continue
            x = x0 + (x1 - x0) * k / (len(PAPERS) - 1)
            na = a * smooth(st, st + 0.25, t)
            hi = pos_hi if k >= 4 else 0.0
            g = pulse(t, st, 0.4) + (pulse(t, C["positive"], 0.5) if k >= 4 else 0.0)
            e.circle(x, y, 6 + 2 * g, fill=col, fill_a=na, glow=2, intensity=1.3 + 0.8 * g)
            up = k % 2 == 0
            ty = y - 120 if up else y + 120
            e.line([(x, y - 14 if up else y + 14), (x, ty + (30 if up else -30))], 1.2, col, 0.6 * na)
            e.text(yr, x, ty, 52, "latin_b", col, na, "mm", 0.05, 1.5 + g + hi, scale=1 + 0.08 * hi)
            e.text(nm, x, ty + (48 if up else 48), 28, "sans_b", WHITE, na, "mm", 0.06, 1.2)
            e.text(note, x, ty + (88 if up else 88), 24, "sans_m", mix3(DIM, col, 0.5 + 0.5 * hi), na, "mm", 0.06, 1.1)
        sa = vis(t, C["slower"] - 0.1, self.tM, 0.3, 0.4)
        e.text("但仍然比光慢", (x0 + x1) / 2 + 520, y + 300, 44, "sans_b", AMBER, sa, "mm", 0.15, 1.6,
               scale=stamp(t, C["slower"], 0.4, 1.25))
        e.text("现实中的曲率引擎", W / 2, 180, 64, "serif", WHITE, vis(t, C["paper"], self.tM, 0.5, 0.4), "mm", 0.12, 1.4,
               t=t, start=C["paper"], dur=0.6, stagger=0.06)

    # ------------------------------------------------ 也许永远无法实现 -> 维德的话（飞船静静漂向远方，曲率环慢慢亮起）
    def phase_drift(self, t):
        e = self.eng
        lt = t - self.tM
        a = smooth(self.tM, self.tM + 0.3, t)
        m = ease_in_out(lin(self.tM, self.tF, t))
        cam = Camera(tuple(lerp((-5.2, 1.6, -9.5), (-3.6, 0.9, -6.8), m)), (0.3, 0.2, 3.0), fov=38)
        relstars(e, cam, stars=a, neb=0.5 * a, gal=(0.25, 0.9, -0.3))
        tp = cam.project((2.0, 1.0, 300.0))
        if tp:
            bodies(e, [(tp[0], tp[1], 4, 1.6 * a, (1.0, 0.92, 0.8), 0.9)])
        charge = smooth(self.tQ, self.tF, t)
        ship(e, cam, (0, 0, 0), roll(ship_frame((0, 0, 1)), 0.3 + 0.05 * lt), 1.0, amt=a, ring=0.3 + 2.2 * charge ** 2,
             phase=t * (1 + 20 * charge), engine=0.4 + charge, sun=(-0.6, 0.6, 0.4))
        wa = vis(t, C["wade"] - 0.2, self.tF, 0.4, 0.3)
        e.text("托马斯 · 维德", W - 140, 200, 40, "serif", GOLD, wa, "rm", 0.15, 1.4)
        e.text("《三体 III · 死神永生》", W - 140, 256, 26, "sans_m", DIM, wa, "rm", 0.2, 1.1)

    # ------------------------------------------------ 前进！前进！！不择手段地前进！！！
    def phase_forward(self, t):
        e = self.eng
        hits = C["fwd"]
        n = sum(1 for h in hits if t >= h)
        hp = sum(pulse(t, h, 0.3) for h in hits)
        cam = Camera((0, 0, 0), (0.0, 0.0, 1.0), fov=70 + 6 * hp)
        # 每一声"前进"都往光速再推一级：星星聚向前方并拖出光线，第三声之后直接进隧道
        lvl = [0.0, 0.55, 0.82, 0.97][n]
        prev = [0.0, 0.0, 0.55, 0.82][n]
        b = prev + (lvl - prev) * ease_out_expo(lin(hits[n - 1], hits[n - 1] + 0.35, t)) if n else 0.0
        t_tun = hits[2] + 0.3
        sa = 1 - smooth(t_tun, t_tun + 0.5, t)
        if sa > 0:
            relstars(e, cam, beta=b, beta0=max(0.0, b - 0.25 * hp - 0.05), stars=0.6 * sa, neb=0.3 * sa)
        if t > t_tun - 0.2:
            tau = t - (t_tun - 0.2)
            tunnel(e, smooth(0.0, 0.5, tau) * (1 + 0.8 * smooth(self.t1 - 1.0, self.t1, t)), tunnel_z(tau) * 1.3,
                   length=0.7, twist=0.4 * tau, ca=(0.15, 0.3, 1.0), cb=(1.0, 0.25, 0.7), rings=1.2)
        flat(e, (0.75, 0.9, 1.0), 1.2 * sum(pulse(t, h, 0.08) for h in hits) + 1.8 * smooth(self.t1 - 0.3, self.t1, t))
        # 三行大字，一声一行砸下来
        rows = [("前进！", 300, 130), ("前进！！", 500, 160), ("不择手段地前进！！！", 740, 132)]
        out = smooth(self.t1 - 0.5, self.t1 - 0.15, t)
        for k, (s, y, size) in enumerate(rows):
            t0 = hits[k]
            if t < t0:
                continue
            sc = stamp(t, t0, 0.35, 1.5)
            g = math.exp(-(t - t0) / 0.5)
            darkspot(e, W / 2, y, 300 + 60 * len(s), size * 0.9, 0.3 * (1 - out))
            glitch_text(e, s, W / 2, y, size, "heavy", (1.0, 0.97, 0.92), 1 - out, t, seed=k, amt=min(1, g + 0.12),
                        scale=sc, intensity=1.2 + 1.5 * g, c1=(1.0, 0.25, 0.4), c2=(0.2, 0.8, 1.0))
            if g > 0.05:
                e.text(s, W / 2, y, size, "heavy", CYAN, g * 0.35, "mm", 0.08, 1.6, scale=sc * 1.04, blur=size * 0.1)
        e.text("—— 托马斯 · 维德", W / 2 + 420, 860, 30, "sans_m", GOLD, vis(t, hits[2] + 0.8, self.t1, 0.4, 0.3), "mm",
               0.2, 1.2)

    def render(self, t):
        if t < self.tM:
            self.phase_papers(t)
        elif t < self.tF:
            self.phase_drift(t)
        else:
            self.phase_forward(t)

    def post(self, t):
        if t >= self.tF:
            return dict(uBloomAmt=0.45, uVignette=0.9, uCA=0.02 + 0.03 * smooth(C["fwd"][2], self.t1, t))
        return dict(uBloomAmt=0.5, uVignette=0.75)


class End(Scene):
    def render(self, t):
        e = self.eng
        lt = t - self.t0
        cam = Camera((-1.6 + 0.2 * lt / 12, 1.0, -7.5 - 0.6 * lt / 12), (0.5, 0.6, 20.0), fov=38)
        relstars(e, cam, stars=1.0, neb=0.55, gal=(0.25, 0.9, -0.3))
        tp = cam.project((3.0, 2.2, 400.0))
        g = pulse(t, self.t0, 0.6)
        if tp:
            bodies(e, [(tp[0], tp[1], 6 + 6 * g, 2.0 + 3 * g, (1.0, 0.9, 0.75), 1.0)])
        z = 4.0 + 18.0 * ease_out(lin(self.t0, self.t1, t))
        ship(e, cam, (0.0, 0.0, z), roll(ship_frame((0, 0, 1)), 0.4 + 0.04 * lt), 1.0, ring=1.4, phase=t * 4, engine=0.9,
             sun=(-0.4, 0.5, 0.6))
        flat(e, (0.75, 0.9, 1.0), 1.5 * pulse(t, self.t0, 0.25))
        a = smooth(self.t0 + 0.6, self.t0 + 1.6, t)
        e.text("曲率引擎", W / 2, 300, 140, "serif", WHITE, a, "mm", 0.2, 1.3, t=t, start=self.t0 + 0.6, dur=1.0,
               stagger=0.12, kind="blur")
        e.text("WARP  DRIVE", W / 2, 410, 30, "latin_m", ICE, a, "mm", 0.9, 1.4, t=t, start=self.t0 + 1.0, dur=1.0,
               stagger=0.03, kind="spread")
        refs = ["Alcubierre, Class. Quantum Grav. 11, L73 (1994)", "Pfenning & Ford, Class. Quantum Grav. 14, 1743 (1997)",
                "Van Den Broeck, Class. Quantum Grav. 16, 3973 (1999)", "Bobrick & Martire, Class. Quantum Grav. 38, 105009 (2021)",
                "Fell et al., constant-velocity physical warp drive (2024)", "刘慈欣《三体》三部曲"]
        ra = vis(t, self.t0 + 2.2, self.t1, 0.8, 1.0)
        e.text("参考", W / 2, 760, 24, "sans_b", GOLD, ra, "mm", 0.4, 1.2)
        for k, s in enumerate(refs):
            e.text(s, W / 2, 800 + k * 34, 20, "latin_m" if k < 5 else "sans_m", DIM, ra, "mm", 0.05, 1.0)

    def post(self, t):
        return dict(uBloomAmt=0.55, uVignette=0.8)
