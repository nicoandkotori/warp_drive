# -*- coding: utf-8 -*-
"""opusvid.scene — 场景基类、通用 UI 组件（章节卡、标注、大字标题、坐标轴）、饼图/暗角着色器、屏幕空间粒子。"""
import math
import numpy as np
from .gl import (Camera, ease_out, ease_in_out, ease_out_expo, smooth, lin, rot_x, rot_y, rot_z,
                 translate, scale_m, W, H)


GOLD = (1.0, 0.78, 0.42)        # 普通物质 / 光
VIOLET = (0.62, 0.42, 1.0)      # 暗物质
CYAN = (0.30, 0.85, 1.0)        # 暗能量
PINK = (1.0, 0.36, 0.62)
WHITE = (1.0, 1.0, 1.0)
ORANGE = (1.0, 0.55, 0.25)
RED = (1.0, 0.25, 0.22)


PIE_FS = r"""
// 饼图/环形图（像素坐标左上为原点；角度 0=正上方，顺时针）
uniform vec2 uCenter; uniform float uR0; uniform float uR1;
uniform vec4 uEdges;          // 累计比例 e0..e3
uniform vec3 uCol0; uniform vec3 uCol1; uniform vec3 uCol2;
uniform vec3 uFill;           // 各扇区扫过的比例
uniform vec3 uSwirl;          // 各扇区"暗旋涡"风格程度
uniform vec3 uAmt;            // 各扇区亮度
uniform float uGap; uniform float uRim;
in vec2 vUV; out vec4 fragColor;
vec3 sectorCol(int k){ return k == 0 ? uCol0 : (k == 1 ? uCol1 : uCol2); }
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    vec2 d = P - uCenter;
    float r = length(d);
    float ang = atan(d.x, -d.y); if (ang < 0.0) ang += TAU;
    float fr = ang / TAU;
    vec3 col = vec3(0);
    for (int k = 0; k < 3; k++){
        float a0 = uEdges[k], a1 = uEdges[k + 1];
        if (a1 <= a0) continue;
        float fill = uFill[k];
        float am = uAmt[k];
        if (fill <= 0.0 || am <= 0.0) continue;
        float end = a0 + (a1 - a0) * fill;
        float g = uGap / TAU;
        float inA = smoothstep(a0 + g - 0.0008, a0 + g + 0.0008, fr) * (1.0 - smoothstep(end - g - 0.0008, end - g + 0.0008, fr));
        if (inA <= 0.0) continue;
        float inR = smoothstep(uR0 - 0.8, uR0 + 0.8, r) * (1.0 - smoothstep(uR1 - 0.8, uR1 + 0.8, r));
        vec3 c = sectorCol(k);
        float rr = (r - uR0) / max(uR1 - uR0, 1.0);
        vec2 q = rot2(uTime * 0.04 + (1.0 - r / uR1) * 2.5) * (d / uR1);
        float n = fbm2(q * 2.6 + float(k) * 7.0 + uTime * 0.05, 5);
        float n2 = fbm2(q * 5.0 - uTime * 0.03 + 4.0, 4);
        vec3 solid = c * (0.45 + 0.55 * rr + 0.35 * (n - 0.5));
        vec3 dark = mix(vec3(0.03, 0.01, 0.09), vec3(0.3, 0.16, 0.7), pow(n, 2.3)) * (0.35 + n2) + vec3(0.5, 0.3, 1.0) * pow(n * n2, 3.0) * 2.2;
        vec3 body = mix(solid, dark, uSwirl[k]);
        float rim = exp(-abs(r - uR1) / 1.6) + exp(-abs(r - uR0) / 1.6) * step(1.0, uR0);
        float glowOut = exp(-max(r - uR1, 0.0) / 8.0) * step(uR1, r) * 0.3;
        col += (body * inR + c * rim * uRim + c * glowOut * (1.0 - uSwirl[k] * 0.6)) * inA * am;
    }
    fragColor = vec4(col, 1.0);
}
"""


DARKSPOT_FS = r"""
uniform vec2 uCenter; uniform vec2 uSize; uniform float uAmt;
in vec2 vUV; out vec4 fragColor;
void main(){
    vec2 P = vec2(vUV.x, 1.0 - vUV.y) * uRes;
    vec2 d = (P - uCenter) / uSize;
    float g = exp(-dot(d, d));
    fragColor = vec4(vec3(uAmt * g), 1.0);
}
"""


SPRITE_BODY = r"""
uniform float uBright; uniform float uReveal;
void main(){
    float k = smoothstep(in_col.a, in_col.a + 0.12, uReveal);
    emit2(in_pos, vec4(in_col.rgb * k, 1.0) * uBright, in_extra.x, in_extra.y, in_extra.z, in_extra.w);
}
"""


