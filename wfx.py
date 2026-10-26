# -*- coding: utf-8 -*-
"""《曲率引擎》项目通用特效：调色板、转场、2D 星空/星云、恒星光晕、相机射线工具、离屏缓冲、文字与 HUD 小部件。

部分 2D 小部件（bodies / glitch_text / stamp / brackets / ring）源自 projects/three_body/fx.py，
复制过来是为了不依赖别的项目；稳定后可以一起提到 opusvid。

3D 光线步进着色器（飞船、星空、平面）都用同一套相机约定：
    cam_uniforms(cam) 给出 uEye / uCF / uCR / uCU / uTan / uShift，GLSL 里 CAM_GLSL 的 camRay(vUV) 生成射线，
    与 opusvid.gl.Camera.project / mvp 完全一致，所以 2D 标注可以直接用 cam.project 对齐 3D 画面。
"""
import math
import numpy as np
import moderngl
from opusvid.gl import ease_in_out, ease_out_expo, lin, W, H
from opusvid.scene import DARKSPOT_FS

MONO = r"C:\Windows\Fonts\CascadiaMono.ttf"     # 等宽字体（HUD 的数字和英文读数）

# ------------------------------------------------------------------ 调色板
# 颜色语言：CYAN 曲率/前方收缩（蓝移），RED 后方膨胀（红移），VIOLET 负能量，GOLD 光与 HUD，IRIS 肥皂膜
CYAN = (0.25, 0.85, 1.0)
BLUE = (0.30, 0.50, 1.0)
RED = (1.0, 0.30, 0.22)
MAGENTA = (1.0, 0.25, 0.75)
VIOLET = (0.62, 0.38, 1.0)
GOLD = (1.0, 0.78, 0.42)
AMBER = (1.0, 0.6, 0.22)
WHITE = (1.0, 1.0, 1.0)
DIM = (0.72, 0.78, 0.9)
ICE = (0.6, 0.85, 1.0)


# ------------------------------------------------------------------ GLSL 片段
CAM_GLSL = r"""
uniform vec3 uEye; uniform vec3 uCF; uniform vec3 uCR; uniform vec3 uCU; uniform float uTan; uniform vec2 uShift;
// 与 opusvid.gl.Camera 一致的透视射线（vUV 左下原点）
vec3 camRay(vec2 uv){
    vec2 ndc = uv * 2.0 - 1.0 - uShift;
    return normalize(uCF + ndc.x * uTan * (uRes.x / uRes.y) * uCR + ndc.y * uTan * uCU);
}
"""

# 方向星空：方向投到立方体六个面上，每个面用固定角度网格撒星。星点按屏幕像素大小绘制，FOV 变化时不会糊。
DIRSTARS_GLSL = r"""
uniform float uPixAng;   // 一个屏幕像素对应的弧度
uniform float uFine;     // 最暗一层小星星的权重：拖影时调低，否则密集的拖线会糊成一片灰雾
vec3 starCellLayer(vec3 d, float cell, float seed, float density, float bright){
    vec3 a = abs(d);
    vec2 uv; float face; float m;
    if (a.x >= a.y && a.x >= a.z){ uv = d.yz / a.x; face = d.x > 0.0 ? 0.0 : 1.0; m = a.x; }
    else if (a.y >= a.z){ uv = d.xz / a.y; face = d.y > 0.0 ? 2.0 : 3.0; m = a.y; }
    else { uv = d.xy / a.z; face = d.z > 0.0 ? 4.0 : 5.0; m = a.z; }
    vec2 g = uv / cell; vec2 id = floor(g); vec2 f = fract(g);
    // 面坐标 -> 屏幕像素：uv = tanφ，dθ ≈ duv·cos²φ = duv·m²
    float pxPerG = cell * m * m / uPixAng;
    vec3 col = vec3(0);
    for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++){
        vec2 o = vec2(x, y); vec2 cid = id + o + face * 1000.0;
        float h = hash12(cid + seed * 17.13);
        if (h > density) continue;
        vec2 pos = hash22(cid + seed * 3.7);
        vec2 dd = (o + pos - f) * pxPerG;
        float r2 = dot(dd, dd);
        float mg = hash12(cid * 1.37 + seed);
        float mag = pow(mg, 8.0);
        float b = bright * (0.3 + 6.0 * mag);
        float core = exp(-r2 / 1.2);
        float halo = exp(-sqrt(r2) / (1.5 + 3.0 * mag)) * 0.03 * mag;
        col += starColor(hash12(cid + 9.1)) * b * (core + halo);
    }
    return col;
}
vec3 dirStars(vec3 d, float amt){
    vec3 c = vec3(0);
    c += starCellLayer(d, 0.010, 1.0, 0.16, 0.28) * uFine;
    c += starCellLayer(d, 0.026, 2.0, 0.28, 0.55);
    c += starCellLayer(d, 0.070, 3.0, 0.40, 1.3);
    return c * amt;
}
// 银河：一条窄的发光带 + 暗尘带 + 零星的发射星云结；带外只有很淡的弥散光（方向上的 3D 噪声，无接缝）
vec3 dirNebula(vec3 d, vec3 gal, vec3 c1, vec3 c2, float amt){
    float lat = dot(d, gal);
    float band = exp(-lat * lat / (0.16 * 0.16));
    float wide = exp(-lat * lat / (0.5 * 0.5));
    vec3 q = d * 3.0;
    float n = fbm3(q + fbm3(q * 2.0 + 3.1, 4) * 0.8, 6);
    float fine = fbm3(q * 7.0 + 1.3, 5);
    float dust = smoothstep(0.45, 0.72, fbm3(q * 4.5 + vec3(5.0, 1.0, 2.0) + fine * 0.6, 5)) * band;
    float glow = band * (0.25 + 0.75 * smoothstep(0.3, 0.8, n)) * (0.5 + 0.8 * fine);
    vec3 col = mix(c1, c2, smoothstep(0.35, 0.7, fbm3(q * 1.5 + 9.0, 4))) * (glow * 0.55 + wide * 0.05 * n);
    col += mix(c2, vec3(1.0, 0.75, 0.55), 0.3) * pow(smoothstep(0.6, 0.85, n * fine * 1.45), 2.0) * band * 0.9;
    col *= 1.0 - dust * 0.85;
    return col * amt;
}
"""


