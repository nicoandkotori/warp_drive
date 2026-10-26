# -*- coding: utf-8 -*-
"""第三章 肥皂船（童话开场 -> 水面上的小船、肥皂膜、表面张力 -> 水面变成时空膜：熨平后方、前方拉动 -> 曲率驱动）
第四章 曲率泡（1994 阿库别瑞度规 -> 前缩后胀的约克时间曲面 -> 曲率泡冲浪 -> 泡内无加速、时间照常 -> 比光还快）"""
import math
import numpy as np
from opusvid.scene import Scene
from opusvid.gl import ease_out, ease_in_out, ease_out_expo, smooth, lin, W, H, Camera
from opusvid.mathtex import Tex, write_fx, highlight_fx, combine
from cues import C, ls
from wfx import (CAM_GLSL, CYAN, GOLD, WHITE, DIM, ICE, cam_uniforms, bodies, flat, darkspot, stamp, arrow,
                 year_tag, pulse, vis, Offscreen, streaks, clock_face, glowline)
from ship import ship, ship_frame, roll, relstars, lens
from grid import Grid

# ---------------------------------------------------------------------- 童话开场：月夜的海（油画笔触）
STORY_FS = r"""
uniform float uAmt; uniform float uPush;
in vec2 vUV; out vec4 fragColor;
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    vec2 c = (P - uRes * 0.5) / (1.0 + uPush) + uRes * 0.5;     // 推镜
    float hor = uRes.y * 0.6;
    vec2 q = c / uRes.y;
    // 笔触：沿流场拉长的噪声
    vec2 flow = vec2(fbm2(q * 2.0 + 1.0, 4), fbm2(q * 2.0 + 7.0, 4)) - 0.5;
    float stroke = fbm2(vec2(q.x * 3.0 + flow.y * 2.0, q.y * 22.0 + flow.x * 6.0), 5);
    vec3 col;
    vec2 moon = vec2(uRes.x * 0.74, uRes.y * 0.2);
    if (c.y < hor){
        float alt = (hor - c.y) / hor;
        col = mix(vec3(0.05, 0.16, 0.24), vec3(0.015, 0.03, 0.09), pow(alt, 0.6));
        // 漩涡状的天空笔触（梵高式）
        vec2 s = (c - moon) / uRes.y;
        float sw = sin(length(s) * 26.0 - atan(s.y, s.x) * 2.0 + fbm2(q * 3.0, 4) * 6.0);
        col += vec3(0.1, 0.18, 0.35) * smoothstep(0.5, 1.0, sw) * 0.35 * (0.5 + stroke);
        col *= 0.75 + 0.5 * stroke;
        col += starfield2d(c * 1.2, uTime, 0.7) * smoothstep(0.0, 0.3, alt);
        // 月牙
        vec2 d = c - moon; float r = length(d);
        float disk = smoothstep(46.0, 43.0, r) * smoothstep(38.0, 42.0, length(d - vec2(-16.0, -9.0)));
        col += vec3(1.0, 0.9, 0.65) * disk * 3.0;
        col += vec3(1.0, 0.85, 0.55) * (exp(-r / 70.0) * 0.35 + exp(-r / 300.0) * 0.12);
    } else {
        float dep = (c.y - hor) / (uRes.y - hor);
        col = mix(vec3(0.02, 0.07, 0.1), vec3(0.005, 0.02, 0.035), dep);
        float wv = fbm2(vec2(c.x * 0.004, c.y * 0.04 - uTime * 0.15), 5);
        col *= 0.6 + 0.8 * wv * (0.6 + stroke * 0.6);
        // 月光倒影：竖向闪烁的光柱
        float colm = exp(-pow((c.x - moon.x) / (60.0 + 220.0 * dep), 2.0));
        float glit = pow(fbm2(vec2(c.x * 0.03, c.y * 0.25 - uTime * 0.8), 4), 3.0) * 6.0;
        col += vec3(1.0, 0.85, 0.55) * colm * glit * (0.4 + dep);
    }
    // 地平线上的一点光晕
    col += vec3(0.25, 0.4, 0.5) * exp(-abs(c.y - hor) / 8.0) * 0.25;
    fragColor = vec4(col * uAmt, 1.0);
}
"""

