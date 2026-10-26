# -*- coding: utf-8 -*-
"""连续跃迁镜头用的三件素材（开场"充能 -> 跃迁 -> 抵达"一镜到底）。

  StarStream   真正的三维星场：几万颗星星分布在一个沿航线周期重复的长盒子里，飞船前进时它们从前方迎面而来、
               从两侧掠过飞到身后，近快远慢。每颗星画成"当前位置 -> 一小段时间之前的位置"的短光条，
               长度在屏幕上封顶，所以高速时仍然读得出是一颗颗星，不会变成射线隧道。
  nebula(...)  航线上的一团彩色星云（世界空间里的体积噪声，光线步进），镜头直接从里面穿过。
  star(...)    恒星：不透明的解析球体 + 米粒组织（细胞噪声）+ 黑子与光斑 + 临边昏暗 + 色球层 + 日冕流 + 日珥；
               很远时退化成一个光点。
跃迁分镜（镜头留在原地、飞船弹射出去，再追上去）和抵达分镜用的几件：
  trail(...)       飞船身后留下的航迹：从发射点到船尾的一道光束，留下之后慢慢扩散、变暗、被扰动撕成一缕缕。
                   第六章星环号的航迹也用它（同一种画法，观众认得出来）。
  ring_warp(...)   透明的激波环：垂直于航线、以航线为圆心的一圈，不发光，只把它后面的背景往外推、往里拉（画面形变）。
  rush(...)        镜头追赶飞船时的全画面形变：朝消失点的径向拖影 + 外圈拉伸、轻微旋转 + 色散。
                   抵达时也用它做退出超光速：背景的径向拖线从长到短收成一个个星点。
  shock(...)       急停时的球形冲击波：曲率泡塌缩后反弹出的一层层透明球壳，只把画面往外推、往里拉，
                   波前带一点纹影式的明暗；扫过镜头以后整幅画面鼓胀、回弹（余震）。
  ShockDust        冲击波扫过时被照亮的星际尘埃：波前连成一层细密的光点球壳，让球形冲击波在稀疏的星空上也看得出体积。

坐标约定：飞船固定在原点、船头朝 +z；"行程" s 是飞船已经飞过的距离（场景里对速度积分得到）。
星场只依赖 s（以及 s 在快门时间内的增量 ds），因此画面只依赖时刻 t，可以任意跳帧。"""
import math
import numpy as np
import moderngl
from opusvid.gl import W, H
from wfx import CAM_GLSL, cam_uniforms

# ---------------------------------------------------------------------- 三维星场
STREAM_VS = r"""
#version 430
in vec3 in_pos; in vec4 in_col;
uniform float uS; uniform float uDS; uniform float uL; uniform float uBack; uniform float uZ0;
out vec3 vP0; out vec3 vP1; out vec4 vC;
void main(){
    // 沿 z 周期重复：星星永远在 uZ0 前后 [-uBack, uL-uBack] 的范围里循环
    float z = mod(in_pos.z - uS - uZ0, uL) - uBack + uZ0;
    vP0 = vec3(in_pos.xy, z);
    vP1 = vec3(in_pos.xy, z + uDS);      // 快门开始时（更早）的位置：当时它还在更前方
    vC = in_col;
}
"""

STREAM_GS = r"""
#version 430
layout(points) in;
layout(triangle_strip, max_vertices = 4) out;
uniform mat4 uMVP; uniform vec2 uRes; uniform float uMaxLen; uniform float uFar; uniform float uSize; uniform float uGain;
in vec3 vP0[]; in vec3 vP1[]; in vec4 vC[];
out vec2 gUV; out float gLen; out float gHalf; out vec3 gC;
void main(){
    vec4 c0 = uMVP * vec4(vP0[0], 1.0), c1 = uMVP * vec4(vP1[0], 1.0);
    if (c0.w < 0.05) return;
    if (c1.w < 0.05) c1 = mix(c0, c1, (c0.w - 0.05) / max(c0.w - c1.w, 1e-4));
    vec2 s0 = (c0.xy / c0.w * 0.5 + 0.5) * uRes, s1 = (c1.xy / c1.w * 0.5 + 0.5) * uRes;
    vec2 d = s1 - s0; float L = length(d);
    if (L > uMaxLen){ s1 = s0 + d / L * uMaxLen; d = s1 - s0; L = uMaxLen; }
    // 亮度：越远越暗（远处淡出），近处更大；拖尾越长，单位长度上的亮度越低（能量守恒，避免成片发白）
    float dist = c0.w;
    float fade = smoothstep(uFar, uFar * 0.55, dist) * smoothstep(0.3, 2.0, dist);
    float r = clamp(uSize * vC[0].a * 30.0 / dist, 0.9, 3.2);
    float energy = fade * uGain * min(1.0, (r * 3.0) / (L + r * 3.0) * 2.2);
    if (energy < 0.002) return;
    vec2 dir = L > 1e-3 ? d / L : vec2(1.0, 0.0);
    vec2 nrm = vec2(-dir.y, dir.x);
    float hw = r * 2.5;                          // 半宽（含光晕）
    vec2 a = s0 - dir * hw, b = s1 + dir * hw;
    vec2 corners[4] = vec2[](a - nrm * hw, a + nrm * hw, b - nrm * hw, b + nrm * hw);
    vec2 uvs[4] = vec2[](vec2(-hw, -hw), vec2(-hw, hw), vec2(L + hw, -hw), vec2(L + hw, hw));
    for (int k = 0; k < 4; k++){
        gl_Position = vec4(corners[k] / uRes * 2.0 - 1.0, 0.0, 1.0);
        gUV = uvs[k]; gLen = L; gHalf = r; gC = vC[0].rgb * energy;
        EmitVertex();
    }
    EndPrimitive();
}
"""

STREAM_FS = r"""
#version 430
in vec2 gUV; in float gLen; in float gHalf; in vec3 gC;
out vec4 fragColor;
void main(){
    // 到线段 [0, L] 的距离：胶囊形光条，核心亮、外圈柔光
    float x = clamp(gUV.x, 0.0, gLen);
    float d = length(vec2(gUV.x - x, gUV.y));
    float core = exp(-d * d / (gHalf * gHalf * 0.5));
    float halo = exp(-d / (gHalf * 1.6)) * 0.18;
    // 光条头部（当前位置）最亮，尾部渐暗
    float head = mix(0.35, 1.0, 1.0 - x / max(gLen, 1e-3));
    vec3 c = gC * (core + halo) * head;
    fragColor = vec4(c, 1.0);
}
"""


