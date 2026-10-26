# -*- coding: utf-8 -*-
"""开场的飞船 HUD（第三版，替换 navhud.py / spacehud.py 那一版）。两部分，同一套视觉语言：

  BridgeHUD   舰桥第一人称平视显示（0 秒 -> C["handoff"]）：
              开机自检 -> 扫描近邻恒星（扫描线扫过，逐颗打上标记）-> 光标逐颗比对候选星（数据卡：名字、光谱型、距离、
              按 13 倍光速算的航时）-> 选定半人马座 α -> 规划航线（空中一串"航道框"伸向目标 + 右下角立体星图画出航线）
              -> 锁定（距离 / 航时 / 光要走几年）-> 曲率引擎就绪 -> 整个 HUD 收起，镜头离开舰桥。
  遥测函数     第三人称（镜头离开舰桥以后）：曲率场充能面板、超光速航速（越过 1 c 时
              提示"光障突破"）与底部航程条、脱离曲率、抵达时挂在恒星上的标签。

信息靠画面讲（无人声版）：底部"模式条"用一行中文说清这一拍在干什么；读数都是真实数字；细刻度、小字清单只做质感。
视觉语言：冰蓝白发丝线（1~1.5 像素）+ 等宽小字；青色表示"进行中"，琥珀色只给目标与航线；不用色块、圆角卡片、舷窗框。
≤30 像素的字走清晰文字层（scenes.setup_renderer 里 ui_text_max=30），不受泛光和色差影响。
所有元素只依赖 t（可任意跳帧）。时刻全部来自 cues.C。"""
import math
import numpy as np
from opusvid.gl import smooth, lin, ease_out_expo, W, H
from cues import C
from wfx import MONO, vis, ring, bodies

HUD = (0.62, 0.86, 1.0)       # 主线条、读数
DIM = (0.30, 0.44, 0.56)      # 未激活的刻度
ACC = (0.35, 0.92, 1.0)       # 进行中
AMB = (1.0, 0.70, 0.32)       # 目标、航线、锁定
WHT = (0.94, 0.97, 1.0)       # 重点数字
WARP_C = 13.0                 # 巡航时的光速倍数（4.37 光年约 4 个月）
DAYS_PER_LY = 365.25 / WARP_C

# 真实的近邻恒星：(中文名, 英文名, 光谱型, 距离/光年, 赤经 时/分, 赤纬 度/分, 舰桥视野里的方位 偏航°/俯仰°)
# 视野里的方位是镜头语言上的安排（正前方是半人马座 α），右下角星图用真实的赤经赤纬换算成银道坐标。
STARS = [
    ("半人马座 α", "ALPHA CENTAURI", "G2V", 4.37, (14, 39.6), (-60, 50.0), (0.0, 0.0)),
    ("巴纳德星", "BARNARD'S STAR", "M4V", 5.96, (17, 57.8), (4, 41.6), (19.0, -9.0)),
    ("沃尔夫 359", "WOLF 359", "M6V", 7.86, (10, 56.5), (7, 0.9), (29.0, 11.0)),
    ("拉兰德 21185", "LALANDE 21185", "M2V", 8.31, (11, 3.3), (35, 58.2), (9.0, 15.0)),
    ("天狼星", "SIRIUS", "A1V", 8.60, (6, 45.1), (-16, 43.0), (-24.0, 8.0)),
    ("鲸鱼座 UV", "LUYTEN 726-8", "M5V", 8.73, (1, 39.0), (-17, 57.0), (25.0, 3.0)),
    ("罗斯 154", "ROSS 154", "M3V", 9.69, (18, 49.8), (-23, 50.2), (-31.0, -5.0)),
    ("罗斯 248", "ROSS 248", "M5V", 10.3, (23, 41.9), (44, 10.5), (-34.0, 15.0)),
    ("天苑四", "EPSILON ERIDANI", "K2V", 10.47, (3, 32.9), (-9, 27.5), (-13.0, -12.0)),
    ("拉卡伊 9352", "LACAILLE 9352", "M0V", 10.7, (23, 5.9), (-35, 51.2), (33.0, -14.0)),
    ("南河三", "PROCYON", "F5IV", 11.46, (7, 39.3), (5, 13.5), (-6.0, 17.0)),
]
CANDS = [4, 1, 8, 0]          # 光标依次停在：天狼星、巴纳德星、天苑四 -> 半人马座 α（对应 C["cands"] 和 C["select"]）
# 赤道坐标 J2000 -> 银道坐标
_EQ2GAL = np.array([[-0.0548755604, -0.8734370902, -0.4838350155],
                    [0.4941094279, -0.4448296300, 0.7469822445],
                    [-0.8676661490, -0.1980763734, 0.4559837762]])


def _galactic(ra, dec, d):
    a = math.radians((ra[0] + ra[1] / 60) * 15)
    s = 1 if dec[0] >= 0 else -1
    b = math.radians(dec[0] + s * dec[1] / 60)
    return _EQ2GAL @ np.array([math.cos(b) * math.cos(a), math.cos(b) * math.sin(a), math.sin(b)]) * d


# ---------------------------------------------------------------------- 基本笔触
def ln(e, pts, a, c=HUD, w=1.1, glow=0.0, k=1.1, **kw):
    """HUD 的发丝线。默认不加光晕、亮度压在泛光阈值以下，否则会被泛光晕成粗粗的金属条；重点元素自己传 glow。"""
    if a > 0.003:
        e.line(pts, w, c, a, glow=glow, intensity=k, **kw)


def tx(e, s, x, y, size, a, c=HUD, anchor="lm", font=MONO, track=0.12, k=1.25, **kw):
    if a > 0.003:
        e.text(s, x, y, size, font, c, a, anchor, track, k, **kw)


