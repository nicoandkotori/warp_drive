# -*- coding: utf-8 -*-
"""时空网格：一张 GPU 细分平面，顶点着色器按"时空形变"抬高/压低并横向挤压，片段着色器画发光网格线。

形变项（可叠加，全部是 draw() 的参数，默认关闭）：
  wells   引力井 [(x, z, 深度, 宽度)]：质量把膜压出凹陷
  york    阿库别瑞曲率泡的"约克时间"（体积膨胀率）θ = v·(xs/rs)·df/drs：
          前方（+x）为负 = 收缩（凹下、蓝），后方为正 = 膨胀（隆起、红）
  comp    网格线沿 x 的挤压：x' = x + comp·R·f(rs)，前方线变密、后方变稀（直观表现"前缩后胀"）
  well_f / well_b   船前/船后各自的凹陷深度（肥皂船隐喻："熨平"船后、保留船前的弯曲）
  ripple  从 rip_c 向外传播的环形波；wave 整张膜的起伏
  flow    网格线相对形变整体平移（形变跟着飞船不动、网格线向后流过 = 飞船在前进）
颜色：高度 <0 偏 col_neg、>0 偏 col_pos，平处为 col_flat；越远越暗（雾），边缘淡出。
坐标：世界 x 向右、z 向前、y 向上；网格铺在 y=0 平面，范围 center ± L。
"""
import numpy as np
import moderngl

GRID_VS = r"""
#version 430
in vec2 in_uv;                       // -1..1
uniform mat4 uMVP;
uniform float uL; uniform vec2 uCenter;
uniform vec4 uWells[4]; uniform int uNW;
uniform vec2 uShip; uniform float uR; uniform float uSig; uniform float uYork; uniform float uComp;
uniform float uWellF; uniform float uWellB; uniform float uWellS;
uniform float uRipple; uniform vec2 uRipC; uniform float uRipK; uniform float uRipPhase;
uniform float uWave; uniform float uTime; uniform float uYScale; uniform vec2 uFlow;
out vec2 vG; out float vH; out float vEdge; out vec3 vW; out float vSlope;
float shapeF(float r){ return (tanh(uSig * (r + uR)) - tanh(uSig * (r - uR))) / (2.0 * tanh(uSig * uR)); }
float dshapeF(float r){
    float a = 1.0 / cosh(uSig * (r + uR)), b = 1.0 / cosh(uSig * (r - uR));
    return uSig * (a * a - b * b) / (2.0 * tanh(uSig * uR));
}
float height(vec2 p){
    float h = 0.0;
    for (int i = 0; i < 4; i++){
        if (i >= uNW) break;
        vec2 d = p - uWells[i].xy;
        float w = uWells[i].w;
        h -= uWells[i].z / sqrt(1.0 + dot(d, d) / (w * w));
    }
    vec2 s = p - uShip;
    float rs = max(length(s), 1e-4);
    if (uYork != 0.0) h += uYork * (s.x / rs) * dshapeF(rs);     // df/dr<0 在泡壁：前方为负（收缩）
    if (uWellF != 0.0 || uWellB != 0.0){
        float k = smoothstep(-0.25, 0.25, s.x / uWellS);
        h -= mix(uWellB, uWellF, k) * exp(-dot(s, s) / (uWellS * uWellS));
    }
    if (uRipple != 0.0){
        float r = length(p - uRipC);
        h += uRipple * sin(r * uRipK - uRipPhase) * exp(-r * 0.12) * smoothstep(0.0, 1.0, uRipPhase / uRipK - r + 2.0);
    }
    if (uWave != 0.0) h += uWave * (sin(p.x * 0.45 + uTime * 1.3) * cos(p.y * 0.35 - uTime * 0.9) + 0.5 * sin(p.x * 0.9 - p.y * 0.7 + uTime * 2.1));
    return h * uYScale;
}
void main(){
    vec2 p0 = uCenter + in_uv * uL;
    float h = height(p0);
    // 网格线挤压：只改变显示位置，网格坐标（vG）仍用原始位置，所以线条跟着"空间"一起被挤
    vec2 p = p0;
    if (uComp != 0.0){
        vec2 s = p0 - uShip;
        p.x += uComp * uR * shapeF(length(s));
    }
    float e = 0.01;
    float hx = height(p0 + vec2(e, 0.0)) - height(p0 - vec2(e, 0.0));
    float hz = height(p0 + vec2(0.0, e)) - height(p0 - vec2(0.0, e));
    vSlope = length(vec2(hx, hz)) / (2.0 * e);
    vG = p0 + uFlow; vH = h; vW = vec3(p.x, h, p.y);
    vEdge = max(abs(in_uv.x), abs(in_uv.y));
    gl_Position = uMVP * vec4(p.x, h, p.y, 1.0);
}
"""

