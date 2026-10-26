# -*- coding: utf-8 -*-
"""开场导航段（0 秒 -> C["handoff"]，9 小节）：银河是主角，HUD 在它上面选星。替换 galaxyhud.py（程序化银河那一版）。

分镜（卡点全在 cues.C）：
  0 -> sun_mark     银河从黑暗里浮现、缓缓旋转，镜头从低角度慢慢抬升、推近（主角镜头）；gal_title 时出字"银河系"。
  sun_mark -> zoom  外侧旋臂上标出"太阳系 · 我们在这里"，镜头朝它移动。
  zoom -> local     缩放潜入太阳邻域：镜头距离按对数一路缩小，"视野宽度"读数从 10 万光年降到几十光年；
                    银河不消失：云雾在镜头前分开（galaxy.draw 的 clear），潜进盘面以后它是绕天一圈的光带和远处的银心；
                    太阳周围的近邻星场一路从镜头边掠过。
  local -> select   近邻恒星逐颗标出；光标每停一颗候选星（天狼星 / 巴纳德星 / 天苑四），镜头就推近到它，旁边出数据卡。
  select            选中半人马座 α：镜头推近，看到 α Cen A、B 和比邻星。
  switch -> lock    规划航线：镜头拉开，从侧面看到太阳和半人马座 α，琥珀色航线每光年一个刻度；
                    随即绕到太阳背后，顺着航线看向画面正中的 α（和随后舰桥看出去的方向一致，交接时它不跳）。
  lock -> engage    锁定：瞄准环收拢，右侧读数（4.37 光年 / 123 天），下方"光走完这段路要 4.37 年"。
  engage            "曲率引擎 · 准备就绪"。
  collapse -> handoff  星图收起（一道亮线，HUD 往中心收），露出舰桥前方的真实星空；锁定框留在真实的 α A 上（lock_bracket）。

坐标：银河坐标（galaxy.py：盘面 xy、z 朝上，1 单位约 2400 光年）。太阳放在半径 11（约 2.6 万光年）的一条旋臂上
（按体积纹理挑的发光强、尘埃少的位置）。近邻恒星用真实的赤经赤纬换成银道坐标（x 指向银心、z 朝上），
按 1 / LY_PER_UNIT 缩进模型里，所以缩放时是同一个三维空间连续推进，不切换尺度。
银河缓缓旋转（spin），到开始潜入时停住，之后太阳和近邻恒星的位置都不再变。所有画面只依赖 t。"""
import math
import numpy as np
from opusvid.gl import smooth, lin, ease_out_expo, W, H
from cues import C
from galaxy import Galaxy, GalCam, LY_PER_UNIT, spin_matrix
from shiphud import BridgeHUD, STARS, CANDS, DAYS_PER_LY, HUD, DIM, ACC, AMB, WHT, ln, tx, corner, box_corners, type_in
from wfx import MONO, bodies, ring, darkspot, Offscreen, blit
from warpshot import hermite

SUN0 = np.array([11.0 * math.cos(2.53), 11.0 * math.sin(2.53), 0.0])   # 太阳在模型里的位置（旋转前）
SPIN = 0.32                       # 银河在主角镜头里一共转过的角度（弧度），开始潜入时停住
# α Cen 三合星：A、B 实际相距约 23 天文单位，这个尺度下会叠成一个点，图上示意性地错开；比邻星离 A 约 0.21 光年
ACEN_B = np.array([0.035, -0.02, 0.012])
PROXIMA = np.array([-0.12, 0.15, -0.06])
# 光谱型 -> 星点颜色、大小（像素）
SPEC = {"A": ((0.75, 0.85, 1.0), 4.2), "F": ((0.95, 0.95, 1.0), 3.6), "G": ((1.0, 0.92, 0.75), 3.4),
        "K": ((1.0, 0.75, 0.5), 3.0), "M": ((1.0, 0.5, 0.35), 2.4)}


