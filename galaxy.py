# -*- coding: utf-8 -*-
"""银河模型在本引擎里的实时渲染（开场导航段的主角）。

模型：Sketchfab「Free simple 3d galaxy composed of 6000 stars」，作者 caton.laubergiste，CC BY 4.0
（https://sketchfab.com/3d-models/free-simple-3d-galaxy-composed-of-6000-stars-46c390591651438abe3ccb2396d16e6b）。
另一个会话在 Blender 里给它上了色、加了程序化体积星云，导出成 blender/sketchfab_6000/viewer/data.js；
用户在交互预览页（galaxy-interactive.html）里认可了这个样子。这里的着色器照那个预览页移植：
  · 6000 颗星画成点精灵（加法混合）：白色小核心 + 很淡的彩色光晕。
  · 星云是 384×384×64 的三维纹理（R 发光、G 尘埃密度、B 玫红发射区），沿视线步进：发光按离银心的半径配色
    （核心暖橙 -> 外圈蓝紫），周期梯度噪声提供五个倍频，尘埃裂缝吸收光线。结果按"盖在上面"叠到星点上。
  · 另按原发光体积采样固定的微星，随像素覆盖连续淡入，为盘内光带提供恒星颗粒。
从盘面里面看（开场潜入太阳邻域以后）：
  · draw(clear=)：以"镜头 -> 太阳"这段视线为轴、半径 clear 的胶囊里的星云全部清掉。潜入时它从 0 长大，云雾在镜头前分开；
    到了太阳旁边，太阳就在一个清空的"本地泡"里，外面的银河盘成了绕天一圈的光带。不清掉的话近处的体素会糊成满屏白雾。
  · draw(em=)：沿盘面看时光线穿过几十个单位的星云，发光会一路叠到饱和变白，所以在里面要把发光调低。
  · make_field()：太阳周围再撒一把星（半径按对数均匀分布），缩放时每个尺度都有星从镜头边掠过（"十的次方"式的视差）。
坐标：银河自己的单位，盘面在 xy 平面、z 朝上；半径约 21（约 5 万光年，1 单位约 2400 光年）。
镜头用 GalCam（位置 + 前 / 右 / 上三个方向 + 竖直视场角），不走引擎那套 y 朝上的 Camera。
用法：
    g = Galaxy(e)
    cam = GalCam.orbit(focus, az, el, dist, fov)
    g.draw(cam, spin, stars=1.0, clouds=1.0)       # spin：银河绕 z 轴转过的角度（弧度）
    g.make_field(SUN0, 4000, r0, r1)                 # 可选：太阳周围的近邻星场，draw(field=亮度) 时画
    cam.project(p)                                  # 世界坐标 -> 屏幕像素（HUD 标注用）
数据第一次用时从 data.js 解出来，缓存成 build/galaxy_model.npz。"""
import base64
import math
import os
import re
import numpy as np
import moderngl
from opusvid.settings import W, H
from config import ROOT, BUILD

SOURCE = os.path.join(ROOT, "blender", "sketchfab_6000", "viewer", "data.js")
CACHE = os.path.join(BUILD, "galaxy_model.npz")
DIMS = (384, 384, 64)                 # 体积纹理的 x、y、z 分辨率
BOUNDS = (24.0, 24.0, 2.5)            # 体积覆盖的半宽
LY_PER_UNIT = 2400.0                  # 模型半径约 21 单位 ≈ 5 万光年


def load():
    """(星点 float32[N, 7]：位置 xyz、颜色 rgb、大小；体积 uint8[64, 384, 384, 3])。"""
    if os.path.exists(CACHE) and os.path.getmtime(CACHE) >= os.path.getmtime(SOURCE):
        d = np.load(CACHE)
        return d["stars"], d["volume"]
    s = open(SOURCE, encoding="utf-8").read()
    stars = np.frombuffer(base64.b64decode(re.search(r'stars:"([^"]+)"', s).group(1)), np.float32).reshape(-1, 7)
    vol = np.frombuffer(base64.b64decode(re.search(r'volume:"([^"]+)"', s).group(1)), np.uint8)
    vol = vol.reshape(DIMS[2], DIMS[1], DIMS[0], 3)
    np.savez(CACHE, stars=stars, volume=vol)
    return stars, vol


