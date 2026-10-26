# -*- coding: utf-8 -*-
"""第一章 光速之墙（速度表 -> 能量曲线撞上光速墙 -> 困在太阳系 -> 墙上的裂缝 -> 运动 vs 空间本身）
第二章 空间本身（时空膜 -> 质量压出引力井 -> 宇宙膨胀、超光速退行 -> 顺风车？）"""
import math
import numpy as np
from opusvid.scene import Scene, ScreenCam
from opusvid.gl import ease_out, ease_in_out, ease_out_expo, smooth, lin, W, H, Camera
from opusvid.mathtex import Tex, write_fx, highlight_fx, combine
from config import BEAT
from cues import C, ls
from wfx import (CYAN, BLUE, RED, GOLD, AMBER, WHITE, DIM, ICE, VIOLET, space, bodies, flat, darkspot, stamp, ring,
                 arrow, pulse, vis, mix3, streaks, glowline, needle)
from ship import ship, ship_frame, roll, relstars
from grid import Grid

# 光速墙：竖直的能量屏障（六边形能量纹 + 噪声流动），crack>0 时中间裂开一道发光缝隙
WALL_FS = r"""
uniform float uX; uniform float uW; uniform float uAmt; uniform float uCrack; uniform float uHit; uniform vec3 uCol;
in vec2 vUV; out vec4 fragColor;
float hexDist(vec2 p){
    p = abs(p);
    return max(dot(p, normalize(vec2(1.0, 1.73))), p.x);
}
vec4 hexCoords(vec2 uv){
    vec2 r = vec2(1.0, 1.73); vec2 h = r * 0.5;
    vec2 a = mod(uv, r) - h; vec2 b = mod(uv - h, r) - h;
    vec2 gv = dot(a, a) < dot(b, b) ? a : b;
    return vec4(gv, uv - gv);
}
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    float dx = (P.x - uX) / uW;
    float band = exp(-dx * dx * 2.0);
    float edge = exp(-abs(dx) * 7.0);
    vec4 hc = hexCoords(P / 38.0 + vec2(0.0, uTime * 0.15));
    float hx = smoothstep(0.42, 0.5, hexDist(hc.xy));
    float flick = 0.5 + 0.5 * sin(hash12(hc.zw) * 40.0 + uTime * 3.0);
    float n = fbm2(vec2(dx * 2.0, P.y / 180.0 - uTime * 0.6), 5);
    vec3 col = uCol * (band * (0.25 + 0.9 * n) + edge * 1.4 + hx * band * (0.4 + 0.6 * flick) * 0.9);
    col *= 1.0 + 2.5 * uHit * exp(-pow((P.y - uRes.y * 0.5) / 260.0, 2.0));
    // 裂缝：沿 y 的锯齿折线，开口宽度随 crack 增大，缝里透出青白色的光
    if (uCrack > 0.0){
        float cx = uX + (fbm2(vec2(P.y / 90.0, 3.0), 4) - 0.5) * 70.0 + (hash11(floor(P.y / 23.0)) - 0.5) * 12.0;
        float open = uCrack * (6.0 + 30.0 * exp(-pow((P.y - uRes.y * 0.48) / 280.0, 2.0)));
        float d = abs(P.x - cx);
        float core = 1.0 - smoothstep(open * 0.3, open, d);
        float halo = exp(-d / (open * 1.5 + 4.0)) * uCrack;
        col = mix(col, vec3(0.0), core * 0.7);
        col += vec3(0.6, 0.95, 1.0) * (core * 3.0 + halo * 1.2) * smoothstep(0.0, 0.2, uCrack);
    }
    fragColor = vec4(col * uAmt, 1.0);
}
"""


