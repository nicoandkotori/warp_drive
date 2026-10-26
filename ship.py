# -*- coding: utf-8 -*-
"""飞船与曲率跃迁的着色器：
  ship(...)      光线步进的曲率飞船（模型在 ship_model.py），带抗锯齿轮廓，"over" 叠在背景上
  relstars(...)  相对论星空：光行差（前方星星聚拢）+ 多普勒（前蓝后红）+ 速度拖影
  tunnel(...)    曲率隧道：径向星光拖线 + 色散 + 旋转的时空隧道壁
  lens(...)      曲率泡透镜：把离屏背景按"前压缩、后拉伸"扭曲，并给泡壁加色散光边

飞船局部坐标：+z 船头，+y 上，单位约等于船体半宽的 3 倍（全长约 5.2）。
ship_frame(fwd, up) 返回 局部->世界 的旋转矩阵。
"""
import math
import numpy as np
from wfx import CAM_GLSL, DIRSTARS_GLSL, cam_uniforms
from ship_model import SHIP_MODEL_GLSL

# 飞船模型着色器见 ship_model.py（细节 + 基于物理的材质）
SHIP_FS = CAM_GLSL + SHIP_MODEL_GLSL


def ship_frame(fwd, up=(0.0, 1.0, 0.0)):
    """局部 +z 指向 fwd 的旋转矩阵（局部 -> 世界）。"""
    f = np.asarray(fwd, np.float64)
    f /= np.linalg.norm(f)
    r = np.cross(np.asarray(up, np.float64), f)
    r /= np.linalg.norm(r)
    u = np.cross(f, r)
    return np.stack([r, u, f], 1)


def roll(R, a):
    """绕船体自身 z 轴滚转。"""
    c, s = math.cos(a), math.sin(a)
    return R @ np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def ship(e, cam, pos, R, scale=1.0, ring=1.0, phase=0.0, engine=1.0, amt=1.0, sun=(0.6, 0.5, 0.4),
         sun_col=(1.6, 1.45, 1.3), fill=(0.25, 0.35, 0.6), ring_col=(0.35, 0.85, 1.0), stretch=1.0, flow=0.0,
         charge=1.0, charge_flash=0.0, spin=0.0, warp_on=0.0, countdown=0, countdown_phase=0.0):
    """画飞船。pos 世界坐标，R 局部->世界旋转（ship_frame），scale 整体缩放，stretch 沿船轴拉长（跃迁瞬间）。"""
    if amt <= 0.001:
        return
    s = np.asarray(sun, np.float64)
    # 飞船在屏幕上占得大（特写）时开 2x2 超采样，远景省掉
    p0 = cam.project(tuple(pos))
    p1 = cam.project(tuple(np.asarray(pos) + np.asarray(cam.up) * 3.0 * scale))
    big = p0 is not None and p1 is not None and math.hypot(p0[0] - p1[0], p0[1] - p1[1]) > 220
    u = cam_uniforms(cam)
    u.update(uPos=tuple(pos), uRot=np.asarray(R, np.float32), uScale=float(scale), uSun=tuple(s / np.linalg.norm(s)),
             uSunCol=tuple(sun_col), uFill=tuple(fill), uRing=float(ring), uPhase=float(phase),
             uEngine=float(engine), uAmt=float(amt), uRingCol=tuple(ring_col), uStretch=float(stretch),
             uFlow=float(flow), uCharge=float(np.clip(charge, 0, 1)),
             uCountdown=float(countdown), uCountdownPhase=float(countdown_phase),
             uChargeFlash=float(max(0, charge_flash)), uSS=2 if big else 1, uSpin=float(spin), uWarpOn=float(warp_on))
    e.draw_fs("wd_ship", SHIP_FS, u, blend="over")


