# -*- coding: utf-8 -*-
"""opusvid.space — 宇宙题材可复用素材：星云/透镜/光斑/暗物质晕着色器，旋涡星系、星空、宇宙网粒子生成器。"""
import math
import numpy as np
from .gl import (Camera, ease_out, ease_in_out, ease_out_expo, smooth, lin, rot_x, rot_y, rot_z,
                 translate, scale_m, W, H)


NEBULA_FS = r"""
uniform vec3 uC1; uniform vec3 uC2; uniform vec3 uC3;
uniform float uAmt; uniform float uStars; uniform vec2 uOff; uniform float uZoom; uniform float uRot;
uniform float uSeed; uniform float uDust;
in vec2 vUV; out vec4 fragColor;
void main(){
    vec2 px = (vUV * uRes - uRes * 0.5);
    px = rot2(uRot) * px;
    vec2 p = px / uZoom + uOff;
    vec2 q = p / uRes.y * 2.2;
    vec2 w = vec2(fbm2(q * 1.3 + uSeed, 5), fbm2(q * 1.3 + vec2(5.2, 1.3) + uSeed, 5));
    float n = fbm2(q * 1.6 + w * 2.2 + uTime * 0.01, 6);
    float n2 = fbm2(q * 3.1 - w * 1.5 + 7.0, 5);
    float haze = pow(n, 2.6) * 0.38;
    float wisp = pow(smoothstep(0.52, 1.0, n), 2.0) * 1.1;
    vec3 col = mix(uC1, uC2, smoothstep(0.3, 0.85, n2)) * (haze + wisp);
    col += uC3 * pow(smoothstep(0.62, 1.0, n * n2 * 1.6), 2.5) * 0.6;
    float dust = smoothstep(0.5, 0.8, fbm2(q * 4.0 + w * 3.0 + 3.3, 5));
    col *= 1.0 - dust * uDust * 0.6;
    col *= uAmt;
    vec3 st = starfield2d(px / uZoom + uOff * 0.6 + uRes * 0.5, uTime, uStars);
    fragColor = vec4(col + st, 1.0);
}
"""


HALO_FS = r"""
uniform mat4 uInvVP; uniform vec3 uEye; uniform vec3 uCenter; uniform float uRadius;
uniform vec3 uColor; uniform float uAmt; uniform float uCore; uniform float uNoise; uniform float uFlat;
in vec2 vUV; out vec4 fragColor;
void main(){
    vec4 ndc = vec4(vUV * 2.0 - 1.0, 1.0, 1.0);
    vec4 wp = uInvVP * ndc; wp /= wp.w;
    vec3 rd = normalize(wp.xyz - uEye);
    vec3 oc = uEye - uCenter;
    float b = dot(oc, rd), c = dot(oc, oc) - uRadius * uRadius;
    float h = b * b - c;
    if (h < 0.0 || uAmt <= 0.0){ fragColor = vec4(0); return; }
    h = sqrt(h);
    float t0 = max(-b - h, 0.0), t1 = -b + h;
    if (t1 <= 0.0){ fragColor = vec4(0); return; }
    float acc = 0.0;
    const int N = 40;
    float dt = (t1 - t0) / float(N);
    for (int i = 0; i < N; i++){
        vec3 p = uEye + rd * (t0 + (float(i) + 0.5) * dt) - uCenter;
        p.y /= uFlat;
        float r = length(p) / uRadius;
        float rho = 1.0 / (1.0 + pow(r / uCore, 2.0)) * pow(smoothstep(1.0, 0.0, r), 2.0);
        float nz = fbm3(p / uRadius * 3.0 + vec3(0.0, uTime * 0.03, 0.0), 4);
        rho *= mix(1.0, 0.3 + 1.4 * nz, uNoise);
        acc += rho * dt;
    }
    acc /= uRadius;
    fragColor = vec4(uColor * acc * uAmt, 1.0);
}
"""