def cam_uniforms(cam):
    """把 opusvid.gl.Camera 转成光线步进着色器用的 uniform。"""
    eye = np.asarray(cam.eye, np.float64)
    f = np.asarray(cam.target, np.float64) - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, np.asarray(cam.up, np.float64))
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    tan = math.tan(math.radians(cam.fov) / 2)
    return dict(uEye=tuple(eye), uCF=tuple(f), uCR=tuple(r), uCU=tuple(u), uTan=tan,
                uShift=tuple(float(s) for s in cam.shift), uPixAng=2 * tan / H)


# ------------------------------------------------------------------ 离屏缓冲
def offscreen(e, k=0):
    """项目自用的 HDR 离屏缓冲（与场景缓冲同尺寸），第一次用时创建并缓存在引擎上。"""
    if not hasattr(e, "_wd_off"):
        e._wd_off = {}
    if k not in e._wd_off:
        tex = e.ctx.texture((W, H), 4, dtype="f2")
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        tex.repeat_x = tex.repeat_y = False
        e._wd_off[k] = (tex, e.ctx.framebuffer([tex]))
    return e._wd_off[k]


class Offscreen:
    """with Offscreen(e, k) as tex: ... 在块内把绘制改到离屏缓冲，退出时切回原来的缓冲。
    块内的 2D 绘制列表（文字/线）会在退出前 flush 到离屏缓冲。"""

    def __init__(self, e, k=0, clear=True):
        self.e, self.k, self.clear = e, k, clear

    def __enter__(self):
        e = self.e
        e.flush()                          # 之前排队的 2D 图元属于原缓冲
        self.prev = e.ctx.fbo
        tex, fbo = offscreen(e, self.k)
        fbo.use()
        e.ctx.viewport = (0, 0, W, H)
        if self.clear:
            fbo.clear(0, 0, 0, 1)
        return tex

    def __exit__(self, *a):
        self.e.flush()
        self.prev.use()
        self.e.ctx.viewport = (0, 0, W, H)


COPY_FS = r"""
uniform sampler2D uSrc; uniform float uAmt; uniform vec3 uTint;
in vec2 vUV; out vec4 fragColor;
void main(){ fragColor = vec4(texture(uSrc, vUV).rgb * uTint * uAmt, 1.0); }
"""


def blit(e, tex, amt=1.0, blend="add", tint=(1.0, 1.0, 1.0)):
    """把离屏缓冲画到当前缓冲（tint 逐通道染色，例如飞船残影的青色）。"""
    e.draw_fs("wd_copy", COPY_FS, dict(uAmt=amt, uTint=tuple(tint)), dict(uSrc=tex), blend=blend)


