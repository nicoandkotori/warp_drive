# -*- coding: utf-8 -*-
"""第五章 代价：负能量环 -> 能量需求的数量级（宇宙 10^53 kg / 最初估算 10^62 kg / 几个太阳 / 700 kg）
-> 卡西米尔效应 -> 因果视界（关不掉） -> 停下时倾泻的高能粒子摧毁目的地。"""
import math
import numpy as np
from opusvid.scene import Scene
from opusvid.gl import ease_in_out, ease_out_expo, smooth, lin, W, Camera
from opusvid.mathtex import Tex, write_fx
from cues import C, ls
from wfx import (CAM_GLSL, CYAN, RED, GOLD, AMBER, WHITE, DIM, ICE, VIOLET, MAGENTA, cam_uniforms, space, flat,
                 darkspot, stamp, ring, arrow, pulse, vis, mix3, Offscreen, streaks, glowline)
from ship import ship, ship_frame, roll, relstars, lens
from grid import Grid

# 阿库别瑞曲率泡的能量密度 ρ ∝ -(y²+z²)/r² · (df/dr)²：集中在垂直于运动方向的一圈"甜甜圈"里
NEGE_FS = CAM_GLSL + r"""
uniform vec3 uC; uniform float uR; uniform float uSig; uniform float uAmt; uniform vec3 uCol;
in vec2 vUV; out vec4 fragColor;
float shapeD(float r){
    float a = 1.0 / cosh(uSig * (r + uR)), b = 1.0 / cosh(uSig * (r - uR));
    return uSig * (a * a - b * b) / (2.0 * tanh(uSig * uR));
}
void main(){
    vec3 rd = camRay(vUV);
    vec3 oc = uEye - uC;
    float Rb = uR * 1.9;
    float b = dot(oc, rd), c = dot(oc, oc) - Rb * Rb;
    float h = b * b - c;
    if (h < 0.0 || uAmt <= 0.0){ fragColor = vec4(0); return; }
    h = sqrt(h);
    float t0 = max(-b - h, 0.0), t1 = -b + h;
    const int N = 72;
    float dt = (t1 - t0) / float(N);
    float acc = 0.0;
    float jit = hash12(vUV * uRes + uTime);
    for (int i = 0; i < N; i++){
        vec3 p = uEye + rd * (t0 + (float(i) + jit) * dt) - uC;
        float r = length(p);
        float rho = dot(p.yz, p.yz) / max(r * r, 1e-4) * pow(shapeD(r), 2.0);
        float n = 0.6 + 0.8 * fbm3(p * 2.2 + vec3(uTime * 0.4, 0.0, uTime * 0.2), 3);
        acc += rho * n * dt;
    }
    acc /= uSig * uSig * uR;
    vec3 col = uCol * acc * 1.6 + vec3(1.0, 0.8, 1.0) * pow(acc, 2.0) * 0.6;
    fragColor = vec4(col * uAmt, 1.0);
}
"""