class ScreenCam:
    """像素坐标（左上原点）的正交相机，配合粒子着色器使用。"""
    pix = 1.0

    def mvp(self, model=None):
        m = np.array([[2.0 / W, 0, 0, -1], [0, -2.0 / H, 0, 1], [0, 0, 0.001, 0], [0, 0, 0, 1]], dtype=np.float32)
        return m if model is None else (m @ model).astype(np.float32)


SIMPLE_BODY = r"""
uniform float uBright;
void main(){ emit2(in_pos, in_col * uBright, in_extra.x, in_extra.y, in_extra.z, 1.0); }
"""


class Scene:
    chapter = None
    chapters = {}          # 项目设置：{段落id: (编号, 中文标题, 英文标题)}
    kind_in = 0

    def __init__(self, eng, sec, beats):
        self.eng = eng
        self.sec = sec
        self.id = sec["id"]
        self.t0 = sec["start"]
        self.t1 = sec["end"]
        self.lines = {l["id"]: l for l in sec["lines"]}
        self.beats = beats
        self.setup()

    def setup(self):
        """子类覆盖：一次性准备粒子、相机路径、卡点时间等。render(t) 必须只依赖 t（可任意跳帧、分段并行渲染）。"""

    # 时间工具
    def ls(self, lid):
        return self.lines[lid]["start"]

    def le(self, lid):
        return self.lines[lid]["end"]

    def w(self, lid, sub, end=False):
        L = self.lines[lid]
        txt, idx = "", []
        for k, wd in enumerate(L["words"]):
            txt += wd["text"]
            idx += [k] * len(wd["text"])
        i = txt.find(sub)
        assert i >= 0, (lid, sub, txt)
        if end:
            return L["words"][idx[i + len(sub) - 1]]["end"]
        return L["words"][idx[i]]["start"]

    def accent_times(self, kinds=None):
        return [a["t"] for a in self.beats["accents"] if (kinds is None or a["kind"] in kinds)
                and self.t0 - 0.5 <= a["t"] <= self.t1 + 0.5]

    def render(self, t):
        raise NotImplementedError

    def post(self, t):
        return {}

    # ---------------------------------------------------------- UI widgets
    def chapter_card(self, t, dur=None):
        """章节卡：段落开头一小节。返回卡片可见度（用于压暗背景）。"""
        if self.chapter is None:
            return 0.0
        num, cn, en = self.chapters[self.id]
        e = self.eng
        t0 = self.t0
        dur = dur or (self.lines[next(iter(self.lines))]["start"] - t0 - 0.15)
        tout = t0 + dur - 0.45
        lt = t - t0
        vis = smooth(-0.1, 0.4, lt) * (1 - smooth(tout - t0, tout - t0 + 0.5, lt))
        if vis > 0.001:
            cx, cy = W / 2, H / 2
            e.draw_fs("darkspot", DARKSPOT_FS, dict(uCenter=(cx, cy), uSize=(700.0, 260.0), uAmt=0.8 * vis), blend="darken")
            e.text(num, cx, cy - 110, 120, "latin", WHITE, 0.95, "mm", 0.08, 1.4, t=t, start=t0 + 0.02, dur=0.7,
                   stagger=0.08, kind="blur", out=tout, out_dur=0.45, style="outline")
            lw = 380 * ease_out_expo(lin(t0 + 0.1, t0 + 0.9, t)) * (1 - ease_in_out(lin(tout, tout + 0.45, t)))
            if lw > 1:
                e.line([(cx - lw, cy - 22), (cx + lw, cy - 22)], 1.4, GOLD, 0.8, glow=0.6, intensity=1.6)
            e.text(cn, cx, cy + 46, 76, "serif_m", WHITE, 1.0, "mm", 0.18, 1.3, t=t, start=t0 + 0.2, dur=0.7,
                   stagger=0.07, kind="rise", out=tout, out_dur=0.45)
            e.text(en, cx, cy + 118, 22, "latin", (0.8, 0.85, 1.0), 0.8, "mm", 0.55, 1.0, t=t, start=t0 + 0.5, dur=0.8,
                   stagger=0.015, kind="spread", out=tout, out_dur=0.45)
        # 角标
        ca = smooth(tout, tout + 0.8, t) * (1 - smooth(self.t1 - 0.8, self.t1 - 0.2, t))
        if ca > 0.001:
            e.text(num, 70, 62, 30, "latin_m", GOLD, 0.85 * ca, "lm", 0.05, 1.2)
            e.line([(118, 50), (118, 74)], 1.2, WHITE, 0.4 * ca)
            e.text(cn, 134, 62, 25, "sans_m", WHITE, 0.8 * ca, "lm", 0.15, 1.0)
        return vis

    def label(self, t, start, x, y, text, sub=None, color=WHITE, anchor_pt=None, out=None, size=34, side="r",
              font="sans_m", sub_size=18, line_color=None):
        e = self.eng
        if t < start:
            return
        a = ease_out(lin(start, start + 0.6, t))
        if out is not None:
            a *= 1 - ease_in_out(lin(out, out + 0.5, t))
        if a <= 0.001:
            return
        if anchor_pt is not None:
            ax, ay = anchor_pt
            p = ease_out_expo(lin(start, start + 0.7, t))
            mx = x - (14 if side == "r" else -14)
            pts = [(ax, ay), (ax + (mx - ax) * 0.55, y), (mx, y)]
            e.line(pts, 1.3, line_color or color, 0.75 * a, glow=0.4, progress=p, intensity=1.3)
            e.circle(ax, ay, 3.5, fill=line_color or color, fill_a=a, glow=3.0, intensity=1.6)
        anc = "lm" if side == "r" else "rm"
        e.text(text, x, y - (12 if sub else 0), size, font, color, a, anc, 0.06, 1.25, t=t, start=start + 0.1, dur=0.5,
               stagger=0.03, kind="rise", out=out, out_dur=0.4)
        if sub:
            e.text(sub, x, y + size * 0.62, sub_size, "latin", (0.78, 0.82, 0.92), 0.85 * a, anc, 0.3, 1.0, t=t,
                   start=start + 0.3, dur=0.6, stagger=0.01, kind="spread", out=out, out_dur=0.4)

    def big_term(self, t, start, cn, en, color, out=None, y=H / 2, size=150, sub_y=None):
        e = self.eng
        if t < start - 0.05:
            return 0.0
        a = 1.0
        if out is not None:
            a = 1 - ease_in_out(lin(out, out + 0.6, t))
        if a <= 0.001:
            return 0.0
        e.draw_fs("darkspot", DARKSPOT_FS, dict(uCenter=(W / 2, y + 20), uSize=(560.0, 230.0),
                                                uAmt=0.75 * a * smooth(start - 0.1, start + 0.4, t)), blend="darken")
        e.text(cn, W / 2, y, size, "serif", color, a, "mm", 0.12, 2.2, t=t, start=start, dur=0.55, stagger=0.09,
               kind="blur")
        e.text(cn, W / 2, y, size, "serif", WHITE, a * 0.9, "mm", 0.12, 1.2, t=t, start=start + 0.05, dur=0.55,
               stagger=0.09, kind="blur")
        e.text(en, W / 2, (sub_y or y + size * 0.72), 26, "latin", color, a * 0.95, "mm", 0.6, 1.6, t=t,
               start=start + 0.35, dur=0.9, stagger=0.02, kind="spread")
        return a

    def axes(self, t, start, x0, y0, w, h, xl, yl, out=None, color=(0.75, 0.8, 0.9)):
        e = self.eng
        if t < start:
            return 0.0
        a = ease_out(lin(start, start + 0.5, t))
        if out is not None:
            a *= 1 - ease_in_out(lin(out, out + 0.5, t))
        if a <= 0.001:
            return 0.0
        p = ease_out_expo(lin(start, start + 0.9, t))
        e.rect(x0 - 40, y0 - 30, w + 80, h + 90, 14, fill=(0.01, 0.015, 0.04), fill_a=0.55 * a,
               stroke=(0.5, 0.6, 0.9), stroke_w=1.0 * a)
        e.line([(x0, y0 + h), (x0 + w * p, y0 + h)], 1.6, color, a, intensity=1.2)
        e.line([(x0, y0 + h), (x0, y0 + h - h * p)], 1.6, color, a, intensity=1.2)
        e.line([(x0 + w * p - 9, y0 + h - 5), (x0 + w * p, y0 + h), (x0 + w * p - 9, y0 + h + 5)], 1.6, color, a * p)
        e.line([(x0 - 5, y0 + h - h * p + 9), (x0, y0 + h - h * p), (x0 + 5, y0 + h - h * p + 9)], 1.6, color, a * p)
        e.text(xl, x0 + w, y0 + h + 32, 22, "sans", color, a * 0.9, "rm", 0.05, 1.1)
        e.text(yl, x0 + 14, y0 - 4, 22, "sans", color, a * 0.9, "lm", 0.05, 1.1)
        return a