# ------------------------------------------------------------------ 转场
TRANSITION_WD = r"""
uniform sampler2D uA;
uniform sampler2D uB;
uniform float uP;
uniform int uKind;     // 0 曲率冲刺 1 泡泡透镜 2 黑场 3 白闪穿越 4 信号故障 5 虹彩溶解 6 青溶解
uniform float uSeed;
in vec2 vUV; out vec4 fragColor;
vec3 sampleIn(sampler2D tex, vec2 uv){
    vec2 m = smoothstep(vec2(-0.002), vec2(0.01), uv) * smoothstep(vec2(-0.002), vec2(0.01), 1.0 - uv);
    return texture(tex, clamp(uv, 0.0, 1.0)).rgb * m.x * m.y;
}
vec3 zoomBlur(sampler2D tex, vec2 uv, float amt){
    vec2 c = uv - 0.5; vec3 acc = vec3(0); float wsum = 0.0;
    for (int i = 0; i < 28; i++){
        float k = float(i) / 27.0;
        float w = 1.0 - k * 0.6;
        acc += sampleIn(tex, 0.5 + c * (1.0 - amt * k)) * w; wsum += w;
    }
    return acc / wsum;
}
vec3 iris(float x){ return 0.5 + 0.5 * cos(TAU * (x + vec3(0.0, 0.33, 0.67))); }
void main(){
    vec2 uv = vUV; vec2 c = uv - 0.5;
    vec2 asp = vec2(uRes.x / uRes.y, 1.0);
    float p = uP;
    vec3 col;
    if (uKind == 0){
        // 曲率冲刺：A 被拉向中心（前方压缩、色散），B 从中心冲出
        float a = smoothstep(0.0, 0.5, p), b = smoothstep(0.5, 1.0, p);
        vec3 A, B;
        for (int k = 0; k < 3; k++){
            float ck = 1.0 + float(k - 1) * 0.06 * sin(p * PI);
            A[k] = zoomBlur(uA, 0.5 + c * (1.0 - a * 0.5) * ck, a * 0.45)[k];
            B[k] = zoomBlur(uB, 0.5 + c * (1.0 - (1.0 - b) * 0.6) * ck, (1.0 - b) * 0.45)[k];
        }
        float m = smoothstep(0.4, 0.6, p);
        float fl = exp(-pow((p - 0.5) / 0.09, 2.0));
        float r = length(c * asp);
        col = mix(A * (1.0 + a), B * (0.4 + 0.6 * b), m) + vec3(0.55, 0.85, 1.0) * fl * exp(-r * 2.5) * 1.6;
    } else if (uKind == 1){
        // 泡泡透镜：画面被一个膨胀的球形透镜吞没
        float s = sin(p * PI);
        float R = mix(0.02, 1.25, smoothstep(0.0, 1.0, p));
        vec2 q = c * asp;
        float r = length(q);
        float inside = smoothstep(R + 0.01, R - 0.01, r);
        float wall = exp(-pow((r - R) / 0.035, 2.0)) * s;
        vec2 dir = q / max(r, 1e-4);
        vec2 off = dir * wall * 0.06;
        vec3 A, B;
        for (int k = 0; k < 3; k++){
            float ck = float(k - 1) * 0.012 * s;
            A[k] = sampleIn(uA, uv - off / asp * (1.0 + ck * 8.0))[k];
            B[k] = sampleIn(uB, 0.5 + (q * (0.7 + 0.3 * smoothstep(0.0, R + 0.001, r)) / asp) + off / asp * (1.0 + ck * 8.0))[k];
        }
        col = mix(A, B, inside) + mix(vec3(1.0, 0.3, 0.25), vec3(0.3, 0.8, 1.0), 0.5 + 0.5 * dir.x) * wall * 0.8;
    } else if (uKind == 3){
        float a = smoothstep(0.0, 0.5, p), b = smoothstep(0.5, 1.0, p);
        vec3 A = zoomBlur(uA, 0.5 + c * (1.0 - a * 0.25), a * 0.3);
        vec3 B = zoomBlur(uB, 0.5 + c * (1.0 - (1.0 - b) * 0.2), (1.0 - b) * 0.25);
        float m = smoothstep(0.42, 0.58, p);
        float fl = exp(-pow((p - 0.5) / 0.11, 2.0));
        col = mix(A * (1.0 + a * 0.8), B, m) + vec3(0.9, 0.95, 1.0) * fl * 1.1;
    } else if (uKind == 4){
        float s = sin(p * PI);
        float rows = 14.0 + 30.0 * hash11(floor(p * 14.0) + uSeed);
        float sl = floor(uv.y * rows);
        float h = hash12(vec2(sl, floor(p * 22.0) + uSeed));
        float off = (h - 0.5) * 0.22 * s * step(0.35, h);
        float pick = step(hash12(vec2(sl * 1.7, uSeed)), smoothstep(0.2, 0.8, p));
        for (int k = 0; k < 3; k++){
            vec2 u2 = vec2(uv.x + off + float(k - 1) * 0.012 * s, uv.y);
            col[k] = mix(sampleIn(uA, u2), sampleIn(uB, u2), pick)[k];
        }
        col += vec3(0.2, 0.7, 1.0) * step(0.95, h) * s * 0.5;
    } else if (uKind == 5 || uKind == 6){
        float n = fbm2(uv * asp * 3.0 + uSeed, 5);
        float th = p * 1.25 - 0.1;
        float m = smoothstep(th - 0.06, th + 0.06, n);
        vec3 A = texture(uA, uv).rgb, B = texture(uB, uv).rgb;
        float edge = exp(-pow((n - th) / 0.014, 2.0)) * sin(p * PI);
        vec3 ec = uKind == 5 ? iris(n * 3.0 + p) : vec3(0.25, 0.8, 1.0);
        col = mix(B, A, m) + ec * edge * 0.8;
    } else {
        float k = 1.0 - sin(p * PI);
        col = (p < 0.5 ? texture(uA, uv).rgb : texture(uB, uv).rgb) * k * k;
    }
    fragColor = vec4(col, 1.0);
}
"""


def install(eng):
    """用本项目的转场替换引擎默认转场（make.py 里通过 cli(setup=...) 调用）。"""
    def transition(texA, texB, dst_fbo, p, kind=0, seed=0.0):
        dst_fbo.use()
        eng.draw_fs("transition_wd", TRANSITION_WD, dict(uP=p, uKind=kind, uSeed=seed), dict(uA=texA, uB=texB))
    eng.transition = transition


# ------------------------------------------------------------------ 2D 背景星空 + 星云
SPACE_FS = r"""
uniform vec3 uC1; uniform vec3 uC2; uniform vec3 uC3;
uniform float uNeb; uniform float uStars; uniform vec2 uOff; uniform float uZoom; uniform float uRot; uniform float uSeed;
in vec2 vUV; out vec4 fragColor;
void main(){
    vec2 px = (vUV * uRes - uRes * 0.5);
    px = rot2(uRot) * px;
    vec2 p = px / uZoom + uOff;
    vec3 col = vec3(0);
    if (uNeb > 0.0){
        vec2 q = p / uRes.y * 1.8;
        vec2 w = vec2(fbm2(q * 1.2 + uSeed, 5), fbm2(q * 1.2 + vec2(5.2, 1.3) + uSeed, 5));
        float n = fbm2(q * 1.5 + w * 2.4 + uTime * 0.008, 6);
        float n2 = fbm2(q * 3.0 - w * 1.4 + 7.0 + uSeed, 5);
        float haze = pow(n, 2.4) * 0.35;
        float wisp = pow(smoothstep(0.5, 1.0, n), 2.0);
        col = mix(uC1, uC2, smoothstep(0.3, 0.85, n2)) * (haze + wisp);
        col += uC3 * pow(smoothstep(0.6, 1.0, n * n2 * 1.6), 2.5) * 0.7;
        float dust = smoothstep(0.5, 0.8, fbm2(q * 4.0 + w * 3.0 + 3.3, 5));
        col *= (1.0 - dust * 0.4) * uNeb;
    }
    col += starfield2d(px / uZoom + uOff * 0.5 + uRes * 0.5, uTime, uStars);
    fragColor = vec4(col, 1.0);
}
"""