def _star_colors(rng, n):
    """恒星颜色：多数偏白/淡黄，少数蓝白与橙红。"""
    t = rng.random(n)
    blue = np.array([0.7, 0.82, 1.0]); white = np.array([1.0, 0.97, 0.92]); orange = np.array([1.0, 0.72, 0.45])
    c = np.where(t[:, None] < 0.25, blue, np.where(t[:, None] < 0.8, white, orange))
    return c * (0.8 + 0.4 * rng.random((n, 1)))


class StarStream:
    """L：盒子沿航线的长度；R：横向半径；hole：航线周围不放星星的半径（免得穿过飞船）。"""

    def __init__(self, e, n=9000, L=600.0, R=110.0, hole=9.0, seed=3):
        self.e, self.L = e, L
        ctx = e.ctx
        if not hasattr(e, "_wd_stream_prog"):
            e._wd_stream_prog = ctx.program(vertex_shader=STREAM_VS, geometry_shader=STREAM_GS, fragment_shader=STREAM_FS)
        self.prog = e._wd_stream_prog
        rng = np.random.default_rng(seed)
        # 横向分布：越靠近航线越稀（近处的星少而亮，远处的多而暗），留出中心空洞
        rr = hole + (R - hole) * rng.random(n) ** 0.7
        th = rng.random(n) * math.tau
        pos = np.stack([rr * np.cos(th), rr * np.sin(th) * 0.8, rng.random(n) * L], 1).astype("f4")
        col = np.zeros((n, 4), "f4")
        col[:, :3] = _star_colors(rng, n)
        mag = rng.random(n) ** 6                               # 少数亮星
        col[:, :3] *= (0.25 + 2.8 * mag)[:, None]
        col[:, 3] = 0.5 + 1.5 * mag                            # 尺寸系数
        self.n = n
        self.vbo = ctx.buffer(np.hstack([pos, col]).astype("f4").tobytes())
        self.vao = ctx.vertex_array(self.prog, [(self.vbo, "3f 4f", "in_pos", "in_col")])

    def draw(self, cam, s, ds, gain=1.0, max_len=70.0, far=None, size=1.0, z0=0.0):
        """s：当前行程；ds：快门时间内飞过的距离（决定拖尾长短，屏幕上最长 max_len 像素）。
        z0：循环盒子的中心（默认围着飞船）。镜头离开飞船时传镜头的 z，盒子就跟着镜头走；
        这时 s 要用镜头自己的行程（飞船行程 + 镜头相对飞船的 z 都已含在 s + z0 里），镜头不动星星就不动。"""
        e = self.e
        u = dict(uMVP=cam.mvp(), uS=float(s), uDS=float(ds), uL=float(self.L), uBack=float(self.L * 0.12), uZ0=float(z0),
                 uRes=(float(W), float(H)), uMaxLen=float(max_len), uFar=float(far or self.L * 0.55),
                 uSize=float(size), uGain=float(gain))
        e.set_u(self.prog, u)
        e._blend("add")
        self.vao.render(moderngl.POINTS, vertices=self.n)


# ---------------------------------------------------------------------- 穿过星云
NEBULA_FS = CAM_GLSL + r"""
uniform float uZc;          // 星云中心相对飞船的 z
uniform float uHalf;        // 星云沿航线的半长
uniform float uAmt; uniform float uSeed;
uniform vec3 uC1; uniform vec3 uC2; uniform vec3 uC3;
in vec2 vUV; out vec4 fragColor;
void main(){
    vec3 rd = camRay(vUV);
    // 只在星云所在的 z 区间里步进
    float z0 = uZc - uHalf, z1 = uZc + uHalf;
    float ta = (z0 - uEye.z) / rd.z, tb = (z1 - uEye.z) / rd.z;
    float t0 = max(min(ta, tb), 0.0), t1 = min(max(ta, tb), 600.0);
    if (t1 <= t0 || uAmt <= 0.0){ fragColor = vec4(0); return; }
    const int N = 40;
    float dt = (t1 - t0) / float(N);
    float jit = hash12(vUV * uRes + uTime * 7.0);
    vec3 acc = vec3(0); float tr = 1.0;
    for (int i = 0; i < N; i++){
        vec3 p = uEye + rd * (t0 + (float(i) + jit) * dt);
        vec3 q = vec3(p.xy / 40.0, (p.z - uZc) / 140.0) + uSeed;     // 沿航线拉长的大尺度结构，高速穿过时不闪烁
        float edge = smoothstep(uHalf, uHalf * 0.4, abs(p.z - uZc));
        float hollow = smoothstep(2.5, 10.0, length(p.xy));     // 航线附近稀薄，飞船周围不糊
        float den = pow(max(fbm3(q + fbm3(q * 1.7, 3) * 0.9, 5) - 0.42, 0.0), 1.6) * 3.0 * edge * hollow;
        float hue = fbm3(q * 0.6 + 7.0, 3);
        vec3 c = mix(mix(uC1, uC2, smoothstep(0.35, 0.6, hue)), uC3, pow(den, 3.0) * 0.6);
        float a = den * dt * 0.06;
        acc += c * a * tr;
        tr *= exp(-a * 0.6);
    }
    fragColor = vec4(acc * uAmt, 1.0);
}
"""


def nebula(e, cam, zc, half=60.0, amt=1.0, seed=2.0, c1=(0.55, 0.12, 0.45), c2=(0.1, 0.35, 0.75), c3=(1.0, 0.7, 0.5)):
    """zc：星云中心相对飞船（原点）的 z 坐标，随行程减小，镜头就从星云里穿过。"""
    if amt <= 0.001 or zc > 600 or zc < -half - 50:
        return
    u = cam_uniforms(cam)
    u.update(uZc=float(zc), uHalf=float(half), uAmt=float(amt), uSeed=float(seed), uC1=tuple(c1), uC2=tuple(c2),
             uC3=tuple(c3))
    e.draw_fs("wd_nebula_vol", NEBULA_FS, u, blend="add")