# 屏幕空间的行星：解析球体 + 程序化大陆/云 + 大气边缘；burn>0 时被高能粒子烧成熔岩
PLANET_FS = r"""
uniform vec2 uC; uniform float uR; uniform vec3 uL; uniform float uAmt; uniform float uBurn; uniform float uRot;
in vec2 vUV; out vec4 fragColor;
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    vec2 d = (P - uC) / uR;
    d.y = -d.y;
    float r2 = dot(d, d);
    vec3 col = vec3(0);
    float rim = exp(-abs(sqrt(r2) - 1.0) * 30.0) * 0.7 + exp(-max(sqrt(r2) - 1.0, 0.0) * 9.0) * 0.25 * step(1.0, r2);
    if (r2 < 1.0){
        vec3 n = vec3(d, sqrt(1.0 - r2));
        float c = cos(uRot), s = sin(uRot);
        vec3 q = vec3(c * n.x + s * n.z, n.y, -s * n.x + c * n.z);
        float land = smoothstep(0.5, 0.56, fbm3(q * 2.2 + 3.0, 6));
        float cloud = smoothstep(0.55, 0.75, fbm3(q * 3.0 + vec3(uTime * 0.02, 0.0, 0.0) + 9.0, 5));
        vec3 base = mix(vec3(0.02, 0.08, 0.22), mix(vec3(0.12, 0.25, 0.08), vec3(0.45, 0.38, 0.25), fbm3(q * 6.0, 3)), land);
        base = mix(base, vec3(0.9), cloud * 0.8);
        float dif = max(dot(n, uL), 0.0);
        col = base * (0.03 + 0.8 * dif);
        // 夜面城市灯光
        col += vec3(1.0, 0.7, 0.35) * land * step(0.62, fbm3(q * 14.0, 3)) * smoothstep(0.15, -0.1, dot(n, uL)) * 0.6;
        // 被烧穿：熔岩裂纹 + 白热
        float lava = pow(1.0 - abs(fbm3(q * 5.0 + 1.0, 5) * 2.0 - 1.0), 12.0);
        col = mix(col, vec3(0.1, 0.02, 0.0) + vec3(1.0, 0.35, 0.08) * lava * 4.0 + vec3(1.0, 0.6, 0.3) * pow(n.x * -1.0 + 1.0, 3.0) * 0.4,
                  uBurn);
    }
    col += mix(vec3(0.35, 0.6, 1.0), vec3(1.0, 0.4, 0.15), uBurn) * rim * (0.4 + 0.6 * max(dot(normalize(vec3(d, 0.2)), uL), 0.0));
    fragColor = vec4(col * uAmt, 1.0);
}
"""


def planet(e, c, R, light=(-0.8, 0.3, 0.5), amt=1.0, burn=0.0, rot=0.0):
    L = np.asarray(light, np.float64)
    e.draw_fs("wd_planet", PLANET_FS, dict(uC=tuple(c), uR=float(R), uL=tuple(L / np.linalg.norm(L)), uAmt=float(amt),
                                          uBurn=float(burn), uRot=float(rot)), blend="add")



def energy_bar(e, x0, xe, y, color, a, hot=0.0):
    """对数刻度上的一根量条：实心的窄条，亮度压在泛光阈值以下（原来是 12 像素宽的发光粗线，被泛光晕成霓虹灯管），
    末端一道亮的竖刻线标出数值的位置。hot 是数值刚变化时的闪亮。"""
    e.rect(x0, y - 6, max(xe - x0, 1.0), 12, 2, fill=color, fill_a=0.5 * a, intensity=0.9 + 0.5 * hot)
    e.line([(xe, y - 13), (xe, y + 13)], 2.5, color, a, intensity=1.8 + 1.5 * hot)