LENS_FS = r"""
uniform vec2 uLens;        // 透镜中心（像素）
uniform float uThetaE;     // 爱因斯坦半径（像素）
uniform vec2 uSrc;         // 主光源星系（源平面，相对透镜中心，像素）
uniform float uSrcAmt; uniform float uSrcSize;
uniform float uField;      // 背景深空亮度
uniform vec2 uDrift;
uniform float uHaloAmt;    // 可视化：暗物质晕
uniform float uRingFlash;
uniform float uNeb;
in vec2 vUV; out vec4 fragColor;
vec3 smallGalaxies(vec2 p){
    vec3 col = vec3(0);
    float cell = 46.0;
    vec2 g = p / cell; vec2 id = floor(g);
    for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++){
        vec2 cid = id + vec2(x, y);
        float h = hash12(cid + 31.7);
        if (h > 0.55) continue;
        vec2 pos = (cid + hash22(cid + 3.1)) * cell;
        vec2 d = p - pos;
        float ang = hash12(cid + 7.7) * PI;
        d = rot2(ang) * d;
        float e = 1.0 + 2.5 * hash12(cid + 1.3);
        d.y *= e;
        float sz = 1.2 + 4.5 * pow(hash12(cid + 2.2), 3.0);
        float r = length(d) / sz;
        float t = hash12(cid + 5.5);
        vec3 c = t < 0.4 ? vec3(1.0, 0.75, 0.5) : (t < 0.8 ? vec3(0.7, 0.8, 1.0) : vec3(1.0, 0.5, 0.7));
        col += c * (exp(-r * r * 0.8) * 0.9 + exp(-r * 0.9) * 0.15) * (0.25 + 0.75 * hash12(cid + 9.9));
    }
    return col;
}
vec3 srcGalaxy(vec2 p){
    // 一个面朝我们的旋涡星系
    float r = length(p) / uSrcSize;
    float a = atan(p.y, p.x);
    float arms = 0.5 + 0.5 * cos(2.0 * a - log(r + 0.05) * 3.2);
    float disk = exp(-r * 2.6);
    float core = exp(-r * r * 30.0) * 2.5;
    vec3 c = vec3(0.55, 0.75, 1.0) * disk * (0.35 + 1.2 * pow(arms, 3.0)) + vec3(1.0, 0.8, 0.55) * core;
    c += vec3(1.0, 0.4, 0.7) * disk * pow(arms, 8.0) * 0.8 * step(0.25, r);
    return c * 1.4;
}
void main(){
    vec2 px = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    vec2 th = px - uLens;
    float r2 = max(dot(th, th), 1e-3);
    vec2 beta = th - uThetaE * uThetaE * th / r2;
    vec2 sp = beta + uLens + uDrift;
    vec3 col = vec3(0);
    col += starfield2d(sp, uTime, 1.0) * uField;
    col += smallGalaxies(sp) * uField * 0.9;
    if (uNeb > 0.0){
        vec2 q = sp / uRes.y * 2.0;
        float n = fbm2(q * 1.4 + 2.0, 5);
        float n2 = fbm2(q * 2.8 + 9.0, 4);
        col += mix(vec3(0.1, 0.25, 0.6), vec3(0.6, 0.15, 0.5), n2) * pow(smoothstep(0.4, 0.95, n), 2.0) * uNeb;
    }
    col += srcGalaxy(beta - uSrc) * uSrcAmt;
    float r = sqrt(r2);
    col += vec3(0.55, 0.4, 1.0) * uHaloAmt * exp(-r / (uThetaE * 1.4 + 1.0)) * 0.35;
    col += vec3(0.75, 0.7, 1.0) * uRingFlash * exp(-pow((r - uThetaE) / (uThetaE * 0.06 + 2.0), 2.0));
    fragColor = vec4(col, 1.0);
}
"""


