# -*- coding: utf-8 -*-
"""第六章 航迹（《三体》）：星环号 -> 太阳系被二向箔压成一幅画 -> 星环号点火逃离、留下航迹
-> 航迹让光速变慢，无数航迹叠成黑域 -> 通往星辰的引擎也可能是牢笼。"""
import math
import numpy as np
from opusvid.scene import Scene
from opusvid.gl import ease_out, ease_in_out, ease_out_expo, smooth, lin, W, H, Camera
from cues import C, ls
from wfx import (CAM_GLSL, CYAN, GOLD, WHITE, DIM, ICE, cam_uniforms, space, bodies, flat, stamp, ring,
                 pulse, vis, mix3, streaks)
from ship import ship, ship_frame, roll, relstars
from scenes_ch5 import planet
import warpfield as F

# 二维化的太阳系：y=0 平面上的"画"——太阳摊成巨大的同心色环，行星落进来后摊开成层层叠叠的圆盘，
# 空白处是梵高式的旋涡笔触。所有东西自发光（二维世界没有光照）。
FLAT2D_FS = CAM_GLSL + r"""
uniform float uZone;        // 二维化区域半径（世界单位）
uniform vec4 uP[4];         // 摊开的行星：x, z, 当前半径, 种类（0 地球 1 木星 2 海王星 3 火星）
uniform float uAmt; uniform float uSunR;
in vec2 vUV; out vec4 fragColor;
vec3 hot(float x){
    x = clamp(x, 0.0, 1.0);
    return mix(mix(vec3(1.0, 0.98, 0.9), vec3(1.0, 0.75, 0.25), smoothstep(0.0, 0.35, x)),
               mix(vec3(0.95, 0.3, 0.08), vec3(0.35, 0.03, 0.08), smoothstep(0.6, 1.0, x)), smoothstep(0.3, 0.75, x));
}
vec3 layers(float r, int kind, float n){
    // 行星内部结构按半径一圈圈摊开：核 -> 幔 -> 壳 -> 海洋/云 -> 大气
    if (kind == 0){
        if (r < 0.35) return mix(vec3(1.0, 0.85, 0.5), vec3(1.0, 0.45, 0.1), r / 0.35) * 1.6;
        if (r < 0.75) return mix(vec3(0.9, 0.35, 0.08), vec3(0.45, 0.12, 0.05), (r - 0.35) / 0.4) * (0.8 + 0.4 * n);
        if (r < 0.86) return vec3(0.35, 0.28, 0.2) * (0.7 + 0.6 * n);
        if (r < 0.95) return mix(vec3(0.05, 0.25, 0.65), vec3(0.15, 0.5, 0.25), step(0.55, n)) * 1.2;
        return vec3(0.6, 0.8, 1.0) * 0.9;
    } else if (kind == 1){
        float band = sin(r * 60.0 + n * 6.0);
        return mix(vec3(0.85, 0.6, 0.35), vec3(0.95, 0.88, 0.75), 0.5 + 0.5 * band) * (r < 0.3 ? 1.6 : 1.0);
    } else if (kind == 2){
        return mix(vec3(0.15, 0.3, 0.95), vec3(0.5, 0.85, 1.0), 0.5 + 0.5 * sin(r * 40.0 + n * 5.0)) * (r < 0.25 ? 1.5 : 1.0);
    }
    return mix(vec3(0.85, 0.35, 0.15), vec3(0.6, 0.25, 0.12), 0.5 + 0.5 * sin(r * 30.0 + n * 4.0));
}
void main(){
    vec3 rd = camRay(vUV);
    if (rd.y >= -1e-4){ fragColor = vec4(0); return; }
    float tt = -uEye.y / rd.y;
    vec2 p = (uEye + rd * tt).xz;
    float R = length(p);
    if (R > uZone + 3.0){ fragColor = vec4(0); return; }
    vec2 flow = vec2(fbm2(p * 0.05 + 3.0, 4), fbm2(p * 0.05 + 9.0, 4)) - 0.5;
    // 背景：深蓝底 + 旋涡笔触 + 点点"星"
    float ang = atan(p.y, p.x);
    float sw = sin(R * 0.35 - ang * 3.0 + fbm2(p * 0.04, 4) * 8.0);
    float stroke = fbm2(vec2(R * 0.6, ang * 6.0) + flow * 4.0, 5);
    vec3 col = mix(vec3(0.02, 0.05, 0.16), vec3(0.08, 0.16, 0.42), smoothstep(0.2, 1.0, sw) * stroke);
    col += vec3(0.9, 0.85, 0.5) * pow(hash12(floor(p * 3.0)), 60.0) * 0.8;
    // 太阳：巨大的同心火环
    if (R < uSunR * 1.25){
        float n = fbm2(vec2(R * 0.4, ang * 5.0) + flow * 6.0, 5);
        float x = R / uSunR + 0.12 * (n - 0.5);
        vec3 s = hot(x) * (1.2 + 0.8 * n);
        s *= 0.75 + 0.25 * sin(R * 3.0 + n * 10.0);                       // 细密的年轮纹
        s += vec3(1.0, 0.6, 0.2) * pow(abs(sin(ang * 40.0 + n * 12.0)), 30.0) * smoothstep(0.3, 0.9, x) * 0.5;
        col = mix(col, s, smoothstep(1.25, 1.0, R / uSunR));
    }
    // 摊开的行星
    for (int i = 0; i < 4; i++){
        float pr = uP[i].z;
        if (pr <= 0.0) continue;
        vec2 d = p - uP[i].xy;
        float r = length(d) / pr;
        if (r > 1.15) continue;
        float n = fbm2(d / pr * 4.0 + float(i) * 7.0, 5);
        vec3 c = layers(clamp(r + 0.06 * (n - 0.5), 0.0, 1.0), int(uP[i].w), n);
        c += vec3(1.0) * exp(-abs(r - 1.0) * 60.0) * 0.8;                // 摊开的前沿发亮
        col = mix(col, c, smoothstep(1.02, 0.98, r));
    }
    // 二维化区域的边界：一圈发光的"纸边"
    float edge = exp(-abs(R - uZone) * 1.5);
    col = col * smoothstep(uZone + 0.5, uZone - 0.5, R) + vec3(0.6, 0.8, 1.0) * edge * 0.6;
    float fog = exp(-tt * 0.006);
    fragColor = vec4(col * fog * uAmt, 1.0);
}
"""