# ---------------------------------------------------------------------- 水面 + 小船 + 肥皂膜（俯视透视）
WATER_FS = CAM_GLSL + r"""
uniform vec2 uBoat;            // 小船位置（世界 xz），船头朝 +x；船体是三维的折纸小船（boatLocal）
uniform float uXs; uniform float uTs; uniform float uAcc; uniform float uNow;   // 抹肥皂的位置/时刻、加速度
uniform float uSoap;           // 肥皂膜总强度
uniform float uSpeed;          // 船速（尾迹强度）
uniform float uAmt; uniform float uBoatAmt;
uniform vec3 uMoon;
in vec2 vUV; out vec4 fragColor;
vec3 iris(float x){ return 0.5 + 0.5 * cos(TAU * (x + vec3(0.0, 0.33, 0.67))); }
// 肥皂膜厚度：船经过某处的时刻 t_pass(x) 由匀加速运动反解，膜从那时起向两侧扩散
float filmAt(vec2 p, out float age){
    age = 0.0;
    if (uSoap <= 0.0) return 0.0;
    float f = 0.0;
    // 抹肥皂处的一团，随时间向外摊开
    float a0 = max(uNow - uTs, 0.0);
    f = max(f, smoothstep(0.25 + 0.4 * sqrt(a0), 0.08 + 0.25 * sqrt(a0), length(p - vec2(uXs, uBoat.y))));
    float dx = p.x - uXs;
    if (dx > 0.0 && p.x < uBoat.x - 0.35){
        float tp = uTs + sqrt(2.0 * dx / max(uAcc, 1e-4));
        age = max(uNow - tp, 0.0);
        float w = 0.18 + 0.35 * sqrt(age);
        f = max(f, smoothstep(w, w * 0.55, abs(p.y - uBoat.y)));
    }
    return f * uSoap;
}
float waveH(vec2 p, float calm){
    float h = 0.0;
    h += 0.012 * sin(dot(p, vec2(0.8, 0.6)) * 9.0 + uTime * 2.6);
    h += 0.009 * sin(dot(p, vec2(-0.5, 0.9)) * 13.0 + uTime * 3.1);
    h += 0.02 * (fbm2(p * 4.0 + vec2(uTime * 0.4, uTime * 0.2), 4) - 0.5);
    h *= 1.0 - 0.7 * calm;                           // 肥皂降低表面张力，细碎波纹变平
    vec2 q = p - uBoat;
    if (q.x < 0.0){
        float ang = abs(q.y) / (-q.x + 0.3);
        float vl = exp(-pow((ang - 0.36) / 0.08, 2.0));   // 开尔文尾迹 ~19.5°
        h += 0.07 * uSpeed * vl * sin(length(q) * 12.0 - uTime * 8.0) * exp(q.x * 0.3);
        h += 0.04 * uSpeed * exp(-q.y * q.y * 10.0) * exp(q.x * 0.5) * (fbm2(q * 6.0 - vec2(uTime * 3.0, 0.0), 3) - 0.5) * 2.0;
    }
    return h;
}
// ---- 三维纸船（折纸小船，光线步进）。原来是画在水面上的二维轮廓，俯看像一架纸飞机（用户要求换模型）。
// 船体局部坐标：x 船头方向、y 向上、z 横向，单位 = 1/BOAT_S 世界单位
const float BOAT_S = 1.6;
// 船体：两端外斜的梯形船身（底短口长）、两侧船帮外张、船头船尾收尖；纸很薄，上口敞开
float hullSolid(vec3 p){
    vec2 q = vec2(abs(p.x), p.y);
    float az = abs(p.z);
    float h = max(-p.y - 0.06, p.y - 0.22);                               // 船底（略吃水）到船帮上沿
    h = max(h, dot(vec2(q.x - 0.33, q.y), vec2(1.0, -1.35)) / 1.68);         // 两端外斜：底长 0.5、口长 1.26
    h = max(h, (az - 0.04 - 0.8 * (p.y + 0.06)) / 1.28);                     // 船帮外张
    h = max(h, (az + 0.42 * q.x - 0.27) / 1.085);                           // 船头船尾收尖
    return h;
}
float boatLocal(vec3 p){
    float shell = max(abs(hullSolid(p)) - 0.008, p.y - 0.215);             // 只留一层纸，上口敞开
    // 中间立起的三角"帆"（两层纸叠成的尖顶，略带厚度）
    vec2 q = vec2(abs(p.x), p.y);
    float sail = max(-p.y, dot(vec2(q.x, q.y - 0.62), vec2(1.25, 1.0)) / 1.6);
    sail = max(sail, abs(p.z) - (0.006 + 0.07 * (0.62 - p.y)));
    return min(shell, sail);
}
// 世界坐标 -> 船体局部（随波轻轻俯仰、横摇）
vec3 toBoat(vec3 P){
    vec3 p = (P - vec3(uBoat.x, 0.0, uBoat.y)) / BOAT_S;
    float pitch = 0.035 * sin(uTime * 1.3), rollA = 0.05 * sin(uTime * 1.7 + 1.0);
    p.xy = mat2(cos(pitch), -sin(pitch), sin(pitch), cos(pitch)) * p.xy;
    p.zy = mat2(cos(rollA), -sin(rollA), sin(rollA), cos(rollA)) * p.zy;
    return p;
}
float boatW(vec3 P){ return boatLocal(toBoat(P)) * BOAT_S; }
// 光线与纸船求交（先用包围球裁掉），没打中返回 -1
float traceBoat(vec3 ro, vec3 rd){
    vec3 oc = ro - vec3(uBoat.x, 0.3, uBoat.y);
    float b = dot(oc, rd), c = dot(oc, oc) - 1.5 * 1.5, disc = b * b - c;
    if (disc < 0.0) return -1.0;
    float t = max(-b - sqrt(disc), 0.0), t1 = -b + sqrt(disc);
    for (int i = 0; i < 96; i++){
        float d = boatW(ro + rd * t);
        if (d < 0.0012 * max(t, 1.0)) return t;
        t += max(d * 0.8, 0.002);
        if (t > t1) break;
    }
    return -1.0;
}
// 纸船投在水面上的软阴影（沿月光方向步进）
float boatShadow(vec3 ro){
    float res = 1.0, t = 0.02;
    for (int i = 0; i < 32; i++){
        float d = boatW(ro + uMoon * t);
        res = min(res, 10.0 * d / t);
        t += clamp(d, 0.02, 0.2);
        if (res < 0.01 || t > 3.0) break;
    }
    return clamp(res, 0.0, 1.0);
}
vec3 shadeBoat(vec3 P, vec3 rd){
    float e = 0.002;
    vec3 n = normalize(vec3(boatW(P + vec3(e, 0, 0)) - boatW(P - vec3(e, 0, 0)), boatW(P + vec3(0, e, 0)) - boatW(P - vec3(0, e, 0)),
                            boatW(P + vec3(0, 0, e)) - boatW(P - vec3(0, 0, e))));
    if (dot(n, rd) > 0.0) n = -n;                                            // 纸是两面的
    vec3 lp = toBoat(P);
    vec3 paper = vec3(0.93, 0.9, 0.84) * (0.9 + 0.1 * fbm2(lp.xz * 40.0 + lp.y * 25.0, 3));
    float dif = max(dot(n, uMoon), 0.0);
    float back = max(dot(-n, uMoon), 0.0);                                   // 背光一面透出一点光（纸的半透明）
    float ao = 0.55 + 0.45 * smoothstep(-0.05, 0.2, lp.y);                   // 船舱里面、靠近船底的地方暗一些
    vec3 c = paper * (vec3(1.0, 0.88, 0.7) * dif * 0.85 + vec3(1.0, 0.85, 0.6) * back * 0.12 + vec3(0.05, 0.09, 0.15)) * ao;
    // 折痕：船帮上沿和帆的棱线上一点高光
    c += vec3(1.0, 0.92, 0.8) * pow(max(dot(reflect(rd, n), uMoon), 0.0), 30.0) * 0.25;
    return c;
}
vec3 sky(vec3 r){
    vec3 c = mix(vec3(0.035, 0.07, 0.13), vec3(0.005, 0.012, 0.04), pow(clamp(r.y, 0.0, 1.0), 0.5));
    float m = max(dot(r, uMoon), 0.0);
    c += vec3(1.0, 0.85, 0.6) * (pow(m, 400.0) * 0.5 + pow(m, 8.0) * 0.05);
    return c;
}
void main(){
    vec3 rd = camRay(vUV);
    if (rd.y >= -1e-4){
        // 地平线以上：只可能看到纸船的帆尖
        float tb = uBoatAmt > 0.0 ? traceBoat(uEye, rd) : -1.0;
        fragColor = vec4(tb > 0.0 ? shadeBoat(uEye + rd * tb, rd) * uBoatAmt * uAmt : vec3(0.0), 1.0);
        return;
    }
    float tt = -uEye.y / rd.y;
    vec3 P3 = uEye + rd * tt;
    vec2 p = P3.xz;
    float age;
    float film = filmAt(p, age);
    float e = 0.02;
    float h0 = waveH(p, film);
    vec3 n = normalize(vec3(-(waveH(p + vec2(e, 0.0), film) - h0) / e, 1.0, -(waveH(p + vec2(0.0, e), film) - h0) / e));
    vec3 r = reflect(rd, n);
    float fr = 0.02 + 0.98 * pow(1.0 - max(dot(n, -rd), 0.0), 5.0);
    vec3 water = vec3(0.0, 0.018, 0.035) * (0.6 + 0.8 * fbm2(p * 0.7, 3));
    vec3 refl = sky(r);
    if (uBoatAmt > 0.0){
        // 水里纸船的倒影、水面上的阴影
        float tr = traceBoat(P3 + r * 0.01, r);
        if (tr > 0.0) refl = mix(refl, shadeBoat(P3 + r * (0.01 + tr), r) * 0.7, uBoatAmt);
        water *= 1.0 - 0.5 * (1.0 - boatShadow(P3)) * uBoatAmt;
    }
    vec3 col = mix(water, refl, fr);
    col += vec3(1.0, 0.85, 0.6) * pow(max(dot(r, uMoon), 0.0), 2500.0) * 3.0;
    // 肥皂膜：薄膜干涉的彩虹色 + 打旋的纹理
    if (film > 0.0){
        vec2 sw = vec2(fbm2(p * 1.2 + age * 0.3, 4), fbm2(p * 1.2 + 5.0 - age * 0.2, 4));
        float th = fbm2(p * 2.2 + sw * 2.5, 5) * 2.4 + age * 0.15;
        vec3 ic = mix(vec3(0.75), iris(th), 0.7);          // 真实的皂膜是淡淡的虹彩，不是满饱和
        col += ic * film * (0.08 + 0.4 * fr + 0.25 * pow(max(dot(r, uMoon), 0.0), 20.0));
        col += vec3(1.0) * film * pow(max(dot(r, uMoon), 0.0), 200.0) * 2.0;
    }
    float fog = exp(-tt * 0.035);
    // 纸船（白纸折的，月光照着有一点暖色）：在水面之前被看到的部分盖在水面上
    if (uBoatAmt > 0.0){
        float tb = traceBoat(uEye, rd);
        if (tb > 0.0 && tb < tt) col = mix(col, shadeBoat(uEye + rd * tb, rd), uBoatAmt);
    }
    fragColor = vec4(col * fog * uAmt, 1.0);
}
"""