class GalCam:
    """银河坐标里的镜头（z 朝上）。k = 1 / tan(竖直视场角 / 2)。"""

    def __init__(self, eye, fwd, right, up, fov):
        self.eye = np.asarray(eye, np.float64)
        self.f, self.r, self.u = (np.asarray(v, np.float64) for v in (fwd, right, up))
        self.fov = fov
        self.k = 1.0 / math.tan(math.radians(fov) / 2)

    @staticmethod
    def orbit(focus, az, el, dist, fov=50.0):
        """绕 focus 的轨道镜头：方位角 az、仰角 el（弧度）、距离 dist。"""
        ce, se, ca, sa = math.cos(el), math.sin(el), math.cos(az), math.sin(az)
        f = -np.array([ce * ca, ce * sa, se])
        return GalCam(np.asarray(focus, np.float64) - f * dist, f, (-sa, ca, 0.0), (-se * ca, -se * sa, ce), fov)

    def project(self, p):
        """世界坐标 -> (屏幕 x, 屏幕 y, 深度)，在镜头后面时返回 None。"""
        d = np.asarray(p, np.float64) - self.eye
        z = float(d @ self.f)
        if z <= 1e-6:
            return None
        x = float(d @ self.r) * self.k / (W / H) / z
        y = float(d @ self.u) * self.k / z
        return ((x + 1) * 0.5 * W, (1 - y) * 0.5 * H, z)

    def uniforms(self):
        return dict(uEye=tuple(self.eye), uF=tuple(self.f), uR=tuple(self.r), uU=tuple(self.u), uK=float(self.k),
                    uAspect=float(W / H))


def spin_matrix(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], np.float32)


STAR_VS = r"""
#version 430
in vec3 in_pos; in vec3 in_col; in float in_size;
uniform vec3 uEye; uniform vec3 uF; uniform vec3 uR; uniform vec3 uU; uniform float uK; uniform float uAspect;
uniform mat3 uSpin; uniform float uH; uniform float uGain;
uniform float uRef;    // > 0 时星点亮度随距离变化：离镜头 uRef 处为 1，更远更暗（近邻星场用）
uniform vec3 uCenter;  // 近邻星场的中心（太阳）：离它比 uRef 近得多的星淡出，不然按对数撒的星会在太阳周围挤成一团
uniform float uNear;   // > 0 时离镜头不到 uNear 的星点淡出（贴着镜头掠过时不闪成大白点）
out vec3 vCol; out float vE;
void main(){
    vec3 d = uSpin * in_pos - uEye;
    float depth = dot(d, uF);
    gl_Position = depth > 0.02 ? vec4(dot(d, uR) * uK / uAspect, dot(d, uU) * uK, depth * 0.99, depth) : vec4(2.0, 2.0, 2.0, 1.0);
    // 和预览页一样：每颗星一个固定的随机亮度，少数格外亮
    float seed = fract(sin(dot(in_pos, vec3(12.9898, 78.233, 39.425))) * 43758.5453);
    vE = (0.55 + 1.6 * pow(seed, 4.0)) * uGain;
    if (uRef > 0.0) vE *= clamp(pow(uRef / max(depth, 1e-6), 0.8), 0.04, 1.6)
                          * smoothstep(0.15 * uRef, 0.5 * uRef, length(in_pos - uCenter));
    if (uNear > 0.0) vE *= smoothstep(uNear * 0.4, uNear, depth);
    gl_PointSize = clamp(in_size * uH / max(depth, 0.02) * 6.5 * uK / 1.9 + 3.0, 5.5, 16.0) * (0.85 + 0.2 * sqrt(max(vE, 0.0)));
    vCol = in_col;
}
"""

STAR_FS = r"""
#version 430
in vec3 vCol; in float vE;
out vec4 fragColor;
void main(){
    float r = length(gl_PointCoord - 0.5) * 2.0;
    if (r >= 1.0) discard;
    float core = 1.7 * exp(-r * r * 65.0);
    float halo = 0.14 * exp(-r * r * 6.0) * (1.0 - smoothstep(0.65, 1.0, r));
    vec3 light = (mix(vCol, vec3(1.0), 0.4) * core + vCol * halo) * vE;
    fragColor = vec4(vec3(1.0) - exp(-light), 1.0);
}
"""