FLARE_FS = r"""
uniform vec2 uPos; uniform float uAmt; uniform vec3 uColor; uniform float uStreak; uniform float uRays;
in vec2 vUV; out vec4 fragColor;
void main(){
    vec2 d = vec2(vUV.x, 1.0 - vUV.y) * uRes - uPos;
    float r = length(d);
    vec3 c = uColor * (exp(-r * r / 18.0) * 5.0 + exp(-r / 18.0) * 0.5 + exp(-r / 120.0) * 0.025);
    float streak = exp(-abs(d.y) / 1.8) * exp(-abs(d.x) / (300.0 * uStreak + 1.0));
    c += vec3(0.45, 0.65, 1.0) * streak * 1.4 * uStreak;
    float a = atan(d.y, d.x);
    float rays = pow(abs(cos(a * 2.0)), 220.0) * exp(-r / 95.0) + pow(abs(cos(a * 2.0 + 0.785)), 300.0) * exp(-r / 60.0) * 0.5;
    c += uColor * rays * uRays * 1.2;
    fragColor = vec4(c * uAmt, 1.0);
}
"""


def make_spiral_galaxy(n=400000, seed=1, arms=2, pitch=0.30, r_scale=0.32, rmax=1.45):
    rng = np.random.default_rng(seed)
    out_pos, out_col, out_ex = [], [], []

    def add(pos, col, ex):
        out_pos.append(pos); out_col.append(col); out_ex.append(ex)

    # 盘面恒星
    nd = int(n * 0.66)
    r = rng.exponential(r_scale, nd * 2)
    r = r[(r < rmax) & (r > 0.02)][:nd]
    nd = len(r)
    arm = rng.integers(0, arms, nd)
    th_arm = np.log(np.maximum(r, 0.04) / 0.08) / pitch + arm * 2 * np.pi / arms
    close = rng.random(nd) < 0.7
    spread = np.where(close, rng.normal(0, 0.16, nd) * (1 + 0.6 * r), rng.normal(0, 1.2, nd))
    th = th_arm + spread
    z = rng.normal(0, 1, nd) * (0.012 + 0.018 * r)
    armness = np.exp(-(spread / 0.3) ** 2)
    temp = np.clip(0.45 + 0.5 * armness * rng.random(nd) + rng.normal(0, 0.1, nd), 0, 1)
    c = star_rgb(temp)
    lum = rng.lognormal(-0.3, 0.8, nd) * (0.45 + 1.0 * armness)
    lum = np.minimum(lum, 6)
    col = np.hstack([c * lum[:, None] * 0.11, np.ones((nd, 1))])
    ex = np.stack([np.full(nd, 0.0035), np.zeros(nd), rng.random(nd), np.zeros(nd)], 1)
    add(np.stack([r, th, z], 1), col, ex)
    # 核球
    nb = int(n * 0.2)
    v = rng.normal(0, 1, (nb, 3)) * np.array([0.11, 0.07, 0.11])
    v *= (rng.random((nb, 1)) ** 0.8)
    rb = np.hypot(v[:, 0], v[:, 2]) + 1e-4
    thb = np.arctan2(v[:, 2], v[:, 0])
    tb = np.clip(rng.normal(0.22, 0.1, nb), 0, 1)
    cb = star_rgb(tb) * (rng.lognormal(-0.2, 0.5, nb) * 0.16)[:, None]
    add(np.stack([rb, thb, v[:, 1]], 1), np.hstack([cb, np.ones((nb, 1))]),
        np.stack([np.full(nb, 0.0035), np.zeros(nb), rng.random(nb), np.zeros(nb)], 1))
    # 漫射光（大尺寸、低亮度，给星系一层柔和的"光晕"）
    ng = int(n * 0.06)
    rg = rng.exponential(r_scale * 1.1, ng * 2)
    rg = rg[rg < rmax][:ng]
    ng = len(rg)
    armg = rng.integers(0, arms, ng)
    thg = np.log(np.maximum(rg, 0.04) / 0.08) / pitch + armg * 2 * np.pi / arms + rng.normal(0, 0.35, ng)
    cg = np.where(rg[:, None] < 0.15, np.array([[1.0, 0.8, 0.55]]), np.array([[0.55, 0.65, 1.0]])) * 0.006
    add(np.stack([rg, thg, rng.normal(0, 0.02, ng)], 1), np.hstack([cg, np.ones((ng, 1))]),
        np.stack([rng.uniform(0.018, 0.04, ng), np.zeros(ng), rng.random(ng), np.ones(ng)], 1))
    # 电离氢区（粉色亮点）
    nh = int(n * 0.012)
    rh = rng.uniform(0.15, rmax * 0.85, nh)
    armh = rng.integers(0, arms, nh)
    thh = np.log(rh / 0.08) / pitch + armh * 2 * np.pi / arms + rng.normal(0, 0.1, nh)
    ch = np.array([[1.0, 0.32, 0.55]]) * rng.uniform(0.08, 0.3, (nh, 1))
    add(np.stack([rh, thh, rng.normal(0, 0.01, nh)], 1), np.hstack([ch, np.ones((nh, 1))]),
        np.stack([rng.uniform(0.006, 0.016, nh), np.ones(nh), rng.random(nh), np.full(nh, 2.0)], 1))
    pos = np.vstack(out_pos).astype(np.float32)
    col = np.vstack(out_col).astype(np.float32)
    ex = np.vstack(out_ex).astype(np.float32)
    # 尘埃带（单独一组，用"变暗"混合绘制）
    nu = int(n * 0.1)
    ru = rng.exponential(r_scale * 1.2, nu * 2)
    ru = ru[(ru > 0.08) & (ru < rmax * 0.9)][:nu]
    nu = len(ru)
    armu = rng.integers(0, arms, nu)
    thu = np.log(ru / 0.08) / pitch + armu * 2 * np.pi / arms - 0.28 + rng.normal(0, 0.12, nu)
    dpos = np.stack([ru, thu, rng.normal(0, 0.006, nu)], 1).astype(np.float32)
    dcol = np.hstack([np.tile([[0.10, 0.12, 0.16]], (nu, 1)) * rng.uniform(0.4, 1.0, (nu, 1)), np.ones((nu, 1))]).astype(np.float32)
    dex = np.stack([rng.uniform(0.01, 0.025, nu), np.zeros(nu), rng.random(nu), np.zeros(nu)], 1).astype(np.float32)
    return (pos, col, ex), (dpos, dcol, dex)