def gauge(e, cx, cy, R, v, a, t):
    """速度表：0..c 的弧形刻度（每 0.02c 一根细刻度、每 0.1c 一根长的），0.9c 以上是红区，指针指向 v（0..1）。
    按精密仪表画：细芯线、亮度压在泛光阈值以下；读数是刻度外侧一道由暗到亮的细弧，末端一个亮标记。
    （原来是 3～7 像素宽的发光粗弧和粗指针，泛光一晕成了霓虹灯管，用户嫌丑。）"""
    if a <= 0.002:
        return
    th0, th1 = math.pi * 1.15, math.pi * -0.15     # 从左下到右下，经过正上方
    P = lambda f, r: (cx + r * math.cos(th0 + (th1 - th0) * f), cy - r * math.sin(th0 + (th1 - th0) * f))
    hot = smooth(0.8, 0.99, v)
    col = mix3(CYAN, RED, hot)
    # 刻度圈：一根发丝弧 + 细刻度
    glowline(e, [P(f, R) for f in np.linspace(0, 1, 200)], (0.55, 0.7, 0.95), 0.5 * a, width=1.2, k=0.9)
    for i in range(51):
        f = i / 50
        major = i % 5 == 0
        red = f >= 0.9 - 1e-6
        glowline(e, [P(f, R - (22 if major else 10)), P(f, R)], RED if red else WHITE,
                 a * (0.9 if major else 0.4) * (1.0 if f <= v + 1e-6 or red else 0.6), width=1.6 if major else 1.0, k=0.95)
        if i % 25 == 0:
            e.text(["0", "0.5c", "c"][i // 25], *P(f, R - 58), 30, "latin_b", RED if red else WHITE, a, "mm", 0.02, 1.0)
    # 红区：刻度外侧一道细红弧
    glowline(e, [P(f, R + 8) for f in np.linspace(0.9, 1.0, 30)], RED, a, width=2.0, k=1.0, halo=0.25)
    # 读数：刻度外侧一道细弧，从 0 到当前速度由暗到亮，末端一个亮标记
    n = max(2, int(120 * v))
    fs = np.linspace(0, v, n + 1)
    for i in range(n):
        glowline(e, [P(fs[i], R + 8), P(fs[i + 1], R + 8)], col, a * (0.15 + 0.85 * (i / n) ** 2), width=2.2, k=1.0)
    if v > 0.005:
        streaks(e, [dict(tail=P(max(v - 0.02, 0.0), R + 8), head=P(v, R + 8), color=col, a=1.3 * a, width=4.0, taper=0.3,
                         spark=1.2)])
    needle(e, cx, cy, *P(v, R - 30), col, a, width=4.5, pivot=10.0)


class Ch1(Scene):
    chapter = True

    def setup(self):
        self.gam = Tex(self.eng, [(r"\gamma", "g"), "=", (r"\frac{1}{\sqrt{1-v^2/c^2}}", "f")], size=92)
        self.tW = C["curve"]           # 能量曲线开始
        self.tS = C["trapped"]         # 太阳系
        self.tK = C["loophole"]        # 墙上的裂缝
        self.tP = ls("A06")             # 运动 vs 空间本身

    # ------------------------------------------------ 速度表：越来越快，指针顶到红区
    def phase_gauge(self, t):
        e = self.eng
        a = smooth(self.t0 + 2.0, self.t0 + 2.5, t)          # 章节卡淡出后再出现
        cam = Camera((0, 0, 0), (0, 0, 1), fov=60)
        v = 0.97 * smooth(C["why"] - 0.3, C["climit"] + 0.3, t) ** 0.7
        relstars(e, cam, beta=min(v, 0.97) * 0.8, beta0=max(0.0, min(v, 0.97) * 0.8 - 0.06), stars=0.8 * a, neb=0.3 * a,
                 gal=(0.3, 0.9, 0.1))
        darkspot(e, W / 2, 680, 640, 420, 0.75 * a)
        shake = 3.0 * smooth(0.85, 0.97, v) * math.sin(t * 90)
        gauge(e, W / 2 + shake, 720, 330, v, a * (1 - smooth(self.tW - 0.12, self.tW, t)), t)
        out = self.tW - 0.4
        e.text(f"{v:0.3f} c", W / 2, 800, 64, "latin_b", WHITE, a * (1 - smooth(out, out + 0.4, t)), "mm", 0.04, 1.6)
        # 铁律：光速
        if t > C["law"] - 0.1:
            g = pulse(t, C["law"], 0.5)
            al = smooth(C["law"] - 0.1, C["law"] + 0.2, t) * (1 - smooth(out, out + 0.4, t))
            e.text("c = 299 792 458 m/s", W / 2, 150, 64, "latin_b", GOLD, al, "mm", 0.06, 1.5 + g,
                   scale=stamp(t, C["law"], 0.4, 1.25))
            e.text("宇宙限速", W / 2, 250, 48, "sans_b", WHITE, al * smooth(C["climit"] - 0.2, C["climit"] + 0.2, t), "mm",
                   0.4, 1.3 + pulse(t, C["climit"], 0.5), scale=stamp(t, C["climit"], 0.4, 1.3))

    # ------------------------------------------------ 能量曲线 -> 撞墙
    def phase_curve(self, t):
        e = self.eng
        a = smooth(self.tW, self.tW + 0.12, t) * (1 - smooth(self.tS - 0.12, self.tS, t))
        space(e, neb=0.12, stars=0.5, c1=(0.05, 0.08, 0.2), c2=(0.2, 0.05, 0.15), c3=(0.3, 0.2, 0.5), seed=9.0)
        x0, y0, gw, gh = 280, 190, 900, 680              # 坐标区：左上角与宽高
        vx = x0 + gw * 0.92                                # v = c 的位置
        # 光速墙（着色器层），撞击时一闪
        wall = smooth(C["harder"], C["inf"], t)
        hit = pulse(t, C["wall"], 0.35)
        e.draw_fs("wd_wall", WALL_FS, dict(uX=vx, uW=40.0 + 55 * smooth(C["wall"] - 0.3, C["wall"] + 0.2, t),
                                          uAmt=a * (0.25 + 0.75 * wall), uCrack=0.0, uHit=hit, uCol=(1.0, 0.25, 0.12)),
                  blend="add")
        p = ease_out_expo(lin(self.tW, self.tW + 0.9, t))
        e.line([(x0, y0 + gh), (x0 + (gw + 60) * p, y0 + gh)], 2.0, DIM, a, intensity=1.2)
        e.line([(x0, y0 + gh), (x0, y0 + gh - (gh + 40) * p)], 2.0, DIM, a, intensity=1.2)
        e.text("速度", x0 + gw + 50, y0 + gh + 40, 30, "sans_m", DIM, a, "rm", 0.1, 1.1)
        e.text("所需能量", x0 + 14, y0 - 30, 30, "sans_m", DIM, a, "lm", 0.1, 1.1)
        e.text("c", vx, y0 + gh + 40, 40, "latin_b", RED, a, "mm", 0.0, 1.8)
        # γ - 1 曲线：一个光点沿曲线往上爬，越接近墙越慢
        vmax = 0.995 * smooth(self.tW + 0.5, C["inf"] + 0.4, t) ** 0.55
        vs = np.linspace(0, max(vmax, 0.001), 240)
        E = 1 / np.sqrt(1 - vs ** 2) - 1
        ys = y0 + gh - np.minimum(E / 9.0, 1.15) * gh
        xs = x0 + gw * 0.92 * vs
        pts = np.stack([xs, ys], 1)
        hot = smooth(0.8, 0.99, vmax)
        glowline(e, pts, mix3(CYAN, AMBER, hot), a, width=2.4, k=1.0, halo=0.3)
        if vmax > 0.01:
            streaks(e, [dict(tail=tuple(pts[max(len(pts) - 14, 0)]), head=tuple(pts[-1]), color=mix3(CYAN, AMBER, hot), a=1.4 * a,
                             width=4.0, taper=0.4, spark=1.6)])
        # ∞
        if t > C["inf"] - 0.1:
            ai = a * smooth(C["inf"] - 0.1, C["inf"] + 0.15, t)
            e.text("∞", vx - 90, y0 + 30, 140, "sans_b", RED, ai, "mm", 0.0, 1.8 + 2 * pulse(t, C["inf"], 0.4),
                   scale=stamp(t, C["inf"], 0.45, 1.6))
        # γ 公式
        fa = a * smooth(C["harder"] - 0.3, C["harder"] + 0.3, t) * (1 - smooth(C["wall"] - 0.4, C["wall"], t))
        if fa > 0.001:
            fx = combine(write_fx(t, C["harder"] - 0.3, 0.5, 0.05, tex=self.gam),
                         highlight_fx(t, ["f"], C["inf"], color=RED, glow=0.5, pulse=1.0))
            self.gam.draw(1430, 420, anchor="=", scale=0.85, alpha=fa, intensity=1.4, fx=fx)
            e.text("洛伦兹因子", 1500, 540, 30, "sans_m", GOLD, fa, "mm", 0.2, 1.2)
        # 这堵墙
        if t > C["wall"] - 0.1:
            aw = a * smooth(C["wall"] - 0.1, C["wall"] + 0.2, t)
            e.text("光速之墙", vx + 160, 300, 64, "serif", (1.0, 0.55, 0.4), aw, "lm", 0.15, 1.5 + 2 * hit,
                   scale=stamp(t, C["wall"], 0.4, 1.3))
        flat(e, (1.0, 0.35, 0.2), 0.5 * hit)

    # ------------------------------------------------ 太阳系被困在一层"墙"里
    def phase_trapped(self, t):
        e = self.eng
        lt = t - self.tS
        a = smooth(self.tS, self.tS + 0.12, t)
        out = smooth(self.tK - 0.12, self.tK, t)
        zoom = 1.0 - 0.25 * ease_out(lin(self.tS, self.tK, t))
        space(e, neb=0.18 * a, stars=0.8 * a, c1=(0.08, 0.06, 0.2), c2=(0.25, 0.05, 0.1), zoom=zoom, seed=4.0)
        cx, cy = W / 2, H / 2 + 10
        bodies(e, [(cx, cy, 10 * zoom, 2.0 * a, (1.0, 0.85, 0.55), 0.6)])
        for k, (r, sp, c) in enumerate(((60, 1.6, (0.8, 0.7, 0.6)), (95, 1.2, (1.0, 0.8, 0.5)), (130, 1.0, (0.4, 0.7, 1.0)),
                                        (170, 0.8, (1.0, 0.45, 0.3)), (250, 0.45, (1.0, 0.8, 0.6)), (320, 0.35, (0.9, 0.8, 0.6)))):
            rr = r * zoom
            ring(e, cx, cy, rr, 0.35 * a, DIM, 1.0, 0.0, 160, 1.0, squash=0.55)
            th = lt * sp + k * 1.7
            e.circle(cx + rr * math.cos(th), cy + rr * 0.55 * math.sin(th), 4, fill=c, fill_a=a, glow=3, intensity=2)
        # 光速墙变成包住太阳系的泡（远处是够不着的恒星）
        R = 400 * zoom
        g = pulse(t, self.tS, 0.6)
        e.draw_fs("wd_shell", SHELL_FS, dict(uC=(cx, cy), uR=R, uAmt=a * (1 - out), uHit=g), blend="add")
        for k, (sx, sy, nm) in enumerate(((cx + 760, cy - 300, "比邻星 4.2 光年"), (cx - 780, cy + 250, "天狼星 8.6 光年"),
                                           (cx + 640, cy + 330, "织女星 25 光年"))):
            bodies(e, [(sx, sy, 4, 1.2 * a, (0.9, 0.9, 1.0), 0.5)])
            e.text(nm, sx, sy + 34, 26, "sans_m", DIM, a * vis(t, self.tS + 0.3 + 0.2 * k, self.tK, 0.4, 0.4), "mm", 0.1, 1.1)
        e.text("太阳系", cx, cy - R - 40, 40, "sans_b", (1.0, 0.6, 0.45), a * (1 - out), "mm", 0.3, 1.4)

    # ------------------------------------------------ 墙上的缝隙 + 运动 vs 空间本身
    def phase_gap(self, t):
        e = self.eng
        a = smooth(self.tK, self.tK + 0.12, t) * (1 - smooth(self.tP - 0.12, self.tP, t))
        space(e, neb=0.1, stars=0.5, c1=(0.05, 0.08, 0.2), c2=(0.2, 0.05, 0.15), seed=12.0)
        crack = smooth(C["gap"] - 0.5, C["gap"] + 0.6, t)
        e.draw_fs("wd_wall", WALL_FS, dict(uX=W / 2, uW=220.0, uAmt=a, uCrack=crack, uHit=pulse(t, C["gap"], 0.4),
                                          uCol=(1.0, 0.25, 0.12)), blend="add")
        e.text("爱因斯坦", W / 2 - 330, 420, 64, "serif", WHITE, a * smooth(self.tK + 0.1, self.tK + 0.6, t), "rm", 0.1, 1.3)
        e.text("广义相对论", W / 2 - 330, 500, 34, "sans_m", GOLD, a * smooth(self.tK + 0.4, self.tK + 0.9, t), "rm", 0.2, 1.2)
        e.text("1915", W / 2 - 330, 560, 30, "latin_m", DIM, a * smooth(self.tK + 0.6, self.tK + 1.1, t), "rm", 0.2, 1.1)
        e.text("缝隙", W / 2 + 120, 540, 64, "serif", ICE, a * crack, "lm", 0.2, 1.6 + 2 * pulse(t, C["gap"], 0.4))

    def phase_split(self, t):
        e = self.eng
        a = smooth(self.tP, self.tP + 0.12, t)
        space(e, neb=0.08, stars=0.5, c1=(0.05, 0.08, 0.2), c2=(0.2, 0.05, 0.15), seed=12.0)
        e.line([(W / 2, 170), (W / 2, 900)], 1.0, DIM, 0.4 * a)
        hl = smooth(C["motion"] - 0.2, C["motion"] + 0.2, t) * (1 - 0.6 * smooth(C["space_itself"] - 0.2, C["space_itself"], t))
        hr = smooth(C["space_itself"] - 0.1, C["space_itself"] + 0.1, t)
        # 左：固定网格上移动的物体（≤ c）
        L0, T0, S = 140, 280, 70
        for i in range(11):
            x = L0 + i * S
            e.line([(x, T0), (x, T0 + 7 * S)], 1.0, BLUE, 0.4 * a, intensity=1.0 + hl)
        for j in range(8):
            y = T0 + j * S
            e.line([(L0, y), (L0 + 10 * S, y)], 1.0, BLUE, 0.4 * a, intensity=1.0 + hl)
        u = ((t - self.tP) * 0.22) % 1.0
        px = L0 + 30 + u * (10 * S - 60)
        py = T0 + 3.5 * S
        streaks(e, [dict(tail=(max(px - 170, L0), py), head=(px, py), color=CYAN, a=1.4 * a, width=4.0, spark=1.6)])
        e.text("在空间中运动", L0 + 5 * S, 210, 40, "sans_b", WHITE, a, "mm", 0.2, 1.1 + 0.6 * hl)
        e.text("≤ c", L0 + 5 * S, T0 + 7 * S + 70, 64, "sans_b", RED, a * (0.4 + 0.6 * hl), "mm", 0.05, 1.4 + hl)
        # 右：网格本身在伸展，带着点一起走（没有上限）
        cx, cy = W / 2 + 480, T0 + 3.5 * S
        sc = 1.0 + 1.6 * ease_in_out(lin(C["space_itself"], self.t1, t)) + 0.15 * math.sin((t - self.tP) * 1.5) * (1 - hr)
        n = 8
        for i in range(-n, n + 1):
            x = cx + i * S * 0.62 * sc
            if abs(x - cx) < 420:
                e.line([(x, T0 - 20), (x, T0 + 7 * S + 20)], 1.0, VIOLET, 0.5 * a, intensity=1.0 + 1.5 * hr)
        for j in range(-5, 6):
            y = cy + j * S * 0.62 * sc
            if abs(y - cy) < 280:
                e.line([(cx - 400, y), (cx + 400, y)], 1.0, VIOLET, 0.5 * a, intensity=1.0 + 1.5 * hr)
        for (gx, gy) in ((-2, -1), (2, 1), (-1, 2), (3, -2)):
            x, y = cx + gx * S * 0.62 * sc, cy + gy * S * 0.62 * sc
            if abs(x - cx) < 400 and abs(y - cy) < 270:
                e.circle(x, y, 5, fill=GOLD, fill_a=a, glow=2, intensity=1.3)
        e.text("空间本身", cx, 210, 40, "sans_b", WHITE, a, "mm", 0.2, 1.1 + 0.8 * hr)
        e.text("没有上限", cx, T0 + 7 * S + 70, 52, "sans_b", VIOLET, a * hr, "mm", 0.2, 1.5 + 2 * pulse(t, C["space_itself"], 0.4),
               scale=stamp(t, C["space_itself"], 0.4, 1.3))
        flat(e, (0.6, 0.4, 1.0), 0.35 * pulse(t, C["space_itself"], 0.3))

    def render(self, t):
        if t < self.tW:
            self.phase_gauge(t)
        elif t < self.tS:
            self.phase_curve(t)
        elif t < self.tK:
            self.phase_trapped(t)
        elif t < self.tP:
            self.phase_gap(t)
        else:
            self.phase_split(t)
        self.chapter_card(t)

    def post(self, t):
        if t < self.tW:
            return dict(uBloomAmt=0.5, uVignette=0.8, uCA=0.012)
        return dict(uBloomAmt=0.5, uVignette=0.7)


# 太阳系外的"光速壳"：淡红色的球壳 + 六边形纹
SHELL_FS = r"""
uniform vec2 uC; uniform float uR; uniform float uAmt; uniform float uHit;
in vec2 vUV; out vec4 fragColor;
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    vec2 d = P - uC;
    float r = length(d);
    float shell = exp(-pow((r - uR) / 6.0, 2.0)) + exp(-abs(r - uR) / 40.0) * 0.25;
    float inner = smoothstep(uR, uR * 0.6, r) * 0.06;
    float n = fbm2(d / 60.0 + uTime * 0.1, 4);
    vec3 col = vec3(1.0, 0.3, 0.15) * (shell * (0.6 + 0.8 * n) * (1.0 + 2.0 * uHit) + inner);
    fragColor = vec4(col * uAmt, 1.0);
}
"""


# ====================================================================== 第二章
GALAXY_BODY = r"""
uniform float uA; uniform vec2 uC; uniform float uRH; uniform float uRed; uniform float uBright; uniform float uSel;
void main(){
    vec2 p = uC + in_pos.xy * uA;
    float far = smoothstep(uRH - 10.0, uRH + 30.0, length(p - uC));
    vec3 c = mix(in_col.rgb, vec3(1.0, 0.3, 0.2) * luma(in_col.rgb) * 1.6, far * uRed);
    float sel = in_col.a > 0.5 ? uSel : 0.0;
    emit2(vec3(p, 0.0), vec4(c * (1.0 + sel * 2.0), 1.0) * uBright, in_extra.x * (1.0 + 0.4 * sel), 2.0, in_extra.z, in_extra.w);
}
"""


class Ch2(Scene):
    chapter = True

    def setup(self):
        self.grid = Grid(self.eng)
        rng = np.random.default_rng(21)
        n = 950
        pos = np.zeros((n, 3), np.float32)
        r = np.sqrt(rng.random(n)) * 1500
        th = rng.random(n) * math.tau
        pos[:, 0], pos[:, 1] = r * np.cos(th), r * np.sin(th) * 0.75
        col = np.zeros((n, 4), np.float32)
        hue = rng.random(n)
        col[:, :3] = np.stack([0.8 + 0.2 * hue, 0.75 + 0.1 * hue, 1.0 - 0.3 * hue], 1) * (0.5 + 0.8 * rng.random((n, 1)))
        # 被点名的那个星系
        self.sel = int(np.argmin(np.abs(r - 330) + np.abs(th - 5.6) * 200))
        col[self.sel, 3] = 1.0
        extra = np.zeros((n, 4), np.float32)
        extra[:, 0] = 4.0 + 10.0 * rng.random(n) ** 3
        extra[:, 2] = rng.random(n) * math.pi
        extra[:, 3] = 1.0 + 1.6 * rng.random(n)
        self.gal_pos = pos
        self.cloud = self.eng.make_cloud("wd_galaxies", GALAXY_BODY, pos, col, extra)
        self.tU = C["expand"] - 0.6           # 切到宇宙膨胀
        self.tR = C["ride_q"] - BEAT           # 顺风车

    def scale(self, t):
        """宇宙尺度因子：从"膨胀"一词开始变大，到"之间的空间"之后约 1.75 倍（再大星系就都跑出画面了）。"""
        return 1.0 + 0.75 * ease_in_out(lin(C["expand"], C["between"] + 1.0, t))

    # ------------------------------------------------ 时空之膜 + 引力井
    def phase_membrane(self, t):
        e = self.eng
        lt = t - self.t0
        az = 0.4 + 0.05 * lt
        eye = (11 * math.sin(az), 5.5 - 1.2 * lin(C["mass"], self.tU, t), -11 * math.cos(az))
        cam = Camera(eye, (0, -0.8, 0), fov=42)
        relstars(e, cam, stars=0.6, neb=0.3)
        ripple = 0.55 * smooth(C["bend"] - 0.2, C["bend"] + 0.4, t) * (1 - smooth(C["mass"] - 0.6, C["mass"], t))
        dent = 2.6 * ease_out(lin(C["mass"] + 0.3, C["dent"] + 0.4, t))
        cell = 0.6 * (1 + 0.25 * math.sin((t - C["stretch"]) * 3.0) * smooth(C["stretch"] - 0.2, C["stretch"] + 0.3, t)
                      * (1 - smooth(C["mass"] - 0.6, C["mass"], t)))
        self.grid.draw(cam, L=16, cell=cell, wells=[(0, 0, dent, 1.4)] if dent > 0 else [], ripple=ripple,
                       rip_c=(0.0, 0.0), rip_k=2.2, rip_phase=(t - C["bend"]) * 7.0, wave=0.25 * smooth(self.t0 + 1, C["stage"], t)
                       * (1 - smooth(C["bend"] - 0.3, C["bend"], t)), time=t, hue_h=2.0, col_neg=(0.35, 0.75, 1.0),
                       col_flat=(0.15, 0.4, 0.95), minor=0.3, fog=(10.0, 28.0))
        # 恒星落下
        if t > C["mass"] - 0.1:
            drop = 1 - ease_out(lin(C["mass"] - 0.1, C["dent"] + 0.3, t))
            sy = -dent * 0.92 + 0.6 + 6.0 * drop
            q = cam.project((0, sy, 0))
            if q:
                g = pulse(t, C["dent"], 0.5)
                bodies(e, [(q[0], q[1], 26 * (1 + 0.2 * g), 2.2 * (1 + g), (1.0, 0.85, 0.55), 0.8)])
            # 行星绕转（落在井壁上）
            pa = smooth(C["gravity"] - 0.6, C["gravity"], t)
            if pa > 0:
                th = (t - C["gravity"]) * 1.6
                px, pz = 3.0 * math.cos(th), 3.0 * math.sin(th)
                py = self.grid.height(px, pz, wells=[(0, 0, dent, 1.4)]) + 0.15
                orbit = [cam.project((3.0 * math.cos(a), self.grid.height(3.0 * math.cos(a), 3.0 * math.sin(a),
                                                                         wells=[(0, 0, dent, 1.4)]) + 0.1, 3.0 * math.sin(a)))
                         for a in np.linspace(0, math.tau, 120)]
                orbit = [o[:2] for o in orbit if o]
                glowline(e, orbit, CYAN, 0.6 * pa, width=1.2, k=0.95, halo=0.2)
                q2 = cam.project((px, py, pz))
                if q2:
                    e.circle(q2[0], q2[1], 6, fill=(0.4, 0.75, 1.0), fill_a=pa, glow=2, intensity=1.4)
        a1 = vis(t, C["stage"] - 0.2, C["mass"], 0.4, 0.4)
        e.text("时空", 140, 200, 72, "serif", WHITE, a1, "lm", 0.15, 1.4)
        e.text("一张可以弯曲、伸缩的膜", 146, 280, 34, "sans_m", ICE, a1, "lm", 0.15, 1.2, t=t, start=C["stage"], dur=0.6)
        a2 = vis(t, C["gravity"] - 0.2, self.tU, 0.3, 0.4)
        e.text("引力 = 时空弯曲", 140, 200, 60, "serif", GOLD, a2, "lm", 0.12, 1.5, scale=stamp(t, C["gravity"], 0.4, 1.25))

    # ------------------------------------------------ 宇宙膨胀：远处星系超光速退行
    def phase_expand(self, t):
        e = self.eng
        a = smooth(self.tU, self.tU + 0.12, t) * (1 - smooth(self.tR - 0.12, self.tR, t))
        A = self.scale(t)
        cx, cy = W / 2, H / 2 - 10
        space(e, neb=0.08, stars=0.35 * a, c1=(0.04, 0.06, 0.18), c2=(0.12, 0.04, 0.14), seed=2.0)
        # 共动网格：随尺度因子一起变大
        step = 110 * A
        n = int(1200 / step) + 2
        ga = 0.32 * a
        for i in range(-n, n + 1):
            x = cx + i * step
            if -10 < x < W + 10:
                e.line([(x, 0), (x, H)], 1.0, BLUE, ga, intensity=1.0)
        for j in range(-n, n + 1):
            y = cy + j * step
            if -10 < y < H + 10:
                e.line([(0, y), (W, y)], 1.0, BLUE, ga, intensity=1.0)
        RH = 360.0
        red = smooth(C["ftl"] - 0.4, C["ftl"] + 0.3, t)
        sel = smooth(C["notviol"] + 0.4, C["notviol"] + 1.0, t)
        e.draw_cloud(self.cloud, ScreenCam(), dict(uA=A, uC=(cx, cy), uRH=RH, uRed=red, uBright=1.8 * a, uSel=sel,
                                                   uMinPx=1.5))
        # 我们
        bodies(e, [(cx, cy, 6, 1.6 * a, (1.0, 0.9, 0.7), 0.5)])
        e.text("我们", cx, cy + 40, 30, "sans_b", WHITE, a, "mm", 0.2, 1.2)
        # 哈勃球
        ha = smooth(C["galaxies"] - 0.2, C["galaxies"] + 0.4, t) * a
        if ha > 0:
            ring(e, cx, cy, RH, ha, GOLD, 2.0, 0.8, 240, 1.8)
            e.text("哈勃球", cx, cy - RH + 50, 34, "sans_b", GOLD, ha, "mm", 0.2, 1.4)
            e.text("半径约 140 亿光年", cx, cy - RH + 86, 26, "sans_m", GOLD, ha, "mm", 0.1, 1.2)
        # 球外：退行速度超过光速（红色箭头）
        if red > 0:
            for k in range(10):
                th = k * math.tau / 10 + 0.3
                r0 = RH + 70 + 20 * (k % 3)
                r1 = r0 + 90 + 40 * red
                arrow(e, cx + r0 * math.cos(th), cy + r0 * math.sin(th), cx + r1 * math.cos(th), cy + r1 * math.sin(th),
                      RED, a * red, 3.0, 16, 0.8, 2.0, progress=ease_out_expo(lin(C["ftl"] - 0.2, C["ftl"] + 0.5, t)))
            e.text("退行速度 > 光速", W - 120, 140, 52, "sans_b", RED, a * red, "rm", 0.1, 1.6 + 2 * pulse(t, C["ftl"], 0.4),
                   scale=stamp(t, C["ftl"], 0.4, 1.3))
        # 被点名的星系：自己几乎没动，是之间的空间在变大
        if sel > 0:
            gx = cx + self.gal_pos[self.sel, 0] * A
            gy = cy + self.gal_pos[self.sel, 1] * A
            ring(e, gx, gy, 34, a * sel, CYAN, 2.0, 0.8, 120, 2.0)
            e.text("星系自己几乎没动", gx + 50, gy - 46, 30, "sans_m", CYAN, a * sel, "lm", 0.1, 1.3)
            bt = smooth(C["between"] - 0.3, C["between"] + 0.2, t)
            if bt > 0:
                k = int(24 * bt)
                pts = [(cx + (gx - cx) * i / 24, cy + (gy - cy) * i / 24) for i in range(k + 1)]
                if len(pts) > 1:
                    glowline(e, pts, VIOLET, a, width=2.0, k=1.0, halo=0.3, dash=18.0)
                e.text("是中间的空间在变大", (cx + gx) / 2 + 30, (cy + gy) / 2 + 50, 34, "sans_b", VIOLET, a * bt, "lm", 0.1, 1.6)

    # ------------------------------------------------ 顺风车？
    def phase_ride(self, t):
        e = self.eng
        lt = t - self.tR
        a = smooth(self.tR, self.tR + 0.12, t)
        cam = Camera((-6.5, 3.2, -8.5), (0.5, -0.3, 0.5), fov=40)
        relstars(e, cam, stars=0.7, neb=0.35)
        bump = 1.2 * smooth(C["ride"] - 0.4, C["ride"] + 0.5, t)
        self.grid.draw(cam, L=14, flow=(lt * 1.2 * bump, 0.0), cell=0.55, york=bump * 1.6, comp=0.2 * bump, R=2.0,
                       sigma=1.6, amt=a, hue_h=0.8, minor=0.25, fog=(8.0, 24.0), col_flat=(0.15, 0.4, 0.95))
        ship(e, cam, (0, 0.35, 0), roll(ship_frame((1, 0, 0)), lt * 0.4), 0.42, ring=0.6 + 1.2 * bump, phase=t * 4,
             engine=0.6, sun=(0.3, 0.8, -0.5))
        q = smooth(C["ride"] - 0.1, C["ride"] + 0.2, t)
        e.text("？", W / 2 + 280, 300, 180, "serif", GOLD, a * q, "mm", 0.0, 1.8 + 2 * pulse(t, C["ride"], 0.4),
               scale=stamp(t, C["ride"], 0.45, 1.5))

    def render(self, t):
        if t < self.tU:
            self.phase_membrane(t)
        elif t < self.tR:
            self.phase_expand(t)
        else:
            self.phase_ride(t)
        self.chapter_card(t)

    def post(self, t):
        return dict(uBloomAmt=0.55, uVignette=0.75)