# ---------------------------------------------------------------------- 恒星
STAR_FS = CAM_GLSL + r"""
uniform vec3 uC; uniform float uR; uniform vec3 uCol; uniform float uBright; uniform float uCorona; uniform float uProm;
uniform float uSeed;
uniform float uPixAng;                // 一个屏幕像素对应的弧度（米粒太小时淡掉，避免闪烁）
in vec2 vUV; out vec4 fragColor;
// 三维细胞噪声：返回 (到最近、次近细胞中心的距离, 最近细胞的随机数)。
// 米粒 = 对流元胞，中心热、边界下沉成暗线（F2 - F1 小的地方），每个元胞亮度略有不同
vec3 cells3(vec3 p){
    vec3 i = floor(p), f = fract(p);
    float d1 = 9.0, d2 = 9.0, id = 0.0;
    for (int x = -1; x <= 1; x++) for (int y = -1; y <= 1; y++) for (int z = -1; z <= 1; z++){
        vec3 g = vec3(float(x), float(y), float(z));
        vec3 o = hash33(i + g);
        vec3 r = g + o - f;
        float d = dot(r, r);
        if (d < d1){ d2 = d1; d1 = d; id = o.x; } else if (d < d2) d2 = d;
    }
    return vec3(sqrt(d1), sqrt(d2), id);
}
void main(){
    vec3 rd = camRay(vUV);
    vec3 oc = uEye - uC;
    float b = dot(oc, rd);
    float c = dot(oc, oc) - uR * uR;
    float h = b * b - c;
    // 视线到球心的最近距离（以半径为单位），用于日冕和日珥
    float tc = max(-b, 0.0);
    float dmin = length(oc + rd * tc) / uR;
    vec3 col = vec3(0);
    float alpha = 0.0;
    // 投影到垂直视线的平面上的方位角（日冕流、日珥的角向变化）
    vec3 ax = normalize(cross(rd, vec3(0.0, 1.0, 0.0) + 1e-4));
    vec3 ay = cross(ax, rd);
    vec3 rel = oc + rd * tc;
    float ang = atan(dot(rel, ay), dot(rel, ax));
    if (h > 0.0 && -b - sqrt(h) > 0.0){
        float th = -b - sqrt(h);
        vec3 p = oc + rd * th;
        vec3 n = normalize(p);
        float mu = max(dot(n, -rd), 0.0);
        // 米粒组织：细小的对流元胞（约半径的 1/140），缓慢翻滚；外面再罩一层大得多的超米粒网络（边界略亮）。
        // 屏幕上小到几个像素时各自淡掉（远处只剩平均亮度，不闪烁）
        float px = th * uPixAng / max(mu, 0.2);                            // 一个像素在星面上的尺寸
        float dG = 1.0 - smoothstep(0.15, 0.5, px / (uR / 140.0));
        float dN = 1.0 - smoothstep(0.15, 0.5, px / (uR / 32.0));
        vec3 c1 = cells3(n * 140.0 + vec3(0.0, 0.0, uTime * 0.12 + uSeed * 7.0));
        float g1 = (0.74 + 0.26 * smoothstep(0.0, 0.16, c1.y - c1.x)) * (0.86 + 0.28 * c1.z);
        vec3 c2 = cells3(n * 32.0 + vec3(uSeed * 3.0, 5.0, uTime * 0.01));
        float net = 1.0 - smoothstep(0.0, 0.07, c2.y - c2.x);
        float gran = mix(0.87, g1, dG) + 0.1 * net * dN;
        // 超米粒组织与活动区（大尺度明暗起伏）、黑子（本影 + 半影）、靠近临边更显眼的光斑
        float act = fbm3(n * 3.0 + uSeed, 4);
        float sp = fbm3(n * 4.5 + 11.0 + uSeed, 4);
        float umbra = smoothstep(0.80, 0.81, sp), penum = smoothstep(0.775, 0.79, sp);
        gran = mix(gran, 0.87, penum);                  // 黑子里没有米粒，是一片平滑的暗区
        float fac = smoothstep(0.55, 0.72, act) * pow(1.0 - mu, 1.2);
        // 临边昏暗（二次律）：边缘既更暗也更"冷"（偏橙红）
        float limb = 1.0 - 0.62 * (1.0 - mu) - 0.22 * (1.0 - mu) * (1.0 - mu);
        float temp = limb * (0.7 + 0.3 * gran) * (0.9 + 0.2 * act);
        vec3 hot = mix(uCol, vec3(1.0, 0.9, 0.7), 0.3);
        vec3 cool = uCol * vec3(1.0, 0.55, 0.35);
        vec3 tint = mix(cool, hot, smoothstep(0.25, 0.95, temp));
        // 亮度别太高：盘面占大半个画面时，过曝会被色调映射压成灰白（"白蒙蒙"）
        float I = 1.9 * uBright * limb * (0.45 + 0.75 * gran) * (0.85 + 0.3 * act);
        I *= 1.0 - 0.45 * penum - 0.45 * umbra;
        I += 0.8 * uBright * fac * (0.6 + 0.4 * gran);
        col = tint * I;
        alpha = 1.0;                                    // 不透明：挡住后面的星空
    } else {
        float r = dmin;
        // 色球层：贴着边缘的一圈红光
        float chromo = exp(-max(r - 1.0, 0.0) * 90.0) * step(1.0, r);
        // 日冕：随半径衰减，带角向的流线
        float stream = 0.55 + 0.45 * fbm2(vec2(ang * 3.0 + uSeed, r * 1.5 - uTime * 0.05), 4);
        float corona = (exp(-(r - 1.0) * 6.0) * 0.5 + exp(-(r - 1.0) * 1.6) * 0.12) * stream;
        // 日珥：边缘附近的弧形亮丝
        float pn = fbm2(vec2(ang * 7.0 + uSeed * 3.0, uTime * 0.05), 4);
        float ph = (r - 1.0) / 0.12;
        float loop = smoothstep(0.55, 0.75, pn) * exp(-pow(ph - 0.4 * pn, 2.0) * 6.0) * step(1.0, r) * smoothstep(1.4, 0.0, ph);
        col = vec3(1.0, 0.45, 0.25) * chromo * 1.2 * uBright + mix(uCol, vec3(1.0), 0.4) * corona * uCorona * uBright
            + vec3(1.0, 0.38, 0.2) * loop * uProm * uBright;
    }
    // 预乘 alpha："over" 混合下盘面盖住背景，盘外的日冕（alpha = 0）照常叠加发光
    fragColor = vec4(col, alpha);
}
"""


