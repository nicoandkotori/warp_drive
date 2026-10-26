# -*- coding: utf-8 -*-
"""开场（23 小节）和冷开场之后回到半人马座 α 的段落。
Warp：银河 + 导航选目标（galaxynav.GalaxyNav：银河缓缓旋转 -> 潜入太阳邻域 -> 选星）-> 星图收起、镜头从舰桥拉开露出飞船 -> 充能 -> 空间扭曲 -> 跃迁分镜
      （镜头留在原地看飞船弹射出去，再追上去）-> 超光速巡航 -> 减速 -> 抵达 + 片名。镜头与特效在 warpshot.py。
Arrive："而它只需要几个月"（航时回顾）-> "曲率驱动"（《三体》）-> 爱因斯坦场方程（现实）。
时刻全部来自 cues.C / cues.AI。"""
import math
from opusvid.scene import Scene
from opusvid.gl import smooth, W
from opusvid.mathtex import Tex, write_fx, highlight_fx, combine
from config import SHIP_AI
from cues import C, AI
from wfx import CYAN, GOLD, WHITE, DIM, ICE, bodies, darkspot, stamp, pulse, vis
import star_model
from ship import ship, ship_frame, roll, relstars
from scenes_open import cam_lerp
import warpseq
from warpshot import WarpShot
from galaxynav import GalaxyNav

# 半人马座 α（世界坐标，飞船在原点、船头朝 +z）：与开场抵达时同一套恒星（star_model，参数照 warpshot.stars），
# 回到这里时观众看到的是同一颗蓝巨星——原来是两个发光的小光点，和开场对不上。
# A 在右下方占掉画面右下角（星心在画面外；这台镜头的画面右边是 -x），飞船和上方的标题区落在暗的星空上；
# B 是左上远处一颗橙色的小星，比邻星是一个红点
A_POS, A_RADIUS = (-300.0, -250.0, 700.0), 260.0
B_POS, B_RADIUS = (800.0, 90.0, 900.0), 7.0
PROXIMA = (1150.0, 380.0, 2400.0)
A_LIGHT = (-0.36, -0.2, 0.91)              # 照在飞船上的星光方向（大致朝向 A 的盘面，偏上一点）


def alpha_cen(e, cam, glow=0.0):
    """α A、α B、比邻星。glow：说到"曲率驱动"时 A 亮一下。"""
    star_model.star(e, cam, B_POS, B_RADIUS, color=(1.0, 0.5, 0.2), bright=0.6, corona=0.7, prom=0.5, seed=4.0)
    star_model.star(e, cam, A_POS, A_RADIUS, color=(0.16, 0.48, 1.0), bright=0.5 * (1 + 0.4 * glow), blue=1.0,
                    spots=0.25, seed=1.0, granules=1500.0, corona=0.35)
    q = cam.project(PROXIMA)
    if q:
        bodies(e, [(q[0], q[1], 1.6, 0.7, (1.0, 0.25, 0.15), 0.3)])


class Warp(Scene):
    """开场 23 小节：银河 + 导航选目标（galaxynav）-> 充能 -> 空间扭曲 -> 跃迁分镜 -> 巡航 -> 抵达 + 片名（warpshot）。"""

    def setup(self):
        self.nav = GalaxyNav(self.eng)
        self.shot = WarpShot(self.eng)

    def render(self, t):
        e = self.eng
        shot = self.shot
        if t < C["handoff"]:
            # 银河星图；收起时露出舰桥看出去的真实星空（与后面的飞船镜头同一台镜头、同一片星空）
            self.nav.render(t, shot.camera(t), lambda cam: shot.navigation_sky(cam, t), shot.target_a(t))
            if SHIP_AI:
                warpseq.ai_caption(e, t, AI, C["charge"])
        else:
            shot.render(t)
        # 金色锁定框：星图收起后落在真实的 α A 上，镜头拉开时一直跟着它
        self.nav.lock_bracket(t, shot.camera(t), shot.target_a(t))

    def post(self, t):
        if t < C["handoff"]:
            return dict(uBloomAmt=0.35, uVignette=0.55, uCA=0.0, uGrain=0.02)
        return self.shot.post(t)


