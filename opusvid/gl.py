# -*- coding: utf-8 -*-
"""opusvid.gl — 离屏 GPU 渲染引擎（moderngl）：HDR 场景缓冲、泛光、色调映射、粒子、2D 线条/形状、逐字动画文字。"""
import math
import numpy as np
import moderngl
from PIL import Image, ImageDraw, ImageFont
from .settings import W, H, FONTS

GLSL_COMMON = r"""
#version 430
#define PI 3.14159265359
#define TAU 6.28318530718
uniform vec2 uRes;
uniform float uTime;

float hash11(float p){ p = fract(p * .1031); p *= p + 33.33; p *= p + p; return fract(p); }
float hash12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
vec2 hash22(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * vec3(.1031, .1030, .0973)); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.xx + p3.yz) * p3.zy); }
vec3 hash33(vec3 p3){ p3 = fract(p3 * vec3(.1031, .1030, .0973)); p3 += dot(p3, p3.yxz + 33.33); return fract((p3.xxy + p3.yxx) * p3.zyx); }
float hash13(vec3 p3){ p3 = fract(p3 * .1031); p3 += dot(p3, p3.zyx + 31.32); return fract((p3.x + p3.y) * p3.z); }

float vnoise3(vec3 x){
    vec3 i = floor(x); vec3 f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(hash13(i + vec3(0,0,0)), hash13(i + vec3(1,0,0)), f.x),
                   mix(hash13(i + vec3(0,1,0)), hash13(i + vec3(1,1,0)), f.x), f.y),
               mix(mix(hash13(i + vec3(0,0,1)), hash13(i + vec3(1,0,1)), f.x),
                   mix(hash13(i + vec3(0,1,1)), hash13(i + vec3(1,1,1)), f.x), f.y), f.z);
}
float vnoise2(vec2 x){
    vec2 i = floor(x); vec2 f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1,0)), f.x), mix(hash12(i + vec2(0,1)), hash12(i + vec2(1,1)), f.x), f.y);
}
float fbm3(vec3 p, int oct){
    float a = 0.5, s = 0.0;
    for (int i = 0; i < oct; i++){ s += a * vnoise3(p); p = p * 2.03 + vec3(1.7, 9.2, 3.1); a *= 0.5; }
    return s;
}
float fbm2(vec2 p, int oct){
    float a = 0.5, s = 0.0;
    for (int i = 0; i < oct; i++){ s += a * vnoise2(p); p = mat2(1.6, 1.2, -1.2, 1.6) * p + vec2(3.1, 1.7); a *= 0.5; }
    return s;
}
mat2 rot2(float a){ float c = cos(a), s = sin(a); return mat2(c, s, -s, c); }
vec3 aces(vec3 x){ const float a = 2.51, b = 0.03, c = 2.43, d = 0.59, e = 0.14; return clamp((x*(a*x+b))/(x*(c*x+d)+e), 0.0, 1.0); }
float luma(vec3 c){ return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
// 星光颜色（温度 0..1：橙红 -> 白 -> 蓝白）
vec3 starColor(float t){
    vec3 c1 = vec3(1.0, 0.62, 0.38), c2 = vec3(1.0, 0.93, 0.85), c3 = vec3(0.72, 0.84, 1.0);
    return t < 0.5 ? mix(c1, c2, t * 2.0) : mix(c2, c3, (t - 0.5) * 2.0);
}
// 2D 屏幕空间星空：p 像素坐标，cell 网格像素大小
vec3 starLayer(vec2 p, float cell, float seed, float density, float bright, float time){
    vec2 g = p / cell; vec2 id = floor(g); vec2 f = fract(g);
    vec3 col = vec3(0);
    for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++){
        vec2 o = vec2(x, y); vec2 cid = id + o;
        float h = hash12(cid + seed * 17.13);
        if (h > density) continue;
        vec2 pos = hash22(cid + seed * 3.7);
        vec2 d = (o + pos - f) * cell;
        float r2 = dot(d, d);
        float m = hash12(cid * 1.37 + seed);
        float mag = pow(m, 9.0);
        float tw = 0.75 + 0.25 * sin(time * (1.0 + 3.0 * hash12(cid + 5.0)) + h * 60.0);
        float b = bright * (0.25 + 5.5 * mag) * tw;
        float core = exp(-r2 / 1.1);
        float rr = sqrt(r2);
        float halo = exp(-rr / min(1.2 + 3.0 * mag, cell * 0.1)) * 0.02 * mag * smoothstep(cell * 0.95, cell * 0.45, rr);
        col += starColor(hash12(cid + 9.1)) * b * (core + halo);
    }
    return col;
}
vec3 starfield2d(vec2 p, float time, float amount){
    vec3 c = vec3(0);
    c += starLayer(p, 9.0, 1.0, 0.18, 0.35, time);
    c += starLayer(p, 23.0, 2.0, 0.35, 0.8, time);
    c += starLayer(p, 61.0, 3.0, 0.45, 1.6, time);
    return c * amount;
}
"""

FS_VERT = r"""
#version 430
in vec2 in_pos;
out vec2 vUV;
void main(){ vUV = in_pos * 0.5 + 0.5; gl_Position = vec4(in_pos, 0.0, 1.0); }
"""