class GalaxyNav(BridgeHUD):
    """沿用 BridgeHUD 的开机 / 收起节奏（power、shrink）和交接时的锁定框（lock_bracket）。"""

    def __init__(self, e):
        super().__init__(e)
        self.g = Galaxy(e)
        self.sun = spin_matrix(SPIN) @ SUN0                          # 停转以后太阳的位置
        ex = -np.array([self.sun[0], self.sun[1], 0.0])
        ex /= np.linalg.norm(ex)
        ez = np.array([0.0, 0.0, 1.0])
        self.axes = np.stack([ex, np.cross(ez, ex), ez], 1)          # 银道坐标 -> 模型坐标（列向量是三根轴）
        self.local = [self.sun + self.axes @ g / LY_PER_UNIT for g in self.gal]
        self.az_c = math.atan2(-ex[1], -ex[0])                        # 镜头看向银心时的方位角
        # 近邻星场：15 光年（比星表里最远的南河三还远）到 6000 光年
        self.g.make_field(SUN0, 4000, 15.0 / LY_PER_UNIT, 2.5)
        self.keys = self._keys()

    # ---------------- 时间线
    @staticmethod
    def spin(t):
        """银河转过的角度：主角镜头里匀减速地转，开始潜入（C["zoom"]）时停住。"""
        x = lin(C["warp"], C["zoom"], t)
        return SPIN * (1 - (1 - x) ** 2)

    def sun_at(self, t):
        return spin_matrix(self.spin(t)) @ SUN0

    def star_pos(self, i):
        """第 i 颗近邻恒星（STARS 的顺序）在模型里的位置；0 是半人马座 α A。"""
        return self.local[i]

    @staticmethod
    def orbit_of(focus, eye, near_az):
        """镜头放在 eye、看向 focus 时的 (方位角, 仰角, 距离)；方位角取与 near_az 相差不到半圈的那个值。"""
        d = np.asarray(eye) - np.asarray(focus)
        dist = float(np.linalg.norm(d))
        az = math.atan2(d[1], d[0])
        az += math.tau * round((near_az - az) / math.tau)
        return az, math.asin(d[2] / dist), dist

    def _keys(self):
        """镜头关键帧：(时刻, 注视点, 方位角, 仰角, ln 距离, 视场角)。方位角一路单调增加（镜头始终朝一个方向绕）。"""
        A, O, S = self.az_c, np.zeros(3), self.sun
        P = self.star_pos(0)
        mid = (S + P) / 2
        u = (P - S) / np.linalg.norm(P - S)
        # 规划航线：从航线的侧面看（方位角取离选中时最近的那一侧）
        side = np.cross(u, (0.0, 0.0, 1.0))
        cands = [self.orbit_of(mid, mid + s * side * 0.0045 + np.array([0, 0, 0.0015]), A + 0.5) for s in (1, -1)]
        az_s, el_s, _ = min(cands, key=lambda c: abs(c[0] - (A + 0.5)))
        # 锁定：太阳背后 1.4 光年、偏右上一点，顺着航线看向 α（太阳落在左下角，航线斜着伸向画面中心）
        right = np.cross(u, (0.0, 0.0, 1.0))
        right /= np.linalg.norm(right)
        eye = S + (-u * 1.4 + right * 0.55 + np.array([0, 0, 0.4])) / LY_PER_UNIT
        az_l, el_l, d_l = self.orbit_of(P, eye, az_s)
        k = [(C["warp"], O, A - 2.4, 0.14, math.log(70.0), 44.0),
             (C["sun_mark"], O, A - 1.7, 0.50, math.log(50.0), 44.0),          # 主角镜头：低角度慢慢抬升、推近
             (C["zoom"], S * 0.6, A - 1.0, 0.62, math.log(26.0), 46.0),         # 朝"我们在这里"移动
             (C["zoom"] + 1.2, S, A - 0.35, 0.42, math.log(1.2), 48.0),         # 潜入：距离按对数缩小
             (C["local"], S, A, 0.16, math.log(0.012), 50.0)]                   # 太阳邻域（约 29 光年外看）
        for j, tk in enumerate(C["cands"]):                                     # 每选一颗候选星，镜头推近到它
            p = self.star_pos(CANDS[j])
            k.append((tk, p, A + 0.12 * (j + 1), 0.18, math.log(0.0075), 50.0))
            k.append((tk + 0.6, p, A + 0.12 * (j + 1) + 0.04, 0.18, math.log(0.0072), 50.0))
        k += [(C["select"], self.star_pos(0), A + 0.5, 0.2, math.log(0.0009), 50.0),   # 推近半人马座 α：三颗星分开
              (C["select"] + 0.7, self.star_pos(0), A + 0.53, 0.21, math.log(0.00085), 50.0),
              (C["switch"] + 0.3, mid, az_s, el_s, math.log(0.0045), 50.0),          # 拉开：侧面看到太阳和 α
              (C["switch"] + 0.7, mid, az_s, el_s, math.log(0.0044), 50.0),
              (C["lock"], P, az_l, el_l, math.log(d_l), 46.0),                        # 绕到太阳背后，α 在正中
              (C["handoff"], P, az_l, el_l, math.log(d_l * 0.85), 44.0)]
        return k

    def camera(self, t):
        kf = self.keys
        focus = hermite(kf, t, 1)
        az, el, ld, fov = (float(hermite(kf, t, i)) for i in (2, 3, 4, 5))
        return GalCam.orbit(focus, az, el, math.exp(ld), fov)

    # ---------------- 画面
    def render(self, t, cam, sky, target):
        e = self.e
        reveal = smooth(C["collapse"], C["handoff"], t)                # 星图收起、舰桥星空露出来
        if reveal > 0.001:
            with Offscreen(e, 5) as sk:
                sky(cam)
            blit(e, sk, reveal)
        on = smooth(C["warp"], C["warp"] + 1.2, t) * (1 - reveal)
        if on <= 0.002:
            return
        gc, kw = self.galaxy_args(t)
        self.g.draw(gc, opacity=on, **kw)
        self.local_stars(gc, t, on)
        hud = on * smooth(C["warp"] + 1.0, C["warp"] + 1.8, t)
        self.frame_corners(t, hud)
        self.galaxy_title(t, hud)
        self.credit(t, hud)
        self.sun_marker(gc, t, hud)
        self.scale_readout(gc, t, hud)
        self.labels(gc, t, hud)
        self.cursor_card(gc, t, hud)
        self.route(gc, t, hud)
        self.lock_reticle(gc, t, hud)
        self.modes(t, hud)

    def galaxy_args(self, t):
        """这一帧银河怎么画：(镜头, galaxy.draw 的其余参数)。preview_galaxy.py 也调用它，单独预览和成片完全一致。"""
        gc = self.camera(t)
        dive = smooth(C["zoom"], C["local"], t)
        # 离太阳多近（按对数）：4 个单位以外为 0，0.3 以内为 1。越近，视线胶囊清得越宽、星云发光越弱、近邻星场越亮
        dsun = float(np.linalg.norm(gc.eye - self.sun_at(t)))
        inside = 1 - smooth(math.log(0.3), math.log(4.0), math.log(dsun))
        # 潜进盘面以后模型里那 6000 颗"代表性"的星点只当远处的银河星光，压暗一些
        return gc, dict(spin=self.spin(t), stars=1.0 - 0.55 * dive, clouds=1.0, clear=2.5 * inside,
                        em=1.0 - 0.85 * inside, field=0.6 * inside, near=0.3 * inside)

    def local_stars(self, gc, t, on):
        """近邻恒星：潜到太阳附近时亮起（真实的光谱型决定颜色和大小）。"""
        a = on * smooth(C["zoom"] + 1.5, C["local"] + 0.2, t)
        if a <= 0.01:
            return
        items = []
        q = gc.project(self.sun)
        if q:
            items.append((q[0], q[1], 4.0, 2.2 * a, (1.0, 0.93, 0.78), 0.3))
        for i in range(len(STARS)):
            q = gc.project(self.star_pos(i))
            if not q:
                continue
            col, r = SPEC[STARS[i][2][0]]
            items.append((q[0], q[1], r, (1.8 if i == 0 else 1.2) * a, col, 0.2))
        # α Cen 的 B 和比邻星：推近到它时才分得开
        for off, col, r in ((ACEN_B, (1.0, 0.72, 0.45), 2.6), (PROXIMA, (1.0, 0.4, 0.28), 1.8)):
            q = gc.project(self.star_pos(0) + self.axes @ off / LY_PER_UNIT)
            if q:
                items.append((q[0], q[1], r, 1.2 * a, col, 0.15))
        for i in range(0, len(items), 12):                               # bodies 一次最多 12 个
            bodies(self.e, items[i:i + 12])

    # ---------------- HUD
    def frame_corners(self, t, a):
        sk = self.shrink(t)
        if a <= 0.01:
            return
        m, mv = 78 + (W / 2 - 300) * sk, 74 + (H / 2 - 120) * sk
        for x, sx in ((m, 1), (W - m, -1)):
            for y, sy in ((mv, 1), (H - mv, -1)):
                corner(self.e, x, y, sx, sy, 58, 0.8 * a * (1 - sk))
                corner(self.e, x + sx * 10, y + sy * 10, sx, sy, 14, 0.35 * a * (1 - sk), DIM, 1.0)
        cl = math.sin(math.pi * lin(C["collapse"], C["handoff"], t)) if t > C["collapse"] else 0.0
        if cl > 0.01:                                                  # 收起：一道亮线横过中心
            ln(self.e, [(W / 2 - 800 * (1 - sk), H / 2), (W / 2 + 800 * (1 - sk), H / 2)], 0.7 * cl, ACC, 1.0, 0.3, 1.4)

    def galaxy_title(self, t, a):
        a *= smooth(C["gal_title"], C["gal_title"] + 0.4, t) * (1 - smooth(C["sun_mark"] + 1.4, C["sun_mark"] + 2.0, t))
        if a <= 0.01:
            return
        e, x, y = self.e, 110, 170
        t0 = C["gal_title"]
        tx(e, "银河系", x, y, 46, a, WHT, "lm", "sans_m", 0.25, k=1.0)
        tx(e, "THE MILKY WAY", x + 2, y + 44, 13, 0.75 * a, HUD, "lm", MONO, 0.45)
        s = "直径约 10 万光年  ·  约 2000 亿颗恒星"
        tx(e, s[:type_in(t, t0 + 0.4, len(s), 30)], x + 2, y + 78, 18, 0.85 * a, HUD, "lm", "sans_m", 0.1)
        ln(e, [(x, y + 98), (x + 360 * ease_out_expo(lin(t0 + 0.2, t0 + 0.9, t)), y + 98)], 0.4 * a)

    def credit(self, t, a):
        a *= 1 - smooth(C["local"], C["local"] + 0.6, t)
        tx(self.e, "GALAXY MODEL  caton.laubergiste  ·  CC BY 4.0", 100, H - 96, 11, 0.4 * a, DIM, "lm", MONO, 0.15)

    def sun_marker(self, gc, t, a):
        """"太阳系 · 我们在这里"：两圈扩散的细环 + 四角括号 + 标签，潜入时跟着放大、淡出。"""
        a *= smooth(C["sun_mark"], C["sun_mark"] + 0.3, t) * (1 - smooth(C["zoom"] + 1.2, C["local"], t))
        if a <= 0.01:
            return
        q = gc.project(self.sun_at(t))
        if not q:
            return
        e, x, y = self.e, q[0], q[1]
        for j in range(2):
            ph = ((t - C["sun_mark"]) / 1.2 + j * 0.5) % 1.0
            ring(e, x, y, 10 + 40 * ph, a * (1 - ph) * 0.8, AMB, 1.2, 0.3, 64, 1.4)
        s = 18 + 8 * (1 - ease_out_expo(lin(C["sun_mark"], C["sun_mark"] + 0.5, t)))
        box_corners(e, x - s, y - s, x + s, y + s, a, AMB, 7, 1.3)
        lx, ly = x + 70, y - 70
        ln(e, [(x + s * 0.7, y - s * 0.7), (lx, ly), (lx + 240, ly)], 0.7 * a, AMB, 1.0, 0.2,
           progress=ease_out_expo(lin(C["sun_mark"], C["sun_mark"] + 0.5, t)))
        tx(e, "太阳系  ·  我们在这里", lx + 4, ly - 22, 24, a, WHT, "lm", "sans_m", 0.1)
        tx(e, "SOL  ·  YOU ARE HERE", lx + 4, ly + 16, 12, 0.75 * a, AMB, "lm", MONO, 0.3)
        tx(e, "距银河中心约 2.6 万光年", lx + 4, ly + 40, 16, 0.85 * a, HUD, "lm", "sans_m", 0.08)

    def scale_readout(self, gc, t, a):
        """缩放时的"视野宽度"读数（光年）+ 一条对数刻度：读数一路从 10 万光年降到几十光年。"""
        a *= smooth(C["zoom"] - 0.3, C["zoom"], t) * (1 - smooth(C["local"] + 0.6, C["local"] + 1.2, t))
        if a <= 0.01:
            return
        e = self.e
        dist = float(np.linalg.norm(gc.eye - self.camera_focus(t)))
        field = 2 * dist * math.tan(math.radians(gc.fov) / 2) * LY_PER_UNIT * W / H
        x, y = W - 110, 170
        tx(e, "视野宽度  FIELD OF VIEW", x, y, 14, 0.75 * a, HUD, "rm", "sans_m", 0.15)
        tx(e, f"{field:,.0f}", x - 70, y + 52, 52, a, WHT, "rm", "latin", 0.02, layer="ui")
        tx(e, "光年", x, y + 58, 18, 0.85 * a, HUD, "rm", "sans_m", 0.1)
        x0, x1, yb = x - 420, x, y + 104
        ln(e, [(x0, yb), (x1, yb)], 0.35 * a)
        for i, lab in enumerate(("10", "100", "1 000", "10 000", "100 000")):
            xx = x0 + (x1 - x0) * i / 4
            ln(e, [(xx, yb), (xx, yb + 8)], 0.6 * a)
            tx(e, lab, xx, yb + 22, 11, 0.6 * a, DIM, "mm", MONO, 0.0)
        u = min(max((math.log10(max(field, 1.0)) - 1) / 4, 0.0), 1.0)
        xm = x0 + (x1 - x0) * u
        ln(e, [(xm - 6, yb - 14), (xm, yb - 4), (xm + 6, yb - 14), (xm - 6, yb - 14)], a, ACC, 1.3, 0.3)

    def camera_focus(self, t):
        return hermite(self.keys, t, 1)

    def labels(self, gc, t, a):
        """近邻恒星的名字和距离：到达邻域后逐颗出现；正被光标选着的那颗由数据卡代替。"""
        a *= smooth(C["local"], C["local"] + 0.4, t) * (1 - smooth(C["switch"], C["switch"] + 0.5, t))
        if a <= 0.01:
            return
        e = self.e
        k, u = self.cursor_state(t)
        cur = CANDS[k] if k is not None and u >= 1 else None
        q = gc.project(self.sun)
        if q:
            tx(e, "太阳", q[0] + 12, q[1] + 16, 15, 0.8 * a, AMB, "lm", "sans_m", 0.1)
        for i in range(len(STARS)):
            if i == cur:
                continue
            q = gc.project(self.star_pos(i))
            if not q or not (-50 < q[0] < W + 50 and -50 < q[1] < H + 50):
                continue
            ai = a * smooth(0.0, 0.3, t - (C["local"] + 0.06 * i))
            big = i in CANDS
            tx(e, STARS[i][0], q[0] + 10, q[1] - 10, 16 if big else 13, (0.85 if big else 0.55) * ai, WHT if big else HUD,
               "lm", "sans_m", 0.08)
            tx(e, f"{STARS[i][3]:.2f} LY", q[0] + 10, q[1] + 8, 11, 0.5 * ai, DIM, "lm", MONO, 0.08)

    def cursor_card(self, gc, t, a):
        """取景光标逐颗停在候选星上（镜头同时推近），旁边出数据卡；选中半人马座 α 时变成琥珀色。"""
        k, u = self.cursor_state(t)
        a *= smooth(C["cands"][0] - 0.4, C["cands"][0] - 0.1, t) * (1 - smooth(C["switch"], C["switch"] + 0.4, t))
        if k is None or a <= 0.01:
            return
        e = self.e
        q1 = gc.project(self.star_pos(CANDS[k]))
        if not q1:
            return
        q0 = (gc.project(self.star_pos(CANDS[k - 1])) if k > 0 else None) or q1     # 上一颗已在镜头背后时直接落位
        x, y = q0[0] + (q1[0] - q0[0]) * u, q0[1] + (q1[1] - q0[1]) * u
        sel = CANDS[k] == 0 and u >= 1
        c = AMB if sel else ACC
        s = 26 + 10 * (1 - u)
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            corner(e, x + sx * s, y + sy * s, -sx, -sy, 9, a, c, 1.4)
        if u < 1:
            return
        i = CANDS[k]
        name, en, cls, d = STARS[i][0], STARS[i][1], STARS[i][2], STARS[i][3]
        tk = (list(C["cands"]) + [C["select"]])[k]
        cx0, cy0 = x + 70, y - 150
        draw = ease_out_expo(lin(tk, tk + 0.35, t))
        darkspot(e, cx0 + 150, cy0 + 56, 420, 200, 0.6 * a * draw)                 # 卡片压在银河光带上时也看得清
        ln(e, [(x + s, y - s), (cx0, cy0 + 112)], 0.6 * a, c, 1.0, 0.2, progress=draw)
        ln(e, [(cx0, cy0), (cx0 + 300, cy0), (cx0 + 300, cy0 + 112), (cx0, cy0 + 112), (cx0, cy0)], 0.45 * a, c, 1.0,
           progress=draw)
        ln(e, [(cx0, cy0 - 3), (cx0 + 70, cy0 - 3)], 0.9 * a * draw, c, 2.2, 0.4)
        ta = a * smooth(tk + 0.1, tk + 0.3, t)
        tx(e, "TARGET" if sel else f"CANDIDATE {k + 1:02d}", cx0 + 78, cy0 - 4, 11, 0.7 * ta, c, "lm", MONO, 0.3)
        tx(e, name, cx0 + 16, cy0 + 28, 26, ta, WHT, "lm", "sans_m", 0.08)
        tx(e, f"{en}  ·  {cls}", cx0 + 16, cy0 + 56, 12, 0.75 * ta, HUD, "lm", MONO, 0.12)
        tx(e, f"{d:.2f}", cx0 + 16, cy0 + 88, 30, ta, c, "lm", "latin", 0.02)
        tx(e, "LY", cx0 + 96, cy0 + 93, 13, 0.7 * ta, HUD, "lm", MONO, 0.1)
        tx(e, "ETA @13c", cx0 + 284, cy0 + 78, 11, 0.6 * ta, DIM, "rm", MONO, 0.15)
        tx(e, f"{d * DAYS_PER_LY:.0f} 天", cx0 + 284, cy0 + 96, 18, 0.9 * ta, HUD, "rm", "sans_m", 0.05)
        if sel:                                                        # α Cen 三颗星的小标签
            sa = ta * (1 - smooth(C["switch"] - 0.2, C["switch"] + 0.2, t))
            for off, lab in ((np.zeros(3), "A"), (ACEN_B, "B"), (PROXIMA, "比邻星 PROXIMA")):
                qq = gc.project(self.star_pos(0) + self.axes @ off / LY_PER_UNIT)
                if qq:
                    tx(e, lab, qq[0] - 12, qq[1] + 18, 13, 0.75 * sa, AMB, "rm", "sans_m", 0.1)

    def route(self, gc, t, a):
        """航线：太阳 -> 半人马座 α 的琥珀色线，每光年一个刻度。"""
        a *= smooth(C["switch"], C["switch"] + 0.3, t) * (1 - self.shrink(t))
        if a <= 0.01:
            return
        e = self.e
        p0, p1 = self.sun, self.star_pos(0)
        la = a * (1 - smooth(C["lock"] - 0.4, C["lock"], t))           # 绕到太阳背后以后刻度挤在一起，只留刻线
        prog = ease_out_expo(lin(C["switch"] + 0.1, C["lock"] - 0.2, t))
        pts = [gc.project(p0 + (p1 - p0) * f) for f in np.linspace(0, 1, 24)]
        if any(p is None for p in pts):
            return
        ln(e, [p[:2] for p in pts], 0.8 * a, AMB, 1.2, 0.15, 1.2, progress=prog)
        for ly in range(1, 5):
            f = ly / STARS[0][3]
            if f <= prog:
                q = gc.project(p0 + (p1 - p0) * f)
                ln(e, [(q[0], q[1] - 6), (q[0], q[1] + 6)], 0.8 * a, AMB, 1.0)
                tx(e, f"{ly} LY", q[0], q[1] + 20, 11, 0.6 * la, AMB, "mm", MONO, 0.05)

    def lock_reticle(self, gc, t, a):
        """锁定：瞄准环在半人马座 α 上收拢、变琥珀色；两侧距离和航时，下方一行"光要走几年"。"""
        lock = smooth(C["lock"] - 0.05, C["lock"] + 0.25, t)
        a *= lock * (1 - self.shrink(t))
        if a <= 0.01:
            return
        q = gc.project(self.star_pos(0))
        if not q:
            return
        e, cx, cy = self.e, q[0], q[1]
        ring(e, cx, cy, 40, 0.5 * a, AMB, 1.0, 0.0, 120, 1.3)
        R = 100 + 30 * (1 - lock)
        rot = 0.35 * C["lock"]
        for j in range(3):
            a0 = rot + j * math.tau / 3
            ring(e, cx, cy, R, 0.65 * a, AMB, 1.3, 0.2, 60, 1.25, arc=(a0, a0 + math.radians(52)))
        for j in range(4):
            ang = math.pi / 4 + j * math.pi / 2
            rr = R + 24
            px, py = cx + rr * math.cos(ang), cy + rr * math.sin(ang)
            ux, uy = math.cos(ang), math.sin(ang)
            ln(e, [(px - uy * 6 + ux * 8, py + ux * 6 + uy * 8), (px, py), (px + uy * 6 + ux * 8, py - ux * 6 + uy * 8)], a,
               AMB, 1.3, 0.3, 1.5)
        tx(e, "半人马座 α", cx, cy - 180, 30, a, WHT, "mm", "sans_m", 0.1)
        tx(e, "ALPHA CENTAURI  ·  TARGET LOCKED", cx, cy - 148, 12, 0.8 * a, AMB, "mm", MONO, 0.3)
        # 读数都放右侧（航线从左下方伸过来）：一根竖线串起两组读数
        x = cx + R + 70
        darkspot(e, x + 110, cy, 380, 260, 0.5 * a)
        ln(e, [(x - 18, cy - 92), (x - 18, cy + 92)], 0.45 * a, AMB)
        for y, label, num, unit in ((cy - 46, "距离  DIST", f"{STARS[0][3]:.2f}", "光年  LY"),
                                    (cy + 46, "航时  ETA", f"{STARS[0][3] * DAYS_PER_LY:.0f}", "天  DAYS")):
            tx(e, label, x, y - 30, 13, 0.75 * a, HUD, "lm", "sans_m", 0.15)
            tx(e, num, x, y + 8, 50, a, WHT, "lm", "latin", 0.0, 1.1, layer="ui")
            tx(e, unit, x + 150, y + 18, 13, 0.75 * a, HUD, "lm", "sans_m", 0.15)
        la = a * smooth(C["eta"], C["eta"] + 0.4, t)
        tx(e, "光走完这段路要 4.37 年  ·  曲率航速 13 c", x - 18, cy + 135, 20, la, AMB, "lm", "sans_m", 0.08)

    def modes(self, t, a):
        """底部模式条：这一拍在干什么（代替人声）。"""
        modes = [(C["sun_mark"], "定位太阳系", "LOCATING SOL"),
                 (C["zoom"], "缩放至太阳邻域", "ZOOMING TO SOLAR NEIGHBORHOOD"),
                 (C["local"], "扫描近邻恒星 · 选择目的地", "SCANNING LOCAL STARS"),
                 (C["select"], "目的地：半人马座 α", "DESTINATION SELECTED"),
                 (C["switch"], "规划航线", "PLOTTING COURSE"),
                 (C["lock"], "目标锁定", "TARGET LOCKED"),
                 (C["engage"], "曲率引擎 · 准备就绪", "WARP DRIVE ARMED")]
        if t < modes[0][0]:
            return
        k = max(i for i, m in enumerate(modes) if t >= m[0])
        t0, zh, en = modes[k]
        sk = self.shrink(t)
        a *= (1 - sk) * smooth(t0, t0 + 0.12, t)
        if a <= 0.01:
            return
        e = self.e
        warm = k >= 5
        y = 1000
        tx(e, zh[:type_in(t, t0 + 0.05, len(zh), 40)], W / 2, y, 26, a, AMB if warm else WHT, "mm", "sans_m", 0.18)
        tx(e, en, W / 2, y + 32, 11, 0.6 * a, AMB if warm else HUD, "mm", MONO, 0.45)
        half = 26 * len(zh) * 0.62 + 40
        c = AMB if warm else HUD
        for s in (-1, 1):
            ln(e, [(W / 2 + s * half, y), (W / 2 + s * (half + 120), y)], 0.45 * a, c)
            ln(e, [(W / 2 + s * (half + 120), y - 5), (W / 2 + s * (half + 120), y + 5)], 0.6 * a, c)
