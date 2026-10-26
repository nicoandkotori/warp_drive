# -*- coding: utf-8 -*-
"""opusvid.mathtex — 数学公式排版与动画。

排版用 matplotlib mathtext（Computer Modern 字体，与 LaTeX 同款），得到每个符号的字形与精确位置，
再逐个画进 GPU 文字管线，因此可以：
  · 逐符号书写（先描轮廓、再填充，类似 3Blue1Brown 的 Write）
  · 按标签匹配做公式变形（相同标签的符号平滑移动到新位置，其余淡出/淡入）
  · 按标签高亮、发光，取任意符号的屏幕位置来挂注释

用法：
    eq = Tex(eng, [("x", "x"), "=", (r"0.\\!\\overline{9}", "rhs")], size=96)
    eq.draw(W/2, 500, anchor="=", fx=write_fx(t, start=3.0))
    morph(eng, eqA, eqB, p, (x, y, "="), (x, y2, "="), t=t)
part 可以是字符串（标签就是它本身，重复的自动加 #2、#3）或 (tex, 标签)。
"""
import math
import matplotlib
matplotlib.rcParams["mathtext.fontset"] = "cm"
from matplotlib.mathtext import MathTextParser
from matplotlib.font_manager import FontProperties
import numpy as np
from .gl import ease_out, ease_in_out, smooth

_PARSER = MathTextParser("path")
_CACHE = {}
RULE = 0.62          # 分数线/上划线粗细相对 mathtext 默认值的比例（默认偏粗）
GOLD = (1.0, 0.76, 0.36)

MACROS = {
    r"\ldots": r"\,...",                   # 用 CM 的句点拼省略号（mathtext 的 \ldots 会退回 STIX 字体）
    r"\rep9": r".\!\overline{9}",          # 循环节：0\rep9 -> 0.(9上划线)
}


def expand(tex):
    for k, v in MACROS.items():
        tex = tex.replace(k, v)
    return tex


def parse(tex, size):
    key = (tex, size)
    if key not in _CACHE:
        w, h, d, glyphs, rects = _PARSER.parse("$" + expand(tex) + "$", dpi=72, prop=FontProperties(size=size))
        _CACHE[key] = (float(w), float(h), float(d),
                       [(g[0].fname, float(g[1]), int(g[2]), float(g[4]), float(g[5])) for g in glyphs],
                       [tuple(float(v) for v in r) for r in rects])
    return _CACHE[key]


class Atom:
    __slots__ = ("kind", "font", "size", "ch", "x", "y", "w", "h", "tag", "k", "i", "g", "cx", "cy")

    def key(self):
        return (self.kind, self.font, round(self.size), self.ch, round(self.w, 1), round(self.h, 1))