def star(e, cam, center, radius, color=(1.0, 0.72, 0.38), bright=0.75, corona=1.0, prom=1.0, seed=1.0):
    """画一颗恒星（世界坐标中心、半径）。屏幕上太小时只画光点，避免锯齿。返回屏幕半径（像素）。"""
    q = cam.project(tuple(center))
    if q is None:
        return 0.0
    rpx = radius / q[2] * cam.pix
    if rpx < 2.5:
        from wfx import bodies
        bodies(e, [(q[0], q[1], max(rpx, 1.2), min(3.0, 0.6 + rpx) * bright * 0.6, color, 0.8)])
        return rpx
    u = cam_uniforms(cam)
    u.update(uC=tuple(center), uR=float(radius), uCol=tuple(color), uBright=float(bright), uCorona=float(corona),
             uProm=float(prom), uSeed=float(seed))
    e.draw_fs("wd_star", STAR_FS, u, blend="over")
    return rpx


# ---------------------------------------------------------------------- 曲率泡外壳
BUBBLE_FS = CAM_GLSL + r"""
uniform vec3 uCtr; uniform vec3 uAx;      // 椭球中心、三个半轴（飞船局部 = 世界，船头 +z）
uniform int uSide;                        // 0 画背面（在飞船之前画），1 画正面（在飞船之后画）
uniform float uAmt; uniform float uFlowT; uniform float uCap; uniform float uPulse; uniform float uPulseW;
uniform float uFlash;
in vec2 vUV; out vec4 fragColor;
void main(){
    vec3 rd = camRay(vUV);
    vec3 ro = (uEye - uCtr) / uAx, rs = rd / uAx;
    float a = dot(rs, rs), b = dot(ro, rs), c = dot(ro, ro) - 1.0;
    float h = b * b - a * c;
    if (h <= 0.0 || uAmt <= 0.0){ fragColor = vec4(0); return; }
    h = sqrt(h);
    float t = uSide == 1 ? (-b - h) / a : (-b + h) / a;
    if (t <= 0.0){ fragColor = vec4(0); return; }
    vec3 q = ro + rs * t;                 // 单位球上的点
    vec3 n = normalize(q / uAx);
    float u = q.z;                        // -1 船尾 .. +1 船头
    float ang = atan(q.y, q.x + 1e-7);
    // |dot| 会因浮点误差略大于 1：不夹住的话负数的非整数次方是 NaN，单个 NaN 像素会被泛光扩成黑色方块
    float fres = pow(max(1.0 - abs(dot(n, -rd)), 0.0), 2.5);
    // 从船头流向船尾的场线 + 细碎的六边形闪烁
    float lines = pow(0.5 + 0.5 * sin((u * 9.0 + uFlowT) * PI), 14.0);
    float hex = vnoise2(vec2(ang * 9.0, u * 14.0 + uFlowT * 1.6));
    float shimmer = smoothstep(0.62, 0.9, hex);
    // 前缩（蓝白，前沿堆积的光）后胀（红）
    vec3 col = mix(vec3(1.0, 0.32, 0.18), vec3(0.45, 0.35, 1.0), smoothstep(-0.8, 0.2, u));
    col = mix(col, vec3(0.55, 0.9, 1.0), smoothstep(0.2, 0.9, u));
    float body = pow(fres, 1.6) * (0.06 + 0.3 * lines + 0.18 * shimmer);       // 外壳很淡，主要是边缘一圈
    // 前沿堆积的光集中在边缘（正对镜头的部分很淡）：正面看过去像一层玻璃，而不是一整块平涂的青色
    float cap = uCap * smoothstep(0.55, 1.0, u) * (0.15 + 0.85 * fres) * (0.7 + 0.6 * hex);
    // 一道能量脉冲：从船头沿外壳跑到船尾（uPulse 从 +1 走到 -1）
    float pulse = exp(-pow((u - uPulse) / uPulseW, 2.0)) * (0.35 + 0.65 * fres) * step(-1.2, uPulse);
    vec3 outc = col * body + vec3(0.5, 0.85, 1.0) * cap * 0.7 + mix(col, vec3(0.8, 0.95, 1.0), 0.4) * pulse * 0.9
              + vec3(0.6, 0.85, 1.0) * uFlash * pow(fres, 2.0) * 0.6;
    fragColor = vec4(outc * uAmt * (uSide == 1 ? 1.0 : 0.6), 1.0);
}
"""


def bubble(e, cam, side, amt, flow_t, cap=0.0, pulse=-2.0, pulse_w=0.08, flash=0.0, center=(0.0, 0.0, 0.8),
           axes=(3.0, 3.0, 6.2)):
    """曲率泡外壳（椭球）。side=0 在飞船之前画背面，side=1 在飞船之后画正面（透明外壳的正确叠放）。
    flow_t：场线的流动相位；cap：前沿堆积的光；pulse：沿外壳从船头到船尾的脉冲位置（+1 .. -1，小于 -1.2 不画）。"""
    if amt <= 0.001:
        return
    u = cam_uniforms(cam)
    u.update(uCtr=tuple(center), uAx=tuple(axes), uSide=int(side), uAmt=float(amt), uFlowT=float(flow_t), uCap=float(cap),
             uPulse=float(pulse), uPulseW=float(pulse_w), uFlash=float(flash))
    e.draw_fs("wd_bubble", BUBBLE_FS, u, blend="add")


def arcs(e, cam, t, amount, z0=0.25, z1=-1.65, r=1.95, n=4, rate=14.0, color=(0.35, 0.65, 1.0), seed=0):
    """前后两道曲率环之间跳动的电弧：每 1/rate 秒换一组，只画在朝向镜头的那半边（免得画到船体上）。"""
    if amount <= 0.001:
        return
    eye = np.asarray(cam.eye, np.float64)
    face = math.atan2(eye[1], eye[0])
    k = math.floor(t * rate)
    rng = np.random.default_rng(int(k * 7919 + seed * 104729) % (2 ** 31))
    life = (t * rate) % 1.0
    for _ in range(n):
        th = face + (rng.random() - 0.5) * 2.4
        th2 = th + (rng.random() - 0.5) * 0.15
        m = 24
        pts = []
        for i in range(m + 1):
            f = i / m
            z = z0 + (z1 - z0) * f
            ang = th + (th2 - th) * f
            rr = r + math.sin(f * math.pi) * 0.1 + (rng.random() - 0.5) * 0.09 * math.sin(f * math.pi)
            ang += (rng.random() - 0.5) * 0.035 * math.sin(f * math.pi)
            pts.append((rr * math.cos(ang), rr * math.sin(ang), z))
        sp = [cam.project(p) for p in pts]
        sp = [q[:2] for q in sp if q]
        if len(sp) > 1:
            a = amount * max(0.0, 1.0 - life * 1.6) * (0.6 + 0.4 * rng.random())
            e.line(sp, 0.9, color, a, glow=0.5, intensity=1.6)