def space(e, neb=0.4, stars=1.0, c1=(0.05, 0.12, 0.35), c2=(0.35, 0.08, 0.32), c3=(1.0, 0.6, 0.4), off=(0.0, 0.0),
          zoom=1.0, rot=0.0, seed=3.0):
    e.draw_fs("space_wd", SPACE_FS, dict(uC1=c1, uC2=c2, uC3=c3, uNeb=neb, uStars=stars, uOff=off, uZoom=zoom,
                                         uRot=rot, uSeed=seed), blend="add")


# ------------------------------------------------------------------ 恒星 / 天体光晕（屏幕空间）
BODIES_FS = r"""
uniform vec4 uB[12];    // x, y(像素，左上原点), 半径, 亮度
uniform vec4 uBC[12];   // rgb, 横向星芒强度
uniform int uN;
in vec2 vUV; out vec4 fragColor;
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    vec3 col = vec3(0);
    for (int i = 0; i < uN; i++){
        float I = uB[i].w;
        if (I <= 0.0) continue;
        vec2 d = P - uB[i].xy;
        float r = length(d);
        float R = max(uB[i].z, 0.6);
        vec3 c = uBC[i].rgb;
        vec3 hot = mix(c, vec3(1.0, 0.97, 0.93), 0.7);
        float disk = 1.0 - smoothstep(R * 0.85, R * 1.08, r);
        float core = exp(-r * r / (R * R * 0.35)) * 3.0;
        float halo = exp(-r / (R * 1.4 + 2.5)) * 0.7 + exp(-r / (R * 4.0 + 12.0)) * 0.05 + exp(-r / (R * 14.0 + 50.0)) * 0.004;
        float streak = exp(-abs(d.y) / (1.0 + R * 0.05)) * exp(-abs(d.x) / (R * 12.0 + 50.0)) * uBC[i].w;
        float ang = atan(d.y, d.x);
        float rays = pow(abs(cos(ang * 2.0 + 0.3)), 80.0) * exp(-r / (R * 3.5 + 14.0)) * uBC[i].w;
        col += (hot * (disk * 2.5 + core) + c * (halo + streak * 0.45 + rays * 0.35)) * I;
    }
    fragColor = vec4(col, 1.0);
}
"""


def bodies(e, items, blend="add"):
    """items: [(x, y, 半径px, 亮度, (r,g,b), 星芒)]，最多 12 个。"""
    items = [it for it in items if it is not None and it[3] > 0.0005]
    if not items:
        return
    B = np.zeros((12, 4), np.float32)
    C = np.zeros((12, 4), np.float32)
    for i, (x, y, r, I, c, s) in enumerate(items[:12]):
        B[i] = (x, y, r, I)
        C[i] = (c[0], c[1], c[2], s)
    e.draw_fs("bodies_wd", BODIES_FS, dict(uB=B.ravel(), uBC=C.ravel(), uN=len(items[:12])), blend=blend)


FLAT_FS = r"""
uniform vec3 uCol; in vec2 vUV; out vec4 fragColor;
void main(){ fragColor = vec4(uCol, 1.0); }
"""


def flat(e, color, amt, blend="add"):
    """整屏叠加一层纯色（闪白/闪蓝）；blend="mul" 时用于整体压暗。"""
    if amt > 0.001:
        e.draw_fs("flat_wd", FLAT_FS, dict(uCol=tuple(c * amt for c in color)), blend=blend)


def darkspot(e, x, y, w, h, amt):
    if amt > 0.001:
        e.draw_fs("darkspot", DARKSPOT_FS, dict(uCenter=(x, y), uSize=(w, h), uAmt=amt), blend="darken")


# ------------------------------------------------------------------ 文字与 HUD
def glitch_text(e, s, x, y, size, font, color, alpha, t, seed=0.0, amt=1.0, anchor="mm", tracking=0.08, scale=1.0,
                intensity=1.6, c1=(1.0, 0.15, 0.3), c2=(0.1, 0.75, 1.0)):
    """RGB 分离 + 随机横向抖动的故障字。amt 0..1 控制故障强度。"""
    if alpha <= 0.002:
        return
    k = math.floor(t * 24)
    rnd = np.random.default_rng(int(k * 7919 + seed * 104729) % (2 ** 31))
    j = rnd.random(len(s))

    def fx(i, n):
        return dict(dx=(j[i] - 0.5) * size * 0.35 * amt if j[i] > 0.7 else 0.0)

    off = size * 0.045 * amt
    sep = alpha * min(1, amt * 2 + 0.2)
    e.text(s, x - off, y, size, font, c1, sep * 0.8, anchor, tracking, intensity, scale=scale, char_fx=fx)
    e.text(s, x + off, y, size, font, c2, sep * 0.7, anchor, tracking, intensity, scale=scale, char_fx=fx)
    e.text(s, x, y, size, font, color, alpha, anchor, tracking, intensity, scale=scale, char_fx=fx)


def stamp(t, t0, dur=0.45, over=1.35):
    """砸下来的缩放：从 over 倍迅速落到 1。"""
    x = lin(t0, t0 + dur, t)
    return 1 + (over - 1) * (1 - ease_out_expo(x))