class Ch3(Scene):
    chapter = True

    def setup(self):
        self.grid = Grid(self.eng)
        self.tB, self.tM, self.tV = C["boat"], ls("D04"), ls("D05")
        self.acc = 0.42

    def boat_x(self, t):
        """抹上肥皂之后匀加速向前（WATER_FS 里用同一个公式反解 t_pass）。"""
        x = max(0.0, t - C["soap"])
        return 0.5 * self.acc * x * x

    # ------------------------------------------------ 童话开场
    def phase_story(self, t):
        e = self.eng
        a = smooth(self.t0 + 0.2, self.t0 + 1.2, t)
        push = 0.12 * smooth(C["fairy"] - 0.6, self.tB, t) ** 2
        e.draw_fs("wd_story", STORY_FS, dict(uAmt=a * (1 - smooth(self.tB - 0.25, self.tB, t)), uPush=push), blend="add")
        # 金色画框
        fa = a * vis(t, ls("D01") - 0.5, self.tB, 0.6, 0.3)
        m = 60
        e.rect(m, m, W - 2 * m, H - 2 * m, 6, fill=(0, 0, 0), fill_a=0.0, stroke=GOLD, stroke_w=1.5 * fa)
        for (x, y) in ((m, m), (W - m, m), (m, H - m), (W - m, H - m)):
            e.circle(x, y, 7, fill=GOLD, fill_a=fa, glow=3, intensity=1.6)
        ta = vis(t, ls("D01") + 0.3, self.tB, 0.6, 0.3)
        darkspot(e, W / 2, 330, 620, 200, 0.5 * ta)
        g = pulse(t, C["fairy"], 0.5)
        e.text("云天明的童话", W / 2, 330, 104, "serif", GOLD, ta, "mm", 0.18, 1.5 + g, t=t, start=ls("D01") + 0.3,
               dur=0.8, stagger=0.12, kind="blur")
        for k, nm in enumerate(("《王国的新画师》", "《饕餮海》", "《深水王子》")):
            st = ls("D01") + 1.2 + k * 0.5
            e.text(nm, W / 2 + (k - 1) * 330, 455, 30, "sans_m", (1.0, 0.92, 0.75), vis(t, st, self.tB, 0.5, 0.3), "mm",
                   0.12, 1.2, t=t, start=st, dur=0.6)
        e.text("小说《三体 III · 死神永生》", W / 2, 520, 24, "sans_m", DIM, vis(t, ls("D01") + 2.4, self.tB, 0.5, 0.3),
               "mm", 0.2, 1.0)
        flat(e, (1.0, 0.9, 0.7), 0.6 * smooth(self.tB - 0.25, self.tB, t))

    # ------------------------------------------------ 水面
    def water_cam(self, t):
        bx = self.boat_x(t)
        k = smooth(self.tB, self.tB + 3.0, t)
        eye = (bx - 2.2 - 1.0 * k, 3.8 - 0.6 * k, -2.9 + 0.5 * k)
        return Camera(eye, (bx + 0.6, 0.0, 0.0), fov=40.0)

    def phase_water(self, t, amt=1.0, boat_amt=1.0):
        e = self.eng
        cam = self.water_cam(t)
        bx = self.boat_x(t)
        speed = self.acc * max(0.0, t - C["soap"])
        u = cam_uniforms(cam)
        moon = np.array([0.5, 0.45, 0.75])
        u.update(uBoat=(bx, 0.0), uXs=-0.55, uTs=C["soap"], uAcc=self.acc, uNow=t,
                 uSoap=smooth(C["soap"] - 0.1, C["soap"] + 0.5, t), uSpeed=min(1.0, speed * 0.6), uAmt=amt,
                 uBoatAmt=boat_amt, uMoon=tuple(moon / np.linalg.norm(moon)))
        e.draw_fs("wd_water", WATER_FS, u, blend="add")
        return cam, bx

    def water_overlay(self, t, cam, bx):
        e = self.eng
        a = vis(t, self.tB, self.tM, 0.4, 0.4)
        # 抹肥皂的闪光
        g = pulse(t, C["soap"], 0.5)
        q = cam.project((bx - 0.55, 0.0, 0.0))
        if q and g > 0.01:
            bodies(e, [(q[0], q[1], 6, 2.5 * g, (1.0, 0.95, 0.9), 0.8)])
        ls_ = vis(t, C["soap"] - 0.1, C["tension"], 0.3, 0.4)
        if q:
            e.text("香皂", q[0] - 20, q[1] + 60, 30, "sans_b", WHITE, ls_ * a, "rm", 0.2, 1.3)
        # 表面张力箭头：船尾弱、船头强
        ta = vis(t, C["tension"], self.tM, 0.4, 0.4) * a
        if ta > 0:
            pr = ease_out_expo(lin(C["tension"], C["tension"] + 0.6, t))
            pf = ease_out_expo(lin(C["front_water"], C["front_water"] + 0.6, t))
            for zz in (-0.35, 0.0, 0.35):
                p0, p1 = cam.project((bx - 0.75, 0, zz)), cam.project((bx - 1.05, 0, zz))
                if p0 and p1:
                    arrow(e, p0[0], p0[1], p1[0], p1[1], (1.0, 0.45, 0.4), ta, 2.5, 12, 0.6, 1.6, progress=pr)
                p0, p1 = cam.project((bx + 0.75, 0, zz)), cam.project((bx + 1.9, 0, zz))
                if p0 and p1:
                    arrow(e, p0[0], p0[1], p1[0], p1[1], CYAN, ta * smooth(C["front_water"] - 0.1, C["front_water"] + 0.2, t),
                          3.5, 18, 0.8, 2.0, progress=pf)
            pb, pfr = cam.project((bx - 1.3, 0, 0.75)), cam.project((bx + 2.0, 0, 0.75))
            if pb:
                e.text("张力弱", pb[0], pb[1] + 30, 30, "sans_b", (1.0, 0.55, 0.5), ta * pr, "mm", 0.15, 1.4)
            if pfr:
                e.text("张力强", pfr[0], pfr[1] + 30, 30, "sans_b", CYAN, ta * pf, "mm", 0.15, 1.6)
            # 合力：把船拉向前方
            pa = smooth(C["pull"] - 0.2, C["pull"] + 0.2, t)
            p0, p1 = cam.project((bx - 0.2, 0.0, -0.8)), cam.project((bx + 1.6, 0.0, -0.8))
            if p0 and p1 and pa > 0:
                arrow(e, p0[0], p0[1], p1[0], p1[1], GOLD, ta * pa, 6.0, 26, 1.0, 2.0 + 2 * pulse(t, C["pull"], 0.4),
                      progress=ease_out_expo(lin(C["pull"] - 0.2, C["pull"] + 0.4, t)))

    # ------------------------------------------------ 水面 -> 时空膜：熨平后方、前方拉动
    def ship_x(self, t):
        x = max(0.0, t - C["pullship"])
        return 1.2 * x * x

    def phase_space(self, t):
        e = self.eng
        k = smooth(self.tM, self.tM + 1.2, t)                 # 水面淡出 / 网格淡入
        if k < 1:
            self.phase_water(t, 1 - k, 1 - k)
        bx0 = self.boat_x(self.tM)
        sx = bx0 + self.ship_x(t)
        cw = self.water_cam(min(t, self.tM + 1.2))
        eye = np.asarray(cw.eye) + np.array([sx - bx0, 0.0, 0.0])        # 镜头跟着飞船平移
        cam = Camera(tuple(eye + np.array([-1.5, 1.2, -1.8]) * k), (sx + 0.6, -0.4 * k, 0.0), fov=40.0)
        well_b = 1.3 * (1 - ease_in_out(lin(C["iron"], C["iron"] + 0.9, t)))
        well_f = 1.3 + 0.9 * ease_out(lin(C["curved"], C["curved"] + 0.6, t))
        gk = dict(ship=(sx, 0.0), well_f=well_f, well_b=well_b, well_s=1.7)
        relstars(e, cam, stars=0.6 * k, neb=0.3 * k)
        # 网格跟着飞船走，但中心按格距取整，网格线在世界里保持不动（看得出飞船在前进）
        self.grid.draw(cam, L=18, center=(round(sx / 0.45) * 0.45, 0.0), cell=0.45, amt=k, hue_h=1.2, minor=0.25, fog=(8.0, 24.0),
                       col_neg=(0.3, 0.85, 1.0), col_flat=(0.15, 0.4, 0.95), **gk)
        sh = self.grid.height(sx, 0.0, **gk)
        ship(e, cam, (sx, sh + 0.32, 0.0), roll(ship_frame((1, 0, 0)), 0.3 + t * 0.2), 0.3, amt=k,
             ring=0.6 + 1.5 * smooth(C["pullship"] - 0.3, C["pullship"], t), phase=t * 5, engine=0.6, sun=(0.3, 0.8, -0.5))
        la = vis(t, C["iron"] - 0.1, self.tV, 0.3, 0.4)
        p = cam.project((sx - 3.2, 0.3, 1.6))
        if p:
            e.text("后方：熨平", p[0], p[1], 34, "sans_b", GOLD, la, "mm", 0.15, 1.4 + pulse(t, C["iron"], 0.4))
        lb = vis(t, C["curved"] - 0.1, self.tV, 0.3, 0.4)
        p = cam.project((sx + 2.6, 0.3, 1.8))
        if p:
            e.text("前方：弯曲", p[0], p[1], 34, "sans_b", CYAN, lb, "mm", 0.15, 1.6 + pulse(t, C["curved"], 0.4))
        return cam

    def phase_name(self, t):
        e = self.eng
        cam = self.phase_space(t)
        a = smooth(C["curvature"] - 0.05, C["curvature"] + 0.15, t) * (1 - smooth(self.t1 - 0.7, self.t1 - 0.2, t))
        if a > 0:
            y = 300
            darkspot(e, W / 2, y + 20, 700, 230, 0.7 * a)
            sc = stamp(t, C["curvature"], 0.45, 1.4)
            e.text("曲率驱动", W / 2, y, 170, "serif", CYAN, 0.25 * a, "mm", 0.14, 1.2, scale=sc * 1.03, blur=20)
            e.text("曲率驱动", W / 2, y, 170, "serif", WHITE, a, "mm", 0.14, 1.4 + 1.5 * pulse(t, C["curvature"], 0.4), scale=sc)
            e.text("CURVATURE  PROPULSION", W / 2, y + 125, 26, "latin_m", ICE, a, "mm", 0.6, 1.5, t=t,
                   start=C["curvature"] + 0.2, dur=0.8, stagger=0.02, kind="spread")
        flat(e, (0.6, 0.85, 1.0), 0.6 * pulse(t, C["curvature"], 0.2))
        return cam

    def render(self, t):
        if t < self.tB:
            self.phase_story(t)
        elif t < self.tM:
            cam, bx = self.phase_water(t)
            self.water_overlay(t, cam, bx)
            flat(self.eng, (1.0, 0.9, 0.7), 0.6 * (1 - smooth(self.tB, self.tB + 0.35, t)))
        elif t < self.tV:
            self.phase_space(t)
        else:
            self.phase_name(t)
        self.chapter_card(t)

    def post(self, t):
        if t < self.tB:
            return dict(uBloomAmt=0.55, uVignette=0.9, uGrain=0.05, uSat=1.1)
        if t < self.tM:
            return dict(uBloomAmt=0.5, uVignette=0.85, uSat=1.15)
        return dict(uBloomAmt=0.55, uVignette=0.75)