# ---------------------------------------------------------------------- 跃迁分镜：航迹、冲击波、追赶形变
TRAIL_FS = CAM_GLSL + r"""
uniform vec3 uA; uniform vec3 uB;     // 航迹起点（发射点）、终点（船尾）
uniform float uW;                     // 刚留下时的核心半宽（世界单位）
uniform float uAge;                   // 起点处已经留下了多久（秒）；终点处为 0
uniform float uDecay; uniform float uSpread;   // 留下之后多久暗下去（秒）、每秒变宽多少倍
uniform float uAmt; uniform float uSeed;
uniform float uPixAng;                // 一个屏幕像素对应的弧度
in vec2 vUV; out vec4 fragColor;
void main(){
    vec3 rd = camRay(vUV);
    vec3 ab = uB - uA; float L = length(ab);
    if (uAmt <= 0.0 || L < 1e-3){ fragColor = vec4(0); return; }
    // 视线与线段 AB 的最近点
    vec3 u = ab / L, w0 = uEye - uA;
    float b = dot(rd, u), d = dot(rd, w0), e = dot(u, w0);
    float tl = clamp((e - b * d) / max(1.0 - b * b, 1e-6), 0.0, L);
    vec3 q = uA + u * tl;
    float s = dot(q - uEye, rd);
    if (s <= 0.05){ fragColor = vec4(0); return; }
    float dist = length(uEye + rd * s - q);
    float f = tl / L;                                     // 0 发射点 .. 1 船尾
    // 飞船越飞越快，大部分航迹是最后一瞬间才留下的：年龄随 f 的四次方根减到 0
    float age = uAge * (1.0 - pow(f, 0.25));
    float w = uW * (1.0 + uSpread * age);                 // 留下之后慢慢扩散变宽
    float we = max(w, s * uPixAng * 1.2);                 // 远处细到不足一个像素时按像素宽度画，亮度按比例降（不闪烁）
    vec3 side = normalize(cross(u, rd) + 1e-5);
    float turb = fbm2(vec2(tl * 0.05 + uSeed, age * 1.3 + dot(uEye + rd * s - q, side) / we * 0.15), 4);
    float core = exp(-pow(dist / (we * 0.45), 2.0));
    float sheath = exp(-dist / (we * 2.2)) * (0.4 + 1.0 * turb);
    float life = exp(-age / uDecay) * (w / we);
    vec3 col = vec3(0.85, 0.95, 1.0) * core * 2.4
             + mix(vec3(0.25, 0.5, 1.0), vec3(0.6, 0.35, 1.0), smoothstep(0.35, 0.7, turb)) * sheath * 0.55;
    fragColor = vec4(col * life * uAmt, 1.0);
}
"""


def trail(e, cam, a, b, amt, age, width=0.35, seed=0.0, decay=0.9, spread=2.2):
    """航迹：从发射点 a 到船尾 b 的光束（世界坐标）。age：发射点那一端已经留下了多久（秒）。
    decay：留下之后多久暗下去（第六章的航迹不消散，传一个很大的值）；spread：每秒变宽多少倍。"""
    if amt <= 0.002:
        return
    u = cam_uniforms(cam)
    u.update(uA=tuple(float(x) for x in a), uB=tuple(float(x) for x in b), uW=float(width), uAge=float(age),
             uAmt=float(amt), uSeed=float(seed), uDecay=float(decay), uSpread=float(spread))
    e.draw_fs("wd_trail", TRAIL_FS, u, blend="add")


RUSH_FS = r"""
uniform sampler2D uSrc;
uniform vec2 uC;                  // 消失点（像素，左上原点）
uniform float uZoom;              // 朝消失点的径向拖影长度（占到中心距离的比例）
uniform float uStretch;           // 外圈向外拉伸
uniform float uTwist;             // 外圈旋转（弧度，按半径平方增长）
uniform float uChroma;            // 三个颜色通道的缩放差
uniform float uGain;              // 整体增益（默认 1）
in vec2 vUV; out vec4 fragColor;
vec3 at(vec2 P){ vec2 uv = vec2(P.x, uRes.y - P.y) / uRes; uv = 1.0 - abs(1.0 - mod(uv, 2.0)); return texture(uSrc, uv).rgb; }
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    vec2 d = P - uC;
    float r = length(d) / uRes.y;
    // 外圈从更靠近中心的地方取样 = 外圈被向外拉长
    d *= 1.0 - uStretch * r * r / (1.0 + r * r);
    float a = uTwist * r * r;
    d = mat2(cos(a), -sin(a), sin(a), cos(a)) * d;
    vec3 acc = vec3(0.0); float ws = 0.0;
    float jit = hash12(P + fract(uTime * 13.0) * 100.0);
    for (int i = 0; i < 24; i++){
        float f = (float(i) + jit) / 24.0;
        float k = 1.0 - uZoom * f * min(r * 2.5, 1.0);   // 越靠外拖得越长，消失点本身保持清楚
        float wgt = 1.0 - 0.6 * f;
        acc.r += at(uC + d * k * (1.0 + uChroma)).r * wgt;
        acc.g += at(uC + d * k).g * wgt;
        acc.b += at(uC + d * k * (1.0 - uChroma)).b * wgt;
        ws += wgt;
    }
    fragColor = vec4(acc / ws * uGain, 1.0);
}
"""


def rush(e, tex, center, amt, zoom=0.35, stretch=0.3, twist=0.12, chroma=0.012, gain=1.0):
    """把离屏缓冲 tex（整幅画面）经"追赶形变"画到当前缓冲。amt 0..1 统一缩放各项强度；gain 是整体亮度增益
    （径向拖影越长，每个像素分到的亮度越少；退出超光速时用它把星星的拖线补亮）。"""
    e.draw_fs("wd_rush", RUSH_FS, dict(uC=tuple(float(x) for x in center), uZoom=float(zoom * amt),
                                      uStretch=float(stretch * amt), uTwist=float(twist * amt),
                                      uChroma=float(chroma * amt), uGain=float(gain)), dict(uSrc=tex), blend="add")