def brackets(e, x, y, w, h, a, color=WHITE, L=26, width=1.4, intensity=1.3):
    """四角取景框（左上角 x,y，宽高 w,h）。"""
    if a <= 0.001:
        return
    for sx, sy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        cx, cy = x + w * sx, y + h * sy
        dx = L if sx == 0 else -L
        dy = L if sy == 0 else -L
        e.line([(cx + dx, cy), (cx, cy), (cx, cy + dy)], width, color, a, intensity=intensity)


# ---------------------------------------------------------------------- 仪表笔触（精密仪器的样子，不是霓虹灯管）
# 粗线 + 高亮度 + glow 会被泛光（阈值 1.0、软膝 0.5）晕成一根根灯管：速度表、时钟、圆环、曲线都出过这个问题
#（用户："这看起来都太丑了"）。仪表一律用细而清楚的芯线，亮度压在泛光阈值附近以下，最多加一层很淡的柔光。
LINE_K_MAX = 1.0           # 芯线亮度上限（乘到颜色上）
LINE_W_MAX = 2.2           # 芯线宽度上限（像素）


def glowline(e, pts, color, a, width=1.4, k=0.95, halo=0.0, **kw):
    """仪表用的线：清楚的芯线（宽度、亮度都有上限）+ 可选的一层很淡的柔光（halo 0..0.4）。"""
    if a <= 0.002:
        return
    w = min(width, LINE_W_MAX)
    e.line(pts, w, color, a, glow=min(halo, 0.4), glow_w=w * 6 + 6, intensity=min(k, LINE_K_MAX), **kw)


def ring(e, cx, cy, r, a, color, width=1.6, glow=0.6, n=180, intensity=1.5, arc=None, squash=1.0, rot=0.0):
    """圆环/弧（squash 压扁成椭圆，rot 旋转）。按仪表笔触画：width、intensity 会被压到 LINE_W_MAX、LINE_K_MAX 以内，
    glow 换成很淡的一层柔光（以前是粗发光线，泛光一晕成了灯管）。"""
    if a <= 0.002 or r <= 1:
        return
    th = np.linspace(0, 2 * math.pi, n) if arc is None else np.linspace(arc[0], arc[1], n)
    x, y = r * np.cos(th), r * np.sin(th) * squash
    c, s = math.cos(rot), math.sin(rot)
    glowline(e, np.stack([cx + x * c - y * s, cy + x * s + y * c], 1), color, a, width=width, k=intensity,
             halo=0.3 * glow)


def needle(e, x0, y0, x1, y1, color, a, width=4.0, pivot=9.0):
    """仪表指针：从轴心到针尖渐细、由暗到亮的一根针（streaks），轴心是一个细圆圈加一个小点。"""
    if a <= 0.002:
        return
    L = math.hypot(x1 - x0, y1 - y0) + 1e-6
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    # 针身从轴心背后一小段（配重）开始，针尖最亮
    streaks(e, [dict(tail=(x0 - ux * pivot * 1.8, y0 - uy * pivot * 1.8), head=(x1, y1), color=color, a=1.2 * a,
                     width=width, taper=0.55)])
    ring(e, x0, y0, pivot, a, color, 1.3, 0.0, 48, 1.0)
    e.circle(x0, y0, 2.5, fill=WHITE, fill_a=a, intensity=1.0)


def clock_face(e, cx, cy, R, ang, a, color, sweep0=None):
    """时钟：一圈细表圈 + 内圈 60 根细刻度（每 5 根一根长的）+ 一根渐细的指针。
    ang 为指针角度（弧度，0 = 12 点方向，顺时针）；sweep0 给出起点角度时，从起点扫到指针的那段弧上铺一层淡淡的扇形光，
    表示"走过的时间"。"""
    if a <= 0.002:
        return
    ring(e, cx, cy, R, 0.8 * a, color, 1.3, 0.0, 160, 0.95)
    ring(e, cx, cy, R - 5, 0.25 * a, color, 1.0, 0.0, 160, 0.8)
    for i in range(60):
        th = i * math.tau / 60 - math.pi / 2
        major = i % 5 == 0
        r0 = R - (20 if major else 12)
        glowline(e, [(cx + r0 * math.cos(th), cy + r0 * math.sin(th)), (cx + (R - 9) * math.cos(th), cy + (R - 9) * math.sin(th))],
                 WHITE, a * (0.85 if major else 0.3), width=1.3 if major else 1.0, k=0.9)
    th = ang - math.pi / 2
    if sweep0 is not None and ang - sweep0 > 1e-3:
        # 走过的那段：在刻度内侧铺一道细弧，越靠近指针越亮
        n = 48
        ths = np.linspace(sweep0, ang, n) - math.pi / 2
        for i in range(n - 1):
            f = (i + 1) / (n - 1)
            glowline(e, [(cx + (R - 26) * math.cos(ths[i]), cy + (R - 26) * math.sin(ths[i])),
                         (cx + (R - 26) * math.cos(ths[i + 1]), cy + (R - 26) * math.sin(ths[i + 1]))],
                     color, a * 0.7 * f ** 1.5, width=2.0, k=0.95)
    needle(e, cx, cy, cx + (R - 24) * math.cos(th), cy + (R - 24) * math.sin(th), color, a, width=3.5, pivot=6.0)