def star_rgb(t):
    t = np.asarray(t)[:, None]
    c1, c2, c3 = np.array([1.0, 0.62, 0.38]), np.array([1.0, 0.93, 0.85]), np.array([0.72, 0.84, 1.0])
    return np.where(t < 0.5, c1 + (c2 - c1) * (t * 2), c2 + (c3 - c2) * ((t - 0.5) * 2))


GALAXY_BODY = r"""
uniform float uT; uniform float uOmega; uniform float uBright;
void main(){
    float r = in_pos.x; float z = in_pos.z;
    float v = 1.0 - exp(-r / 0.1);
    float w = v / max(r, 0.03);
    float th = in_pos.y + w * uT * uOmega;
    vec3 P = vec3(r * cos(th), z, r * sin(th));
    emit2(P, in_col * uBright, in_extra.x, in_extra.w, 0.0, 1.0);
}
"""


def make_sky_stars(n=40000, seed=3, radius=200.0):
    rng = np.random.default_rng(seed)
    v = rng.normal(0, 1, (n, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    pos = v * radius
    mag = rng.random(n) ** 7
    c = star_rgb(rng.random(n)) * (0.25 + 5.0 * mag)[:, None]
    col = np.hstack([c, np.ones((n, 1))])
    ex = np.stack([np.full(n, 0.0), np.zeros(n), rng.random(n), np.zeros(n)], 1)
    return pos.astype(np.float32), col.astype(np.float32), ex.astype(np.float32)


SKY_BODY = r"""
uniform float uBright;
void main(){
    float tw = 0.8 + 0.2 * sin(uTime * (1.0 + 2.0 * in_extra.z) + in_extra.z * 50.0);
    emit(in_pos, in_col * uBright * tw, 0.0);
}
"""


def make_cosmic_web(n=1400000, seed=5, L=10.0, n_nodes=260):
    rng = np.random.default_rng(seed)
    nodes = rng.uniform(-L, L, (n_nodes, 3))
    mass = rng.pareto(1.6, n_nodes) + 1
    mass = np.minimum(mass, 12)
    # 最近邻连边
    d = np.linalg.norm(nodes[:, None] - nodes[None], axis=2)
    np.fill_diagonal(d, 1e9)
    edges = set()
    for i in range(n_nodes):
        nn = np.argsort(d[i])[:4]
        for j in nn[: rng.integers(2, 5)]:
            if d[i, j] < L * 0.75:
                edges.add((min(i, j), max(i, j)))
    edges = np.array(sorted(edges))
    elen = d[edges[:, 0], edges[:, 1]]
    ew = (mass[edges[:, 0]] + mass[edges[:, 1]]) ** 0.6 * elen
    n_fil = int(n * 0.62)
    n_node = int(n * 0.26)
    n_void = n - n_fil - n_node
    # 纤维
    ei = rng.choice(len(edges), n_fil, p=ew / ew.sum())
    s = rng.random(n_fil)
    a, b = nodes[edges[ei, 0]], nodes[edges[ei, 1]]
    base = a + (b - a) * s[:, None]
    # 弯曲
    perp = np.cross(b - a, rng.normal(0, 1, (1, 3)))
    perp /= np.linalg.norm(perp, axis=1, keepdims=True) + 1e-9
    bend = np.sin(np.pi * s)[:, None] * perp * (rng.normal(0, 1, (len(edges), 1))[ei] * 0.28)
    thick = 0.10 + 0.16 * (1 - np.sin(np.pi * s)) ** 2
    fil = base + bend + rng.normal(0, 1, (n_fil, 3)) * thick[:, None] * (rng.random((n_fil, 1)) ** 1.5 * 1.6 + 0.2)
    # 节点（星系团）
    ni = rng.choice(n_nodes, n_node, p=mass / mass.sum())
    rr = (0.12 + 0.07 * mass[ni]) * (rng.random(n_node) ** 2.2)
    dirs = rng.normal(0, 1, (n_node, 3))
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    nod = nodes[ni] + dirs * rr[:, None]
    # 空洞中稀疏粒子
    vo = rng.uniform(-L, L, (n_void, 3))
    pos = np.vstack([fil, nod, vo]).astype(np.float32)
    dens = np.concatenate([0.3 + 0.25 * (1 - np.sin(np.pi * s)) ** 4, 1.0 - np.clip(rr / 0.8, 0, 0.8), np.full(n_void, 0.04)])
    # 初始位置偏移（结构形成前近乎均匀）
    disp = rng.normal(0, 1, pos.shape) * 1.8
    disp += (rng.uniform(-L, L, pos.shape) - pos) * 0.25
    t = np.clip(dens, 0, 1)[:, None]
    c_lo = np.array([[0.22, 0.14, 0.80]])
    c_hi = np.array([[1.0, 0.62, 0.62]])
    col = (c_lo + (c_hi - c_lo) * t ** 2) * (0.03 + 0.13 * t)
    col = np.hstack([col, np.ones((len(pos), 1))])
    ex = np.hstack([disp, rng.random((len(pos), 1))]).astype(np.float32)
    return pos, col.astype(np.float32), ex, nodes, mass, edges


WEB_BODY = r"""
uniform float uForm; uniform float uBright; uniform float uPsize;
void main(){
    float f = clamp(uForm + (in_extra.w - 0.5) * 0.1, 0.0, 1.0);
    f = f * f * (3.0 - 2.0 * f);
    vec3 P = in_pos + in_extra.xyz * (1.0 - f);
    emit(P, in_col * uBright, uPsize);
}
"""