# ---------------------------------------------------------------------- 急停时的球形冲击波（只折射，不发光）
SHOCK_FS = CAM_GLSL + r"""
uniform sampler2D uSrc;
uniform vec3 uO;            // 冲击波中心（世界坐标）
uniform vec2 uQ;            // 中心在屏幕上的位置（像素，左上原点）
uniform vec4 uShell[6];     // 每层球壳：半径、壳厚（世界单位）、最大位移（像素，负数 = 往里吸）、纹影明暗强度
uniform int uN;
uniform float uChroma;
uniform float uBulge;       // 整幅画面以中心为原点的鼓胀（>0 往外鼓、<0 往里收），冲击波扫过镜头后的余震
uniform float uHaze;        // 球壳边缘一层很淡、很宽的冷色薄雾（黑色的天空上折射看不出来，靠它勾出球的轮廓）
in vec2 vUV; out vec4 fragColor;
vec3 at(vec2 P){ vec2 uv = vec2(P.x, uRes.y - P.y) / uRes; uv = 1.0 - abs(1.0 - mod(uv, 2.0)); return texture(uSrc, uv).rgb; }
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    vec3 rd = camRay(vUV);
    vec3 v = uO - uEye;
    float D = length(v);
    // 视线与"镜头 -> 中心"的夹角；半径 R 的球壳在画面上是张角 asin(R/D) 的一圈
    float th = acos(clamp(dot(rd, v / D), -1.0, 1.0));
    vec2 dir = P - uQ;
    dir /= max(length(dir), 1.0);
    float disp = 0.0, lum = 0.0, haze = 0.0;
    for (int i = 0; i < 6; i++){
        if (i >= uN) break;
        vec4 S = uShell[i];
        if (S.x >= D * 0.98) continue;          // 已经扫过镜头（镜头那一下由 uBulge 和抖动来讲）
        float x = (th - asin(S.x / D)) / max(S.y / D, 1e-3);
        // 高斯的导数：波前外侧往外推、内侧往里拉
        disp += S.z * x * exp(-x * x) * 1.65;
        // 纹影：波前外缘被压缩的空间微微提亮、身后稀疏的一带微微压暗——像热浪里的光，不是一道发光的线
        lum += S.w * (exp(-2.0 * (x - 0.6) * (x - 0.6)) - 0.6 * exp(-1.5 * (x + 0.9) * (x + 0.9)));
        haze += S.w * exp(-2.0 * x * x);
    }
    vec2 c = P - 0.5 * uRes;
    float r2 = dot(c, c) / dot(0.5 * uRes, 0.5 * uRes);
    vec2 off = dir * disp + c * uBulge * (0.35 + 0.65 * r2);
    vec3 col;
    col.r = at(P - off * (1.0 + uChroma)).r;
    col.g = at(P - off).g;
    col.b = at(P - off * (1.0 - uChroma)).b;
    fragColor = vec4(col * max(1.0 + lum, 0.0) + uHaze * haze * vec3(0.45, 0.7, 1.0), 1.0);
}
"""


def shock(e, cam, tex, center, shells, bulge=0.0, chroma=0.15, haze=0.0):
    """把离屏缓冲 tex 经球形冲击波折射后画到当前缓冲。center：球心（世界坐标）；
    shells：[(半径, 壳厚, 最大位移像素, 纹影强度)]，最多 6 层，半径为 0、位移为负的一层就是往中心"吸"的塌缩；
    bulge：整幅画面的鼓胀量（比例）；haze：球壳边缘冷色薄雾的亮度（按每层的纹影强度加权）。中心不在镜头前方、或者什么都不用画时返回 False（调用方直接用原图）。"""
    q = cam.project(tuple(float(x) for x in center))
    rows = [(float(r), float(w), float(a), float(g)) for r, w, a, g in shells[:6] if abs(a) >= 0.5 or abs(g) >= 0.005]
    if q is None or (not rows and abs(bulge) < 1e-4):
        return False
    n = len(rows)
    while len(rows) < 6:
        rows.append((0.0, 1.0, 0.0, 0.0))
    u = cam_uniforms(cam)
    u.update(uO=tuple(float(x) for x in center), uQ=(float(q[0]), float(q[1])),
             uShell=np.array(rows, np.float32).ravel(), uN=n, uChroma=float(chroma), uBulge=float(bulge), uHaze=float(haze))
    e.draw_fs("wd_shock", SHOCK_FS, u, dict(uSrc=tex), blend="add")
    return True


# 星际尘埃：平时看不见，冲击波的波前扫过时被照亮一下。波前处的尘埃连成一层细密的光点球壳，
# 球的边缘（视线擦过的地方）光点叠得最密，所以不靠发光线条也读得出一个三维的球在鼓出去
SHOCKDUST_BODY = r"""
uniform vec3 uO;            // 球心（世界坐标）
uniform vec3 uFront[3];     // 每道波前：半径、厚度（世界单位）、亮度
uniform int uNF;
uniform vec3 uEyeW;
uniform float uSplit;       // 球心的视深：uSide = 1 只画比它远的（在飞船之前画，被船体挡住），-1 只画近的
uniform float uSide;
uniform vec3 uFwd;
void main(){
    vec3 P = uO + in_pos;
    float r = length(in_pos);
    float b = 0.0;
    for (int i = 0; i < 3; i++){
        if (i >= uNF) break;
        float x = (r - uFront[i].x) / uFront[i].y;
        // 只有波前那一层亮（身后只留很短的余辉）：身后整片都亮的话满屏都是光点，像暴风雪
        b += uFront[i].z * (x > 0.0 ? exp(-x * x) : exp(-x * x * 0.6));
    }
    float dz = dot(P - uEyeW, uFwd);
    b *= smoothstep(1.5, 5.0, dz);                  // 离镜头太近的淡出，免得扫过镜头时糊成大光斑
    emit(P, vec4(in_col.rgb * b, 1.0), in_extra.x);
    if ((dz - uSplit) * uSide < 0.0) vCol = vec4(0.0);
}
"""