ARROW_FS = r"""
uniform vec2 uA; uniform vec2 uB;          // 箭尾、箭尖（像素，左上原点）
uniform float uW; uniform float uHead;     // 箭杆半宽、箭头长度（像素）
uniform vec3 uCol; uniform float uAmt; uniform float uGlow;
in vec2 vUV; out vec4 fragColor;
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    vec2 ab = uB - uA; float L = length(ab);
    if (L < 1.0){ fragColor = vec4(0); return; }
    vec2 dir = ab / L, nrm = vec2(-dir.y, dir.x);
    vec2 q = P - uA;
    float u = dot(q, dir), v = dot(q, nrm);
    float hl = min(uHead, L * 0.6), hw = uHead * 0.55;
    // 箭杆：从箭尾的细线渐渐变粗，到箭头根部为全宽
    float s = clamp(u / max(L - hl, 1.0), 0.0, 1.0);
    float w = uW * mix(0.35, 1.0, s);
    float dShaft = max(abs(v) - w, max(-u, u - (L - hl)));
    // 箭头：实心等腰三角形
    float hu = u - (L - hl);
    float dHead = max(-hu, abs(v) - hw * (1.0 - hu / hl));
    dHead = max(dHead, hu - hl);
    float d = min(dShaft, dHead * 0.9);
    float body = 1.0 - smoothstep(-0.8, 0.8, d);
    float glow = exp(-max(d, 0.0) / (uW * 2.5 + 3.0)) * uGlow;
    float fade = mix(0.25, 1.0, clamp(u / L, 0.0, 1.0));               // 箭尾暗、箭头亮
    float core = exp(-abs(v) / max(w * 0.6, 0.8)) * step(u, L - hl) * step(0.0, u) * 0.6;
    vec3 col = uCol * (body * (0.9 + core) * fade * 1.4 + glow * fade * 0.35) + vec3(1.0) * core * body * fade * 0.35;
    fragColor = vec4(col * uAmt, 1.0);
}
"""


def arrow(e, x0, y0, x1, y1, color, a, width=2.0, head=14.0, glow=0.5, intensity=1.6, progress=1.0):
    """矢量箭头（全屏着色器画的 SDF）：箭杆从箭尾渐粗、由暗到亮，箭头是实心三角，外加柔和光晕。
    width 为箭杆宽度（像素），head 为箭头长度（像素），progress 控制画出的比例。立即绘制（加法混合）。"""
    if a <= 0.002 or progress <= 0.0:
        return
    x1p, y1p = x0 + (x1 - x0) * progress, y0 + (y1 - y0) * progress
    e.draw_fs("wd_arrow", ARROW_FS, dict(uA=(float(x0), float(y0)), uB=(float(x1p), float(y1p)), uW=float(width * 0.5 + 0.6),
                                        uHead=float(head * 1.6 + 6.0), uCol=tuple(c * intensity * 0.6 for c in color),
                                        uAmt=float(a), uGlow=float(glow)), blend="add")


# ---------------------------------------------------------------------- 光迹（取代"粗线 + 光晕"的长方形光条）
# 以前的光迹、光束、彗尾都是 e.line(宽度不变, glow=...)：整条一样粗、一样亮，泛光一晕就成了两头齐平的霓虹灯管
#（用户："这个长方形光线资产被大量使用，而且非常丑"）。这里改成真正的光迹：
#   · 从尾到头渐粗（尾部收成一根细丝），亮度从尾部的 0 渐亮到头部；
#   · 横截面是窄而亮的芯 + 很淡的一层柔光，没有硬边；
#   · 头部可以带一个小而锐的光点（不再另画一个大光球）；
#   · wisp > 0 时是"航迹"：越老的一段越散、越淡，被扰动撕成一缕缕，并轻轻蜿蜒。
STREAK_N = 32
STREAK_FS = r"""
uniform vec4 uSeg[32];      // 尾 x,y、头 x,y（像素，左上原点）
uniform vec4 uPar[32];      // 头部宽度（像素）、尾部宽度比例、亮度、wisp
uniform vec4 uCol[32];      // 颜色、头部光点亮度
uniform int uN;
in vec2 vUV; out vec4 fragColor;
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    vec3 acc = vec3(0.0);
    for (int i = 0; i < 32; i++){
        if (i >= uN) break;
        vec2 a = uSeg[i].xy, b = uSeg[i].zw;
        vec2 ab = b - a;
        float L = length(ab);
        if (L < 0.5) continue;
        vec2 dir = ab / L, nrm = vec2(-dir.y, dir.x);
        vec2 q = P - a;
        float s = dot(q, dir), off = dot(q, nrm);
        float w = uPar[i].x, wisp = uPar[i].w;
        // 头部的小光点：锐利的芯 + 一点点柔光（按到头部的距离单独算，不受下面光迹范围的裁剪）
        float dh = length(P - b);
        if (uCol[i].w > 0.0 && dh < 10.0 * (2.5 * w + 4.0))
            acc += mix(uCol[i].rgb, vec3(1.0), 0.6) * uPar[i].z * uCol[i].w
                 * (exp(-0.5 * pow(dh / (0.7 * w + 0.6), 2.0)) + 0.15 * exp(-dh / (2.5 * w + 4.0)));
        // 光迹本身的范围：要把柔光层整个包进去，否则在裁剪处留下一圈方框
        float reach = 4.0 * (2.2 * w * (1.0 + 3.0 * wisp) + 1.5) + wisp * 20.0;
        if (s < -reach || s > L + reach || abs(off) > reach) continue;
        float h = clamp(s / L, 0.0, 1.0);                       // 0 = 尾，1 = 头
        float age = 1.0 - h;
        // 航迹：老的一段轻轻蜿蜒、变宽变散
        off += wisp * age * 14.0 * (vnoise2(vec2(s * 0.006, float(i) * 7.1)) - 0.5) * 2.0;
        float wd = w * mix(uPar[i].y, 1.0, h) * (1.0 + wisp * 3.0 * age);
        float core = exp(-0.5 * pow(off / (0.42 * wd), 2.0));
        float halo = exp(-0.5 * pow(off / (2.2 * wd + 1.5), 2.0)) * 0.12;
        // 亮度沿长度：尾部从 0 渐亮；越散的地方单位面积越暗（能量守恒，不会胀成一大片）
        float along = pow(h, 1.6) / (1.0 + wisp * 3.0 * age);
        // 航迹被扰动撕成一缕缕
        along *= mix(1.0, 0.25 + 1.5 * fbm2(vec2(s * 0.02, off / (wd + 1.0) * 0.8 + float(i) * 3.3), 4), wisp);
        // 两端：头部是圆的、尾部收尖
        float ends = smoothstep(0.0, 0.04, h) * (s > L ? exp(-0.5 * pow((s - L) / (0.5 * w + 0.5), 2.0)) : 1.0);
        acc += uCol[i].rgb * uPar[i].z * (core + halo) * along * ends;
    }
    fragColor = vec4(acc, 1.0);
}
"""