class Tex:
    def __init__(self, eng, parts, size=72):
        self.eng = eng
        self.size = size
        if isinstance(parts, str):
            parts = [parts]
        seen, P = {}, []
        for p in parts:
            src, tag = (p, p) if isinstance(p, str) else p
            n = seen.get(tag, 0) + 1
            seen[tag] = n
            P.append((src, tag if n == 1 else f"{tag}#{n}"))
        self.parts = P
        self.tex = "".join(s for s, _ in P)
        w, h, d, glyphs, rects = parse(self.tex, size)
        self.w, self.h, self.d = w, h, d
        # 前缀计数：确定每个符号属于哪一段
        bounds_g, bounds_r, acc = [], [], ""
        for src, _ in P:
            acc += src
            _, _, _, g2, r2 = parse(acc, size)
            bounds_g.append(len(g2))
            bounds_r.append(len(r2))
        assert bounds_g[-1] == len(glyphs) and bounds_r[-1] == len(rects), ("part split mismatch", self.tex)
        atlas = eng.atlas
        self.atoms = []
        gi = ri = 0
        for pi, (src, tag) in enumerate(P):
            k = 0
            while gi < bounds_g[pi]:
                font, fs, code, ox, oy = glyphs[gi]
                a = Atom()
                a.kind, a.font, a.size, a.ch = "g", font, fs, chr(code)
                a.g = atlas.glyph(a.ch, font, max(4, int(round(fs))))
                a.x, a.y = ox, -oy
                a.w, a.h = a.g["w"], a.g["h"]
                a.cx = ox + a.g["x0"] + a.g["w"] / 2
                a.cy = -oy + a.g["y0"] + a.g["h"] / 2
                a.tag, a.k = tag, k
                self.atoms.append(a)
                gi += 1
                k += 1
            while ri < bounds_r[pi]:
                ox, oy, rw, rh = rects[ri]
                a = Atom()
                a.kind, a.font, a.size, a.ch, a.g = "r", None, size, None, None
                th = rh * RULE
                a.x, a.y, a.w, a.h = ox, -(oy + rh / 2) - th / 2, rw, th
                a.cx, a.cy = ox + rw / 2, a.y + th / 2
                a.tag, a.k = tag, k
                self.atoms.append(a)
                ri += 1
                k += 1
        for i, a in enumerate(self.atoms):
            a.i = i
        # 书写顺序：从左到右（按符号中心 x）
        order = sorted(range(len(self.atoms)), key=lambda i: (self.atoms[i].cx - self.atoms[i].w * 0.3))
        self.order = {i: r for r, i in enumerate(order)}

    # ---------------------------------------------------------- 几何
    def tags(self):
        return [t for _, t in self.parts]

    def group(self, tag):
        return [a for a in self.atoms if a.tag == tag]

    def tag_bbox(self, tag):
        """标签在排版坐标里的包围盒（x0, y0, x1, y1），y 向下，基线为 0。"""
        xs0, ys0, xs1, ys1 = [], [], [], []
        for a in self.group(tag):
            if a.kind == "g":
                pad = max(6, int(round(a.size) * 0.28))
                x0, y0 = a.x + a.g["x0"] + pad, a.y + a.g["y0"] + pad
                xs0.append(x0); ys0.append(y0); xs1.append(x0 + a.w - 2 * pad); ys1.append(y0 + a.h - 2 * pad)
            else:
                xs0.append(a.x); ys0.append(a.y); xs1.append(a.x + a.w); ys1.append(a.y + a.h)
        assert xs0, (self.tex, tag)
        return min(xs0), min(ys0), max(xs1), max(ys1)

    def origin(self, x, y, anchor="l", scale=1.0):
        """anchor: l/m/r 或某个标签（该标签中心对准 x，用于等号对齐）。返回排版原点的屏幕坐标。"""
        if anchor == "l":
            return x, y
        if anchor == "m":
            return x - self.w * scale / 2, y
        if anchor == "r":
            return x - self.w * scale, y
        x0, _, x1, _ = self.tag_bbox(anchor)
        return x - (x0 + x1) / 2 * scale, y

    def screen_bbox(self, tag, x, y, anchor="l", scale=1.0):
        ox, oy = self.origin(x, y, anchor, scale)
        x0, y0, x1, y1 = self.tag_bbox(tag)
        return ox + x0 * scale, oy + y0 * scale, ox + x1 * scale, oy + y1 * scale

    def anchor_pt(self, tag, x, y, anchor="l", scale=1.0, where="c"):
        x0, y0, x1, y1 = self.screen_bbox(tag, x, y, anchor, scale)
        return {"c": ((x0 + x1) / 2, (y0 + y1) / 2), "t": ((x0 + x1) / 2, y0), "b": ((x0 + x1) / 2, y1),
                "l": (x0, (y0 + y1) / 2), "r": (x1, (y0 + y1) / 2)}[where]

    # ---------------------------------------------------------- 绘制
    def draw(self, x, y, anchor="l", scale=1.0, color=(1, 1, 1), alpha=1.0, intensity=1.0, fx=None):
        """fx(atom) -> dict 或 None：a 透明度、dx/dy 位移、s 缩放、col 颜色、i 亮度、wipe 显现比例、
        outline 轮廓描边量(0..1)、glow 发光量、blur 模糊"""
        if alpha <= 0.002:
            return
        ox, oy = self.origin(x, y, anchor, scale)
        for at in self.atoms:
            r = fx(at) if fx is not None else None
            draw_atom(self.eng, at, ox, oy, scale, color, alpha, intensity, r)