# ------------------------------------------------------------------ post
BLOOM_DOWN = r"""
uniform sampler2D uSrc;
uniform vec2 uTexel;
uniform int uFirst;
in vec2 vUV; out vec4 fragColor;
vec3 S(vec2 o){ return texture(uSrc, vUV + o * uTexel).rgb; }
float KW(vec3 c){ return 1.0 / (1.0 + luma(c) * 1.5); }
void main(){
    vec3 a = S(vec2(-2,2)), b = S(vec2(0,2)), c = S(vec2(2,2));
    vec3 d = S(vec2(-2,0)), e = S(vec2(0,0)), f = S(vec2(2,0));
    vec3 g = S(vec2(-2,-2)), h = S(vec2(0,-2)), i = S(vec2(2,-2));
    vec3 j = S(vec2(-1,1)), k = S(vec2(1,1)), l = S(vec2(-1,-1)), m = S(vec2(1,-1));
    vec3 col = e*0.125 + (a+c+g+i)*0.03125 + (b+d+f+h)*0.0625 + (j+k+l+m)*0.125;
    if (uFirst == 1){
        // Karis 加权：抑制孤立亮点（星点）产生的方块状光晕
        vec3 g0 = (a + b + d + e) * 0.25, g1 = (b + c + e + f) * 0.25, g2 = (d + e + g + h) * 0.25, g3 = (e + f + h + i) * 0.25;
        vec3 g4 = (j + k + l + m) * 0.25;
        float w0 = KW(g0), w1 = KW(g1), w2 = KW(g2), w3 = KW(g3), w4 = KW(g4);
        col = (g0 * w0 * 0.125 + g1 * w1 * 0.125 + g2 * w2 * 0.125 + g3 * w3 * 0.125 + g4 * w4 * 0.5)
            / (w0 * 0.125 + w1 * 0.125 + w2 * 0.125 + w3 * 0.125 + w4 * 0.5);
        // 软阈值 + 防萤火虫
        float br = max(col.r, max(col.g, col.b));
        float knee = 0.6;
        float soft = clamp(br - 0.35 + knee, 0.0, 2.0 * knee); soft = soft * soft / (4.0 * knee + 1e-4);
        float contrib = max(soft, br - 0.35) / max(br, 1e-4);
        col *= contrib;
        col /= (1.0 + luma(col) * 0.08);
    }
    fragColor = vec4(col, 1.0);
}
"""

BLOOM_UP = r"""
uniform sampler2D uSrc;
uniform vec2 uTexel;
uniform float uWeight;
in vec2 vUV; out vec4 fragColor;
vec3 S(vec2 o){ return texture(uSrc, vUV + o * uTexel).rgb; }
void main(){
    vec3 col = S(vec2(0,0)) * 4.0 + (S(vec2(-1,0)) + S(vec2(1,0)) + S(vec2(0,-1)) + S(vec2(0,1))) * 2.0
             + S(vec2(-1,-1)) + S(vec2(1,-1)) + S(vec2(-1,1)) + S(vec2(1,1));
    fragColor = vec4(col / 16.0 * uWeight, 1.0);
}
"""

COMPOSITE = r"""
uniform sampler2D uScene;
uniform sampler2D uBloom;
uniform float uBloomAmt;
uniform float uExposure;
uniform float uCA;
uniform float uVignette;
uniform float uGrain;
uniform float uFade;
uniform float uSat;
uniform vec3 uTint;
uniform vec3 uLift;
uniform float uFrame;
uniform float uLetterbox;
uniform vec2 uShake;
in vec2 vUV; out vec4 fragColor;
void main(){
    vec2 uv = vUV + uShake / uRes;
    vec2 cc = uv - 0.5;
    float r2 = dot(cc, cc);
    vec2 off = cc * r2 * uCA;
    vec3 col;
    col.r = texture(uScene, uv - off).r;
    col.g = texture(uScene, uv).g;
    col.b = texture(uScene, uv + off).b;
    vec3 bl = texture(uBloom, uv).rgb;
    col += bl * uBloomAmt;
    col *= uExposure;
    col = aces(col * uTint);
    col = pow(col, vec3(1.0 / 2.2));
    col = col + uLift * (1.0 - col);
    float l = luma(col);
    col = mix(vec3(l), col, uSat);
    float v = smoothstep(1.05, 0.25, length(cc * vec2(uRes.x / uRes.y, 1.0)) * 0.85);
    col *= mix(1.0, v, uVignette);
    float n = hash12(vUV * uRes + fract(uFrame * 0.6180339) * 1000.0) + hash12(vUV * uRes * 1.31 + uFrame * 0.123) - 1.0;
    col += n * uGrain * (0.4 + 0.6 * (1.0 - l));
    col *= uFade;
    float lb = uLetterbox * 0.5;
    if (vUV.y < lb || vUV.y > 1.0 - lb) col *= 0.0;
    col += (hash12(vUV * uRes + uFrame) - 0.5) / 255.0;
    fragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
"""