# ------------------------------------------------------------------ 相对论星空
RELSTARS_FS = CAM_GLSL + DIRSTARS_GLSL + r"""
uniform vec3 uMot;            // 运动方向（世界）
uniform float uBeta;          // 当前速度 v/c
uniform float uBeta0;         // 拖影起点速度（= uBeta 时无拖影）
uniform float uStars; uniform float uNeb; uniform vec3 uGal; uniform vec3 uN1; uniform vec3 uN2;
uniform float uDop;           // 多普勒着色强度
uniform float uBow;           // 星虹：按多普勒因子把星光染成光谱色（接近光速时前方会出现一圈彩虹）
uniform int uSamples;
in vec2 vUV; out vec4 fragColor;
// 静止系方向 -> 观测方向 的逆变换：已知观测方向 d，求静止系方向
vec3 restDir(vec3 d, float beta, out float D){
    float c1 = dot(d, uMot);
    vec3 perp = d - uMot * c1;
    float pl = length(perp);
    perp = pl > 1e-6 ? perp / pl : vec3(0.0);
    float c0 = (c1 - beta) / (1.0 - beta * c1);
    float s0 = sqrt(max(1.0 - c0 * c0, 0.0));
    float g = 1.0 / sqrt(max(1.0 - beta * beta, 1e-6));
    D = 1.0 / (g * (1.0 - beta * c1));
    return uMot * c0 + perp * s0;
}
vec3 dopplerTint(vec3 c, float D){
    float l = luma(c);
    float k = log2(max(D, 1e-3));
    vec3 blue = vec3(0.35, 0.55, 1.0) * l * 1.3;
    vec3 violet = vec3(0.65, 0.4, 1.0) * l * 1.6;
    vec3 red = vec3(1.0, 0.28, 0.12) * l;
    vec3 o = k > 0.0 ? mix(mix(c, blue, clamp(k * 0.8, 0.0, 1.0)), violet, clamp(k * 0.4 - 0.6, 0.0, 1.0))
                     : mix(c, red, clamp(-k * 1.2, 0.0, 1.0));
    o = mix(c, o, uDop);
    if (uBow > 0.0){
        // 星虹：log2(D) 从 0 到 3.5 对应 红 -> 黄 -> 绿 -> 蓝 -> 紫；D<1 的后方星光（红移到看不见）压暗
        float x = clamp(k / 3.5, 0.0, 1.0);
        vec3 bow = clamp(abs(fract(0.78 * x + vec3(1.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0) - 1.0, 0.0, 1.0);   // 色相 0 -> 0.78
        bow = mix(bow, vec3(0.8, 0.5, 1.0), smoothstep(0.85, 1.0, x));
        vec3 b = bow * l * 2.2 * (k < 0.0 ? exp(k * 2.0) : 1.0);
        o = mix(o, b, uBow);
    }
    return o;
}
void main(){
    vec3 d = camRay(vUV);
    vec3 acc = vec3(0);
    int N = uSamples;
    for (int i = 0; i < 32; i++){
        if (i >= N) break;
        float f = N > 1 ? float(i) / float(N - 1) : 0.0;
        float b = mix(uBeta, uBeta0, f);
        float D;
        vec3 r = restDir(d, b, D);
        vec3 s = dirStars(r, uStars);
        if (uNeb > 0.0) s += dirNebula(r, uGal, uN1, uN2, uNeb);
        // 多普勒聚束：真实是 D^3~D^4，这里压缩成 D^1.5 并封顶，否则前方整片过曝
        float boost = pow(clamp(D, 0.0, 4.0), 1.5);
        acc += dopplerTint(s, D) * mix(1.0, boost, uDop) * (N > 1 ? (1.0 - f * 0.7) : 1.0);
    }
    if (N > 1) acc /= float(N) * 0.65;
    fragColor = vec4(acc, 1.0);
}
"""