def _quad(eng, g, x0, y0, w, h, col, a, blur, wipe=1.0, size=None):
    u0, v0, u1, v1 = g["u0"], g["v0"], g["u1"], g["v1"]
    if wipe < 1.0:
        pad = max(6, int(size * 0.28)) if size else 0
        gw = g["w"]
        frac = (pad + (gw - 2 * pad) * max(wipe, 0.0)) / gw
        w *= frac
        u1 = u0 + (u1 - u0) * frac
    c = (col[0], col[1], col[2], a)
    v = [(x0, y0, u0, v0), (x0 + w, y0, u1, v0), (x0, y0 + h, u0, v1), (x0 + w, y0, u1, v0),
         (x0 + w, y0 + h, u1, v1), (x0, y0 + h, u0, v1)]
    eng.dl_text.append(np.array([[px, py, u, vv, c[0], c[1], c[2], c[3], blur] for (px, py, u, vv) in v],
                                dtype=np.float32))


def draw_atom(eng, at, ox, oy, scale, color, alpha, intensity, r=None, override_xy=None, override_scale=None):
    a = alpha
    dx = dy = 0.0
    s = 1.0
    col = color
    inten = intensity
    wipe, outline, glow, blur = 1.0, 0.0, 0.0, 0.0
    if r:
        a *= r.get("a", 1.0)
        dx, dy = r.get("dx", 0.0), r.get("dy", 0.0)
        s = r.get("s", 1.0)
        col = r.get("col", col)
        inten *= r.get("i", 1.0)
        wipe = r.get("wipe", 1.0)
        outline = r.get("outline", 0.0)
        glow = r.get("glow", 0.0)
        blur = r.get("blur", 0.0)
    if a <= 0.002:
        return
    sc = (override_scale if override_scale is not None else scale) * s
    if override_xy is not None:
        cx, cy = override_xy
    else:
        cx, cy = ox + at.cx * scale, oy + at.cy * scale
    cx += dx
    cy += dy
    cc = (col[0] * inten, col[1] * inten, col[2] * inten)
    if at.kind == "r":
        w, h = at.w * sc * max(wipe, 0.0), at.h * sc
        if w > 0.3:
            x0 = cx - at.w * sc / 2
            if glow > 0:
                gc = r.get("glow_col", GOLD) if r else GOLD
                eng.line([(x0, cy), (x0 + w, cy)], h, gc, a * glow * 0.35, glow=0.8, glow_w=h * 1.2 + 3, intensity=1.5)
            eng.rect(x0, cy - h / 2, w, h, radius=min(h / 2, 2.0), fill=cc, fill_a=a)
        return
    g = at.g
    gw, gh = g["w"] * sc, g["h"] * sc
    x0, y0 = cx - gw / 2, cy - gh / 2
    if glow > 0:
        gc = r.get("glow_col", GOLD) if r else GOLD
        gi = r.get("glow_i", 2.4) if r else 2.4
        # 小半径模糊 + 高亮度，大范围光晕交给泛光（大半径采样会出现重影）
        _quad(eng, g, x0, y0, gw, gh, (gc[0] * gi, gc[1] * gi, gc[2] * gi), a * glow, min(at.size * 0.04, 5.0) + 1.5)
    if outline > 0.001:
        go = eng.atlas.glyph(at.ch, at.font, max(4, int(round(at.size))), "outline")
        ow, oh = go["w"] * sc, go["h"] * sc
        _quad(eng, go, cx - ow / 2, cy - oh / 2, ow, oh, cc, a * outline, blur, wipe, at.size)
    fill_a = a * (1.0 - outline) if wipe >= 1.0 else 0.0
    if fill_a > 0.002:
        _quad(eng, g, x0, y0, gw, gh, cc, fill_a, blur)


# ---------------------------------------------------------- 动画效果（fx 构造器）
def write_fx(t, start, dur=0.55, stagger=0.06, tex=None, tags=None, out=None, out_dur=0.4):
    """逐符号书写：先沿轮廓描出，再填充。tags 限定只书写这些标签（其余不显示）。
    start 也可以是 {标签: 开始时间}：各段分别在自己的时刻开始书写（没列出的标签不显示）。"""
    first = {}
    if isinstance(start, dict) and tex is not None:
        for a in tex.atoms:
            r = tex.order[a.i]
            first[a.tag] = min(first.get(a.tag, r), r)

    def fx(at):
        if tags is not None and at.tag not in tags:
            return dict(a=0.0)
        rank = tex.order[at.i] if tex is not None else at.i
        if isinstance(start, dict):
            if at.tag not in start:
                return dict(a=0.0)
            st = start[at.tag]
            rank -= first.get(at.tag, 0)
        else:
            st = start
        p = (t - st - rank * stagger) / dur
        if p <= 0:
            return dict(a=0.0)
        r = {}
        if p < 1:
            r["wipe"] = min(1.0, p / 0.6) if at.kind == "g" else ease_out(p / 0.8)
            if at.kind == "g":
                r["outline"] = 1.0 - smooth(0.45, 1.0, p)
                if p > 0.6:
                    r["wipe"] = 1.0
            r["i"] = 1.0 + 0.5 * math.sin(min(p, 1.0) * math.pi)
        if out is not None and t > out:
            q = ease_in_out((t - out - rank * stagger * 0.4) / out_dur)
            r["a"] = r.get("a", 1.0) * (1 - q)
            r["blur"] = q * 6
        return r
    return fx