# ====================================================================== 第四章
class Ch4(Scene):
    chapter = True

    def setup(self):
        self.grid = Grid(self.eng)
        self.metric = Tex(self.eng, [(r"ds^2", "ds"), "=", (r"-c^2dt^2", "t"), "+", (r"(dx-v_s\,", "a"),
                                     (r"f(r_s)", "f"), (r"\,dt)^2", "b"), (r"+dy^2+dz^2", "yz")], size=74)
        self.tY, self.tS, self.tB, self.tI, self.tF = ls("E02"), ls("E03"), ls("E04"), ls("E05"), ls("E06")

    def york_cam(self, t, t0):
        lt = t - t0
        az = 2.35 + 0.06 * lt
        eye = (11.5 * math.sin(az), 6.2 - 0.4 * min(lt, 6) / 6, 11.5 * math.cos(az))
        return Camera(eye, (0.4, -0.8, 0.0), fov=40, shift=(0.0, -0.12))

    # ------------------------------------------------ 开场：平直的膜，飞船悬着
    def phase_intro(self, t):
        e = self.eng
        cam = self.york_cam(t, self.t0)
        relstars(e, cam, stars=0.7, neb=0.35)
        a = smooth(self.t0, self.t0 + 1.0, t) * (1 - smooth(self.tY - 0.12, self.tY, t))
        self.grid.draw(cam, L=16, cell=0.5, amt=a, minor=0.2, fog=(9.0, 26.0), col_flat=(0.15, 0.4, 0.95), wave=0.08,
                       time=t)
        ship(e, cam, (0, 0.35, 0), roll(ship_frame((1, 0, 0)), t * 0.2), 0.42, amt=a, ring=0.5, phase=t * 2,
             engine=0.4, sun=(0.3, 0.8, -0.5))
        la = vis(t, C["coincide"] + 0.4, self.tY, 0.5, 0.4)
        e.text("现实中的物理学家", W / 2, 200, 56, "serif", WHITE, la, "mm", 0.15, 1.3, t=t, start=C["coincide"] + 0.4,
               dur=0.6, stagger=0.06)

    # ------------------------------------------------ 1994 阿库别瑞
    def phase_alc(self, t):
        e = self.eng
        a = smooth(self.tY, self.tY + 0.12, t) * (1 - smooth(self.tS - 0.12, self.tS, t))
        cam = self.york_cam(t, self.t0)
        relstars(e, cam, stars=0.5, neb=0.25)
        self.grid.draw(cam, L=16, cell=0.5, amt=0.35 * a, minor=0.1, fog=(9.0, 26.0), col_flat=(0.15, 0.4, 0.95))
        darkspot(e, W / 2, H / 2, 900, 420, 0.75 * a)
        year_tag(e, t, self.tY, "1994", "米格尔 · 阿库别瑞", "MIGUEL ALCUBIERRE", x=170, y=230, out=self.tS - 0.6, color=CYAN)
        fa = a
        fx = combine(write_fx(t, C["alc"] + 0.2, 0.5, 0.045, tex=self.metric),
                     highlight_fx(t, ["f"], C["solution"], color=GOLD, glow=0.6, pulse=1.2))
        self.metric.draw(W / 2, 640, anchor="m", alpha=fa, intensity=1.4, fx=fx)
        ha = vis(t, C["solution"], self.tS, 0.3, 0.4)
        if ha > 0:
            p = self.metric.anchor_pt("f", W / 2, 640, anchor="m", where="b")
            glowline(e, [(p[0], p[1] + 14), (p[0], p[1] + 70)], GOLD, ha, width=1.4, k=1.0)
            e.text("曲率泡的形状", p[0], p[1] + 100, 30, "sans_b", GOLD, ha, "mm", 0.15, 1.4)
        e.text("广义相对论的一个精确解", W / 2, 520, 30, "sans_m", DIM, vis(t, C["solution"] + 0.3, self.tS, 0.4, 0.4),
               "mm", 0.2, 1.1)

    # ------------------------------------------------ 前缩后胀 + 曲率泡
    def york(self, t):
        c = 2.2 * ease_out(lin(C["contract"] - 0.2, C["contract"] + 0.6, t))
        x = ease_out(lin(C["expand2"] - 0.2, C["expand2"] + 0.6, t))
        return c, x

    def phase_york(self, t):
        e = self.eng
        cam = self.york_cam(t, self.t0)
        relstars(e, cam, stars=0.7, neb=0.35)
        amp, xk = self.york(t)
        # 先只有前方凹陷（收缩），说到"膨胀"时后方隆起：用 york 振幅 + 对后半边单独加权实现
        surf = smooth(C["surf"] - 0.3, C["surf"] + 0.6, t)
        flow = 0.0
        if t > C["surf"]:
            x = t - C["surf"]
            flow = 1.6 * x + 0.9 * max(0.0, t - C["pushed"]) ** 2
        york_amp = amp * (0.55 + 0.45 * xk)
        self.grid.draw(cam, L=16, flow=(flow, 0.0), cell=0.45, york=york_amp, comp=0.32 * xk + 0.1 * (amp > 0),
                       R=2.0, sigma=1.6, hue_h=0.8, minor=0.25, fill=0.1, fog=(9.0, 26.0), col_flat=(0.15, 0.4, 0.95),
                       wells=[(-1.6, 0.0, -1.2 * (1 - xk) * (amp / 2.2), 0.7)] if xk < 1 else [])
        ship(e, cam, (0, 0.3, 0), roll(ship_frame((1, 0, 0)), t * 0.3), 0.42, ring=0.6 + 1.2 * (amp / 2.2) + 0.8 * surf,
             phase=t * (3 + 4 * surf), engine=0.6 + 0.5 * surf, sun=(0.3, 0.8, -0.5))
        # 标注：前方收缩（蓝）/ 后方膨胀（红）
        pf = cam.project((3.2, -1.6, 0.0))
        pb = cam.project((-3.2, 1.7, 0.0))
        ca = vis(t, C["contract"], self.tB + 1.2, 0.3, 0.5)
        if pf:
            e.text("收缩", pf[0], pf[1] + 30, 56, "serif", CYAN, ca, "mm", 0.1, 1.6 + pulse(t, C["contract"], 0.4),
                   scale=stamp(t, C["contract"], 0.4, 1.3))
            e.text("CONTRACT · 前方", pf[0], pf[1] + 82, 22, "latin_m", ICE, ca, "mm", 0.3, 1.2)
        xa = vis(t, C["expand2"], self.tB + 1.2, 0.3, 0.5)
        if pb:
            e.text("膨胀", pb[0], pb[1] - 40, 56, "serif", (1.0, 0.5, 0.35), xa, "mm", 0.1, 1.6 + pulse(t, C["expand2"], 0.4),
                   scale=stamp(t, C["expand2"], 0.4, 1.3))
            e.text("EXPAND · 后方", pb[0], pb[1] + 10, 22, "latin_m", (1.0, 0.7, 0.6), xa, "mm", 0.3, 1.2)
        # 曲率泡：船周围的平坦区域，一圈标注
        ba = vis(t, C["bubble"] - 0.2, self.tI, 0.3, 0.4)
        if ba > 0:
            pts = [cam.project((1.5 * math.cos(th), 0.05, 1.5 * math.sin(th))) for th in np.linspace(0, math.tau, 100)]
            pts = [p[:2] for p in pts if p]
            glowline(e, pts, WHITE, ba, width=1.6, k=0.8 + 0.2 * pulse(t, C["bubble"], 0.4), halo=0.25 + 0.15 * pulse(t, C["bubble"], 0.4))
            p = cam.project((0.0, 1.6, 1.4))
            if p:
                e.text("曲率泡", p[0], p[1] - 20, 44, "sans_b", WHITE, ba, "mm", 0.2, 1.5)
                e.text("WARP BUBBLE · 内部平坦", p[0], p[1] + 22, 22, "latin_m", DIM, ba, "mm", 0.2, 1.1)
        sa = vis(t, C["surf"], self.tI, 0.3, 0.4)
        e.text("像冲浪一样", 140, 200, 56, "serif", GOLD, sa, "lm", 0.12, 1.4, t=t, start=C["surf"], dur=0.5)

    # ------------------------------------------------ 泡内：没有加速感，时间照常
    def phase_inside(self, t):
        e = self.eng
        lt = t - self.tI
        cam = Camera((-1.6 + 0.4 * lt / 8, 1.5, -6.8 + 0.4 * lt / 8), (0.4, 0.1, 0.6), fov=44)
        with Offscreen(e, 0) as bg:
            relstars(e, cam, beta=0.0, stars=1.0, neb=0.4)
        sp, fw = cam.project((0, 0, 0)), cam.project((1, 0, 0))
        if sp and fw:
            lens(e, bg, sp[:2], 760.0, (fw[0] - sp[0], fw[1] - sp[1]), warp=0.22 + 0.04 * math.sin(t * 2), rim=1.2)
        ship(e, cam, (0, 0, 0), roll(ship_frame((1, 0, 0)), 0.4 + 0.05 * math.sin(t * 0.7)), 1.0, ring=1.6, phase=t * 6,
             engine=0.8, sun=(0.3, 0.8, -0.5))
        # HUD：加速度 0 g；船内时钟与地球时钟同步
        ga = vis(t, C["accel"] - 0.2, self.tF, 0.3, 0.4)
        x0 = 120
        e.text("船内加速度", x0, 210, 30, "sans_m", ICE, ga, "lm", 0.15, 1.2)
        e.text("0 g", x0, 300, 110, "latin_b", WHITE, ga, "lm", 0.04, 1.5 + pulse(t, C["accel"], 0.4),
               scale=stamp(t, C["accel"], 0.4, 1.3))
        ca = vis(t, C["clock"] - 0.2, self.tF, 0.3, 0.4)
        # 两只表：精密表盘（细表圈、60 根细刻度、渐细的指针，指针身后一段淡弧表示走过的时间），
        # 原来是粗白圈 + 发光粗指针，泛光一晕像两根灯管；表盘压在船体上，背后垫一块暗斑让它读得清
        if ca > 0.003:
            darkspot(e, W - 370, 320, 760, 360, 0.6 * ca)
        ang = max(t - C["clock"], 0.0) * math.tau / 4.0                 # 两只表同步走，4 秒一圈
        for k, (nm, cx) in enumerate((("船内时钟", W - 520), ("地球时钟", W - 220))):
            cy = 300
            clock_face(e, cx, cy, 92, ang, ca, CYAN if k == 0 else GOLD, sweep0=max(0.0, ang - 2.2))
            e.text(nm, cx, cy + 130, 30, "sans_b", CYAN if k == 0 else GOLD, ca, "mm", 0.15, 1.3)
        e.text("=", W - 370, 300, 72, "latin_b", WHITE, ca, "mm", 0.0, 1.5)

    # ------------------------------------------------ 比光还快
    def phase_ftl(self, t):
        e = self.eng
        lt = t - self.tF
        a = smooth(self.tF, self.tF + 0.12, t)
        cam = Camera((-2.6, 1.0, 9.5), (0.8, -0.6, 0.0), fov=42)
        b = 0.9 * smooth(self.tF, C["ftl2"], t)
        with Offscreen(e, 0) as bg:
            relstars(e, cam, beta=b, beta0=max(0.0, b - 0.25), motion=(1, 0, 0), stars=1.0, neb=0.3)
        sp, fw = cam.project((0, 0, 0)), cam.project((1, 0, 0))
        if sp and fw:
            lens(e, bg, sp[:2], 520.0, (fw[0] - sp[0], fw[1] - sp[1]), warp=0.3 + 0.2 * b, rim=1.5)
        ship(e, cam, (0, 0, 0), roll(ship_frame((1, 0, 0)), 0.4 + lt * 0.8), 0.9, ring=1.8 + 1.5 * b, phase=t * 12,
             engine=1.2, sun=(0.3, 0.8, -0.5))
        # 一束光（光子）：起初与飞船并排，随后被甩在后面
        px = 3.0 - 9.0 * smooth(self.tF + 0.6, C["ftl2"] + 0.6, t) ** 1.5
        q = cam.project((px, -1.4, 0.0))
        if q:
            tail = cam.project((px - 2.4, -1.4, 0.0))
            if tail:
                streaks(e, [dict(tail=tail[:2], head=q[:2], color=GOLD, a=1.6 * a, width=5.0, spark=1.8)])
            e.text("光", q[0], q[1] + 40, 30, "sans_b", GOLD, a * (1 - smooth(C["ftl2"] + 0.3, C["ftl2"] + 0.8, t)), "mm",
                   0.1, 1.4)
        fa = smooth(C["ftl2"] - 0.05, C["ftl2"] + 0.1, t) * (1 - smooth(self.t1 - 0.6, self.t1 - 0.1, t))
        if fa > 0:
            sc = stamp(t, C["ftl2"], 0.45, 1.5)
            e.text("v > c", W / 2, 230, 170, "latin_b", WHITE, fa, "mm", 0.04, 1.5 + 2 * pulse(t, C["ftl2"], 0.4), scale=sc)
            e.text("比光还快", W / 2, 350, 44, "sans_b", CYAN, fa, "mm", 0.4, 1.5)
        flat(e, (0.6, 0.85, 1.0), 0.6 * pulse(t, C["ftl2"], 0.2))

    def render(self, t):
        if t < self.tY:
            self.phase_intro(t)
        elif t < self.tS:
            self.phase_alc(t)
        elif t < self.tI:
            self.phase_york(t)
        elif t < self.tF:
            self.phase_inside(t)
        else:
            self.phase_ftl(t)
        self.chapter_card(t)

    def post(self, t):
        if self.tI <= t < self.tF:
            return dict(uBloomAmt=0.5, uVignette=0.8, uCA=0.008)
        if t >= self.tF:
            return dict(uBloomAmt=0.55, uVignette=0.85, uCA=0.02)
        return dict(uBloomAmt=0.55, uVignette=0.75)