class ShockDust:
    """冲击波扫过时被照亮的星际尘埃：n 颗散在球心周围 3.5-24 单位的球壳里（按半径均匀，固定种子）。
    要足够密、每颗足够暗，波前才连成一层"薄纱"，太稀的话被照亮的只是零星几颗，看着像多了几颗星。
    波前那层要薄：薄壳在视线擦过的边缘叠得最厚，球的轮廓才出得来（厚了就是一团均匀的雪）。
    draw(side=1) 在飞船之前画远侧一半，side=-1 在之后画近侧一半，船体能挡住背后的尘埃。"""

    def __init__(self, e, n=120000, seed=13):
        rng = np.random.default_rng(seed)
        d = rng.normal(size=(n, 3))
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        pos = d * (3.5 + 20.5 * rng.random(n))[:, None]
        k = rng.random(n)
        col = np.where(k[:, None] < 0.75, [0.55, 0.78, 1.0], [0.9, 0.95, 1.0]) * (0.15 + 0.6 * rng.random(n) ** 3)[:, None]
        col = np.hstack([col, np.ones((n, 1))])
        extra = np.zeros((n, 4))
        extra[:, 0] = 0.007 + 0.007 * rng.random(n)        # 约一个像素：再大就成了雪片，再小就看不见
        self.e = e
        self.cloud = e.make_cloud("wd_shockdust", SHOCKDUST_BODY, pos, col, extra)

    def draw(self, cam, center, fronts, gain, side):
        """fronts：[(半径, 厚度, 亮度)]，最多 3 道。"""
        rows = [tuple(float(v) for v in f) for f in fronts[:3]]
        if not rows or gain <= 0.003:
            return
        n = len(rows)
        while len(rows) < 3:
            rows.append((0.0, 1.0, 0.0))
        eye = np.asarray(cam.eye, np.float64)
        fwd = np.asarray(cam.target, np.float64) - eye
        fwd /= np.linalg.norm(fwd)
        self.e.draw_cloud(self.cloud, cam, dict(uO=tuple(float(x) for x in center), uFront=np.array(rows, np.float32).ravel(),
                                                uNF=n, uEyeW=tuple(eye), uFwd=tuple(fwd), uGain=float(gain),
                                                uSplit=float(np.dot(np.asarray(center, np.float64) - eye, fwd)),
                                                uSide=float(side), uMinPx=1.0))


# ---------------------------------------------------------------------- 曲率环充能：环周围的空间被拧弯
RINGLENS_FS = CAM_GLSL + r"""
uniform sampler2D uSrc;
uniform vec4 uDisk[2];     // 每道环：所在平面的 z、半径、环身处的扭转角（弧度）、环身处的放大量（比例）
uniform int uN;
uniform float uChroma;
in vec2 vUV; out vec4 fragColor;
vec3 at(vec2 P){ vec2 uv = vec2(P.x, uRes.y - P.y) / uRes; uv = 1.0 - abs(1.0 - mod(uv, 2.0)); return texture(uSrc, uv).rgb; }
// 世界坐标 -> 像素（左上原点），与 camRay 互逆
vec2 toScreen(vec3 X){
    vec3 d = X - uEye;
    float z = max(dot(d, uCF), 1e-4);
    vec2 ndc = vec2(dot(d, uCR) / (z * uTan * uRes.x / uRes.y), dot(d, uCU) / (z * uTan));
    vec2 uv = (ndc + 1.0 + uShift) * 0.5;
    return vec2(uv.x, 1.0 - uv.y) * uRes;
}
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    vec3 rd = camRay(vUV);
    vec2 disp = vec2(0.0);
    for (int i = 0; i < 2; i++){
        if (i >= uN) break;
        vec4 D = uDisk[i];
        if (abs(rd.z) < 1e-5) continue;
        float t = (D.x - uEye.z) / rd.z;           // 视线与环面的交点
        if (t <= 0.0) continue;
        vec3 q = uEye + rd * t;
        float rho = length(q.xy) / D.y;
        if (rho >= 2.6) continue;
        // 环身处最强，向里向外平滑减弱：像环把周围的空间拖着转。环里大半被船体挡住，环外露出的星空上才看得出来
        float w = exp(-pow((rho - 1.0) / 0.55, 2.0));
        float a = D.z * w;
        vec2 r2 = mat2(cos(a), sin(a), -sin(a), cos(a)) * q.xy * (1.0 - D.w * w);
        disp += toScreen(vec3(r2, D.x)) - P;
    }
    vec3 col;
    col.r = at(P + disp * (1.0 + uChroma)).r;
    col.g = at(P + disp).g;
    col.b = at(P + disp * (1.0 - uChroma)).b;
    fragColor = vec4(col, 1.0);
}
"""


def ring_lens(e, cam, tex, disks, chroma=0.05):
    """曲率环充能时环周围的空间被拧弯：环身附近（里外各约半个环半径）看到的星空绕环心打旋、被放大（只折射，不发光）。
    disks：[(环面 z, 半径, 环身处扭转角 弧度, 环身处放大量)]，环心在航线（x = y = 0）上，最多 2 个。
    把离屏缓冲 tex 折射后画到当前缓冲；没有要画的环时返回 False（调用方直接用原图）。"""
    rows = [(float(z), float(r), float(a), float(m)) for z, r, a, m in disks[:2] if abs(a) > 1e-3 or abs(m) > 1e-3]
    if not rows:
        return False
    n = len(rows)
    while len(rows) < 2:
        rows.append((0.0, 1.0, 0.0, 0.0))
    u = cam_uniforms(cam)
    u.update(uDisk=np.array(rows, np.float32).ravel(), uN=n, uChroma=float(chroma))
    e.draw_fs("wd_ringlens", RINGLENS_FS, u, dict(uSrc=tex), blend="add")
    return True


# 能量微粒：每颗从环外一圈"甜甜圈"形的区域出发，螺旋着加速卷进环里，到环身时熄灭，然后从起点重来。
# 进度 u 跟着充能脉冲的相位走（每 4 个脉冲走完一趟，各颗快慢不同），所以脉冲越来越快，微粒也越卷越快。
RINGFLOW_BODY = r"""
uniform mat3 uRot;        // 飞船局部 -> 世界
uniform float uPh;        // 充能脉冲相位（cues.charge_phase）
uniform float uAmt;       // 整体亮度
uniform vec3 uEyeW; uniform vec3 uFwd;
uniform float uSplit;     // 飞船中心的视深：uSide = 1 只画比它远的（在飞船之前画，被船体挡住），-1 只画近的
uniform float uSide;
const float RR = 1.72;
vec3 at(float u){
    float zc = in_extra.w < 0.5 ? 0.25 : -1.65;
    float dir = in_extra.w < 0.5 ? 1.0 : -1.0;     // 前后两道环转向相反
    float k = u * u;
    float r = mix(in_pos.y, RR, k);
    float th = in_pos.x + dir * 2.4 * k;
    return uRot * vec3(r * cos(th), r * sin(th), zc + in_pos.z * (1.0 - k));
}
void main(){
    float u = fract(uPh * 0.25 * in_extra.y + in_extra.x);
    vec3 P = at(u);
    // 亮度集中在快撞上环身的那一段（远处只是隐约的光点）；撞上环身时熄灭。离镜头很近的淡出，免得镜头穿过时拉成大光条
    float b = smoothstep(0.0, 0.3, u) * (1.0 - smoothstep(0.92, 1.0, u)) * (0.12 + 0.88 * u * u * u)
            * smoothstep(2.5, 5.0, dot(P - uEyeW, uFwd));
    // 拉成顺着螺旋路径的短光条：方向和长度取前一小段路程在屏幕上的投影
    vec4 c1 = uMVP * vec4(P, 1.0), c0 = uMVP * vec4(at(max(u - 0.08 * in_extra.y, 0.0)), 1.0);
    vec2 dpx = (c1.xy / max(c1.w, 1e-3) - c0.xy / max(c0.w, 1e-3)) * uRes * 0.5;
    float px = max(in_extra.z * uSize * uPix / max(c1.w, 1e-3), uMinPx);
    float len = length(dpx);
    float stretch = clamp(len / px, 1.0, 7.0);
    emit2(P, vec4(in_col.rgb * b * uAmt, 1.0), in_extra.z * stretch, 0.0, atan(dpx.y, dpx.x), stretch);
    if ((dot(P - uEyeW, uFwd) - uSplit) * uSide < 0.0) vCol = vec4(0.0);
}
"""