def highlight_fx(t, tags, start, end=None, color=GOLD, glow=0.0, ramp=0.35, pulse=0.0):
    """把指定标签染成强调色（可带发光）。pulse>0 时在 start 处闪一下。"""
    tags = set(tags)

    def fx(at):
        if at.tag not in tags:
            return None
        m = smooth(start, start + ramp, t)
        if end is not None:
            m *= 1 - smooth(end, end + ramp, t)
        if m <= 0.001:
            return None
        bump = pulse * math.exp(-max(t - start, 0.0) / 0.35) if t >= start else 0.0
        return dict(col=mix3((1, 1, 1), color, m), i=1.0 + 0.35 * m + bump, glow=glow * m + bump * 0.6)
    return fx


def combine(*fxs):
    """组合多个 fx：透明度相乘、位移相加，颜色/发光取后者。"""
    fxs = [f for f in fxs if f is not None]

    def fx(at):
        out = None
        for f in fxs:
            r = f(at)
            if not r:
                continue
            if out is None:
                out = dict(r)
                continue
            for k, v in r.items():
                if k == "a":
                    out["a"] = out.get("a", 1.0) * v
                elif k == "i":
                    out["i"] = out.get("i", 1.0) * v
                elif k in ("dx", "dy"):
                    out[k] = out.get(k, 0.0) + v
                elif k == "s":
                    out["s"] = out.get("s", 1.0) * v
                elif k in ("glow", "outline"):
                    out[k] = max(out.get(k, 0.0), v)
                elif k == "wipe":
                    out["wipe"] = min(out.get("wipe", 1.0), v)
                else:
                    out[k] = v
        return out
    return fx


def mix3(a, b, m):
    return (a[0] + (b[0] - a[0]) * m, a[1] + (b[1] - a[1]) * m, a[2] + (b[2] - a[2]) * m)