def relstars(e, cam, beta=0.0, beta0=None, motion=(0.0, 0.0, 1.0), stars=1.0, neb=0.0, gal=(0.3, 0.9, 0.2),
             n1=(0.12, 0.22, 0.55), n2=(0.55, 0.15, 0.45), dop=1.0, samples=None, bow=0.0):
    """相对论星空。beta0 给出拖影起点（例如 0.2 秒前的速度），samples 自动按拖影长度取。"""
    beta0 = beta if beta0 is None else beta0
    m = np.asarray(motion, np.float64)
    m /= np.linalg.norm(m)
    g = np.asarray(gal, np.float64)
    g /= np.linalg.norm(g)
    if samples is None:
        samples = 1 if abs(beta - beta0) < 1e-4 else int(min(32, 8 + abs(beta - beta0) * 120))
    u = cam_uniforms(cam)
    u.update(uMot=tuple(m), uBeta=float(min(beta, 0.995)), uBeta0=float(min(beta0, 0.995)), uStars=float(stars),
             uNeb=float(neb), uGal=tuple(g), uN1=tuple(n1), uN2=tuple(n2), uDop=float(dop), uSamples=int(samples), uBow=float(bow),
             uFine=1.0 if samples == 1 else 0.12)
    e.draw_fs("wd_relstars", RELSTARS_FS, u, blend="add")


# ------------------------------------------------------------------ 曲率隧道
TUNNEL_FS = r"""
uniform vec2 uC;          // 消失点（像素，左上原点）
uniform float uAmt;       // 整体强度
uniform float uZ;         // 已经"飞过"的距离（随时间积分，场景里算好）
uniform float uLen;       // 拖线长度（与速度成正比）
uniform float uTwist;     // 隧道旋转
uniform vec3 uCa; uniform vec3 uCb;   // 隧道壁的两种颜色
uniform float uRings;                 // 迎面飞过的曲率场光环
uniform float uFly;                   // 迎面掠过的亮星
in vec2 vUV; out vec4 fragColor;
vec3 streaks(vec2 d, float zoff, float lenK){
    float r = length(d);
    float a = atan(d.y, d.x);
    float z = 0.09 / max(r, 1e-3);
    vec3 col = vec3(0);
    for (int L = 0; L < 3; L++){
        float fl = float(L);
        float na = 70.0 + 55.0 * fl;
        float ca = (a / TAU + 0.5) * na;
        float ia = floor(ca), fa = fract(ca);
        float zz = z * (0.8 + 0.25 * fl) + zoff * (1.0 + 0.35 * fl);
        for (int k = 0; k < 2; k++){
            float iz = floor(zz) - float(k);
            vec2 id = vec2(ia, iz + fl * 101.0);
            if (hash12(id) > 0.5) continue;
            float z0 = iz + hash12(id + 3.1);
            float len = lenK * (0.5 + hash12(id + 7.7));
            float u = (zz - z0) / max(len, 1e-3);           // 0..1 沿拖线
            if (u < 0.0 || u > 1.0) continue;
            float ac = hash12(id + 1.9) * 0.8 + 0.1;
            float dx = (fa - ac) / na * TAU * r * uRes.y;   // 横向像素距离
            float w = 1.0 + 1.5 * (1.0 - z / (z + 2.0));
            float core = exp(-dx * dx / (w * w));
            float fade = smoothstep(0.0, 0.15, u) * (1.0 - u) * (1.0 - u);
            float far = smoothstep(0.0, 0.08, r);
            vec3 c = mix(vec3(0.55, 0.75, 1.0), vec3(1.0, 0.85, 1.0), hash12(id + 5.5));
            col += c * core * fade * far * (0.8 + 1.4 * hash12(id + 2.2));
        }
    }
    return col;
}
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    vec2 d = (P - uC) / uRes.y;
    float r = length(d);
    float a = atan(d.y, d.x);
    // 色散：红绿蓝三个通道按略微不同的半径采样
    vec3 s;
    s.r = streaks(d * 1.025, uZ, uLen).r;
    s.g = streaks(d, uZ, uLen).g;
    s.b = streaks(d * 0.975, uZ, uLen).b;
    // 隧道壁：周期化角度的 3D 噪声，沿 z 流动并旋转
    float z = 0.09 / max(r, 1e-3);
    vec3 q = vec3(cos(a + uTwist + z * 0.15), sin(a + uTwist + z * 0.15), z * 0.6 + uZ * 0.8);
    float n = fbm3(q * vec3(1.6, 1.6, 0.5), 5);
    float n2 = fbm3(q * vec3(3.0, 3.0, 1.2) + 4.0, 4);
    float wall = smoothstep(0.35, 0.9, n) * smoothstep(0.02, 0.35, r) * exp(-r * 0.9);
    vec3 wc = mix(uCa, uCb, smoothstep(0.3, 0.7, n2)) * wall * 1.6;
    wc += vec3(1.0) * pow(smoothstep(0.65, 1.0, n * n2 * 1.7), 3.0) * smoothstep(0.03, 0.3, r) * 1.5;
    // 曲率场光环：一圈圈从中心向外飞过镜头
    // 环的宽度按屏幕半径换算（外圈 z 变化很慢，直接用 z 的宽度会糊成一大片）
    float rz = fract(z * 0.22 - uZ * 0.55);
    float dr = (rz - 0.5) * r * r / (0.22 * 0.09);
    float rings = exp(-pow(dr / (0.003 + 0.008 * r), 2.0)) * smoothstep(0.04, 0.3, r) * (1.0 - smoothstep(0.6, 1.1, r)) * (0.6 + 0.4 * n);
    wc += mix(vec3(0.4, 0.9, 1.0), vec3(0.9, 0.5, 1.0), n2) * rings * uRings * 1.8;
    if (uFly > 0.0){
        for (int k = 0; k < 2; k++){
            float zc = z * 0.5 + uZ * 0.35 + float(k) * 0.5;
            float iz = floor(zc), fz = fract(zc);
            vec2 id = vec2(iz, float(k) * 17.0);
            float aa = hash12(id) * TAU;
            float rr = 0.09 / max(mix(3.0, 0.15, fz), 0.05);          // 随着靠近从中心向外飞
            vec2 sp = vec2(cos(aa), sin(aa)) * rr * 0.5;
            float sz = 0.004 + 0.05 * fz * fz;
            float g = exp(-dot(d - sp, d - sp) / (sz * sz)) * smoothstep(0.0, 0.3, fz) * (1.0 - smoothstep(0.85, 1.0, fz));
            wc += mix(vec3(1.0, 0.8, 0.5), vec3(0.6, 0.85, 1.0), hash12(id + 3.0)) * g * 3.0 * uFly;
        }
    }
    // 中心的强光
    vec3 core = vec3(0.7, 0.85, 1.0) * (exp(-r / 0.02) * 4.0 + exp(-r / 0.09) * 0.6);
    fragColor = vec4((s * 1.4 + wc + core) * uAmt, 1.0);
}
"""