CLOUD_FS = r"""
uniform sampler3D uField;
uniform vec3 uEye; uniform vec3 uF; uniform vec3 uR; uniform vec3 uU; uniform float uK; uniform float uAspect;
uniform mat3 uSpin; uniform float uGain; uniform float uOpacity;
uniform vec3 uSun; uniform float uClear; uniform float uEm;
in vec2 vUV; out vec4 fragColor;
// 周期梯度噪声预烘到小纹理；每个倍频按像素覆盖退回均值，避免远处闪烁。
uniform sampler3D uNoise;
uniform sampler2D uDither;
uniform float uHeight;
float noise3(vec3 p){ return texture(uNoise, p / 16.0).r * 2.0 - 1.0; }
float structure(vec3 p, float footprint, int octaves){
    float n = 0.0, amp = .58, freq = 1.0;
    for(int j=0;j<5;j++){
        if(j>=octaves) break;
        float w = 1.0-smoothstep(.20,.65, footprint*freq);
        n += amp*w*noise3(p*freq);
        freq *= 2.73; amp *= .63;
    }
    return n;
}
// 发光的颜色按离银心的半径：核心暖橙 -> 粉 -> 紫 -> 外圈蓝
vec3 colorAt(float r){
    vec3 a = vec3(1, .76, .55), b = vec3(.8, .47, .36), c = vec3(.54, .42, .61), d = vec3(.38, .47, .74), e = vec3(.19, .32, .63);
    float t = r / 19.;
    if (t < .18) return mix(a, b, t / .18);
    if (t < .4) return mix(b, c, (t - .18) / .22);
    if (t < .65) return mix(c, d, (t - .4) / .25);
    return mix(d, e, clamp((t - .65) / .35, 0., 1.));
}
void main(){
    vec2 q = vUV * 2.0 - 1.0;
    vec3 rdw = normalize(uF + uR * q.x * uAspect / uK + uU * q.y / uK);
    // 换到银河自己的坐标里（银河绕 z 轴转了 uSpin）
    mat3 back = transpose(uSpin);
    vec3 eye = back * uEye, rd = back * rdw;
    vec3 bounds = vec3(24, 24, 2.5);
    vec3 t0 = (-bounds - eye) / rd, t1 = (bounds - eye) / rd;
    vec3 nearv = min(t0, t1), farv = max(t0, t1);
    float lo = max(max(nearv.x, nearv.y), nearv.z), hi = min(min(farv.x, farv.y), farv.z);
    if (hi <= max(lo, 0.0)){ fragColor = vec4(0); return; }
    lo = max(lo, 0.0);
    // 固定区间上限加连续步长；取消按镜头半径切换步数造成的跳变。
    float stepSize = max((hi-lo)/256.0, .055);
    vec3 sa = uSun - eye;
    vec3 light = vec3(0); float trans = 1.0;
    float pix = 2.0 / (uK * uHeight);
    float travel = lo;
    for (int i = 0; i < 256; i++){
        if(travel >= hi) break;
        float ds = min(stepSize, hi-travel);
        // 高频蓝噪声抖动打散步进条带，不使用时间或历史帧。
        float jitter = texelFetch(uDither, ivec2(gl_FragCoord.xy) % 128, 0).r;
        vec3 p = eye + rd * (travel + jitter*ds);
        travel += ds;
        vec3 tc = p / (bounds * 2.0) + 0.5;
        vec3 v = texture(uField, tc).rgb;
        if(max(v.r,v.g) < .001) continue;
        float footprint = max(length(p-eye)*pix, .0001);
        float radius = length(p.xy);
        // 连续扭转坐标沿旋臂拉长，细节属于银河而不是屏幕。
        float twist = .7*log(max(radius,.15));
        mat2 turn = mat2(cos(twist),sin(twist),-sin(twist),cos(twist));
        vec2 xy = turn*p.xy;
        vec3 coord = vec3(xy, p.z*2.5);
        float warp = noise3(coord*.7);
        float n = structure(coord*3.2 + vec3(warp*.9), footprint*8.0, 5);
        float fil = structure(vec3(xy*2.1,p.z*3.5)+vec3(warp),footprint*3.5, 3);
        float detail = smoothstep(-.34,.42,n);
        float em = exp(v.r*log(17.0))-1.0;
        em *= mix(1.0, .13+2.0*detail*detail, smoothstep(1.0,4.0,radius));
        // 薄而不透明的裂缝保留到盘内；吸收同时削弱本层发光，避免前景雾填平暗隙。
        float crack = smoothstep(.025,.20,fil + .25*n);
        float den = v.g*4.0*(.5+2.4*crack);
        float local = 1.0-smoothstep(12.0,38.0,length(eye));
        den += local * (1.0-exp(-em*3.0))*crack*4.0;
        em *= exp(-crack*(.5+local*1.2));
        if (uClear > 0.0){                                // 视线胶囊里的星云清掉（见模块说明）
            float h = clamp(dot(p - eye, sa) / max(dot(sa, sa), 1e-8), 0., 1.);
            float w = smoothstep(uClear * 0.45, uClear, length(p - eye - sa * h));
            em *= w; den *= w;
        }
        em *= uEm;
        light += trans * mix(colorAt(length(p.xy)), vec3(.95, .18, .36), v.b * .65) * em * ds;
        trans *= exp(-den * ds);
        if (trans < .015) break;
    }
    // 按亮度整体压缩而非逐通道饱和，暖金色银核不会被压成纯白。
    float peak = max(max(light.r,light.g),light.b);
    light *= (1.0-exp(-peak*1.3))/max(peak,1e-6);
    light = pow(max(light,vec3(0)),vec3(.92));
    float a = min(1. - trans, .85) * uOpacity;
    fragColor = vec4(light * uGain * uOpacity, a);
}
"""