TRANSITION = r"""
uniform sampler2D uA;
uniform sampler2D uB;
uniform float uP;      // 0..1
uniform int uKind;     // 0 warp 1 dissolve 2 dip
uniform float uSeed;
in vec2 vUV; out vec4 fragColor;
vec3 sampleIn(sampler2D tex, vec2 uv){
    // 画面外返回黑色，避免边缘像素被拉成色条
    vec2 m = smoothstep(vec2(-0.002), vec2(0.01), uv) * smoothstep(vec2(-0.002), vec2(0.01), 1.0 - uv);
    return texture(tex, clamp(uv, 0.0, 1.0)).rgb * m.x * m.y;
}
vec3 zoomBlur(sampler2D tex, vec2 uv, float amt, float dir){
    vec2 c = uv - 0.5; vec3 acc = vec3(0); float wsum = 0.0;
    for (int i = 0; i < 24; i++){
        float k = float(i) / 23.0;
        float s = 1.0 - dir * amt * k;
        float w = 1.0 - k * 0.6;
        acc += sampleIn(tex, 0.5 + c * s) * w; wsum += w;
    }
    return acc / wsum;
}
void main(){
    vec2 uv = vUV; vec2 c = uv - 0.5;
    float p = uP;
    if (uKind == 0){
        // 引力扭曲：A 被吸入中心，B 从中心炸开
        float a = smoothstep(0.0, 0.5, p), b = smoothstep(0.5, 1.0, p);
        float lens = sin(p * PI);
        float r = length(c * vec2(uRes.x / uRes.y, 1.0));
        vec2 dir = c / max(length(c), 1e-4);
        float warp = lens * 0.06 * sin(r * 18.0 - p * 22.0) * exp(-r * 2.0);
        vec2 uvA = 0.5 + c * (1.0 - a * 0.35) + dir * warp;
        vec2 uvB = 0.5 + c * (1.0 - (1.0 - b) * 0.3) + dir * warp;
        vec3 A = zoomBlur(uA, uvA, a * 0.16, 1.0);
        vec3 B = zoomBlur(uB, uvB, (1.0 - b) * 0.16, 1.0);
        float m = smoothstep(0.35, 0.65, p);
        vec3 col = mix(A * (1.0 - a * 0.7), B * (0.3 + 0.7 * b), m);
        fragColor = vec4(col, 1.0);
    } else if (uKind == 1){
        float n = fbm2(uv * vec2(uRes.x / uRes.y, 1.0) * 3.0 + uSeed, 5);
        float th = p * 1.25 - 0.1;
        float m = smoothstep(th - 0.06, th + 0.06, n);
        vec3 A = texture(uA, uv).rgb, B = texture(uB, uv).rgb;
        float edge = exp(-pow((n - th) / 0.035, 2.0)) * sin(p * PI);
        vec3 col = mix(B, A, m) + vec3(0.55, 0.35, 1.0) * edge * 1.5;
        fragColor = vec4(col, 1.0);
    } else {
        float k = 1.0 - sin(p * PI);
        vec3 col = p < 0.5 ? texture(uA, uv).rgb : texture(uB, uv).rgb;
        fragColor = vec4(col * k * k, 1.0);
    }
}
"""

# ------------------------------------------------------------------ particles
POINT_VERT_HEAD = r"""
in vec3 in_pos;
in vec4 in_col;
in vec4 in_extra;
uniform mat4 uMVP;
uniform float uPix;        // 像素/世界单位（在距离 1 处）
uniform float uSize;       // 世界尺寸缩放
uniform float uMinPx;
uniform float uGain;
uniform int uFlux;         // 1: 能量守恒的点（恒星）
uniform float uMaxPx;
out vec4 vCol;
out float vShape;
out float vAngle;
out float vAspect;
"""

POINT_VERT_TAIL = r"""
void emit2(vec3 P, vec4 C, float S, float shape, float angle, float aspect){
    vec4 cp = uMVP * vec4(P, 1.0);
    gl_Position = cp;
    float w = max(cp.w, 1e-3);
    float px = S * uSize * uPix / w;
    float s = clamp(px, uMinPx, uMaxPx);
    float energy = uFlux == 1 ? (uMinPx * uMinPx) / (s * s) : min(1.0, (px * px) / (s * s));
    vCol = C * uGain * energy;
    if (cp.w <= 0.0) vCol = vec4(0);
    vShape = shape; vAngle = angle; vAspect = aspect;
    gl_PointSize = s * 3.0;
}
void emit(vec3 P, vec4 C, float S){ emit2(P, C, S, 0.0, 0.0, 1.0); }
"""

POINT_FRAG = r"""
#version 430
in vec4 vCol;
in float vShape;
in float vAngle;
in float vAspect;
out vec4 fragColor;
void main(){
    vec2 d = gl_PointCoord * 2.0 - 1.0;
    if (vAspect != 1.0){
        float c = cos(vAngle), s = sin(vAngle);
        d = mat2(c, s, -s, c) * d;
        d.y *= vAspect;
    }
    // 点精灵直径是 3 倍名义尺寸，r2 换算后 r=1 对应名义半径
    // vShape: 0 高斯星点 / 1 指数衰减的柔光团 / 2 星系（高斯核 + 指数晕）
    float r2 = dot(d, d) * 9.0;
    float g = vShape < 0.5 ? exp(-r2 * 0.5) : exp(-sqrt(r2) * 2.2);
    if (vShape > 1.5) g = exp(-r2 * 0.5) * 0.7 + exp(-sqrt(r2) * 1.6) * 0.3;
    fragColor = vec4(vCol.rgb * g, vCol.a * g);
}
"""

# ------------------------------------------------------------------ 2D primitives
LINE_VERT = r"""
#version 430
in vec2 in_pos; in float in_across; in float in_along; in vec4 in_p; in vec4 in_col;
uniform vec2 uRes;
out float vAcross; out float vAlong; out vec4 vP; out vec4 vCol;
void main(){
    vAcross = in_across; vAlong = in_along; vP = in_p; vCol = in_col;
    gl_Position = vec4(in_pos.x / uRes.x * 2.0 - 1.0, 1.0 - in_pos.y / uRes.y * 2.0, 0.0, 1.0);
}
"""
LINE_FRAG = r"""
#version 430
in float vAcross; in float vAlong; in vec4 vP; in vec4 vCol;
out vec4 fragColor;
// vP: x=半宽(px) y=外扩总半宽 z=glow强度 w=虚线周期(0=实线)
void main(){
    float d = abs(vAcross) * vP.y;
    float core = 1.0 - smoothstep(vP.x - 0.7, vP.x + 0.7, d);
    float gw = max(vP.y - vP.x, 1.0) * 0.45;
    float glow = exp(-d * d / (2.0 * gw * gw)) * vP.z;
    float a = core + glow;
    if (vP.w > 0.0){
        float ph = mod(vAlong, vP.w) / vP.w;
        a *= smoothstep(0.0, 0.05, ph) * (1.0 - smoothstep(0.5, 0.55, ph));
    }
    // alpha 只在 "over" 混合下起作用：线条本体遮挡背景，光晕不遮挡
    fragColor = vec4(vCol.rgb * a * vCol.a, core * vCol.a);
}
"""