def corner(e, x, y, sx, sy, L, a, c=HUD, w=1.2):
    """一个 L 形取景角（sx, sy 为 ±1，表示两条边伸出去的方向）。"""
    ln(e, [(x + sx * L, y), (x, y), (x, y + sy * L)], a, c, w)


def box_corners(e, x0, y0, x1, y1, a, c=HUD, L=None, w=1.3):
    L = L if L is not None else 0.22 * min(x1 - x0, y1 - y0)
    for x, sx in ((x0, 1), (x1, -1)):
        for y, sy in ((y0, 1), (y1, -1)):
            corner(e, x, y, sx, sy, L, a, c, w)


def proj(cam, p):
    q = cam.project(tuple(float(v) for v in p))
    return q if q and q[2] > 0.25 else None


def seg3d(e, cam, pts, a, c=HUD, w=1.1, glow=0.0, k=1.1):
    """三维折线投影到屏幕；跨过镜头近处的部分断开，不画。"""
    run = []
    for p in list(pts) + [None]:
        q = proj(cam, p) if p is not None else None
        if q is not None:
            run.append(q[:2])
        else:
            if len(run) > 1:
                ln(e, run, a, c, w, glow, k)
            run = []


def type_in(t, t0, n, cps=60.0):
    """打字机效果：t0 起每秒 cps 个字，返回已打出的字数。"""
    return max(0, min(n, int((t - t0) * cps)))