MIST_STAR_VS = r"""
#version 430
in vec3 in_pos; in float in_energy;
uniform vec3 uEye; uniform vec3 uF; uniform vec3 uR; uniform vec3 uU;
uniform float uK; uniform float uAspect; uniform mat3 uSpin;
uniform float uGain; uniform float uH;
out float vEnergy;
void main(){
    vec3 d=uSpin*in_pos-uEye;
    float z=dot(d,uF);
    gl_Position=z>.02 ? vec4(dot(d,uR)*uK/uAspect,dot(d,uU)*uK,z*.99,z) : vec4(2,2,2,1);
    // 亚像素恒星的总通量随投影面积变化，淡入连续，尺寸固定防止长出光晕。
    float cover=.0025*uH*uK/max(z,.02);
    vEnergy=in_energy*uGain*smoothstep(.08,.7,cover)*min(1.0,cover*cover)*smoothstep(.05,.3,z);
    gl_PointSize=1.7;
}
"""
MIST_STAR_FS = r"""
#version 430
in float vEnergy; out vec4 fragColor;
void main(){
    vec2 q=gl_PointCoord*2.0-1.0;
    float kernel=max(0.0,1.0-dot(q,q));
    fragColor=vec4(vec3(.82,.84,1.0)*vEnergy*kernel,1.0);
}
"""


def unresolved_stars(vol, count=650000):
    """按原体积发光采样固定微星；不移动原模型的 6000 颗星。"""
    rng = np.random.default_rng(73021)
    weight = np.expm1(vol[..., 0].astype(np.float64)/255*np.log(17))
    cdf = np.cumsum(weight.ravel())
    indices = np.searchsorted(cdf, rng.random(count)*cdf[-1])
    z, y, x = np.unravel_index(indices, vol.shape[:3])
    points = (np.column_stack((x,y,z))+rng.random((count,3))) / np.array(DIMS)
    points = (points-.5)*np.array(BOUNDS)*2
    energy = .25+rng.power(.7,count)*1.8
    return np.column_stack((points, energy)).astype(np.float32)


def detail_volume():
    """固定种子的周期梯度噪声；只在创建银河时生成 128³ 单通道纹理。"""
    size, cells = 128, 16
    rng = np.random.default_rng(17026)
    gradients = rng.normal(size=(cells, cells, cells, 3)).astype(np.float32)
    gradients /= np.linalg.norm(gradients, axis=-1, keepdims=True)
    z, y, x = np.indices((size, size, size), dtype=np.float32) / (size / cells)
    coords = (x, y, z)
    base = [c.astype(np.int32) for c in coords]
    frac = [c-b for c, b in zip(coords, base)]
    fade = [f*f*f*(f*(f*6-15)+10) for f in frac]
    out = np.zeros((size, size, size), np.float32)
    for dz in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                g = gradients[(base[2]+dz) % cells, (base[1]+dy) % cells, (base[0]+dx) % cells]
                dot = sum(g[..., k]*(frac[k]-d) for k, d in enumerate((dx, dy, dz)))
                weight = np.ones_like(out)
                for k, d in enumerate((dx, dy, dz)):
                    weight *= fade[k] if d else 1-fade[k]
                out += weight*dot
    return np.clip(out*.85+.5, 0, 1).astype(np.float32)