# 黑域：球内的光被困住（压暗 + 偏红），球面是一层暗红的视界
DOMAIN_FS = r"""
uniform vec2 uC; uniform float uR; uniform float uAmt;
in vec2 vUV; out vec4 fragColor;
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    float r = length(P - uC) / uR;
    float inside = smoothstep(1.0, 0.97, r);
    vec3 k = mix(vec3(1.0), vec3(0.05, 0.015, 0.02), inside * uAmt);
    fragColor = vec4(k, 1.0);
}
"""
DOMAIN_RIM_FS = r"""
uniform vec2 uC; uniform float uR; uniform float uAmt;
in vec2 vUV; out vec4 fragColor;
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    vec2 d = P - uC;
    float r = length(d) / uR;
    float n = fbm2(d / 90.0 + uTime * 0.05, 4);
    float rim = exp(-abs(r - 1.0) * 90.0) * (0.3 + 0.6 * n) + exp(-max(r - 1.0, 0.0) * 12.0) * step(1.0, r) * 0.08;
    fragColor = vec4(vec3(0.9, 0.2, 0.15) * rim * uAmt, 1.0);
}
"""


def flat2d(e, cam, zone, planets, sun_r=26.0, amt=1.0):
    P = np.zeros((4, 4), np.float32)
    for i, p in enumerate(planets[:4]):
        P[i] = p
    u = cam_uniforms(cam)
    u.update(uZone=float(zone), uP=P.ravel(), uAmt=float(amt), uSunR=float(sun_r))
    e.draw_fs("wd_flat2d", FLAT2D_FS, u, blend="add")