def streaks(e, items):
    """批量画光迹（全屏着色器，立即绘制，加法混合）。items 里每条是一个 dict：
      tail, head   尾、头的像素坐标（左上原点）
      color, a     颜色、整体亮度（直接乘到颜色上；1.5 左右是"明亮但不糊"）
      width        头部宽度（像素），默认 3
      taper        尾部宽度占头部的比例，默认 0.15（尾部收成细丝）；1 = 不收
      spark        头部小光点的亮度，默认 0（不画）
      wisp         0..1，航迹模式：老的一段蜿蜒、变散、被撕成一缕缕，默认 0
    超过 STREAK_N 条时分批画。"""
    rows = [it for it in items if it.get("a", 1.0) > 0.003]
    for k in range(0, len(rows), STREAK_N):
        batch = rows[k:k + STREAK_N]
        seg, par, col = [], [], []
        for it in batch:
            (x0, y0), (x1, y1) = it["tail"], it["head"]
            seg.append((x0, y0, x1, y1))
            par.append((it.get("width", 3.0), it.get("taper", 0.15), it.get("a", 1.0), it.get("wisp", 0.0)))
            col.append(tuple(it["color"]) + (it.get("spark", 0.0),))
        n = len(batch)
        while len(seg) < STREAK_N:
            seg.append((0.0, 0.0, 0.0, 0.0)); par.append((0.0, 1.0, 0.0, 0.0)); col.append((0.0, 0.0, 0.0, 0.0))
        e.draw_fs("wd_streak", STREAK_FS, dict(uSeg=np.array(seg, np.float32).ravel(), uPar=np.array(par, np.float32).ravel(),
                                              uCol=np.array(col, np.float32).ravel(), uN=n), blend="add")


def year_tag(e, t, start, year, name, en, x=150, y=250, out=None, color=GOLD):
    """年份 + 人物 的标签组。"""
    e.text(year, x, y, 104, "latin_b", color, 1.0, "lm", 0.04, 1.7, t=t, start=start, dur=0.6, stagger=0.07,
           kind="drop", out=out, out_dur=0.6)
    e.text(name, x + 4, y + 84, 34, "sans_m", WHITE, 0.95, "lm", 0.1, 1.15, t=t, start=start + 0.2, dur=0.5,
           stagger=0.04, out=out)
    e.text(en, x + 6, y + 126, 19, "latin", DIM, 0.85, "lm", 0.4, 1.0, t=t, start=start + 0.4, dur=0.6,
           stagger=0.02, kind="spread", out=out)


def hud_text(e, t, start, s, x, y, size=20, color=CYAN, alpha=1.0, anchor="lm", out=None, font="latin_m"):
    """HUD 读数：逐字打出（type），出场淡出。"""
    a = alpha
    if out is not None:
        a *= 1 - ease_in_out(lin(out, out + 0.4, t))
    e.text(s, x, y, size, font, color, a, anchor, 0.12, 1.4, t=t, start=start, dur=0.05, stagger=0.025, kind="type")


def pulse(t, t0, tau=0.35):
    """t0 时刻的一次指数衰减脉冲（t0 之前为 0）。"""
    return math.exp(-(t - t0) / tau) if t >= t0 else 0.0


def vis(t, t0, t1, fin=0.4, fout=0.4):
    """t0 处淡入、t1 前淡出的可见度（清晰文字层不参与转场，段落结束前要用它淡出）。"""
    return lin(t0, t0 + fin, t) * (1 - lin(t1 - fout, t1, t))


def mix3(a, b, m):
    return tuple(x + (y - x) * m for x, y in zip(a, b))


def lerp(a, b, m):
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    return a + (b - a) * m


# ------------------------------------------------------------------ 后期：去灰雾
# 引擎默认泛光的阈值很低（0.35），满屏星点和星云都会被模糊成一层灰纱，黑位被抬到 20/255 左右，画面"白蒙蒙"。
# 本项目换成：高阈值泛光（只有曲率环、闪光、亮星核心发光）+ 收窄的光晕 + 压黑位的色调曲线。
# 实测同一镜头的 10% 分位亮度从 20 降到 3 左右。稳定后可以提到引擎里，给其他片子用。
from opusvid.gl import BLOOM_UP, COMPOSITE as _ENGINE_COMPOSITE  # noqa: E402