SHAPE_VERT = r"""
#version 430
in vec2 in_pos; in vec2 in_local; in vec4 in_p; in vec4 in_col; in vec4 in_col2;
uniform vec2 uRes;
out vec2 vLocal; out vec4 vP; out vec4 vCol; out vec4 vCol2;
void main(){
    vLocal = in_local; vP = in_p; vCol = in_col; vCol2 = in_col2;
    gl_Position = vec4(in_pos.x / uRes.x * 2.0 - 1.0, 1.0 - in_pos.y / uRes.y * 2.0, 0.0, 1.0);
}
"""
SHAPE_FRAG = r"""
#version 430
in vec2 vLocal; in vec4 vP; in vec4 vCol; in vec4 vCol2;
out vec4 fragColor;
// vP: x=类型(0圆 1圆角矩形) y=半径/半宽 z=半高或环宽 w=圆角/glow
// vCol: 填充 (预乘)  vCol2: 描边颜色, a=描边宽度 (像素)
float sdRound(vec2 p, vec2 b, float r){ vec2 q = abs(p) - b + r; return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r; }
void main(){
    float d;
    float glowAmt = 0.0;
    if (vP.x < 0.5){ d = length(vLocal) - vP.y; glowAmt = vP.w; }
    else { d = sdRound(vLocal, vec2(vP.y, vP.z), vP.w); }
    float fill = 1.0 - smoothstep(-0.7, 0.7, d);
    float sw = vCol2.a;
    float stroke = sw > 0.0 ? (1.0 - smoothstep(sw * 0.5 - 0.7, sw * 0.5 + 0.7, abs(d))) : 0.0;
    float glow = glowAmt > 0.0 ? exp(-max(d, 0.0) / (glowAmt)) * 0.6 : 0.0;
    vec3 rgb = vCol.rgb * (fill + glow) + vCol2.rgb * stroke;
    float a = vCol.a * fill;
    fragColor = vec4(rgb, a);
}
"""

TEXT_VERT = r"""
#version 430
in vec2 in_pos; in vec2 in_uv; in vec4 in_col; in float in_blur;
uniform vec2 uRes;
out vec2 vUV; out vec4 vCol; out float vBlur;
void main(){
    vUV = in_uv; vCol = in_col; vBlur = in_blur;
    gl_Position = vec4(in_pos.x / uRes.x * 2.0 - 1.0, 1.0 - in_pos.y / uRes.y * 2.0, 0.0, 1.0);
}
"""
TEXT_FRAG = r"""
#version 430
uniform sampler2D uAtlas;
uniform vec2 uAtlasTexel;
in vec2 vUV; in vec4 vCol; in float vBlur;
out vec4 fragColor;
void main(){
    float a;
    if (vBlur < 0.3){
        a = texture(uAtlas, vUV).r;
    } else {
        a = 0.0; float ws = 0.0;
        for (int i = 0; i < 24; i++){
            float k = float(i) + 0.5;
            float r = sqrt(k / 24.0) * vBlur;
            float th = k * 2.39996;
            vec2 o = vec2(cos(th), sin(th)) * r * uAtlasTexel;
            a += texture(uAtlas, vUV + o).r; ws += 1.0;
        }
        a = a / ws;
    }
    fragColor = vec4(vCol.rgb * a * vCol.a, a * vCol.a);
}
"""


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_out_expo(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - 2 ** (-10 * x) if x < 1 else 1.0


def smooth(a, b, x):
    if b == a:
        return 1.0 if x >= b else 0.0
    return ease_in_out((x - a) / (b - a))


def lin(a, b, x):
    return min(max((x - a) / (b - a), 0.0), 1.0)


def perspective(fovy_deg, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fovy_deg) / 2)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = 2 * far * near / (near - far)
    m[3, 2] = -1
    return m


def look_at(eye, target, up=(0, 1, 0)):
    eye, target, up = (np.asarray(v, dtype=np.float64) for v in (eye, target, up))
    f = target - eye
    f /= np.linalg.norm(f)
    s = np.cross(f, up)
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.eye(4)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m.astype(np.float32)


class Camera:
    def __init__(self, eye, target, fov=45.0, up=(0, 1, 0), near=0.01, far=1000.0, shift=(0.0, 0.0)):
        self.eye, self.target, self.fov, self.up, self.near, self.far = eye, target, fov, up, near, far
        self.shift = shift

    def matrices(self):
        P = perspective(self.fov, W / H, self.near, self.far)
        if self.shift != (0.0, 0.0):
            Tn = np.eye(4, dtype=np.float32)
            Tn[0, 3], Tn[1, 3] = self.shift
            P = Tn @ P
        V = look_at(self.eye, self.target, self.up)
        return P, V

    def mvp(self, model=None):
        P, V = self.matrices()
        M = np.eye(4, dtype=np.float32) if model is None else model
        return (P @ V @ M).astype(np.float32)

    @property
    def pix(self):
        return H / (2 * math.tan(math.radians(self.fov) / 2))

    def project(self, p, model=None):
        m = self.mvp(model)
        v = m @ np.array([p[0], p[1], p[2], 1.0])
        if v[3] <= 1e-6:
            return None
        x, y = v[0] / v[3], v[1] / v[3]
        return ((x + 1) * 0.5 * W, (1 - y) * 0.5 * H, v[3])


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]], dtype=np.float32)


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]], dtype=np.float32)


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=np.float32)