class Arrive(Scene):
    """回到半人马座 α：飞船静静停在蓝巨星 α A 旁（与开场抵达时同一颗星）；"几个月"时回顾航时，然后是"曲率驱动"和爱因斯坦场方程。"""

    def setup(self):
        self.eq = Tex(self.eng, [(r"G_{\mu\nu}", "G"), "=", (r"\frac{8\pi G}{c^4}", "k"), (r"T_{\mu\nu}", "T")], size=110)

    def render(self, t):
        e = self.eng
        lt = t - self.t0
        cam = cam_lerp(t, self.t0, self.t1, (-4.2, 1.2, -10.5), (-3.2, 1.6, -9.6), (0.6, 1.0, 8.0), (0.4, 1.3, 8.0), fov=36.0)
        relstars(e, cam, stars=0.9, neb=0.45, gal=(0.6, 0.7, 0.3), n1=(0.35, 0.12, 0.08), n2=(0.15, 0.2, 0.5))
        alpha_cen(e, cam, glow=0.6 * pulse(t, C["name"], 0.5))
        # 冷蓝的星光从右前下方照过来（与开场抵达时一致），背面靠补光读出轮廓
        ship(e, cam, (0.0, -0.4, 0.0), roll(ship_frame((0, 0, 1)), 0.6 + 0.02 * lt), 1.0, ring=0.8 + 0.2 * math.sin(t * 2),
             phase=t * 2, engine=0.4, sun=A_LIGHT, sun_col=(1.5, 2.2, 3.4), fill=(0.24, 0.30, 0.42))
        # 航时回顾：4.37 光年 / 约 4 个月
        ma = vis(t, C["months"] - 0.1, C["name"] - 0.2, 0.2, 0.4)
        if ma > 0:
            sc = stamp(t, C["months"], 0.4, 1.3)
            darkspot(e, W / 2, 300, 620, 200, 0.55 * ma)
            e.text("≈ 4 个月", W / 2, 290, 130, "sans_b", GOLD, ma, "mm", 0.04, 1.6 + 1.5 * pulse(t, C["months"], 0.4), scale=sc)
            e.text("4.37 光年  ·  约 13 倍光速", W / 2, 390, 30, "sans_m", ICE, ma, "mm", 0.15, 1.2)
        out1 = C["real"] - 0.3
        a1 = smooth(C["name"] - 0.1, C["name"] + 0.3, t) * (1 - smooth(out1, out1 + 0.5, t))
        if a1 > 0.001:
            y = 300
            darkspot(e, W / 2, y + 20, 640, 220, 0.65 * a1)
            sc = stamp(t, C["name"], 0.45, 1.3)
            e.text("曲率驱动", W / 2, y, 150, "serif", CYAN, a1, "mm", 0.14, 2.0, scale=sc, blur=6 * (sc - 1))
            e.text("曲率驱动", W / 2, y, 150, "serif", WHITE, a1 * 0.9, "mm", 0.14, 1.2, scale=sc)
            e.text("CURVATURE PROPULSION", W / 2, y + 112, 24, "latin_m", ICE, a1, "mm", 0.6, 1.5, t=t,
                   start=C["name"] + 0.25, dur=0.8, stagger=0.02, kind="spread")
            e.text("小说《三体》· 刘慈欣", W / 2, y - 120, 26, "sans_m", DIM, a1 * vis(t, C["name"], self.t1, 0.3, 0.6), "mm",
                   0.25, 1.1, t=t, start=C["name"] + 0.1, dur=0.6)
        a2 = smooth(C["einstein"] - 0.3, C["einstein"] + 0.2, t) * (1 - smooth(self.t1 - 0.5, self.t1, t))
        if a2 > 0.001:
            y = 330
            darkspot(e, W / 2, y - 20, 700, 220, 0.7 * a2)
            fx = combine(write_fx(t, C["einstein"] - 0.2, dur=0.5, stagger=0.05, tex=self.eq),
                         highlight_fx(t, ["G", "T"], C["eq"], color=CYAN, glow=0.5, pulse=1.0))
            self.eq.draw(W / 2, y + 30, anchor="=", color=WHITE, alpha=a2, intensity=1.5, fx=fx)
            e.text("爱因斯坦场方程", W / 2, y + 130, 28, "sans_m", GOLD, a2 * vis(t, C["eq"], self.t1, 0.3, 0.4), "mm",
                   0.3, 1.3)

    def post(self, t):
        return dict(uBloomAmt=0.55, uVignette=0.7, uCA=0.006)