BLOOM_DOWN_WD = r"""
uniform sampler2D uSrc;
uniform vec2 uTexel;
uniform int uFirst;
uniform float uThresh; uniform float uKnee;
in vec2 vUV; out vec4 fragColor;
// 某个着色器偶尔在单个像素算出 NaN/Inf（例如浮点误差下负数的非整数次方）：这里当作 0，
// 否则它会被一级级降采样、再升采样扩成画面上的黑色方块
vec3 S(vec2 o){ vec3 c = texture(uSrc, vUV + o * uTexel).rgb; return all(lessThan(abs(c), vec3(6.0e4))) ? c : vec3(0.0); }
float KW(vec3 c){ return 1.0 / (1.0 + luma(c) * 1.5); }
void main(){
    vec3 a = S(vec2(-2,2)), b = S(vec2(0,2)), c = S(vec2(2,2));
    vec3 d = S(vec2(-2,0)), e = S(vec2(0,0)), f = S(vec2(2,0));
    vec3 g = S(vec2(-2,-2)), h = S(vec2(0,-2)), i = S(vec2(2,-2));
    vec3 j = S(vec2(-1,1)), k = S(vec2(1,1)), l = S(vec2(-1,-1)), m = S(vec2(1,-1));
    vec3 col = e*0.125 + (a+c+g+i)*0.03125 + (b+d+f+h)*0.0625 + (j+k+l+m)*0.125;
    if (uFirst == 1){
        vec3 g0 = (a + b + d + e) * 0.25, g1 = (b + c + e + f) * 0.25, g2 = (d + e + g + h) * 0.25, g3 = (e + f + h + i) * 0.25;
        vec3 g4 = (j + k + l + m) * 0.25;
        float w0 = KW(g0), w1 = KW(g1), w2 = KW(g2), w3 = KW(g3), w4 = KW(g4);
        col = (g0 * w0 * 0.125 + g1 * w1 * 0.125 + g2 * w2 * 0.125 + g3 * w3 * 0.125 + g4 * w4 * 0.5)
            / (w0 * 0.125 + w1 * 0.125 + w2 * 0.125 + w3 * 0.125 + w4 * 0.5);
        float br = max(col.r, max(col.g, col.b));
        float soft = clamp(br - uThresh + uKnee, 0.0, 2.0 * uKnee); soft = soft * soft / (4.0 * uKnee + 1e-4);
        col *= max(soft, br - uThresh) / max(br, 1e-4);
    }
    fragColor = vec4(col, 1.0);
}
"""

# 在引擎合成着色器的 gamma 之后插入"黑位 + S 曲线"
COMPOSITE_WD = _ENGINE_COMPOSITE.replace(
    "uniform vec2 uShake;\n", "uniform vec2 uShake;\nuniform float uBlack; uniform float uContrast;\n").replace(
    "    col = col + uLift * (1.0 - col);\n",
    "    col = max(col - uBlack, 0.0) / (1.0 - uBlack);                 // 压黑位：去掉灰底\n"
    "    col = mix(col, col * col * (3.0 - 2.0 * col), uContrast);        // 轻微 S 曲线\n"
    "    col = col + uLift * (1.0 - col);\n")
assert "uBlack" in COMPOSITE_WD and "uContrast" in COMPOSITE_WD

# 后期参数（场景的 post() 仍可覆盖其中任何一项）
POST_WD = dict(uThresh=1.0, uKnee=0.5, uBlack=0.035, uContrast=0.22, uSat=1.12)
BLOOM_WEIGHTS = [1.0, 0.55, 0.28, 0.14, 0.07]          # 由细到粗；最粗几级权重小，避免大范围灰纱


def install_post(eng):
    """用本项目的泛光与合成替换引擎默认后期。"""
    def run_bloom(src_tex, thresh, knee):
        prev = src_tex
        for i, (tex, fbo) in enumerate(eng.bloom):
            fbo.use()
            eng.ctx.viewport = (0, 0, tex.width, tex.height)
            eng.draw_fs("bloom_down_wd", BLOOM_DOWN_WD, dict(uTexel=(1.0 / prev.width, 1.0 / prev.height),
                                                             uFirst=1 if i == 0 else 0, uThresh=thresh, uKnee=knee),
                        dict(uSrc=prev))
            prev = tex
        for i in range(len(eng.bloom) - 1, 0, -1):
            src = eng.bloom[i][0]
            tex, fbo = eng.bloom[i - 1]
            fbo.use()
            eng.ctx.viewport = (0, 0, tex.width, tex.height)
            eng.draw_fs("bloom_up", BLOOM_UP, dict(uTexel=(1.0 / src.width, 1.0 / src.height),
                                                   uWeight=BLOOM_WEIGHTS[i - 1]), dict(uSrc=src), blend="add")
        eng.ctx.viewport = (0, 0, W, H)
        return eng.bloom[0][0]

    def composite(scene_tex, post):
        u = dict(uBloomAmt=0.4, uExposure=1.0, uCA=0.005, uVignette=0.55, uGrain=0.028, uFade=1.0, uSat=1.05,
                 uTint=(1.0, 1.0, 1.0), uLift=(0.0, 0.0, 0.0), uFrame=float(eng.frame), uLetterbox=0.0,
                 uShake=(0.0, 0.0))
        u.update(POST_WD)
        u.update(post)
        bl = run_bloom(scene_tex, u.pop("uThresh"), u.pop("uKnee"))
        eng.ldr.use()
        eng.ctx.viewport = (0, 0, W, H)
        eng.draw_fs("composite_wd", COMPOSITE_WD, u, dict(uScene=scene_tex, uBloom=bl))
    eng.composite = composite