# ---------------------------------------------------------------------- 舰桥第一人称平视显示
class BridgeHUD:
    """舰桥视角的 HUD。render(t, cam, sky) 先画真实星空（sky(cam)），再叠 HUD；lock_bracket 是锁定后挂在真实 α A 上的
    琥珀色取景框，镜头离开舰桥、往后拉开时还跟着它，充能开始后消失。"""

    def __init__(self, e):
        self.e = e
        self.gal = [_galactic(s[4], s[5], s[3]) for s in STARS]

    # ---------------- 时间线
    @staticmethod
    def power(t):
        """开机 0 -> 1（0.5 秒），C["collapse"] 起收起。"""
        return smooth(C["warp"], C["warp"] + 0.5, t) * (1 - smooth(C["collapse"], C["handoff"] - 0.1, t))

    @staticmethod
    def shrink(t):
        """收起时整个 HUD 往画面中心收拢的程度 0..1。"""
        return ease_out_expo(lin(C["collapse"], C["handoff"], t))

    def sky_dir(self, i):
        yaw, pitch = (math.radians(v) for v in STARS[i][6])
        # 舰桥镜头朝 +z 看，屏幕右方是世界 -x
        return np.array([-math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])

    def sky_xy(self, cam, i, target):
        """第 i 颗星在屏幕上的位置。半人马座 α 就是真实的目标恒星 α A。"""
        if i == 0:
            q = proj(cam, target)
        else:
            q = proj(cam, np.asarray(cam.eye) + self.sky_dir(i) * 5000.0)
        return q[:2] if q else None

    def render(self, t, cam, sky, target):
        e = self.e
        sky(cam)
        # 星图里的这些恒星在真实天空里也是看得见的亮星（天狼星最亮）
        pts = []
        for i in range(1, len(STARS)):
            q = self.sky_xy(cam, i, target)
            if q:
                br = 1.6 if STARS[i][1] == "SIRIUS" else 0.75 + 0.25 * (STARS[i][2][0] in "AFGK")
                pts.append((q[0], q[1], 1.6 + 0.5 * br, 0.55 * br, (0.85, 0.92, 1.0), 0.4))
        bodies(e, pts)
        on = self.power(t)
        if on <= 0.002:
            return
        self.frame(t, on)
        self.scan(cam, t, on, target)
        self.cursor(cam, t, on, target)
        self.corridor(cam, t, on)
        self.starmap(t, on)
        self.reticle(cam, t, on, target)
        self.mode_strip(t, on)

    # ---------------- 视野框架：四角、航向带、两侧刻度带、自检清单
    def frame(self, t, on):
        e = self.e
        sk = self.shrink(t)
        boot = smooth(C["warp"] + 0.1, C["warp"] + 0.7, t)
        # 开机：中线从中心向两侧展开
        hl = ease_out_expo(lin(C["warp"], C["warp"] + 0.45, t)) * (1 - smooth(C["warp"] + 0.5, C["warp"] + 1.0, t))
        if hl > 0.01:
            ln(e, [(W / 2 - 900 * hl, H / 2), (W / 2 + 900 * hl, H / 2)], 0.8 * on, ACC, 1.2, 0.8, 2.0)
        # 收起：一道亮线横过中心
        cl = math.sin(math.pi * lin(C["collapse"], C["handoff"], t)) if t > C["collapse"] else 0.0
        if cl > 0.01:
            ln(e, [(W / 2 - 800 * (1 - sk), H / 2), (W / 2 + 800 * (1 - sk), H / 2)], cl, ACC, 1.4, 1.0, 2.4)
        a = on * boot
        m = 78 + (W / 2 - 300) * sk                                    # 四角随收起往中心靠
        mv = 74 + (H / 2 - 120) * sk
        for x, sx in ((m, 1), (W - m, -1)):
            for y, sy in ((mv, 1), (H - mv, -1)):
                corner(e, x, y, sx, sy, 58, 0.85 * a)
                corner(e, x + sx * 10, y + sy * 10, sx, sy, 14, 0.35 * a, DIM, 1.0)
        if sk > 0.5:
            return
        a *= 1 - 2 * sk
        self.heading_tape(t, a)
        self.side_tapes(t, a)
        self.checklist(t, a)
        # 舷侧小字：坐标、时间码，只做质感
        tx(e, "ISV-07  BRIDGE HUD", 100, 118, 13, 0.55 * a, DIM, "lm", MONO, 0.25)
        tx(e, f"T+{t:06.2f}", W - 100, 118, 13, 0.55 * a, DIM, "rm", MONO, 0.15)

    def heading_tape(self, t, a):
        """顶部航向带：银经。中心 316°（半人马座 α 的银经 315.7°）；光标比对候选星时，一个小三角标出它的方位。"""
        e = self.e
        cx, y, half = W / 2, 66, 330
        value = 315.7
        ppd = half / 30.0
        for deg in range(int(value - 32) // 5 * 5, int(value + 33), 5):
            x = cx + (deg - value) * ppd
            if abs(x - cx) > half:
                continue
            edge = 1 - smooth(half * 0.7, half, abs(x - cx))
            major = deg % 15 == 0
            ln(e, [(x, y), (x, y + (11 if major else 6))], a * edge * (0.85 if major else 0.45), HUD, 1.0, 0.0)
            if major:
                tx(e, f"{deg % 360:03d}", x, y + 25, 13, a * edge * 0.75, HUD, "mm", MONO, 0.05)
        ln(e, [(cx - half, y), (cx + half, y)], 0.3 * a, HUD, 1.0, 0.0)
        ln(e, [(cx - 7, y - 11), (cx, y - 3), (cx + 7, y - 11)], a, ACC, 1.3)
        tx(e, "HDG  GAL-L", cx - half - 18, y + 6, 12, 0.55 * a, DIM, "rm", MONO, 0.2)
        # 候选星的方位标记
        k, u = self.cursor_state(t)
        if k is not None:
            yaw = STARS[CANDS[k]][6][0] if u >= 1 else (STARS[CANDS[max(k - 1, 0)]][6][0] * (1 - u) + STARS[CANDS[k]][6][0] * u)
            x = cx + yaw * ppd
            c = AMB if CANDS[k] == 0 and u >= 1 else ACC
            ln(e, [(x - 6, y + 22), (x, y + 13), (x + 6, y + 22), (x - 6, y + 22)], a, c, 1.2)

    def side_tapes(self, t, a):
        """左：航速（光速倍数，舰桥上是 0；读出航时后标出 13 c 的巡航目标）。右：到所选恒星的距离（光年）。"""
        e = self.e
        y0, y1 = 290, 700
        # 左侧航速带
        x = 150
        for i in range(16):
            y = y1 - (y1 - y0) * i / 15
            major = i % 5 == 0
            ln(e, [(x, y), (x + (14 if major else 7), y)], a * (0.8 if major else 0.4), HUD, 1.0, 0.0)
            if major:
                tx(e, f"{i:d}", x - 10, y, 13, 0.7 * a, HUD, "rm", MONO, 0.0)
        ln(e, [(x, y0), (x, y1)], 0.3 * a, HUD, 1.0, 0.0)
        tx(e, "VEL  c", x, y0 - 24, 12, 0.6 * a, DIM, "mm", MONO, 0.2)
        ln(e, [(x + 26, y1 - 7), (x + 18, y1), (x + 26, y1 + 7)], a, ACC, 1.3)
        tx(e, "0.00", x + 34, y1, 15, 0.9 * a, WHT, "lm", MONO, 0.05)
        wa = a * smooth(C["eta"], C["eta"] + 0.4, t)
        if wa > 0.01:
            yw = y1 - (y1 - y0) * WARP_C / 15
            ln(e, [(x - 4, yw), (x + 40, yw)], wa, AMB, 1.2, 0.4, 1.8, dash=6.0)
            tx(e, "WARP 13.0", x + 46, yw, 14, wa, AMB, "lm", MONO, 0.1)
        # 右侧距离带：0..12 光年，光标停在哪颗星，箭头就滑到它的距离
        x = W - 150
        for i in range(13):
            y = y1 - (y1 - y0) * i / 12
            major = i % 2 == 0
            ln(e, [(x, y), (x - (14 if major else 7), y)], a * (0.8 if major else 0.4), HUD, 1.0, 0.0)
            if major:
                tx(e, f"{i:d}", x + 10, y, 13, 0.7 * a, HUD, "lm", MONO, 0.0)
        ln(e, [(x, y0), (x, y1)], 0.3 * a, HUD, 1.0, 0.0)
        tx(e, "RNG  LY", x, y0 - 24, 12, 0.6 * a, DIM, "mm", MONO, 0.2)
        k, u = self.cursor_state(t)
        if k is not None:
            d0 = STARS[CANDS[max(k - 1, 0)]][3] if k > 0 else STARS[CANDS[0]][3]
            d = d0 + (STARS[CANDS[k]][3] - d0) * u
            y = y1 - (y1 - y0) * d / 12
            c = AMB if CANDS[k] == 0 and u >= 1 else ACC
            ln(e, [(x - 26, y - 7), (x - 18, y), (x - 26, y + 7)], a, c, 1.3)
            tx(e, f"{d:5.2f}", x - 34, y, 15, 0.95 * a, WHT, "rm", MONO, 0.05)

    def checklist(self, t, a):
        """左下自检清单：开机时逐行打出，引擎就绪时最后一行变成 ARMED。"""
        e = self.e
        rows = [("REACTOR CORE", "NOMINAL"), ("FIELD COILS", "STANDBY"), ("NAV COMPUTER", "ONLINE"),
                ("STAR CATALOG", "2 187"), ("WARP DRIVE", "STANDBY")]
        x, y = 100, 868
        tx(e, "SYS CHECK", x, y - 30, 12, 0.6 * a, DIM, "lm", MONO, 0.3)
        ln(e, [(x, y - 16), (x + 330, y - 16)], 0.3 * a, HUD, 1.0, 0.0)
        for i, (name, val) in enumerate(rows):
            t0 = C["warp"] + 0.3 + 0.18 * i
            if t < t0:
                break
            armed = i == 4 and t >= C["engage"]
            s = f"{name:<13}{'.' * 6} {'ARMED' if armed else val}"
            n = type_in(t, t0, len(s), 90)
            tx(e, s[:n], x, y + 22 * i, 14, 0.85 * a, AMB if armed else HUD, "lm", MONO, 0.05)

    # ---------------- 扫描线：扫过时给近邻恒星逐颗打上标记
    def scan(self, cam, t, on, target):
        e = self.e
        t0, t1 = C["warp"] + 0.9, C["cands"][0] - 0.1
        xs = 60 + (W - 120) * ease_out_expo(lin(t0, t1, t)) if t < t1 + 0.4 else None
        if xs is not None and t0 < t:
            sa = on * (1 - smooth(t1, t1 + 0.4, t))
            ln(e, [(xs, 150), (xs, H - 150)], 0.5 * sa, ACC, 1.0, 0.25, 1.3)
        fade = on * (1 - smooth(C["switch"], C["switch"] + 0.5, t))
        for i in range(len(STARS)):
            q = self.sky_xy(cam, i, target)
            if q is None:
                continue
            # 扫描线按 ease_out_expo 减速移动：反推它扫过这颗星的时刻，扫到才打上标记
            f = min(max((q[0] - 60) / (W - 120), 0.0), 0.999)
            tagged = smooth(0.0, 0.25, t - (t0 + (t1 - t0) * (-math.log2(1 - f) / 10)))
            a = tagged * fade
            if a <= 0.01:
                continue
            sel = i in CANDS
            c = HUD if not (i == 0 and t >= C["select"]) else AMB
            r = 7 if sel else 5
            ln(e, [(q[0], q[1] - r), (q[0] + r, q[1]), (q[0], q[1] + r), (q[0] - r, q[1]), (q[0], q[1] - r)],
               a * (0.75 if sel else 0.45), c, 1.0, 0.3)
            if i != 0:
                tx(e, STARS[i][1], q[0] + 12, q[1] - 10, 12, a * 0.55, HUD, "lm", MONO, 0.12)

    # ---------------- 比对候选星：取景光标 + 数据卡
    @staticmethod
    def cursor_state(t):
        """(第几颗候选, 移向它的进度 0..1)。光标在每个卡点前 0.3 秒开始移动，卡点时刚好到位。"""
        times = list(C["cands"]) + [C["select"]]
        if t < times[0] - 0.4 or t > C["lock"]:
            return None, 0.0
        k = 0
        for i, x in enumerate(times):
            if t >= x - 0.3:
                k = i
        u = 1.0 if k == 0 else ease_out_expo(lin(times[k] - 0.3, times[k], t))
        return k, u

    def cursor(self, cam, t, on, target):
        e = self.e
        k, u = self.cursor_state(t)
        if k is None or t > C["switch"] + 0.6:
            return
        a = on * smooth(C["cands"][0] - 0.4, C["cands"][0] - 0.1, t) * (1 - smooth(C["switch"], C["switch"] + 0.5, t))
        p1 = self.sky_xy(cam, CANDS[k], target)
        p0 = self.sky_xy(cam, CANDS[k - 1], target) if k > 0 else p1
        if p1 is None or p0 is None:
            return
        x, y = p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u
        target_sel = CANDS[k] == 0 and u >= 1
        c = AMB if target_sel else ACC
        s = 26 + 10 * (1 - u)
        for sx_, sy_ in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            corner(e, x + sx_ * s, y + sy_ * s, -sx_, -sy_, 9, a, c, 1.4)
        if u < 1:
            return
        # 数据卡：贴在光标一侧，到位后描边画出、文字打出
        i = CANDS[k]
        name, en, cls, d = STARS[i][0], STARS[i][1], STARS[i][2], STARS[i][3]
        tk = (list(C["cands"]) + [C["select"]])[k]
        right = x < W - 520
        gap = 170 if abs(x - W / 2) < 200 and abs(y - H / 2) < 200 else 54     # 避开中央瞄准环
        cx0 = x + gap if right else x - gap - 300
        cy0 = y - 64
        draw = ease_out_expo(lin(tk, tk + 0.35, t))
        lead = [(x + (s if right else -s), y), (cx0 if right else cx0 + 300, cy0 + 20)]
        ln(e, lead, 0.6 * a, c, 1.0, 0.2, progress=draw)
        rect = [(cx0, cy0), (cx0 + 300, cy0), (cx0 + 300, cy0 + 112), (cx0, cy0 + 112), (cx0, cy0)]
        ln(e, rect, 0.45 * a, c, 1.0, 0.0, progress=draw)
        ln(e, [(cx0, cy0 - 3), (cx0 + 70, cy0 - 3)], 0.9 * a * draw, c, 2.2, 0.4)
        ta = a * smooth(tk + 0.1, tk + 0.3, t)
        tx(e, "TARGET" if target_sel else f"CANDIDATE {k + 1:02d}", cx0 + 78, cy0 - 4, 11, 0.7 * ta, c, "lm", MONO, 0.3)
        tx(e, name, cx0 + 16, cy0 + 28, 26, ta, WHT, "lm", "sans_m", 0.08)
        tx(e, f"{en}  ·  {cls}", cx0 + 16, cy0 + 56, 12, 0.75 * ta, HUD, "lm", MONO, 0.12)
        tx(e, f"{d:.2f}", cx0 + 16, cy0 + 88, 30, ta, c, "lm", "latin", 0.02)
        tx(e, "LY", cx0 + 96, cy0 + 93, 13, 0.7 * ta, HUD, "lm", MONO, 0.1)
        tx(e, "ETA @13c", cx0 + 284, cy0 + 78, 11, 0.6 * ta, DIM, "rm", MONO, 0.15)
        tx(e, f"{d * DAYS_PER_LY:.0f} 天", cx0 + 284, cy0 + 96, 18, 0.9 * ta, HUD, "rm", "sans_m", 0.05)

    # ---------------- 航道框：规划航线时一串取景框沿航线伸向目标
    def corridor(self, cam, t, on):
        e = self.e
        a = on * smooth(C["switch"], C["switch"] + 0.3, t)
        if a <= 0.01:
            return
        locked = smooth(C["lock"], C["lock"] + 0.3, t)
        a *= 1 - 0.7 * locked
        eye = np.asarray(cam.eye)
        zs = [58.0, 92.0, 150.0, 245.0]
        for j, z in enumerate(zs):
            aj = a * smooth(0.0, 0.25, t - (C["switch"] + 0.12 * j))
            if aj <= 0.01:
                continue
            cx, cy = eye[0], eye[1] - 0.15
            hw, hh = 6.4, 3.6
            pts = [(cx - hw, cy - hh, z), (cx + hw, cy - hh, z), (cx + hw, cy + hh, z), (cx - hw, cy + hh, z)]
            q = [proj(cam, p) for p in pts]
            if None in q:
                continue
            x0, x1 = min(p[0] for p in q), max(p[0] for p in q)
            y0, y1 = min(p[1] for p in q), max(p[1] for p in q)
            c = tuple(np.array(ACC) * (1 - locked) + np.array(AMB) * locked)
            fade = 1 - 0.6 * j / len(zs)
            box_corners(e, x0, y0, x1, y1, aj * 0.65 * fade, c, 0.14 * (x1 - x0), 1.0)
            if j < 3:
                tx(e, f"{j + 1:d} LY", x1 + 6, y0, 11, aj * 0.55 * fade, c, "lm", MONO, 0.1)

    # ---------------- 右下角立体星图：近邻恒星的真实位置，航线从太阳画到半人马座 α
    def starmap(self, t, on):
        e = self.e
        a = on * smooth(C["switch"], C["switch"] + 0.4, t)
        if a <= 0.01:
            return
        x0, y0, x1, y1 = 1290, 730, 1820, 1010
        cx, cy, k = (x0 + x1) / 2 + 20, (y0 + y1) / 2 + 22, 10.5
        draw = ease_out_expo(lin(C["switch"], C["switch"] + 0.5, t))
        box_corners(e, x0, y0, x1, y1, 0.7 * a, HUD, 14, 1.2)
        tx(e, "STELLAR CARTOGRAPHY  ·  r 12 LY", x0 + 14, y0 + 18, 12, 0.6 * a, DIM, "lm", MONO, 0.2)
        ln(e, [(x0 + 14, y0 + 32), (x0 + 14 + 260 * draw, y0 + 32)], 0.3 * a, HUD, 1.0, 0.0)
        yaw = 0.9 + 0.16 * (t - C["switch"])
        el = math.radians(58)

        def P(v):
            x, y, z = v
            c, s = math.cos(yaw), math.sin(yaw)
            x1_, y1_ = x * c - y * s, x * s + y * c
            return cx + k * x1_, cy - k * (z * math.cos(el) + y1_ * math.sin(el))
        for r in (5.0, 10.0):                                       # 银道面上的 5、10 光年圈
            pts = [P((r * math.cos(f), r * math.sin(f), 0.0)) for f in np.linspace(0, math.tau, 72)]
            ln(e, pts, 0.28 * a, HUD, 1.0, 0.0, progress=draw)
        tx(e, "5", P((5.0, 0.0, 0.0))[0] + 4, P((5.0, 0.0, 0.0))[1], 11, 0.4 * a, DIM, "lm", MONO, 0.0)
        tx(e, "10", P((10.0, 0.0, 0.0))[0] + 4, P((10.0, 0.0, 0.0))[1], 11, 0.4 * a, DIM, "lm", MONO, 0.0)
        sol = P((0.0, 0.0, 0.0))
        e.circle(sol[0], sol[1], 3.0, fill=WHT, fill_a=a, glow=4, intensity=1.8)
        tx(e, "SOL", sol[0] + 8, sol[1] + 10, 11, 0.7 * a, HUD, "lm", MONO, 0.15)
        for i, g in enumerate(self.gal):
            p, base = P(g), P((g[0], g[1], 0.0))
            ln(e, [base, p], 0.25 * a * draw, HUD, 1.0, 0.0)                 # 到银道面的垂线
            c = AMB if i == 0 else HUD
            e.circle(p[0], p[1], 2.6 if i == 0 else 1.8, fill=c, fill_a=a * draw, glow=3, intensity=1.6)
            if i == 0:
                tx(e, "α CEN", p[0] + 8, p[1] - 9, 12, 0.9 * a * draw, c, "lm", MONO, 0.12)
        # 航线：太阳 -> 半人马座 α，每光年一个刻度
        rp = ease_out_expo(lin(C["switch"] + 0.4, C["lock"] - 0.3, t))
        if rp > 0:
            g = self.gal[0]
            ln(e, [sol, P(g)], a, AMB, 1.5, 0.3, 1.6, progress=rp)
            for ly in range(1, 5):
                f = ly / STARS[0][3]
                if f <= rp:
                    p = P(g * f)
                    ln(e, [(p[0] - 3, p[1] - 3), (p[0] + 3, p[1] + 3)], 0.8 * a, AMB, 1.0, 0.0)
            tx(e, "4.37 LY", x1 - 16, y1 - 18, 13, a * smooth(0.9, 1.0, rp), AMB, "rm", MONO, 0.12)

    # ---------------- 中央瞄准环：平时慢转；锁定时三段弧收拢、变琥珀色，两侧出现距离和航时
    def reticle(self, cam, t, on, target):
        e = self.e
        q = proj(cam, target)
        cx, cy = (q[0], q[1]) if q else (W / 2, H / 2)
        sk = self.shrink(t)
        a = on * smooth(C["warp"] + 0.3, C["warp"] + 0.9, t) * (1 - sk)
        if a <= 0.01:
            return
        lock = smooth(C["lock"] - 0.05, C["lock"] + 0.2, t)
        c = tuple(np.array(HUD) * (1 - lock) + np.array(AMB) * lock)
        g = 7                                                       # 中心十字：留空的四段短线
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ln(e, [(cx + dx * g, cy + dy * g), (cx + dx * (g + 9), cy + dy * (g + 9))], 0.8 * a, c, 1.2, 0.3)
        ring(e, cx, cy, 40, 0.45 * a, c, 1.0, 0.0, 120, 1.3)
        for ang in (0, 90, 180, 270):
            r = math.radians(ang)
            ln(e, [(cx + 40 * math.cos(r), cy + 40 * math.sin(r)), (cx + 48 * math.cos(r), cy + 48 * math.sin(r))],
               0.6 * a, c, 1.0, 0.0)
        # 外圈三段弧：锁定前慢转，锁定时半径收拢、转速停下
        R = 120 - 18 * lock + 30 * (1 - smooth(C["warp"] + 0.3, C["warp"] + 1.0, t))
        rot = 0.35 * min(t, C["lock"]) + 0.35 * (t - C["lock"]) * (1 - lock) * (t > C["lock"])
        for j in range(3):
            a0 = rot + j * math.tau / 3
            ring(e, cx, cy, R, 0.6 * a, c, 1.3, 0.2, 60, 1.25, arc=(a0, a0 + math.radians(52)))
        if lock > 0.01:
            for j in range(4):                                       # 四个三角从外面收进来
                ang = math.pi / 4 + j * math.pi / 2
                rr = R + 24 + 40 * (1 - lock)
                px, py = cx + rr * math.cos(ang), cy + rr * math.sin(ang)
                ux, uy = math.cos(ang), math.sin(ang)
                vx, vy = -uy, ux
                ln(e, [(px + vx * 6 + ux * 8, py + vy * 6 + uy * 8), (px, py), (px - vx * 6 + ux * 8, py - vy * 6 + uy * 8)],
                   a * lock, AMB, 1.3, 0.3, 1.5)
        # 锁定读数：左边距离，右边航时；上面目标名，下面"光要走几年"（无人声版里的超光速钩子）
        ra = a * smooth(C["lock"], C["lock"] + 0.3, t)
        if ra > 0.01:
            tx(e, "半人马座 α", cx, cy - 190, 30, ra, WHT, "mm", "sans_m", 0.1)
            tx(e, "ALPHA CENTAURI  ·  TARGET LOCKED", cx, cy - 158, 12, 0.8 * ra, AMB, "mm", MONO, 0.3)
            for side, label, num, unit in ((-1, "距离  DIST", "4.37", "光年 LY"),
                                           (1, "航时  ETA", f"{STARS[0][3] * DAYS_PER_LY:.0f}", "天 DAYS")):
                x = cx + side * 330
                anc = "rm" if side < 0 else "lm"
                tx(e, label, x, cy - 46, 13, 0.75 * ra, HUD, anc, "sans_m", 0.15)
                tx(e, num, x, cy + 6, 64, ra, WHT, anc, "latin", 0.0, 1.1, layer="ui")
                tx(e, unit, x, cy + 52, 13, 0.75 * ra, HUD, anc, "sans_m", 0.15)
                ln(e, [(x - side * 0, cy - 64), (x - side * 150, cy - 64)], 0.35 * ra, HUD, 1.0, 0.0)
            la = a * smooth(C["eta"], C["eta"] + 0.4, t)
            tx(e, "光走完这段路要 4.37 年  ·  曲率航速 13 c", cx, cy + 190, 22, la, AMB, "mm", "sans_m", 0.08)

    # ---------------- 底部模式条：这一拍在干什么（代替人声）
    def mode_strip(self, t, on):
        e = self.e
        modes = [(C["warp"], "系统启动 · 导航上线", "SYSTEMS ONLINE · NAVIGATION"),
                 (C["cands"][0] - 0.3, "扫描近邻恒星 · 选择目的地", "SCANNING LOCAL STARS"),
                 (C["select"], "目的地：半人马座 α", "DESTINATION SELECTED"),
                 (C["switch"], "规划航线", "PLOTTING COURSE"),
                 (C["lock"], "目标锁定", "TARGET LOCKED"),
                 (C["engage"], "曲率引擎 · 准备就绪", "WARP DRIVE ARMED")]
        k = max(i for i, m in enumerate(modes) if t >= m[0] or i == 0)
        t0, zh, en = modes[k]
        sk = self.shrink(t)
        a = on * smooth(C["warp"] + 0.4, C["warp"] + 0.8, t) * (1 - sk) * smooth(t0, t0 + 0.12, t)
        c = AMB if k >= 4 else HUD
        y = 1000
        n = type_in(t, t0 + 0.05, len(zh), 40)
        tx(e, zh[:n], W / 2, y, 26, a, WHT if k < 4 else AMB, "mm", "sans_m", 0.18)
        tx(e, en, W / 2, y + 32, 11, 0.6 * a, c, "mm", MONO, 0.45)
        half = 26 * len(zh) * 0.62 + 40
        for s in (-1, 1):
            ln(e, [(W / 2 + s * half, y), (W / 2 + s * (half + 120), y)], 0.45 * a, c, 1.0, 0.0)
            ln(e, [(W / 2 + s * (half + 120), y - 5), (W / 2 + s * (half + 120), y + 5)], 0.6 * a, c, 1.0, 0.0)

    # ---------------- 锁定框：从锁定起挂在真实的 α A 上，镜头离开舰桥后跟着它，充能开始后消失
    def lock_bracket(self, t, cam, target):
        a = vis(t, C["collapse"], C["charge"] + 0.6, 0.2, 0.6)
        if a <= 0.01:
            return
        q = proj(cam, target)
        if q is None:
            return
        s = 18 + 10 * pulse_down(t, C["handoff"])
        box_corners(self.e, q[0] - s, q[1] - s, q[0] + s, q[1] + s, a, AMB, 7, 1.4)
        tx(self.e, "α CEN", q[0] + s + 8, q[1] - s, 12, 0.8 * a, AMB, "lm", MONO, 0.2)


def pulse_down(t, t0, dur=0.6):
    """t0 起从 1 平滑降到 0。"""
    return 1 - smooth(t0, t0 + dur, t)


# ---------------------------------------------------------------------- 第三人称遥测
def charge_panel(e, t, level, flash, rpm):
    """右上：曲率场发生器。大号百分比 + 32 格斜切分段条 + 两行读数 + 一段随充能变强的场强波形。"""
    a = vis(t, C["charge"] + 0.5, C["distort"] + 0.6, 0.5, 0.6)
    if a <= 0.01:
        return
    x0, x1, y0 = W - 640, W - 90, 92
    box_corners(e, x0 - 20, y0 - 22, x1 + 14, y0 + 236, 0.55 * a, HUD, 16, 1.2)
    tx(e, "曲率场发生器", x0, y0 + 8, 24, a, WHT, "lm", "sans_m", 0.12)
    tx(e, "WARP FIELD GENERATOR", x0, y0 + 38, 12, 0.6 * a, HUD, "lm", MONO, 0.3)
    full = level >= 1
    c = WHT if full else ACC
    tx(e, f"{int(round(level * 100)):d}", x1 - 34, y0 + 24, 76, a, c, "rm", "latin", 0.0, 1.1 + 0.8 * flash, layer="ui")
    tx(e, "%", x1, y0 + 38, 26, 0.8 * a, c, "rm", "latin", 0.0)
    for i in range(32):                                              # 斜切分段条
        on = level * 32 > i
        xa = x0 + i * 17
        pts = [(xa, y0 + 96), (xa + 11, y0 + 96), (xa + 7, y0 + 112), (xa - 4, y0 + 112), (xa, y0 + 96)]
        ln(e, pts, a * (0.95 if on else 0.22), ACC if on else DIM, 1.1, 0.15 if on else 0.0, 1.25 + flash if on else 1.0)
    rows = (("环转速  RING", f"{rpm * 9.55:6.0f} rpm"), ("场强  FIELD", f"{level * 100:6.1f} %"))
    for i, (k, v) in enumerate(rows):
        y = y0 + 142 + 24 * i
        tx(e, k, x0, y, 15, 0.75 * a, HUD, "lm", "sans_m", 0.1)
        tx(e, v, x1, y, 15, 0.9 * a, WHT, "rm", MONO, 0.05)
    # 场强波形：振幅、频率随充能升高
    pts = []
    for j in range(140):
        u = j / 139
        amp = 4 + 18 * level
        val = (math.sin(u * (8 + 20 * level) * math.pi + t * 9) * 0.7 + math.sin(u * 37 + t * 23) * 0.3) * amp
        pts.append((x0 + (x1 - x0) * u, y0 + 210 + val * math.sin(math.pi * u)))
    ln(e, pts, 0.55 * a, ACC, 1.0, 0.0, 1.15)


def velocity(t):
    """超光速读数（光速倍数）：追上飞船后从 0 升到 1（C["hud_lightcross"] 正好越过光速），再冲到 13；最后一冲时降到 0。"""
    start, cross = C["catch"] - 0.6, C["hud_lightcross"]
    up = (lin(start, cross, t) if t <= cross else 1 + (WARP_C - 1) * ease_out_expo(lin(cross, cross + 1.6, t)))
    return up * (1 - smooth(C["approach"], C["dropout"], t))


def ftl_panel(e, shot, t):
    """左上航速 + 底部航程条。越过 1 c 的瞬间读数闪一下、出现"光障突破"；最后一冲时变成"脱离曲率"，急停时"抵达"。"""
    a = vis(t, C["catch"] - 0.6, C["dropout"] + 0.9, 0.4, 0.5)
    if a <= 0.01:
        return
    v = velocity(t)
    cross = C["hud_lightcross"]
    fl = math.exp(-((t - cross) / 0.09) ** 2)
    dec = smooth(C["approach"] - 0.1, C["approach"] + 0.2, t)
    x0, y0 = 92, 92
    head, head_en, c = ("脱离曲率", "WARP DROP-OUT", AMB) if dec > 0.5 else ("曲率航速", "VELOCITY  ×c", ACC if v >= 1 else HUD)
    tx(e, head, x0, y0 + 8, 24, a, WHT, "lm", "sans_m", 0.12)
    tx(e, head_en, x0, y0 + 38, 12, 0.6 * a, c, "lm", MONO, 0.3)
    # 大数字走清晰文字层：不被色差拉出彩边、不被泛光糊开
    tx(e, f"{v:05.2f}", x0, y0 + 108, 96, a, WHT if v < 1 else c, "lm", "latin", 0.0, 1.1 + 1.2 * fl, layer="ui")
    tx(e, "c", x0 + 262, y0 + 124, 40, 0.85 * a, c, "lm", "latin", 0.0)
    # 0..15 c 刻度带，1 c 处标"光速"
    tx0, tx1, ty = x0, x0 + 420, y0 + 206
    ln(e, [(tx0, ty), (tx1, ty)], 0.35 * a, HUD, 1.0, 0.0)
    for i in range(16):
        x = tx0 + (tx1 - tx0) * i / 15
        major = i % 5 == 0
        ln(e, [(x, ty), (x, ty + (10 if major else 5))], a * (0.8 if major else 0.4), HUD, 1.0, 0.0)
        if major:
            tx(e, f"{i}", x, ty + 22, 12, 0.6 * a, HUD, "mm", MONO, 0.0)
    xl = tx0 + (tx1 - tx0) / 15
    ln(e, [(xl, ty - 12), (xl, ty + 12)], 0.8 * a, AMB, 1.2, 0.3)
    tx(e, "光速", xl, ty - 22, 13, 0.7 * a, AMB, "mm", "sans_m", 0.1)
    xv = tx0 + (tx1 - tx0) * min(v, 15) / 15
    ln(e, [(xv - 7, ty - 14), (xv, ty - 4), (xv + 7, ty - 14), (xv - 7, ty - 14)], a, c, 1.3, 0.4)
    ca = a * vis(t, cross, cross + 1.6, 0.05, 0.5)
    if ca > 0.01:
        tx(e, "光障突破  ·  LIGHT BARRIER CROSSED", x0, ty + 52, 15, ca, AMB, "lm", "sans_m", 0.15)
    # 底部航程条：太阳 -> 半人马座 α
    f = min(1.0, float(np.interp(t, shot.tg, shot.scg)) / float(np.interp(C["dropout"], shot.tg, shot.scg)))
    bx0, bx1, by = 220, W - 220, 1010
    ln(e, [(bx0, by), (bx1, by)], 0.35 * a, HUD, 1.0, 0.0)
    ln(e, [(bx0, by), (bx0 + (bx1 - bx0) * f, by)], a, ACC, 1.6, 0.5, 1.8)
    for i in range(1, 5):
        x = bx0 + (bx1 - bx0) * i / STARS[0][3]
        ln(e, [(x, by - 5), (x, by + 5)], 0.5 * a, HUD, 1.0, 0.0)
        tx(e, f"{i} LY", x, by + 20, 11, 0.45 * a, DIM, "mm", MONO, 0.1)
    e.circle(bx0, by, 4.0, fill=WHT, fill_a=a, glow=4, intensity=2.0)
    tx(e, "太阳", bx0 - 14, by, 18, 0.8 * a, HUD, "rm", "sans_m", 0.1)
    ln(e, [(bx1, by - 7), (bx1 + 7, by), (bx1, by + 7), (bx1 - 7, by), (bx1, by - 7)], a, AMB, 1.3, 0.4)
    tx(e, "半人马座 α", bx1 + 16, by, 18, 0.9 * a, AMB, "lm", "sans_m", 0.1)
    xm = bx0 + (bx1 - bx0) * f
    ln(e, [(xm - 6, by - 16), (xm, by - 7), (xm + 6, by - 16), (xm - 6, by - 16)], a, WHT, 1.3, 0.4)
    rem = STARS[0][3] * (1 - f)
    msg = "抵达  ·  ARRIVED" if t >= C["dropout"] else f"剩余 {rem:4.2f} 光年  ·  {rem * DAYS_PER_LY:3.0f} 天"
    tx(e, msg, xm, by - 34, 16, 0.9 * a, AMB if t >= C["dropout"] else HUD, "mm", "sans_m", 0.08)


def arrival_label(e, cam, shot, t, radius):
    """抵达后挂在星面上的标签：船头前方星面上一个菱形标记，引线折出名字和航程。
    镜头翻过飞船、恒星完全出现、片名落下以后才出来（片名在左上，标签在右下），停几秒后收起。"""
    t0 = C["title"] + 1.0
    a = vis(t, t0, t0 + 4.6, 0.5, 0.6)
    if a <= 0.01:
        return
    center = shot.target_a(t)
    # 锚点：星面上朝向"船头前方偏右、略高"那一点（画面里在飞船右前方的星面上，不压在飞船身上）
    aim = np.array([-60.0, 20.0, 160.0]) - center
    q = proj(cam, center + aim / np.linalg.norm(aim) * radius)
    if q is None:
        return
    x, y = q[0], q[1]
    draw = ease_out_expo(lin(t0, t0 + 0.6, t))
    ln(e, [(x, y - 8), (x + 8, y), (x, y + 8), (x - 8, y), (x, y - 8)], a, AMB, 1.3, 0.5)
    lx, ly = x + 70, y - 120
    ln(e, [(x + 6, y - 6), (lx, ly), (lx + 260, ly)], 0.7 * a, AMB, 1.0, 0.3, progress=draw)
    ta = a * smooth(t0 + 0.3, t0 + 0.6, t)
    tx(e, "半人马座 α A", lx + 4, ly - 26, 30, ta, WHT, "lm", "sans_m", 0.1)
    tx(e, "ALPHA CENTAURI A", lx + 4, ly + 18, 12, 0.75 * ta, AMB, "lm", MONO, 0.3)
    tx(e, f"距地球 {STARS[0][3]:.2f} 光年  ·  航程 {STARS[0][3] * DAYS_PER_LY:.0f} 天", lx + 4, ly + 44, 16, 0.85 * ta,
       HUD, "lm", "sans_m", 0.08)