def translate(x, y, z):
    m = np.eye(4, dtype=np.float32)
    m[:3, 3] = (x, y, z)
    return m


def scale_m(s):
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = m[1, 1] = m[2, 2] = s
    return m


# ================================================================== glyph atlas
class Atlas:
    SIZE = 8192

    def __init__(self, ctx):
        self.ctx = ctx
        self.tex = ctx.texture((self.SIZE, self.SIZE), 1, dtype="f1")
        self.tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.tex.write(np.zeros((self.SIZE, self.SIZE), np.uint8).tobytes())
        self.x = self.y = 0
        self.row_h = 0
        self.glyphs = {}
        self.fonts = {}

    def font(self, key, size):
        k = (key, size)
        if k not in self.fonts:
            path, wght = FONTS[key] if key in FONTS else (key, None)   # 也可直接传字体文件路径（数学字体）
            f = ImageFont.truetype(path, size)
            if wght is not None:
                try:
                    axes = f.get_variation_axes()
                    vals = []
                    for ax in axes:
                        nm = ax.get("name", b"")
                        nm = nm.decode() if isinstance(nm, bytes) else nm
                        if "eight" in str(nm) or "wght" in str(nm):
                            vals.append(max(ax["minimum"], min(ax["maximum"], wght)))
                        else:
                            vals.append(ax.get("default", ax["minimum"]))
                    f.set_variation_by_axes(vals)
                except Exception as e:
                    print("font var fail", key, e)
            self.fonts[k] = f
        return self.fonts[k]

    def glyph(self, ch, key, size, style="fill"):
        if key.startswith("latin") and ord(ch) >= 0x2E80:
            key = "sans"
        k = (ch, key, size, style)
        if k in self.glyphs:
            return self.glyphs[k]
        f = self.font(key, size)
        pad = max(6, int(size * 0.28))
        adv = f.getlength(ch)
        bb = f.getbbox(ch, anchor="ls")
        gw = max(1, bb[2] - bb[0]) + pad * 2
        gh = max(1, bb[3] - bb[1]) + pad * 2
        img = Image.new("L", (gw, gh), 0)
        d = ImageDraw.Draw(img)
        if ch.strip():
            if style == "outline":
                sw = max(1, int(size * 0.025))
                d.text((pad - bb[0], pad - bb[1]), ch, font=f, anchor="ls", fill=0, stroke_width=sw, stroke_fill=255)
            else:
                d.text((pad - bb[0], pad - bb[1]), ch, font=f, anchor="ls", fill=255)
        if self.x + gw > self.SIZE:
            self.x = 0
            self.y += self.row_h + 2
            self.row_h = 0
        if self.y + gh > self.SIZE:
            raise RuntimeError("atlas full")
        self.tex.write(np.asarray(img, np.uint8).tobytes(), viewport=(self.x, self.y, gw, gh))
        g = dict(adv=adv, x0=bb[0] - pad, y0=bb[1] - pad, w=gw, h=gh,
                 u0=self.x / self.SIZE, v0=self.y / self.SIZE, u1=(self.x + gw) / self.SIZE, v1=(self.y + gh) / self.SIZE)
        self.x += gw + 2
        self.row_h = max(self.row_h, gh)
        self.glyphs[k] = g
        return g

    def metrics(self, key, size):
        f = self.font(key, size)
        asc, desc = f.getmetrics()
        return asc, desc