class Galaxy:
    def __init__(self, e):
        self.e = e
        ctx = e.ctx
        stars, vol = load()
        self.n = len(stars)
        if not hasattr(e, "_gal_star_prog"):
            e._gal_star_prog = ctx.program(vertex_shader=STAR_VS, fragment_shader=STAR_FS)
        self.prog = e._gal_star_prog
        self.vbo = ctx.buffer(np.ascontiguousarray(stars, np.float32).tobytes())
        self.vao = ctx.vertex_array(self.prog, [(self.vbo, "3f 3f 1f", "in_pos", "in_col", "in_size")])
        self.tex = ctx.texture3d(DIMS, 3, np.ascontiguousarray(vol).tobytes(), dtype="f1")
        self.tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.tex.repeat_x = self.tex.repeat_y = self.tex.repeat_z = False
        self.noise = ctx.texture3d((128, 128, 128), 1, detail_volume().tobytes(), dtype="f4")
        self.noise.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.noise.repeat_x = self.noise.repeat_y = self.noise.repeat_z = True
        # 固定高通噪声秩变换成均匀分布，避免规则抖动的斜纹。
        rng = np.random.default_rng(1931)
        white = rng.normal(size=(128, 128))
        fy, fx = np.meshgrid(np.fft.fftfreq(128), np.fft.fftfreq(128), indexing="ij")
        blue = np.fft.ifft2(np.fft.fft2(white)*np.sqrt(fx*fx+fy*fy)).real
        ranks = np.argsort(np.argsort(blue.ravel())).reshape(128, 128)
        dither = ((ranks+.5)/16384).astype(np.float32)
        self.dither = ctx.texture((128, 128), 1, dither.tobytes(), dtype="f4")
        self.mist_prog = ctx.program(vertex_shader=MIST_STAR_VS, fragment_shader=MIST_STAR_FS)
        mist = unresolved_stars(vol)
        self.mist_vbo = ctx.buffer(mist.tobytes())
        self.mist_vao = ctx.vertex_array(self.mist_prog, [(self.mist_vbo, "3f 1f", "in_pos", "in_energy")])
        self.mist_n = len(mist)
        self.fvao, self.sun = None, np.zeros(3)

    def make_field(self, center, n, r0, r1, seed=7):
        """center（未旋转的模型坐标）周围撒 n 颗星：距离在 r0..r1 之间按对数均匀，离盘面远的压扁到盘的厚度里。"""
        rng = np.random.default_rng(seed)
        d = rng.normal(size=(n, 3))
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        r = np.exp(rng.uniform(math.log(r0), math.log(r1), n))
        p = d * r[:, None]
        p[:, 2] *= np.minimum(1.0, 0.25 / r)
        # 颜色：多数偏白和偏橙，少数偏蓝（大致按真实恒星的比例）
        pal = np.array([(1.0, 0.95, 0.88), (1.0, 0.82, 0.62), (1.0, 0.66, 0.48), (0.78, 0.86, 1.0)])
        col = pal[rng.choice(4, n, p=(0.35, 0.3, 0.25, 0.1))]
        data = np.concatenate([p + np.asarray(center), col, np.zeros((n, 1))], 1).astype(np.float32)
        self.fbo = self.e.ctx.buffer(data.tobytes())
        self.fvao = self.e.ctx.vertex_array(self.prog, [(self.fbo, "3f 3f 1f", "in_pos", "in_col", "in_size")])
        self.fn, self.sun = n, np.asarray(center, np.float64)

    def draw(self, cam, spin=0.0, stars=1.0, clouds=1.0, opacity=1.0, clear=0.0, em=1.0, field=0.0, near=0.0):
        """先加法画星点，再把星云体积"盖"上去。stars / clouds：亮度；opacity：整体不透明度（淡入淡出用）；
        clear / em：见模块说明（clear 的胶囊以 make_field 的中心为太阳）；field：近邻星场的亮度；
        near：离镜头不到这个距离的银河星点淡出。"""
        e = self.e
        rot = spin_matrix(spin)
        u = cam.uniforms()
        if stars * opacity > 0.002:
            e.set_u(self.prog, dict(u, uSpin=rot, uH=float(H), uGain=float(stars * opacity), uRef=0.0, uNear=float(near)))
            e._blend("add")
            self.vao.render(moderngl.POINTS, vertices=self.n)
        if clouds * opacity > .002:
            e.set_u(self.mist_prog, dict(u, uSpin=rot, uH=float(H), uGain=float(clouds*opacity*.12)))
            e._blend("add")
            self.mist_vao.render(moderngl.POINTS, vertices=self.mist_n)
        if self.fvao is not None and field * opacity > 0.002:
            ref = float(np.linalg.norm(cam.eye - spin_matrix(spin) @ self.sun))
            e.set_u(self.prog, dict(u, uSpin=rot, uH=float(H), uGain=float(field * opacity), uRef=ref, uNear=0.0,
                                    uCenter=tuple(self.sun)))
            e._blend("add")
            self.fvao.render(moderngl.POINTS, vertices=self.fn)
        if clouds * opacity > 0.002:
            e.draw_fs("gal_cloud", CLOUD_FS, dict(u, uSpin=rot, uGain=float(clouds), uOpacity=float(opacity),
                                                  uSun=tuple(self.sun), uClear=float(clear), uEm=float(em), uHeight=float(H)),
                      dict(uField=self.tex, uNoise=self.noise, uDither=self.dither), blend="over")