class Ch5(Scene):
    chapter = True

    def setup(self):
        self.grid = Grid(self.eng)
        self.tN, self.tE, self.tK, self.tH, self.tX = ls("F02"), ls("F03"), ls("F05"), ls("F06"), ls("F07")
        mk = lambda s: Tex(self.eng, s, size=52)
        self.lab = dict(u=mk(r"10^{53}\,\mathrm{kg}"), e=mk(r"10^{62}\,\mathrm{kg}"), s=mk(r"10^{31}\,\mathrm{kg}"),
                        p=mk(r"\approx 700\,\mathrm{kg}"), cas=Tex(self.eng, r"\rho \approx -4\times10^{-4}\,\mathrm{J/m^3}", size=46))
        rng = np.random.default_rng(5)
        self.dust = rng.random((260, 3))
        self._tex = {}

    def tex(self, s, size):
        """按需排版并缓存的公式（计数器的指数每帧都可能变）。"""
        k = (s, size)
        if k not in self._tex:
            self._tex[k] = Tex(self.eng, s, size=size)
        return self._tex[k]

    # ------------------------------------------------ 船票 + 负能量环
    def phase_neg(self, t):
        e = self.eng
        lt = t - self.t0
        az = 0.3 + 0.05 * lt
        eye = (9.5 * math.sin(az), 3.2, 9.5 * math.cos(az))
        cam = Camera(eye, (0.0, 0.2, 0.0), fov=40)
        relstars(e, cam, stars=0.6, neb=0.3, n1=(0.2, 0.05, 0.3), n2=(0.35, 0.05, 0.15))
        a = 1 - smooth(self.tE - 0.12, self.tE, t)
        dark = smooth(C["ticket"] - 0.5, C["ticket"] + 0.5, t)
        self.grid.draw(cam, L=14, cell=0.5, york=1.6, R=2.0, sigma=1.6, comp=0.3, amt=a * (1 - 0.6 * dark), hue_h=0.8,
                       minor=0.2, fog=(8.0, 22.0), col_flat=(0.12, 0.25, 0.6))
        ship(e, cam, (0, 0.2, 0), roll(ship_frame((1, 0, 0)), lt * 0.2), 0.42, amt=a, ring=1.2, phase=t * 4, engine=0.6,
             sun=(0.3, 0.8, -0.5))
        torus = smooth(self.tN + 0.3, C["neg"], t) * a
        if torus > 0:
            u = cam_uniforms(cam)
            u.update(uC=(0.0, 0.2, 0.0), uR=2.0, uSig=1.6, uAmt=torus * (1 + 1.5 * pulse(t, C["neg"], 0.5)), uCol=VIOLET)
            e.draw_fs("wd_nege", NEGE_FS, u, blend="add")
        # 船票：能量需求的计数器疯狂上涨
        ta = vis(t, ls("F01") - 0.2, self.tN + 0.4, 0.3, 0.4)
        if ta > 0:
            ex = int(10 + 52 * smooth(ls("F01"), C["ticket"] + 0.3, t))
            darkspot(e, W / 2, 210, 600, 140, 0.6 * ta)
            e.text("所需能量", W / 2, 140, 30, "sans_m", (1.0, 0.6, 0.55), ta, "mm", 0.3, 1.2)
            self.tex(r"10^{%d}\,\mathrm{J}" % ex, 96).draw(W / 2, 262, anchor="m", color=RED, alpha=ta,
                                                          intensity=1.6 + 1.5 * pulse(t, C["ticket"], 0.4),
                                                          scale=stamp(t, C["ticket"], 0.4, 1.25))
        na = vis(t, C["neg"] - 0.1, self.tE, 0.25, 0.4)
        if na > 0:
            sc = stamp(t, C["neg"], 0.45, 1.35)
            darkspot(e, 360, 250, 420, 170, 0.6 * na)
            e.text("负能量", 140, 230, 110, "serif", (0.85, 0.7, 1.0), na, "lm", 0.1, 1.6 + 1.5 * pulse(t, C["neg"], 0.4), scale=sc)
            e.text("NEGATIVE ENERGY · ρ < 0", 146, 318, 26, "latin_m", VIOLET, na, "lm", 0.25, 1.4, t=t, start=C["neg"] + 0.2,
                   dur=0.6, stagger=0.015, kind="spread")
        # 能级示意：真空 = 0，负能量在它下面
        va = vis(t, C["vacuum"] - 0.2, self.tE, 0.3, 0.4)
        if va > 0:
            x0, y0 = 1460, 560
            glowline(e, [(x0 - 140, y0), (x0 + 220, y0)], WHITE, va, width=1.5, k=0.95)
            e.text("真空 = 0", x0 + 230, y0, 30, "sans_b", WHITE, va, "lm", 0.1, 1.3)
            dep = 180 * ease_out_expo(lin(C["vacuum"], C["vacuum"] + 0.8, t))
            e.rect(x0 - 40, y0 + 4, 80, dep, 4, fill=VIOLET, fill_a=0.45 * va, stroke=VIOLET, stroke_w=1.3, intensity=0.95)
            e.text("负能量", x0, y0 + dep + 36, 30, "sans_b", VIOLET, va, "mm", 0.1, 1.5)

    # ------------------------------------------------ 数量级：对数刻度上的能量条
    def phase_scale(self, t):
        e = self.eng
        a = smooth(self.tE, self.tE + 0.12, t) * (1 - smooth(self.tK - 0.12, self.tK, t))
        space(e, neb=0.12 * a, stars=0.5 * a, c1=(0.08, 0.04, 0.18), c2=(0.2, 0.04, 0.12), seed=17.0)
        x0, x1, y = 170, 1760, 720
        X = lambda k: x0 + (x1 - x0) * k / 65.0
        p = ease_out_expo(lin(self.tE, self.tE + 0.8, t))
        e.line([(x0, y), (x0 + (x1 - x0) * p, y)], 2.0, DIM, a, intensity=1.2)
        for k in range(0, 66, 10):
            e.line([(X(k), y - 8), (X(k), y + 8)], 1.5, DIM, a * p, intensity=1.2)
            self.tex(r"10^{%d}" % k, 34).draw(X(k), y + 52, anchor="m", color=DIM, alpha=a * p, intensity=1.1)
        e.text("千克（对数刻度）", x1, y + 76, 24, "sans_m", DIM, a * p, "rm", 0.1, 1.0)
        # 可观测宇宙（金）
        ua = smooth(C["universe"] - 0.2, C["universe"] + 0.4, t) * a
        if ua > 0:
            xe = X(0) + (X(53) - X(0)) * ease_out_expo(lin(C["universe"] - 0.2, C["universe"] + 0.6, t))
            energy_bar(e, X(0), xe, 470, (1.0, 0.7, 0.3), ua)
            e.text("整个可观测宇宙", X(0), 425, 34, "sans_b", GOLD, ua, "lm", 0.1, 1.3)
            self.lab["u"].draw(xe - 10, 430, anchor="r", alpha=ua, color=GOLD, intensity=1.4, fx=write_fx(t, C["universe"] + 0.3, 0.4, 0.03))
        # 所需负能量（紫）：先冲到 10^62，再一步步缩短
        ea = smooth(self.tE + 0.3, self.tE + 0.6, t) * a
        if ea > 0:
            k = 50 * ease_in_out(lin(self.tE + 0.3, C["universe"] + 0.3, t))
            k += 12 * ease_out_expo(lin(C["bigger_u"] - 0.3, C["bigger_u"] + 0.5, t))
            k += (31 - 62) * ease_in_out(lin(C["suns"] - 0.2, C["suns"] + 0.5, t))
            k += (2.85 - 31) * ease_in_out(lin(C["probe"] - 0.2, C["probe"] + 0.5, t))
            xe = X(max(k, 0.5))
            hot = pulse(t, C["bigger_u"], 0.4) + pulse(t, C["suns"], 0.4) + pulse(t, C["probe"], 0.4)
            energy_bar(e, X(0), xe, 600, VIOLET, ea, hot)
            e.text("所需负能量", X(0), 555, 34, "sans_b", (0.85, 0.7, 1.0), ea, "lm", 0.1, 1.3)
            which = "e" if t < C["suns"] else ("s" if t < C["probe"] else "p")
            if t < C["bigger_u"] - 0.2:
                which = None                          # 还在涨的时候不标数值
            st = {"e": C["bigger_u"], "s": C["suns"], "p": C["probe"], None: C["bigger_u"]}[which]
            right = xe > X(50)                       # 条太长时把数值标在条的上方、末端左侧
            if which:
                self.lab[which].draw(xe - 10 if right else xe + 24, 560 if right else 620, anchor="r" if right else "l",
                                     alpha=ea, color=(0.85, 0.7, 1.0), intensity=1.5, fx=write_fx(t, st + 0.2, 0.4, 0.03))
            note = {"e": ("1997 · 最初估算", "比可观测宇宙还大约百亿倍"), "s": ("1999 · 改进", "几个太阳的质量"),
                    "p": ("2012 · 最乐观的设想", "一艘探测器的质量"), None: ("", "")}[which]
            na = smooth(st, st + 0.4, t)
            e.text(note[0], W / 2, 190, 34, "sans_m", DIM, ea * na, "mm", 0.15, 1.2)
            e.text(note[1], W / 2, 260, 64, "serif", WHITE, ea * na, "mm", 0.1, 1.5 + hot, scale=stamp(t, st, 0.4, 1.2))

    # ------------------------------------------------ 卡西米尔效应
    def phase_casimir(self, t):
        e = self.eng
        a = smooth(self.tK, self.tK + 0.12, t) * (1 - smooth(self.tH - 0.12, self.tH, t))
        space(e, neb=0.08 * a, stars=0.35 * a, c1=(0.04, 0.06, 0.16), c2=(0.12, 0.04, 0.12), seed=23.0)
        cx, cy = W / 2, 560
        gap = 150
        squeeze = 8 * smooth(C["exists"] - 0.2, C["exists"] + 0.8, t) * math.sin(t * 6) ** 2
        # 两块金属板：暗灰的板身 + 发丝轮廓，朝向缝隙的那一面一道细亮边（原来是两根发白的发光粗条，像灯管）
        for s in (-1, 1):
            x = cx + s * (gap / 2 + 14 - squeeze)
            e.rect(x - 12, cy - 230, 24, 460, 2, fill=(0.5, 0.55, 0.65), fill_a=0.35 * a, stroke=(0.75, 0.8, 0.9),
                   stroke_w=1.0, intensity=0.8)
            glowline(e, [(x - s * 12, cy - 228), (x - s * 12, cy + 228)], WHITE, a, width=1.6, k=1.0, halo=0.2)
        # 板外：各种波长的真空涨落；板间：只容得下整数个半波长
        rng = np.random.default_rng(3)
        xs_out = [np.linspace(150, cx - gap / 2 - 30, 900), np.linspace(cx + gap / 2 + 30, W - 150, 900)]   # 采样要密：最短波长只有 30 px，稀了波峰会折成尖角
        for k in range(9):
            lam = 30 + 140 * rng.random()
            amp = 26 + 30 * rng.random()
            y0 = cy - 190 + k * 47
            ph = t * (2.0 + rng.random() * 3) + rng.random() * 6
            col = mix3(CYAN, MAGENTA, k / 8)
            for xs in xs_out:
                ys = y0 + amp * 0.5 * np.sin(xs / lam * math.tau + ph)
                glowline(e, np.stack([xs, ys], 1), col, 0.75 * a, width=1.4, k=0.95)    # 波长短、拐弯急：不加柔光，否则波峰处冒出尖刺
        xs = np.linspace(cx - gap / 2, cx + gap / 2, 60)
        for n in (1, 2, 3):
            y0 = cy - 120 + n * 60
            ys = y0 + 22 * np.sin((xs - xs[0]) / gap * math.pi * n) * math.cos(t * (2 + n))
            glowline(e, np.stack([xs, ys], 1), GOLD, 0.9 * a, width=1.6, k=1.0, halo=0.25)
        pa = smooth(C["casimir"], C["casimir"] + 0.5, t) * a
        for s in (-1, 1):
            xo = cx + s * (gap / 2 + 180)
            arrow(e, xo, cy, cx + s * (gap / 2 + 40), cy, WHITE, pa, 3.0, 16, 0.6, 1.8)
        e.text("卡西米尔效应", W / 2, 170, 72, "serif", WHITE, vis(t, C["casimir"] - 0.2, self.tH, 0.3, 0.4), "mm", 0.15, 1.5,
               scale=stamp(t, C["casimir"], 0.4, 1.2))
        e.text("1948 年预言 · 1997 年精确测量", W / 2, 250, 28, "sans_m", DIM, vis(t, C["casimir"] + 0.3, self.tH, 0.4, 0.4),
               "mm", 0.15, 1.1)
        e.text("板外：所有波长的真空涨落", 380, cy + 300, 28, "sans_m", ICE, a * smooth(C["casimir"] + 0.5, C["casimir"] + 1.0, t),
               "mm", 0.1, 1.2)
        e.text("板间：只剩少数波长", cx, cy + 300, 28, "sans_m", GOLD, a * smooth(C["casimir"] + 0.8, C["casimir"] + 1.3, t), "mm",
               0.1, 1.2)
        xa = vis(t, C["exists"] - 0.1, self.tH, 0.25, 0.4)
        e.text("负能量存在", W - 380, cy + 300, 40, "sans_b", VIOLET, xa, "mm", 0.15, 1.6 + 1.5 * pulse(t, C["exists"], 0.4),
               scale=stamp(t, C["exists"], 0.4, 1.3))
        ta = vis(t, C["tiny"] - 0.1, self.tH, 0.3, 0.4)
        if ta > 0:
            self.lab["cas"].draw(W - 380, cy + 380, anchor="m", alpha=ta, color=(0.85, 0.7, 1.0), intensity=1.4,
                                 fx=write_fx(t, C["tiny"], 0.4, 0.03))
            e.text("（板间距 1 微米）", W - 380, cy + 430, 24, "sans_m", DIM, ta, "mm", 0.1, 1.0)

    # ------------------------------------------------ 因果视界：前沿收不到船上的信号
    def phase_horizon(self, t):
        e = self.eng
        lt = t - self.tH
        a = smooth(self.tH, self.tH + 0.12, t) * (1 - smooth(self.tX - 0.12, self.tX, t))
        cam = Camera((1.5, 9.5, 9.0), (0.6, -0.6, 0.0), fov=40, shift=(0.0, -0.1))
        relstars(e, cam, stars=0.6, neb=0.3, n1=(0.2, 0.05, 0.3), n2=(0.35, 0.05, 0.15))
        sl = smooth(C["superluminal"] - 0.3, C["superluminal"] + 0.6, t)
        flow = 1.0 * lt + 3.5 * max(0.0, t - C["superluminal"]) ** 1.3
        self.grid.draw(cam, L=15, flow=(flow, 0.0), cell=0.45, york=1.8 + 0.6 * sl, R=2.4, sigma=1.6, comp=0.3,
                       amt=a, hue_h=0.8, minor=0.2, fog=(9.0, 24.0), col_flat=(0.12, 0.3, 0.75))
        ship(e, cam, (0, 0.3, 0), roll(ship_frame((1, 0, 0)), lt * 0.3), 0.42, amt=a, ring=1.0 + sl, phase=t * 6,
             engine=0.8, sun=(0.3, 0.8, -0.5))
        # 前沿（视界）：一道红色弧
        ha = smooth(C["causal"] - 0.4, C["causal"], t) * a
        arc = [cam.project((2.4 * math.cos(th), 0.15, 2.4 * math.sin(th))) for th in np.linspace(-1.1, 1.1, 60)]
        arc = [p[:2] for p in arc if p]
        if ha > 0:
            glowline(e, arc, RED, ha, width=2.2, k=1.0, halo=0.3 + 0.1 * pulse(t, C["causal"], 0.4))
            p = cam.project((3.3, 0.4, 1.6))
            if p:
                e.text("前沿", p[0], p[1], 40, "sans_b", RED, ha, "mm", 0.2, 1.5)
        # 船上发出的信号：越靠近前沿越慢，永远到不了
        sa = smooth(C["causal"] - 1.0, C["causal"] - 0.6, t) * a
        for k in range(4):
            t0 = C["causal"] - 1.0 + k * 0.5
            if t > t0:
                x = 2.25 * (1 - math.exp(-(t - t0) / 0.7))
                for zz in (-0.4, 0.0, 0.4):
                    q = cam.project((0.3 + x, 0.25, zz * (1 - x / 3)))
                    if q:
                        e.circle(q[0], q[1], 4, fill=CYAN, fill_a=sa, glow=2, intensity=1.4)
        ca = vis(t, C["causal"], self.tX, 0.3, 0.4)
        e.text("失去因果联系", 140, 200, 64, "serif", WHITE, ca, "lm", 0.12, 1.5, scale=stamp(t, C["causal"], 0.4, 1.25))
        e.text("船上发出的信号，永远追不上泡泡的前沿", 146, 280, 30, "sans_m", ICE, ca, "lm", 0.1, 1.2)
        # 关不掉：电源图标 + 红叉
        oa = vis(t, C["noswitch"] - 0.1, self.tX, 0.25, 0.4)
        if oa > 0:
            cx, cy = W - 260, 240
            ring(e, cx, cy, 70, oa, WHITE, 5.0, 0.6, 120, 1.6, arc=(-math.pi * 0.35, math.pi * 1.35))
            glowline(e, [(cx, cy - 92), (cx, cy - 20)], WHITE, oa, width=2.2, k=0.95)
            k = ease_out_expo(lin(C["noswitch"], C["noswitch"] + 0.3, t))
            glowline(e, [(cx - 100, cy - 100), (cx - 100 + 200 * k, cy - 100 + 200 * k)], RED, oa, width=2.2, k=1.0, halo=0.3)
            e.text("无法从内部关闭", cx, cy + 130, 32, "sans_b", RED, oa, "mm", 0.15, 1.6)

    # ------------------------------------------------ 停下的瞬间：粒子倾泻，摧毁目的地
    def phase_blast(self, t):
        e = self.eng
        lt = t - self.tX
        a = smooth(self.tX, self.tX + 0.12, t)
        stop = C["stop"]
        moving = 1 - smooth(stop - 0.15, stop + 0.1, t)
        cam = Camera((-2.5, 1.2, 13.0), (2.4, -0.3, 0.0), fov=40)
        b = 0.85 * moving
        with Offscreen(e, 0) as bg:
            relstars(e, cam, beta=b, beta0=max(0.0, b - 0.3 * moving), motion=(1, 0, 0), stars=1.0, neb=0.35)
        sp, fw = cam.project((0, 0, 0)), cam.project((1, 0, 0))
        Rpx = 330.0
        if sp and fw:
            lens(e, bg, sp[:2], Rpx, (fw[0] - sp[0], fw[1] - sp[1]), warp=0.35 * moving + 0.05, rim=1.3 * moving + 0.2)
        # 目的地的行星（停下后从远处显现，被击中后烧穿）
        pa = smooth(stop - 0.6, stop + 0.4, t) * a
        burn = smooth(C["destroy"], C["destroy"] + 1.5, t)
        hit = pulse(t, C["destroy"], 0.6)
        pc = (1640.0 + 12 * hit * math.sin(t * 80), 430.0)
        if pa > 0:
            planet(e, pc, 170.0, light=(-0.6, 0.35, 0.7), amt=pa * (1 + 3 * hit), burn=burn, rot=t * 0.05)
        ship(e, cam, (0, 0, 0), roll(ship_frame((1, 0, 0)), 0.3 + lt * 0.5 * moving), 0.75, amt=a, ring=0.8 + 1.4 * moving,
             phase=t * 8 * moving, engine=0.9 * moving + 0.2, sun=(0.3, 0.8, -0.5))
        # 泡泡前沿堆积的高能粒子：越积越多、越来越亮
        if sp:
            n = int(260 * smooth(self.tX, stop, t))
            fill = smooth(self.tX, stop, t)
            burst = smooth(C["burst"] - 0.1, C["burst"] + 0.9, t)
            sparks = []
            if burst > 0:
                # 倾泻：一股柔和的光锥从泡泡前沿涌向行星，亮的前锋往前推（原来是两道粗光柱，泛光一晕成了长方形的光条）
                bx, by = sp[0] + Rpx, sp[1]
                ba = a * math.sin(min(burst, 1.0) * math.pi) ** 0.5
                f = min(1.0, burst * 1.6)
                hx, hy = bx + (pc[0] - 150 - bx) * f, by + (pc[1] - by) * f
                sparks.append(dict(tail=(bx, by), head=(hx, hy), color=AMBER, a=0.5 * ba, width=90.0, taper=0.25))
                sparks.append(dict(tail=(bx, by), head=(hx, hy), color=(1.0, 0.9, 0.75), a=0.9 * ba, width=10.0, taper=0.2))
            for i in range(n):
                if burst > 0 and i % 3:
                    continue
                u, v, w = self.dust[i]
                th = (u - 0.5) * 2.0
                rr = Rpx * (1.0 + 0.04 * v)
                x0, y0 = sp[0] + rr * math.cos(th), sp[1] + rr * math.sin(th) * 0.95
                if burst > 0:
                    # 倾泻：沿锥形射向行星
                    tx, ty = pc[0] - 130 + 260 * v, pc[1] - 120 + 240 * u
                    ang = math.atan2(ty - y0, tx - x0)
                    d = min(burst * (1.0 + 0.5 * w), 1.0) * math.hypot(tx - x0, ty - y0)
                    x0, y0 = x0 + d * math.cos(ang), y0 + d * math.sin(ang)
                    L = 40 + 70 * w
                    sparks.append(dict(tail=(x0 - L * math.cos(ang), y0 - L * math.sin(ang)), head=(x0, y0),
                                       color=mix3(GOLD, WHITE, w), a=1.3 * a * (1 - smooth(0.8, 1.0, burst)), width=2.0 + 1.5 * w,
                                       taper=0.05, spark=0.6))
                else:
                    e.circle(x0, y0, 2.2 + 1.5 * w, fill=mix3(AMBER, WHITE, w), fill_a=a, glow=3, intensity=1.5 + 2.5 * fill)
            streaks(e, sparks)
            if fill > 0 and burst < 1:
                ring(e, sp[0], sp[1], Rpx * 1.02, a * fill * (1 - burst), AMBER, 3.0, 1.0, 160, 2.0 + 2 * fill, arc=(-1.0, 1.0))
        la = vis(t, ls("F07") + 0.2, C["stop"], 0.3, 0.3)
        e.text("前沿不断积攒高能粒子", 140, 200, 44, "sans_b", AMBER, la, "lm", 0.1, 1.4)
        sa = vis(t, stop - 0.05, C["destroy"], 0.15, 0.2)
        e.text("停下！", 140, 220, 96, "serif", WHITE, sa, "lm", 0.1, 1.6, scale=stamp(t, stop, 0.35, 1.4))
        if hit > 0.001 or burn > 0:
            for k in range(3):
                r = (t - C["destroy"]) * (500 + 300 * k)
                if r > 0:
                    ring(e, pc[0], pc[1], 170 + r, a * math.exp(-(t - C["destroy"]) / (0.5 + 0.3 * k)), (1.0, 0.6, 0.3),
                         4.0 - k, 1.0, 200, 2.2)
        flat(e, (1.0, 0.85, 0.7), 1.6 * pulse(t, C["destroy"], 0.15) + 0.6 * pulse(t, stop, 0.12))
        da = vis(t, C["destroy"] + 0.2, self.t1, 0.3, 0.5)
        e.text("摧毁前方的一切", W / 2, 200, 64, "serif", (1.0, 0.55, 0.35), da, "mm", 0.15, 1.6)

    def render(self, t):
        if t < self.tE:
            self.phase_neg(t)
        elif t < self.tK:
            self.phase_scale(t)
        elif t < self.tH:
            self.phase_casimir(t)
        elif t < self.tX:
            self.phase_horizon(t)
        else:
            self.phase_blast(t)
        self.chapter_card(t)

    def post(self, t):
        if t >= self.tX:
            return dict(uBloomAmt=0.4, uVignette=0.85, uCA=0.012)
        return dict(uBloomAmt=0.5, uVignette=0.8, uTint=(1.02, 0.97, 1.05))