class Ch6(Scene):
    chapter = True

    def setup(self):
        self.tF, self.tI, self.tT, self.tD, self.tG = ls("G02"), ls("G03"), ls("G04"), ls("G05"), ls("G06")
        rng = np.random.default_rng(31)
        self.trails = []          # 黑域段落里的航迹：(起点, 终点, 出现时刻)
        for k in range(26):
            a = rng.random() * math.tau
            b = a + math.pi + (rng.random() - 0.5) * 1.6
            r0, r1 = 700 + 300 * rng.random(), 700 + 300 * rng.random()
            c = (W / 2 + 60 * (rng.random() - 0.5), H / 2 + 60 * (rng.random() - 0.5))
            p0 = (c[0] + r0 * math.cos(a), c[1] + r0 * math.sin(a) * 0.62)
            p1 = (c[0] + r1 * math.cos(b), c[1] + r1 * math.sin(b) * 0.62)
            st = C["stack"] - 0.2 + k * 0.11 if k > 2 else C["slowlight"] - 1.2 + k * 0.5
            self.trails.append((p0, p1, st, rng.random()))

    # ------------------------------------------------ 星环号（冥王星附近，太阳成了远处的一颗亮星）
    def phase_halo(self, t):
        e = self.eng
        lt = t - self.t0
        cam = Camera((-6.5 + 0.4 * lt / 7, 1.4, -7.0), (0.3, 0.1, 1.2), fov=38)
        relstars(e, cam, stars=1.0, neb=0.5, gal=(0.2, 0.9, 0.3), n1=(0.12, 0.2, 0.5), n2=(0.45, 0.15, 0.3))
        sp = cam.project((60.0, 8.0, -120.0))
        if sp:
            bodies(e, [(sp[0], sp[1], 5, 2.2, (1.0, 0.92, 0.75), 1.0)])
        ship(e, cam, (0, 0, 0), roll(ship_frame((0, 0, 1)), 0.4 + lt * 0.05), 1.0, ring=0.45, phase=t, engine=0.4,
             sun=(0.4, 0.2, -0.9), sun_col=(1.3, 1.2, 1.05))
        a = vis(t, self.t0 + 2.4, self.tF, 0.5, 0.4)
        e.text("《三体 III · 死神永生》", 140, 200, 30, "sans_m", DIM, a, "lm", 0.2, 1.1)
        e.text("光速飞船", 140, 270, 72, "serif", WHITE, vis(t, C["built"] - 0.2, self.tF, 0.4, 0.4), "lm", 0.15, 1.5,
               scale=stamp(t, C["built"], 0.4, 1.2))

    # ------------------------------------------------ 二维化：太阳系被压成一幅画
    def planets_2d(self, t):
        """行星落进平面的时刻与位置（世界坐标），返回 [(x, z, 当前半径, 种类)]。"""
        spec = [(48.0, -10.0, 9.0, 0, C["flatten"]), (-62.0, 30.0, 16.0, 1, self.tF + 0.3),
                (70.0, 52.0, 11.0, 2, C["painting"]), (-30.0, -58.0, 7.0, 3, self.tF - 0.6)]
        out = []
        for x, z, R, kind, tf in spec:
            k = ease_out(lin(tf, tf + 1.4, t))
            out.append((x, z, R * k, kind))
        return out, spec

    def phase_foil(self, t):
        e = self.eng
        lt = t - self.tF
        up = ease_in_out(lin(C["painting"] - 0.4, self.tI, t))
        cam = Camera((90 - 40 * up, 38 + 90 * up, -110 - 30 * up), (20 * (1 - up), 0.0, 0.0), fov=48)
        relstars(e, cam, stars=0.8, neb=0.3)
        pl, spec = self.planets_2d(t)
        zone = 150 + 12 * lt
        flat2d(e, cam, zone, pl, amt=smooth(self.tF - 0.2, self.tF + 0.3, t))
        # 正在落入平面的那颗行星（地球）：三维的球，碰到平面的瞬间摊开
        x, z, R, kind, tf = spec[0]
        if t < tf + 0.1:
            h = 30.0 * (1 - ease_in_out(lin(self.tF, tf, t)))
            q = cam.project((x, h + 0.01, z))
            rr = cam.project((x, h + R * 0.5, z))
            if q and rr:
                planet(e, q[:2], abs(rr[1] - q[1]), light=(0.4, 0.4, 0.8), amt=1.0)
        g = pulse(t, C["flatten"], 0.4)
        q = cam.project((x, 0.0, z))
        if q and g > 0.01:
            bodies(e, [(q[0], q[1], 20, 3.0 * g, (1.0, 0.9, 0.8), 1.0)])
        a = vis(t, C["flatten"] - 0.1, self.tI, 0.3, 0.4)
        e.text("二向箔", 140, 200, 96, "serif", WHITE, a, "lm", 0.15, 1.6, scale=stamp(t, C["flatten"], 0.45, 1.3))
        e.text("三维空间被压成二维", 146, 300, 34, "sans_m", ICE, a, "lm", 0.15, 1.2)
        pa = vis(t, C["painting"], self.tI, 0.3, 0.4)
        e.text("一幅巨大的画", W - 140, 200, 72, "serif", GOLD, pa, "rm", 0.15, 1.6, scale=stamp(t, C["painting"], 0.45, 1.2))

    # ------------------------------------------------ 星环号点火逃离，身后留下航迹
    def ship_pos(self, t):
        """点火后沿 +z 加速飞离（同一公式也给出航迹的起点与终点）。"""
        x = max(0.0, t - C["ignite"])
        return np.array([0.0, 22.0, 30.0 + 14.0 * x * x + 40.0 * x])

    def phase_escape(self, t):
        e = self.eng
        lt = t - self.tI
        sp = self.ship_pos(t)
        wide = ease_in_out(lin(self.tT - 0.3, self.tT + 1.6, t))
        # 先贴近飞船，随后拉成大远景：画在下方，航迹从画上方一直伸向远处
        near_eye = sp + np.array([-6.0, 2.2, -9.0])
        far_eye = np.array([-160.0, 120.0, -60.0])
        eye = near_eye + (far_eye - near_eye) * wide
        tgt = sp + np.array([0.0, 0.0, 3.0]) * (1 - wide) + (np.array([0.0, 10.0, 90.0]) - sp) * wide
        cam = Camera(tuple(eye), tuple(tgt), fov=40 + 8 * wide)
        relstars(e, cam, stars=0.9, neb=0.35, beta=0.0)
        pl, _ = self.planets_2d(t)
        flat2d(e, cam, 150 + 12 * (t - self.tF), pl)
        # 航迹：点火处到船尾的一道光，和开场跃迁时飞船留下的航迹是同一种画法（warpfield.trail），观众认得出来。
        # 这里的航迹不消散（光速在里面变慢，它会一直留在那里），只慢慢变宽一点；拉成大远景时加粗，远看仍是一道亮线
        start = self.ship_pos(C["ignite"])
        if t > C["ignite"]:
            tg = smooth(C["ignite"], C["ignite"] + 0.3, t) * (1 + 0.6 * pulse(t, C["long_trail"], 0.5))
            F.trail(e, cam, start, sp - np.array([0.0, 0.0, 4.1]), tg, t - C["ignite"], width=0.35 + 1.6 * wide,
                    seed=4.0, decay=1e3, spread=0.3)
        ig = smooth(C["ignite"] - 1.2, C["ignite"], t)
        q = cam.project(tuple(sp))
        if wide < 0.6:
            ship(e, cam, tuple(sp), roll(ship_frame((0, 0, 1)), 0.4 + lt * 0.4), 1.0, amt=1 - smooth(0.4, 0.6, wide),
                 ring=0.5 + 2.5 * ig, phase=t * (2 + 25 * ig), engine=0.5 + ig, sun=(0.4, -0.6, 0.6),
                 sun_col=(1.6, 1.3, 1.0), stretch=1.0 + 2.0 * smooth(C["ignite"], C["ignite"] + 0.4, t))
        if q:
            bodies(e, [(q[0], q[1], 4, 2.5 * smooth(C["ignite"], C["ignite"] + 0.5, t), (0.7, 0.9, 1.0), 1.0)])
        flat(e, (0.7, 0.9, 1.0), 1.5 * pulse(t, C["ignite"], 0.15))
        a = vis(t, self.tI + 0.2, self.tT, 0.3, 0.4)
        e.text("星环号", 140, 200, 80, "serif", WHITE, a, "lm", 0.15, 1.5)
        e.text("程心  ·  艾 AA", 146, 290, 30, "sans_m", ICE, a, "lm", 0.2, 1.1)
        ta = vis(t, C["long_trail"] - 0.2, self.tD, 0.3, 0.4)
        e.text("曲率航迹", W - 140, 200, 80, "serif", CYAN, ta, "rm", 0.15, 1.6, scale=stamp(t, C["long_trail"], 0.45, 1.25))

    # ------------------------------------------------ 航迹叠加 -> 黑域
    def phase_domain(self, t):
        e = self.eng
        lt = t - self.tD
        zoom = 1.0 - 0.15 * ease_in_out(lin(self.tD, self.t1, t))
        space(e, neb=0.25, stars=1.0, c1=(0.06, 0.1, 0.3), c2=(0.3, 0.08, 0.25), zoom=zoom, seed=19.0)
        cx, cy = W / 2, H / 2
        dom = ease_in_out(lin(C["blackdomain"] - 0.6, C["blackdomain"] + 0.2, t))
        # 太阳（被困住后暗下去、变红）
        bodies(e, [(cx, cy, 16, 2.4 * (1 - 0.85 * dom), mix3((1.0, 0.88, 0.6), (1.0, 0.3, 0.15), dom), 0.8)])
        for k, (r, sp) in enumerate(((140, 0.9), (230, 0.6), (330, 0.4))):
            ring(e, cx, cy, r * zoom, 0.3 * (1 - dom), DIM, 1.0, 0.0, 160, 1.0, squash=0.62)
            th = lt * sp + k * 2.0
            e.circle(cx + r * zoom * math.cos(th), cy + r * zoom * 0.62 * math.sin(th), 4, fill=(0.6, 0.8, 1.0),
                     fill_a=1 - dom, glow=3, intensity=2)
        # 航迹：一道道出现，越来越密。画成会散开的光迹（老的一段蜿蜒、变散、撕成一缕缕），不再是等宽的霓虹线
        trails = []
        for (p0, p1, st, w) in self.trails:
            if t < st:
                continue
            pr = ease_out_expo(lin(st, st + 0.5, t))
            x1 = p0[0] + (p1[0] - p0[0]) * pr
            y1 = p0[1] + (p1[1] - p0[1]) * pr
            trails.append(dict(tail=p0, head=(x1, y1), color=mix3(CYAN, (0.6, 0.5, 1.0), w), a=1.3 * (1 - 0.5 * dom),
                               width=3.5, taper=0.6, wisp=0.6, spark=0.8 * (1 - pr)))
        streaks(e, trails)
        # 光速变慢：第一条航迹里的光点越走越慢
        sa = vis(t, C["slowlight"] - 0.3, C["stack"] + 1.0, 0.3, 0.5)
        if sa > 0:
            p0, p1, st, _ = self.trails[0]
            # 每个光点拖一小段尾巴（0.15 秒前的位置），越走越慢、尾巴越缩越短
            dots = []
            for k in range(5):
                u, u0 = ((1 - math.exp(-max(tt - C["slowlight"] + k * 0.25, 0.0) / 1.2)) * 0.55 + k * 0.07 for tt in (t, t - 0.15))
                dots.append(dict(tail=(p0[0] + (p1[0] - p0[0]) * u0, p0[1] + (p1[1] - p0[1]) * u0),
                                 head=(p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u), color=GOLD, a=1.5 * sa,
                                 width=4.0, spark=1.5))
            streaks(e, dots)
            e.text("光速变慢", p0[0] + (p1[0] - p0[0]) * 0.35, p0[1] + (p1[1] - p0[1]) * 0.35 - 50, 40, "sans_b", GOLD, sa,
                   "mm", 0.15, 1.6, scale=stamp(t, C["slowlight"], 0.4, 1.3))
        # 黑域：球内压暗，球面一层暗红视界
        if dom > 0:
            R = 480 * zoom * (0.6 + 0.4 * dom)
            e.flush()
            e.draw_fs("wd_domain", DOMAIN_FS, dict(uC=(cx, cy), uR=R, uAmt=dom), blend="mul")
            e.draw_fs("wd_domain_rim", DOMAIN_RIM_FS, dict(uC=(cx, cy), uR=R, uAmt=dom * (1 + 2 * pulse(t, C["blackdomain"], 0.5))),
                      blend="add")
            e.circle(cx, cy, 5, fill=(1.0, 0.25, 0.1), fill_a=dom, glow=3, intensity=1.2)   # 黑域里的太阳只剩一点暗红
        da = vis(t, C["blackdomain"] - 0.1, self.t1, 0.25, 0.6)
        e.text("黑域", W / 2, 150, 120, "serif", (1.0, 0.45, 0.35), da, "mm", 0.3, 1.6 + 1.5 * pulse(t, C["blackdomain"], 0.4),
               scale=stamp(t, C["blackdomain"], 0.45, 1.4))
        e.text("连光都逃不出去", W / 2, 245, 32, "sans_m", (1.0, 0.7, 0.6), da, "mm", 0.3, 1.2)
        ca = vis(t, C["cage"] - 0.2, self.t1, 0.4, 0.6)
        e.text("牢笼", W / 2, H - 200, 64, "serif", WHITE, ca, "mm", 0.6, 1.3)
        flat(e, (1.0, 0.4, 0.3), 0.35 * pulse(t, C["blackdomain"], 0.25))

    def render(self, t):
        if t < self.tF:
            self.phase_halo(t)
        elif t < self.tI:
            self.phase_foil(t)
        elif t < self.tD:
            self.phase_escape(t)
        else:
            self.phase_domain(t)
        self.chapter_card(t)

    def post(self, t):
        if self.tF <= t < self.tD:
            return dict(uBloomAmt=0.45, uVignette=0.8, uSat=1.15)
        if t >= C["blackdomain"] - 0.6:
            return dict(uBloomAmt=0.3, uVignette=0.85)
        return dict(uBloomAmt=0.5, uVignette=0.8)