# ================================================================== engine
class Engine:
    def __init__(self):
        self.ctx = moderngl.create_standalone_context(require=430)
        ctx = self.ctx
        ctx.enable(moderngl.PROGRAM_POINT_SIZE)
        self.quad = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4"))
        self.targets = [self._target(W, H) for _ in range(3)]
        self.bloom = []
        w, h = W, H
        for i in range(6):
            w, h = max(1, w // 2), max(1, h // 2)
            self.bloom.append(self._target(w, h))
        self.ldr_tex = ctx.texture((W, H), 4)
        self.ldr = ctx.framebuffer([self.ldr_tex])
        self.fs_cache = {}
        self.atlas = Atlas(ctx)
        self.p_line = ctx.program(vertex_shader=LINE_VERT, fragment_shader=LINE_FRAG)
        self.p_shape = ctx.program(vertex_shader=SHAPE_VERT, fragment_shader=SHAPE_FRAG)
        self.p_text = ctx.program(vertex_shader=TEXT_VERT, fragment_shader=TEXT_FRAG)
        self.point_progs = {}
        self.dl_lines, self.dl_shapes, self.dl_text = [], [], []
        # 清晰文字层：字号 ≤ ui_text_max 的文字不画进 HDR 场景，而是在后期之后直接叠到成片上，
        # 不受泛光、色差、颗粒影响，并对齐到整像素（小字因此不发虚）。0 = 关闭，保持旧行为。
        self.ui_text_max = 0
        # 清晰层里 ≤ ui_bold_below 像素的细体字换成常规体：细体在小字号下笔画只有 1 像素，视频压缩后又会糊
        self.ui_bold_below = 24
        self.ui_font_upgrade = {"sans_l": "sans", "latin": "latin_m"}
        self.dl_ui = []
        self.frame = 0
        self.time = 0.0

    def _target(self, w, h):
        tex = self.ctx.texture((w, h), 4, dtype="f2")
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        tex.repeat_x = tex.repeat_y = False
        return tex, self.ctx.framebuffer([tex])

    # ---------------------------------------------------------- fullscreen
    def fs(self, key, frag):
        if key not in self.fs_cache:
            prog = self.ctx.program(vertex_shader=FS_VERT, fragment_shader=GLSL_COMMON + frag)
            vao = self.ctx.vertex_array(prog, [(self.quad, "2f", "in_pos")])
            self.fs_cache[key] = (prog, vao)
        return self.fs_cache[key]

    @staticmethod
    def set_u(prog, u):
        for k, v in u.items():
            if k in prog:
                m = prog[k]
                if isinstance(v, np.ndarray):
                    m.write(v.astype("f4").T.tobytes() if v.ndim == 2 else v.astype("f4").tobytes())
                else:
                    m.value = v

    def draw_fs(self, key, frag, uniforms=None, textures=None, blend=None):
        prog, vao = self.fs(key, frag)
        u = dict(uRes=(float(W), float(H)), uTime=self.time)
        if uniforms:
            u.update(uniforms)
        if textures:
            for i, (name, tex) in enumerate(textures.items()):
                tex.use(location=i)
                u[name] = i
        self.set_u(prog, u)
        self._blend(blend)
        vao.render(moderngl.TRIANGLE_STRIP)

    def _blend(self, mode):
        ctx = self.ctx
        if mode is None:
            ctx.disable(moderngl.BLEND)
        else:
            ctx.enable(moderngl.BLEND)
            if mode == "add":
                ctx.blend_func = moderngl.ONE, moderngl.ONE
            elif mode == "over":
                ctx.blend_func = moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA
            elif mode == "mul":
                ctx.blend_func = moderngl.ZERO, moderngl.SRC_COLOR
            elif mode == "darken":
                ctx.blend_func = moderngl.ZERO, moderngl.ONE_MINUS_SRC_COLOR

    # ---------------------------------------------------------- points
    def point_prog(self, key, body):
        if key not in self.point_progs:
            vs = GLSL_COMMON + POINT_VERT_HEAD + POINT_VERT_TAIL + body
            self.point_progs[key] = self.ctx.program(vertex_shader=vs, fragment_shader=POINT_FRAG)
        return self.point_progs[key]

    def make_cloud(self, key, body, pos, col, extra=None):
        prog = self.point_prog(key, body)
        n = len(pos)
        if extra is None:
            extra = np.zeros((n, 4), np.float32)
        data = np.hstack([pos.astype(np.float32), col.astype(np.float32), extra.astype(np.float32)])
        vbo = self.ctx.buffer(data.astype("f4").tobytes())
        fmt, names = "3f 4f 4f", ["in_pos", "in_col", "in_extra"]
        vao = self.ctx.vertex_array(prog, [(vbo, fmt, *names)], skip_errors=True)
        return dict(prog=prog, vao=vao, vbo=vbo, n=n)

    def draw_cloud(self, cloud, cam, uniforms=None, model=None, blend="add", count=None, first=0):
        prog = cloud["prog"]
        u = dict(uMVP=cam.mvp(model), uPix=float(cam.pix), uSize=1.0, uMinPx=1.6, uMaxPx=400.0, uGain=1.0, uFlux=0,
                 uTime=self.time, uRes=(float(W), float(H)))
        if uniforms:
            u.update(uniforms)
        self.set_u(prog, u)
        self._blend(blend)
        cloud["vao"].render(moderngl.POINTS, vertices=count if count is not None else cloud["n"], first=first)

    # ---------------------------------------------------------- 2D draw lists
    def line(self, pts, width=2.0, color=(1, 1, 1), alpha=1.0, glow=0.0, glow_w=None, dash=0.0, progress=1.0,
             intensity=1.0):
        pts = np.asarray(pts, dtype=np.float64)
        if len(pts) < 2 or alpha <= 0.001 or progress <= 0:
            return
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        along = np.concatenate([[0], np.cumsum(seg)])
        total = along[-1]
        if progress < 1.0:
            L = total * progress
            k = np.searchsorted(along, L)
            k = max(1, min(k, len(pts) - 1))
            f = (L - along[k - 1]) / max(seg[k - 1], 1e-9)
            end = pts[k - 1] + (pts[k] - pts[k - 1]) * f
            pts = np.vstack([pts[:k], end])
            along = np.concatenate([along[:k], [L]])
        hw = width / 2
        ext = hw + (glow_w if glow_w is not None else (width * 3 + 6 if glow > 0 else 1.5))
        d = np.zeros_like(pts)
        d[1:-1] = pts[2:] - pts[:-2]
        d[0] = pts[1] - pts[0]
        d[-1] = pts[-1] - pts[-2]
        nrm = np.linalg.norm(d, axis=1, keepdims=True)
        nrm[nrm < 1e-9] = 1
        d /= nrm
        nv = np.stack([-d[:, 1], d[:, 0]], axis=1)
        c = np.array(color, dtype=np.float64) * intensity
        verts = []
        for i in range(len(pts) - 1):
            for (j, s) in ((i, -1), (i, 1), (i + 1, -1), (i, 1), (i + 1, 1), (i + 1, -1)):
                p = pts[j] + nv[j] * s * ext
                verts.append([p[0], p[1], s, along[j], hw, ext, glow, dash, c[0], c[1], c[2], alpha])
        self.dl_lines.append(np.array(verts, dtype=np.float32))

    def circle(self, x, y, r, fill=(1, 1, 1), fill_a=1.0, stroke=None, stroke_w=0.0, glow=0.0, intensity=1.0):
        ext = r + stroke_w + (glow * 6 if glow > 0 else 2) + 2
        f = np.array(fill) * intensity * fill_a
        s = np.array(stroke if stroke is not None else (0, 0, 0)) * intensity
        self._quad_shape(x, y, ext, ext, [0, r, 0, glow], [f[0], f[1], f[2], fill_a], [s[0], s[1], s[2], stroke_w])

    def rect(self, x, y, w, h, radius=8, fill=(0, 0, 0), fill_a=0.5, stroke=None, stroke_w=0.0, intensity=1.0):
        ext_w, ext_h = w / 2 + stroke_w + 2, h / 2 + stroke_w + 2
        f = np.array(fill) * intensity * fill_a
        s = np.array(stroke if stroke is not None else (0, 0, 0)) * intensity
        self._quad_shape(x + w / 2, y + h / 2, ext_w, ext_h, [1, w / 2, h / 2, radius], [f[0], f[1], f[2], fill_a],
                         [s[0], s[1], s[2], stroke_w])

    def _quad_shape(self, cx, cy, ex, ey, p, c1, c2):
        v = []
        for (sx, sy) in ((-1, -1), (1, -1), (-1, 1), (1, -1), (1, 1), (-1, 1)):
            v.append([cx + sx * ex, cy + sy * ey, sx * ex, sy * ey] + list(p) + list(c1) + list(c2))
        self.dl_shapes.append(np.array(v, dtype=np.float32))

    def text_layout(self, s, font, size, tracking=0.0, style="fill"):
        A = self.atlas
        x = 0.0
        items = []
        for ch in s:
            g = A.glyph(ch, font, size, style)
            items.append((ch, g, x))
            x += g["adv"] + tracking * size
        width = x - (tracking * size if s else 0)
        return items, width

    def text(self, s, x, y, size=48, font="sans", color=(1, 1, 1), alpha=1.0, anchor="mm", tracking=0.0,
             intensity=1.0, t=None, start=0.0, dur=0.6, stagger=0.04, kind="rise", out=None, out_dur=0.5,
             blur=0.0, scale=1.0, style="fill", char_fx=None, layer=None):
        """anchor: 两个字母，水平 l/m/r，垂直 t/m/b（以字形视觉中心计）。
        layer: None 按字号自动选（≤ ui_text_max 走清晰文字层）；"inline" 画进当前目标（旧行为）；"ui" 清晰文字层。"""
        if alpha <= 0.002:
            return 0
        if layer is None:
            layer = "ui" if size <= self.ui_text_max else "inline"
        crisp = layer == "ui"
        if crisp and size <= self.ui_bold_below:
            font = self.ui_font_upgrade.get(font, font)
        items, width = self.text_layout(s, font, size, tracking, style)
        cap = size * 0.80          # 近似字高，用于垂直居中
        ax, ay = anchor
        ox = {"l": 0, "m": -width / 2, "r": -width}[ax] * scale
        base = {"t": cap, "m": cap / 2, "b": 0}[ay] * scale
        n = len(items)
        verts = []
        for i, (ch, g, gx) in enumerate(items):
            if not ch.strip():
                continue
            a = alpha
            dy = 0.0
            bl = blur
            sc = scale
            dx = 0.0
            if t is not None:
                p = (t - start - i * stagger) / max(dur, 1e-4)
                e = ease_out(p)
                if kind == "rise":
                    a *= e
                    dy += (1 - e) * size * 0.45
                    bl += (1 - e) * size * 0.14
                elif kind == "blur":
                    a *= e
                    bl += (1 - e) * size * 0.3
                    sc *= 1 + (1 - e) * 0.25
                elif kind == "type":
                    a *= 1.0 if p >= 0 else 0.0
                elif kind == "drop":
                    a *= e
                    dy -= (1 - e) * size * 0.6
                    bl += (1 - e) * size * 0.1
                elif kind == "spread":
                    a *= e
                    dx += (1 - e) * (i - (n - 1) / 2) * size * 0.35
                    bl += (1 - e) * size * 0.2
                if out is not None:
                    q = ease_in_out((t - out - i * stagger * 0.5) / max(out_dur, 1e-4))
                    a *= 1 - q
                    bl += q * size * 0.25
                    dy -= q * size * 0.25
            if char_fx is not None:
                r = char_fx(i, n)
                if r:
                    a *= r.get("a", 1.0)
                    dy += r.get("dy", 0.0)
                    dx += r.get("dx", 0.0)
                    bl += r.get("blur", 0.0)
                    ci = r.get("i", 1.0)
                else:
                    ci = 1.0
            else:
                ci = 1.0
            if a <= 0.002:
                continue
            gx0 = x + ox + (gx + g["x0"]) * scale
            gy0 = y + base + g["y0"] * sc
            if crisp and sc == 1.0 and scale == 1.0:
                gx0, gy0 = round(gx0), round(gy0)     # 静止时字形贴图与像素一一对应，不被双线性采样摊开
            cx = gx0 + dx
            cy = gy0 + dy
            # 动画缩放（sc ≠ scale）以字形中心为基点
            if sc != scale:
                ccx = x + ox + (gx + g["adv"] / 2) * scale + dx
                cx = ccx + (cx - ccx) * sc / scale
            w_, h_ = g["w"] * sc, g["h"] * sc
            c = (color[0] * intensity * ci, color[1] * intensity * ci, color[2] * intensity * ci, a)
            u0, v0, u1, v1 = g["u0"], g["v0"], g["u1"], g["v1"]
            q = [(cx, cy, u0, v0), (cx + w_, cy, u1, v0), (cx, cy + h_, u0, v1), (cx + w_, cy, u1, v0),
                 (cx + w_, cy + h_, u1, v1), (cx, cy + h_, u0, v1)]
            for (px, py, u, v) in q:
                verts.append([px, py, u, v, c[0], c[1], c[2], c[3], bl])
        if verts:
            (self.dl_ui if crisp else self.dl_text).append(np.array(verts, dtype=np.float32))
        return width * scale

    def flush_ui(self, fade=1.0, shadow=0.55):
        """把清晰文字层画到当前绑定的目标（成片的 LDR 缓冲）。
        文字颜色是 HDR 值，先用与 composite 相同的 ACES + gamma 换成显示值，
        这样和画进场景的同色文字看起来一致；再垫一层柔和暗影，压在亮背景上也读得清。"""
        if not self.dl_ui:
            return
        data = np.concatenate(self.dl_ui)
        self.dl_ui = []
        rgb = data[:, 4:7].astype(np.float64)
        rgb = np.clip((rgb * (2.51 * rgb + 0.03)) / (rgb * (2.43 * rgb + 0.59) + 0.14), 0.0, 1.0) ** (1 / 2.2)
        data[:, 4:7] = rgb
        data[:, 7] *= fade
        if shadow > 0:
            sh = data.copy()
            sh[:, 1] += 1.5
            sh[:, 4:7] = 0.0
            sh[:, 7] *= shadow
            sh[:, 8] = np.maximum(sh[:, 8], 3.0)
            self.dl_text.append(sh)
        self.dl_text.append(data)
        self.flush()

    def flush(self, blend_lines="add", blend_shapes="over", blend_text="over"):
        u = dict(uRes=(float(W), float(H)))
        ctx = self.ctx
        if self.dl_shapes:
            data = np.concatenate(self.dl_shapes)
            vbo = ctx.buffer(data.tobytes())
            vao = ctx.vertex_array(self.p_shape, [(vbo, "2f 2f 4f 4f 4f", "in_pos", "in_local", "in_p", "in_col", "in_col2")])
            self.set_u(self.p_shape, u)
            self._blend(blend_shapes)
            vao.render(moderngl.TRIANGLES)
            vao.release(); vbo.release()
        if self.dl_lines:
            data = np.concatenate(self.dl_lines)
            vbo = ctx.buffer(data.tobytes())
            vao = ctx.vertex_array(self.p_line, [(vbo, "2f 1f 1f 4f 4f", "in_pos", "in_across", "in_along", "in_p", "in_col")])
            self.set_u(self.p_line, u)
            self._blend(blend_lines)
            vao.render(moderngl.TRIANGLES)
            vao.release(); vbo.release()
        if self.dl_text:
            data = np.concatenate(self.dl_text)
            vbo = ctx.buffer(data.tobytes())
            vao = ctx.vertex_array(self.p_text, [(vbo, "2f 2f 4f 1f", "in_pos", "in_uv", "in_col", "in_blur")])
            self.atlas.tex.use(location=0)
            self.set_u(self.p_text, dict(uRes=(float(W), float(H)), uAtlas=0,
                                         uAtlasTexel=(1.0 / Atlas.SIZE, 1.0 / Atlas.SIZE)))
            self._blend(blend_text)
            vao.render(moderngl.TRIANGLES)
            vao.release(); vbo.release()
        self.dl_lines, self.dl_shapes, self.dl_text = [], [], []

    # ---------------------------------------------------------- post
    def run_bloom(self, src_tex):
        prev = src_tex
        for i, (tex, fbo) in enumerate(self.bloom):
            fbo.use()
            self.ctx.viewport = (0, 0, tex.width, tex.height)
            self.draw_fs("bloom_down", BLOOM_DOWN, dict(uTexel=(1.0 / prev.width, 1.0 / prev.height), uFirst=1 if i == 0 else 0),
                         dict(uSrc=prev))
            prev = tex
        weights = [1.0, 0.7, 0.42, 0.26, 0.16]
        for i in range(len(self.bloom) - 1, 0, -1):
            src = self.bloom[i][0]
            tex, fbo = self.bloom[i - 1]
            fbo.use()
            self.ctx.viewport = (0, 0, tex.width, tex.height)
            self.draw_fs("bloom_up", BLOOM_UP, dict(uTexel=(1.0 / src.width, 1.0 / src.height), uWeight=weights[i - 1]),
                         dict(uSrc=src), blend="add")
        self.ctx.viewport = (0, 0, W, H)
        return self.bloom[0][0]

    def composite(self, scene_tex, post):
        bl = self.run_bloom(scene_tex)
        self.ldr.use()
        self.ctx.viewport = (0, 0, W, H)
        u = dict(uBloomAmt=0.4, uExposure=1.0, uCA=0.005, uVignette=0.55, uGrain=0.028, uFade=1.0, uSat=1.05,
                 uTint=(1.0, 1.0, 1.0), uLift=(0.0, 0.0, 0.0), uFrame=float(self.frame), uLetterbox=0.0, uShake=(0.0, 0.0))
        u.update(post)
        self.draw_fs("composite", COMPOSITE, u, dict(uScene=scene_tex, uBloom=bl))

    def transition(self, texA, texB, dst_fbo, p, kind=0, seed=0.0):
        dst_fbo.use()
        self.draw_fs("transition", TRANSITION, dict(uP=p, uKind=kind, uSeed=seed), dict(uA=texA, uB=texB))

    def read(self):
        return self.ldr.read(components=3, alignment=1)


def project_many(cam, pts):
    """批量把 3D 点投影到屏幕像素坐标。返回 (xy, w, ok)。"""
    m = cam.mvp()
    p = np.hstack([pts, np.ones((len(pts), 1))]) @ m.T
    w = p[:, 3:4]
    ok = w[:, 0] > 1e-4
    xy = p[:, :2] / np.where(ok[:, None], w, 1)
    sx = (xy[:, 0] + 1) * 0.5 * W
    sy = (1 - xy[:, 1]) * 0.5 * H
    return np.stack([sx, sy], 1), w[:, 0], ok