def tunnel(e, amt, z, length=0.6, twist=0.0, center=None, ca=(0.1, 0.35, 1.0), cb=(0.75, 0.2, 1.0), rings=0.0,
           fly=0.0):
    """曲率隧道。z：沿隧道累计的行程（场景里对速度积分，保证只依赖时间），length：拖线长度。"""
    if amt <= 0.001:
        return
    from opusvid.gl import W, H
    c = center or (W / 2, H / 2)
    e.draw_fs("wd_tunnel", TUNNEL_FS, dict(uC=tuple(c), uAmt=float(amt), uZ=float(z), uLen=float(length),
                                          uTwist=float(twist), uCa=tuple(ca), uCb=tuple(cb), uRings=float(rings), uFly=float(fly)),
              blend="add")


# ------------------------------------------------------------------ 曲率泡透镜
LENS_FS = r"""
uniform sampler2D uSrc;
uniform vec2 uC; uniform float uR; uniform vec2 uDir;   // 像素坐标（左上原点）；uDir 屏幕上的运动方向
uniform float uWarp; uniform float uRim; uniform float uAmt; uniform float uSigma;
uniform float uCap; uniform float uCapAll;   // 前沿堆积的光
uniform float uChroma;                      // 三个颜色通道的位移差（色散）
uniform float uTintAmt;                     // 前蓝后红的多普勒染色强度
uniform float uRipR; uniform float uRipAmp; uniform float uRipW;   // 向外扩散的折射冲击波（像素）：半径、位移幅度、宽度
in vec2 vUV; out vec4 fragColor;
float shape(float r){ return (tanh(uSigma * (r + 1.0)) - tanh(uSigma * (r - 1.0))) / (2.0 * tanh(uSigma)); }
// 采样坐标超出画面时镜像回来（钳制会把边缘像素拉成彩色竖条）
vec3 at(vec2 P){ vec2 uv = vec2(P.x, uRes.y - P.y) / uRes; uv = 1.0 - abs(1.0 - mod(uv, 2.0)); return texture(uSrc, uv).rgb; }
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    // 冲击波：只折射（把星空沿径向推开再拉回），不发光
    if (uRipAmp > 0.0){
        vec2 dp = P - uC; float rp = length(dp);
        float x = (rp - uRipR) / uRipW;
        P -= dp / max(rp, 1.0) * uRipAmp * sin(x * PI) * exp(-x * x);
    }
    vec2 q = (P - uC) / uR;
    float r = length(q);
    // 沿运动方向的位移 s = P - dir·A·R·f(r)：前方泡壁处采样坐标变化快（压缩），后方变化慢（拉伸）
    vec3 col;
    for (int k = 0; k < 3; k++){
        float A = uWarp * (1.0 + float(k - 1) * uChroma);
        col[k] = at(P - uDir * A * uR * shape(r))[k];
    }
    // 压缩处偏蓝、拉伸处偏红：用 f 沿运动方向的导数
    float along = dot(q, uDir);
    float eps = 0.01;
    float dfd = (shape(length(q + uDir * eps)) - shape(length(q - uDir * eps))) / (2.0 * eps);
    float comp = -dfd * uWarp;                        // >0 压缩（前方）
    vec3 tint = comp > 0.0 ? mix(vec3(1.0), vec3(0.45, 0.75, 1.6), clamp(comp * 1.5, 0.0, 1.0))
                           : mix(vec3(1.0), vec3(1.6, 0.55, 0.35), clamp(-comp * 1.5, 0.0, 1.0));
    col *= mix(vec3(1.0), tint, uTintAmt);
    // 泡壁光边：薄壳 + 流动的焦散纹
    float wall = exp(-pow((r - 1.0) / 0.035, 2.0));
    float caust = 0.6 + 0.4 * sin(atan(q.y, q.x) * 9.0 + uTime * 3.0 + fbm2(q * 4.0 + uTime * 0.5, 3) * 6.0);
    vec3 rimC = mix(vec3(1.0, 0.35, 0.3), vec3(0.3, 0.85, 1.0), 0.5 + 0.5 * along);
    col += rimC * wall * caust * uRim;
    col += rimC * exp(-abs(r - 1.0) / 0.25) * 0.06 * uRim;
    if (uCap > 0.0){
        float front = mix(smoothstep(0.1, 0.95, along), 1.0, uCapAll);
        float shell = exp(-pow((r - 1.0) / 0.06, 2.0)) * (0.7 + 0.3 * caust);
        float haze = smoothstep(1.05, 0.2, r) * 0.12 * uCapAll;
        col += vec3(0.55, 0.8, 1.0) * (shell * 2.5 + haze) * front * uCap;
    }
    fragColor = vec4(col * uAmt, 1.0);
}
"""


def lens(e, tex, center, radius, direction, warp=0.4, rim=1.0, amt=1.0, sigma=4.0, blend="add", cap=0.0, cap_all=0.0,
         chroma=0.03, tint=1.0, ripple=(0.0, 0.0, 60.0)):
    """把离屏背景 tex 经曲率泡透镜画到当前缓冲。center/radius 像素，direction 屏幕运动方向。"""
    d = np.asarray(direction, np.float64)
    d /= max(np.linalg.norm(d), 1e-9)
    e.draw_fs("wd_lens", LENS_FS, dict(uC=tuple(center), uR=float(radius), uDir=tuple(d), uWarp=float(warp),
                                      uRim=float(rim), uAmt=float(amt), uSigma=float(sigma), uCap=float(cap), uChroma=float(chroma), uTintAmt=float(tint),
                                      uRipR=float(ripple[0]), uRipAmp=float(ripple[1]), uRipW=float(ripple[2]),
                                      uCapAll=float(cap_all)),
              dict(uSrc=tex), blend=blend)