GRID_FS = r"""
#version 430
in vec2 vG; in float vH; in float vEdge; in vec3 vW; in float vSlope;
uniform float uCell; uniform float uLineW; uniform float uAmt; uniform float uFill;
uniform vec3 uColFlat; uniform vec3 uColNeg; uniform vec3 uColPos; uniform float uHueH;
uniform vec3 uEye; uniform float uFogNear; uniform float uFogFar; uniform float uMinor;
out vec4 fragColor;
float gridLine(vec2 g, float w){
    vec2 fw = fwidth(g);
    vec2 d = abs(fract(g - 0.5) - 0.5) / max(fw, 1e-5);
    vec2 l = 1.0 - smoothstep(w * 0.5, w * 0.5 + 1.0, d);
    // 远处线太密时淡出，避免摩尔纹
    vec2 fade = 1.0 - smoothstep(0.25, 0.6, fw);
    return max(l.x * fade.x, l.y * fade.y);
}
void main(){
    vec2 g = vG / uCell;
    float major = gridLine(g, uLineW);
    float minor = uMinor > 0.0 ? gridLine(g * 4.0, uLineW * 0.6) * uMinor : 0.0;
    float k = clamp(vH / uHueH, -1.0, 1.0);
    vec3 c = k < 0.0 ? mix(uColFlat, uColNeg, -k) : mix(uColFlat, uColPos, k);
    float lift = 1.0 + 1.8 * abs(k) + 0.25 * vSlope;
    float dist = length(vW - uEye);
    float fog = 1.0 - smoothstep(uFogNear, uFogFar, dist);
    float edge = 1.0 - smoothstep(0.75, 1.0, vEdge);
    float a = (major + minor * 0.5) * lift + uFill * (0.4 + 0.6 * abs(k)) * (0.6 + 0.4 * vSlope);
    fragColor = vec4(c * a * fog * edge * uAmt, 1.0);
}
"""


class Grid:
    def __init__(self, e, n=420):
        self.e = e
        ctx = e.ctx
        if not hasattr(e, "_wd_grid_prog"):
            e._wd_grid_prog = ctx.program(vertex_shader=GRID_VS, fragment_shader=GRID_FS)
        self.prog = e._wd_grid_prog
        u = np.linspace(-1, 1, n, dtype=np.float32)
        X, Z = np.meshgrid(u, u)
        verts = np.stack([X.ravel(), Z.ravel()], 1).astype("f4")
        i = np.arange(n * n, dtype=np.int32).reshape(n, n)
        a, b, c, d = i[:-1, :-1].ravel(), i[:-1, 1:].ravel(), i[1:, :-1].ravel(), i[1:, 1:].ravel()
        idx = np.stack([a, b, c, b, d, c], 1).ravel().astype("i4")
        self.vbo = ctx.buffer(verts.tobytes())
        self.ibo = ctx.buffer(idx.tobytes())
        self.vao = ctx.vertex_array(self.prog, [(self.vbo, "2f", "in_uv")], index_buffer=self.ibo, index_element_size=4)

    def draw(self, cam, L=12.0, center=(0.0, 0.0), cell=0.6, line_w=1.3, amt=1.0, fill=0.06, minor=0.0,
             wells=(), ship=(0.0, 0.0), R=1.6, sigma=3.0, york=0.0, comp=0.0, well_f=0.0, well_b=0.0, well_s=2.0,
             ripple=0.0, rip_c=(0.0, 0.0), rip_k=3.0, rip_phase=0.0, wave=0.0, yscale=1.0,
             col_flat=(0.2, 0.55, 1.0), col_neg=(0.25, 0.8, 1.0), col_pos=(1.0, 0.35, 0.2), hue_h=1.0,
             fog=(10.0, 30.0), time=0.0, flow=(0.0, 0.0)):
        if amt <= 0.001:
            return
        Wl = np.zeros((4, 4), np.float32)
        for k, w in enumerate(wells[:4]):
            Wl[k] = w
        e = self.e
        u = dict(uMVP=cam.mvp(), uL=float(L), uCenter=tuple(center), uWells=Wl.ravel(), uNW=len(wells[:4]),
                 uShip=tuple(ship), uR=float(R), uSig=float(sigma), uYork=float(york), uComp=float(comp),
                 uWellF=float(well_f), uWellB=float(well_b), uWellS=float(well_s), uRipple=float(ripple),
                 uRipC=tuple(rip_c), uRipK=float(rip_k), uRipPhase=float(rip_phase), uWave=float(wave),
                 uTime=float(time), uYScale=float(yscale), uCell=float(cell), uLineW=float(line_w), uAmt=float(amt),
                 uFill=float(fill), uColFlat=tuple(col_flat), uColNeg=tuple(col_neg), uColPos=tuple(col_pos),
                 uHueH=float(hue_h), uEye=tuple(float(v) for v in cam.eye), uFogNear=float(fog[0]),
                 uFogFar=float(fog[1]), uMinor=float(minor), uFlow=tuple(float(f) for f in flow))
        e.set_u(self.prog, u)
        e._blend("add")
        self.vao.render(moderngl.TRIANGLES)

    def height(self, x, z, wells=(), ship=(0.0, 0.0), R=1.6, sigma=3.0, york=0.0, well_f=0.0, well_b=0.0,
               well_s=2.0, yscale=1.0, **_):
        """与顶点着色器同一公式的 CPU 版（只含常用项），用于把飞船/标注放到膜面上。"""
        h = 0.0
        for (wx, wz, dep, wd) in wells:
            h -= dep / np.sqrt(1 + ((x - wx) ** 2 + (z - wz) ** 2) / wd ** 2)
        sx, sz = x - ship[0], z - ship[1]
        rs = max(np.hypot(sx, sz), 1e-4)
        if york:
            a, b = 1 / np.cosh(sigma * (rs + R)), 1 / np.cosh(sigma * (rs - R))
            dfd = sigma * (a * a - b * b) / (2 * np.tanh(sigma * R))
            h += york * (sx / rs) * dfd
        if well_f or well_b:
            k = np.clip((sx / well_s + 0.25) / 0.5, 0, 1)
            k = k * k * (3 - 2 * k)
            h -= (well_b + (well_f - well_b) * k) * np.exp(-(sx * sx + sz * sz) / well_s ** 2)
        return h * yscale