# ---------------------------------------------------------- 公式变形
def morph(eng, A, B, p, placeA, placeB, scaleA=1.0, scaleB=1.0, match=None, color=(1, 1, 1), alpha=1.0,
          intensity=1.0, arc=0.0, fxA=None, fxB=None, lag=0.0):
    """A -> B 的变形。placeX = (x, y, anchor)。
    同标签且符号数相同：逐个对应移动；同标签但数目不同：整组交叉淡化并向对方中心靠拢；
    match={A标签: B标签} 可把不同名的标签对应起来；其余 A 淡出、B 淡入。
    lag>0 时各符号按从左到右错开起步，更有"流动感"。"""
    p = min(max(p, 0.0), 1.0)
    if p <= 0.0:
        A.draw(*placeA[:2], anchor=placeA[2], scale=scaleA, color=color, alpha=alpha, intensity=intensity, fx=fxA)
        return
    if p >= 1.0:
        B.draw(*placeB[:2], anchor=placeB[2], scale=scaleB, color=color, alpha=alpha, intensity=intensity, fx=fxB)
        return
    oxA, oyA = A.origin(placeA[0], placeA[1], placeA[2], scaleA)
    oxB, oyB = B.origin(placeB[0], placeB[1], placeB[2], scaleB)
    mp = dict(match or {})
    for tg in A.tags():
        if tg not in mp and tg in B.tags():
            mp[tg] = tg
    usedB = set()
    nA = max(len(A.atoms) - 1, 1)
    for tgA, tgB in mp.items():
        ga, gb = A.group(tgA), B.group(tgB)
        if not ga or not gb:
            continue
        usedB.add(tgB)
        if len(ga) == len(gb):
            pairs = list(zip(ga, gb))
        else:
            pairs = None
        if pairs:
            for a, b in pairs:
                pp = _lagged(p, A.order[a.i] / nA, lag)
                e = ease_in_out(pp)
                xa, ya = oxA + a.cx * scaleA, oyA + a.cy * scaleA
                xb, yb = oxB + b.cx * scaleB, oyB + b.cy * scaleB
                x = xa + (xb - xa) * e
                y = ya + (yb - ya) * e - arc * math.sin(math.pi * e)
                sc = scaleA + (scaleB - scaleA) * e
                ra = fxA(a) if fxA else None
                rb = fxB(b) if fxB else None
                r = _blend_fx(ra, rb, e)
                if a.key() == b.key():
                    draw_atom(eng, a, 0, 0, scaleA, color, alpha, intensity, r, (x, y), sc)
                else:
                    # 形状不同（字号或字符变化）：交叉淡化
                    q = smooth(0.25, 0.75, pp)
                    draw_atom(eng, a, 0, 0, scaleA, color, alpha * (1 - q), intensity, r, (x, y),
                              sc * (1 + (b.size / a.size - 1) * e) if a.kind == "g" else sc)
                    draw_atom(eng, b, 0, 0, scaleB, color, alpha * q, intensity, r, (x, y),
                              sc * (1 + (a.size / b.size - 1) * (1 - e)) if b.kind == "g" else sc)
        else:
            # 整组：A 组淡出并移向 B 组中心，B 组从 A 组中心移入
            ax0, ay0, ax1, ay1 = A.tag_bbox(tgA)
            bx0, by0, bx1, by1 = B.tag_bbox(tgB)
            ca = (oxA + (ax0 + ax1) / 2 * scaleA, oyA + (ay0 + ay1) / 2 * scaleA)
            cb = (oxB + (bx0 + bx1) / 2 * scaleB, oyB + (by0 + by1) / 2 * scaleB)
            e = ease_in_out(p)
            q = smooth(0.2, 0.8, p)
            shift = (cb[0] - ca[0], cb[1] - ca[1])
            for a in ga:
                x = oxA + a.cx * scaleA + shift[0] * e
                y = oyA + a.cy * scaleA + shift[1] * e - arc * math.sin(math.pi * e)
                draw_atom(eng, a, 0, 0, scaleA, color, alpha * (1 - q), intensity, fxA(a) if fxA else None, (x, y), scaleA)
            for b in gb:
                x = oxB + b.cx * scaleB - shift[0] * (1 - e)
                y = oyB + b.cy * scaleB - shift[1] * (1 - e) - arc * math.sin(math.pi * e)
                draw_atom(eng, b, 0, 0, scaleB, color, alpha * q, intensity, fxB(b) if fxB else None, (x, y), scaleB)
    matchedA = set(mp.keys())
    fo = 1 - smooth(0.0, 0.5, p)
    fi = smooth(0.5, 1.0, p)
    for a in A.atoms:
        if a.tag in matchedA and A.group(a.tag) and B.group(mp[a.tag]):
            continue
        r = fxA(a) if fxA else None
        r = dict(r or {})
        r["a"] = r.get("a", 1.0) * fo
        r["s"] = r.get("s", 1.0) * (1 - 0.15 * (1 - fo))
        draw_atom(eng, a, oxA, oyA, scaleA, color, alpha, intensity, r)
    for b in B.atoms:
        if b.tag in usedB:
            continue
        r = fxB(b) if fxB else None
        r = dict(r or {})
        r["a"] = r.get("a", 1.0) * fi
        r["s"] = r.get("s", 1.0) * (1.15 - 0.15 * fi)
        draw_atom(eng, b, oxB, oyB, scaleB, color, alpha, intensity, r)


def _lagged(p, rank, lag):
    if lag <= 0:
        return p
    return min(max((p - rank * lag) / (1 - lag), 0.0), 1.0)


def _blend_fx(ra, rb, e):
    if not ra and not rb:
        return None
    ra, rb = ra or {}, rb or {}
    out = {}
    for k in set(ra) | set(rb):
        va, vb = ra.get(k), rb.get(k)
        if va is None or vb is None:
            out[k] = va if vb is None else vb
        elif isinstance(va, tuple):
            out[k] = mix3(va, vb, e)
        else:
            out[k] = va + (vb - va) * e
    return out