class RingFlow:
    """曲率环充能时卷进环里的能量微粒（两道环各 n 颗）。draw(side=1) 在飞船之前画远侧的一半，side=-1 在之后画近侧的一半，
    这样船体能挡住背后的微粒。"""

    def __init__(self, e, n=800, seed=5):
        rng = np.random.default_rng(seed)
        m = 2 * n
        # 起点贴着环外一圈（半径 1.95-3.6、离环面不远），形成两个收得很紧的漩涡，而不是满屏的"暴风雪"
        pos = np.stack([rng.random(m) * math.tau, 1.95 + 1.65 * rng.random(m) ** 1.5,
                        np.clip(rng.normal(0.0, 0.5, m), -1.2, 1.2)], 1)
        k = rng.random(m)
        col = np.where(k[:, None] < 0.8, [0.45, 0.82, 1.0], np.where(k[:, None] < 0.93, [0.8, 0.92, 1.0], [0.65, 0.5, 1.0]))
        col = np.hstack([col * (0.8 + 2.2 * rng.random(m) ** 3)[:, None], np.ones((m, 1))])
        extra = np.stack([rng.random(m), 0.7 + 0.6 * rng.random(m), 0.006 + 0.008 * rng.random(m) ** 2,
                          (np.arange(m) >= n).astype(np.float64)], 1)
        self.e = e
        self.cloud = e.make_cloud("wd_ringflow", RINGFLOW_BODY, pos, col, extra)

    def draw(self, cam, R, ph, amt, side):
        if amt <= 0.003:
            return
        eye = np.asarray(cam.eye, np.float64)
        fwd = np.asarray(cam.target, np.float64) - eye
        fwd /= np.linalg.norm(fwd)
        split = float(np.dot(np.asarray(R) @ np.array([0.0, 0.0, -0.7]) - eye, fwd))
        self.e.draw_cloud(self.cloud, cam, dict(uRot=np.asarray(R, np.float32), uPh=float(ph), uAmt=float(amt),
                                                uEyeW=tuple(eye), uFwd=tuple(fwd), uSplit=split, uSide=float(side),
                                                uMinPx=1.2))


# ---------------------------------------------------------------------- 透明的激波环（只折射，不发光）
RINGWARP_FS = CAM_GLSL + r"""
uniform sampler2D uSrc;
uniform vec4 uRing[8];     // 每个环：所在平面的 z、半径、环带半宽（世界单位）、最大位移（像素）
uniform vec2 uRc[8];       // 环心（航线上那一点）在屏幕上的位置（像素，左上原点）
uniform int uN;
uniform float uChroma;
in vec2 vUV; out vec4 fragColor;
vec3 at(vec2 P){ vec2 uv = vec2(P.x, uRes.y - P.y) / uRes; uv = 1.0 - abs(1.0 - mod(uv, 2.0)); return texture(uSrc, uv).rgb; }
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    vec3 rd = camRay(vUV);
    vec2 disp = vec2(0.0);
    for (int i = 0; i < 8; i++){
        if (i >= uN) break;
        vec4 R = uRing[i];
        if (abs(rd.z) < 1e-5) continue;
        float t = (R.x - uEye.z) / rd.z;          // 视线与环所在平面的交点
        if (t <= 0.0) continue;
        vec3 q = uEye + rd * t;
        float x = (length(q.xy) - R.y) / R.z;
        // 高斯的导数：环外侧往外推、内侧往里拉，像一圈透明的激波扫过
        float prof = x * exp(-x * x) * 1.65;
        vec2 dir = P - uRc[i];
        float dl = length(dir);
        if (dl < 1.0) continue;
        disp += dir / dl * R.w * prof;
    }
    vec3 col;
    col.r = at(P - disp * (1.0 + uChroma)).r;
    col.g = at(P - disp).g;
    col.b = at(P - disp * (1.0 - uChroma)).b;
    fragColor = vec4(col, 1.0);
}
"""


def ring_warp(e, cam, tex, rings, chroma=0.12):
    """把离屏缓冲 tex 经若干透明激波环折射后画到当前缓冲。rings：[(z, 半径, 环带半宽, 最大位移像素)]，
    环心都在航线（x = y = 0）上，最多 8 个。返回 False 表示没有可画的环（调用方直接用原图）。"""
    rows, centers = [], []
    for z, r, w, amp in rings[:8]:
        q = cam.project((0.0, 0.0, float(z)))
        if q is None or amp < 0.5:
            continue
        rows.append((float(z), float(r), float(w), float(amp)))
        centers.append((float(q[0]), float(q[1])))
    if not rows:
        return False
    n = len(rows)
    while len(rows) < 8:
        rows.append((0.0, 0.0, 1.0, 0.0))
        centers.append((0.0, 0.0))
    u = cam_uniforms(cam)
    # uniform 数组要压平成 float32 一维数组传（引擎的 set_u 按字节写入）
    u.update(uRing=np.array(rows, np.float32).ravel(), uRc=np.array(centers, np.float32).ravel(),
             uN=n, uChroma=float(chroma))
    e.draw_fs("wd_ringwarp", RINGWARP_FS, u, dict(uSrc=tex), blend="add")
    return True
