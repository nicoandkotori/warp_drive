# -*- coding: utf-8 -*-
"""opusvid.render — 逐帧渲染主循环：场景 -> 转场 -> 泛光/调色 -> 字幕 -> ffmpeg 编码 -> 合成音频。"""
import argparse, json, math, os, subprocess, sys, time
import numpy as np
from PIL import Image
from .settings import W, H, FPS, FFMPEG
from .gl import Engine, smooth


class Renderer:
    """
    timeline: timeline.json 内容；beats: beats.json 内容（kicks / accents）
    registry: {段落id: Scene 子类}
    transitions: {段落id: (出场前秒数, 入场后秒数, 类型)}，类型 0=引力扭曲 1=紫色溶解 2=黑场
    fx: 节拍/重音对画面的影响强度（beat_bloom, beat_exp, acc_bloom, acc_exp, shake）
    hide: 不显示字幕的句子 id
    """
    FX = dict(beat_bloom=0.18, beat_exp=0.04, acc_bloom=0.35, acc_exp=0.08, shake=1.0)

    def __init__(self, timeline, beats, registry, transitions, sub_style=None, fx=None, hide=()):
        self.fx = dict(self.FX)
        self.fx.update(fx or {})
        self.tl = timeline
        self.dur = timeline["duration"]
        self.eng = Engine()
        self.trans = transitions
        self.scenes = [registry[s["id"]](self.eng, s, beats) for s in timeline["sections"]]
        self.subs = [sg for s in timeline["sections"] for l in s["lines"] if l["id"] not in hide for sg in l["subs"]]
        self.sub_style = dict(size=40, font="sans_m", y=H - 78)
        self.sub_style.update(sub_style or {})
        k = beats.get("kicks") or [[-10.0, 0.0]]
        self.kicks = np.array([x[0] for x in k])
        self.kick_g = np.array([x[1] for x in k])
        self.acc = [a for a in beats.get("accents", []) if a["kind"] in ("impact", "transition", "supernova", "flash")]
        # 片头淡入时长（秒）。以钩子镜头开场的项目可在 setup(renderer) 里调短，让第一下重击直接打在画面上
        self.fade_in = 0.4
        # 片尾淡出时长（秒），同样可在 setup(renderer) 里改（短片 demo 不希望最后几秒都在变暗）
        self.fade_out = 3.5

    def beat_pulse(self, t):
        d = t - self.kicks
        m = (d >= 0) & (d < 0.6)
        return float(np.sum(self.kick_g[m] * np.exp(-d[m] / 0.16)))

    def accent_pulse(self, t):
        v, shake = 0.0, 0.0
        for a in self.acc:
            d = t - a["t"]
            if 0 <= d < 1.5:
                v += a["size"] * math.exp(-d / 0.35)
                if a["kind"] in ("impact", "transition"):
                    shake += a["size"] * math.exp(-d / 0.25)
        return v, shake

    def scene_index(self, t):
        for i, s in enumerate(self.tl["sections"]):
            if s["start"] <= t < s["end"]:
                return i
        return len(self.tl["sections"]) - 1

    def render_scene(self, i, t, target):
        e = self.eng
        tex, fbo = e.targets[target]
        fbo.use()
        e.ctx.viewport = (0, 0, W, H)
        fbo.clear(0, 0, 0, 1)
        sc = self.scenes[i]
        sc.render(t)
        e.flush()
        return tex, sc.post(t)

    def frame(self, t, fidx):
        e = self.eng
        e.time = t
        e.frame = fidx
        secs = self.tl["sections"]
        i = self.scene_index(t)
        sid = secs[i]["id"]
        trans = None
        if sid in self.trans and i > 0 and t < secs[i]["start"] + self.trans[sid][1]:
            a, b, k = self.trans[sid]
            trans = (i - 1, i, (t - (secs[i]["start"] - a)) / (a + b), k)
        elif i + 1 < len(secs) and secs[i + 1]["id"] in self.trans:
            a, b, k = self.trans[secs[i + 1]["id"]]
            if t >= secs[i + 1]["start"] - a:
                trans = (i, i + 1, (t - (secs[i + 1]["start"] - a)) / (a + b), k)
        if trans:
            ia, ib, p, k = trans
            p = min(max(p, 0.0), 1.0)
            ta, pa = self.render_scene(ia, t, 0)
            tb, pb = self.render_scene(ib, t, 1)
            e.transition(ta, tb, e.targets[2][1], p, k, seed=float(ib))
            scene_tex = e.targets[2][0]
            post = {}
            m = smooth(0.35, 0.65, p)
            for key in set(pa) | set(pb):
                va, vb = pa.get(key), pb.get(key)
                if va is None or vb is None:
                    post[key] = va if vb is None else vb
                elif isinstance(va, tuple):
                    post[key] = tuple(x + (y - x) * m for x, y in zip(va, vb))
                else:
                    post[key] = va + (vb - va) * m
        else:
            scene_tex, post = self.render_scene(i, t, 0)
        # 节拍与重音：泛光微脉冲、轻微震动
        bp = self.beat_pulse(t)
        ap, shake = self.accent_pulse(t)
        post = dict(post)
        fx = self.fx
        post["uBloomAmt"] = post.get("uBloomAmt", 0.4) * (1 + fx["beat_bloom"] * bp + fx["acc_bloom"] * ap)
        post["uExposure"] = post.get("uExposure", 1.0) * (1 + fx["beat_exp"] * bp + fx["acc_exp"] * ap)
        shake *= fx["shake"]
        post["uShake"] = (shake * 5.0 * math.sin(t * 71.0), shake * 4.0 * math.sin(t * 53.0 + 1.3))
        fade = smooth(0.0, self.fade_in, t) * (1 - smooth(self.dur - self.fade_out, self.dur - 0.2, t))
        post["uFade"] = post.get("uFade", 1.0) * fade
        self.fade = fade                     # overlay 里的清晰文字层也要跟着片头片尾淡入淡出
        e.composite(scene_tex, post)
        self.overlay(t)
        return e.read()

    def overlay(self, t):
        e = self.eng
        e.ldr.use()
        e.flush_ui(getattr(self, "fade", 1.0))   # 场景里的小字（若开启了清晰文字层），画在字幕下面
        st = self.sub_style
        for sg in self.subs:
            if sg["start"] - 0.1 <= t <= sg["end"] + 0.05:
                # 先出后进：上一段在 end 前淡出完毕，下一段在 start 前后淡入，不重叠
                a = smooth(sg["start"] - 0.04, sg["start"] + 0.08, t) * (1 - smooth(sg["end"] - 0.12, sg["end"], t))
                if a > 0.001:
                    e.text(sg["text"], W / 2, st["y"] + 2, st["size"], st["font"], (0, 0, 0), 0.75 * a, "mm", 0.04, 1.0,
                           blur=7, layer="inline")
                    e.text(sg["text"], W / 2, st["y"], st["size"], st["font"], (1, 1, 1), 0.94 * a, "mm", 0.04, 1.0,
                           layer="inline")
        e.flush()


_NVENC = None


def has_nvenc():
    """本机能否用 NVIDIA 硬件编码（试编 1 帧，结果缓存）。没有 N 卡时改用 libx264，慢一些但哪里都能跑。"""
    global _NVENC
    if _NVENC is None:
        probe = subprocess.run([FFMPEG, "-loglevel", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.04",
                                "-frames:v", "1", "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True)
        _NVENC = probe.returncode == 0
        if not _NVENC:
            print("h264_nvenc 不可用，改用 libx264 编码", flush=True)
    return _NVENC


def encoder(path, fps):
    if has_nvenc():
        codec = ["-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq", "-rc", "vbr", "-cq", "17", "-b:v", "28M",
                 "-maxrate", "45M", "-bufsize", "60M", "-bf", "3"]
    else:
        codec = ["-c:v", "libx264", "-preset", "slow", "-crf", "16", "-maxrate", "45M", "-bufsize", "60M"]
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "-", "-vf", "vflip", *codec, "-profile:v", "high",
           "-pix_fmt", "yuv420p", "-g", str(fps * 2), path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def render_range(r, t0, t1, fps, out):
    enc = encoder(out, fps)
    f0, f1 = int(round(t0 * fps)), int(round(t1 * fps))
    t_start = time.time()
    for f in range(f0, f1):
        t = f / fps
        enc.stdin.write(r.frame(t, f))
        if (f - f0) % (fps * 5) == 0:
            el = time.time() - t_start
            done = (f - f0 + 1) / (f1 - f0)
            print(f"[{t0:.0f}-{t1:.0f}] t={t:7.2f}s {done * 100:5.1f}% elapsed {el:6.0f}s eta {el / done - el:6.0f}s",
                  flush=True)
    enc.stdin.close()
    enc.wait()


def mux(build_dir, video, out, start, end):
    audio = os.path.join(build_dir, "mix.wav")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", video, "-ss", str(start), "-t", str(end - start),
                    "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                    "-shortest", "-movflags", "+faststart", out], check=True)
    os.remove(video)


def share(master, out, vbit="14M", vmax="20M", abit="192k"):
    """由母版转出分享版（H.264 + AAC，体积约为母版的三分之一，兼容各平台）。"""
    if has_nvenc():
        codec = ["-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq", "-multipass", "fullres", "-rc", "vbr",
                 "-bf", "3"]
    else:
        codec = ["-c:v", "libx264", "-preset", "slow"]
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", master, *codec, "-b:v", vbit, "-maxrate", vmax,
                    "-bufsize", "30M", "-profile:v", "high", "-pix_fmt", "yuv420p", "-g", "120",
                    "-c:a", "aac", "-b:a", abit, "-movflags", "+faststart", out], check=True)
    print("wrote", os.path.abspath(out), round(os.path.getsize(out) / 1e6, 1), "MB")


def cli(build_dir, registry, transitions, default_out, argv=None, share_out=None, sub_style=None, fx=None, hide=(),
        setup=None):
    """命令行：--still 12.5,40 导出 PNG；--start/--end 渲染片段；--jobs N 多进程分段渲染；
    默认渲染全片并封装音频；给了 share_out 时再转出分享版（--share-only 只做转码）。
    setup(renderer) 可在渲染前替换转场等。"""
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", type=str, default=None)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--fps", type=int, default=FPS)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--segment", action="store_true", help="只输出无声视频片段（并行渲染的子进程用）")
    ap.add_argument("--share-only", action="store_true")
    args = ap.parse_args(argv)
    tl = json.load(open(os.path.join(build_dir, "timeline.json"), encoding="utf-8"))
    end = args.end if args.end is not None else tl["duration"]
    fps = args.fps
    out = args.out or default_out
    full = args.start == 0 and args.end is None and args.out is None
    if args.share_only:
        share(out, share_out)
        return
    if args.jobs > 1 and not args.still and not args.segment:
        # 按帧均分给多个子进程，最后无损拼接
        f0, f1 = int(round(args.start * fps)), int(round(end * fps))
        cuts = np.linspace(f0, f1, args.jobs + 1).round().astype(int)
        seg_dir = os.path.join(build_dir, "segments")
        os.makedirs(seg_dir, exist_ok=True)
        procs, segs = [], []
        t_start = time.time()
        for k in range(args.jobs):
            seg = os.path.join(seg_dir, f"seg{k:02d}.mp4")
            segs.append(seg)
            cmd = [sys.executable, sys.argv[0], "render", "--start", str(cuts[k] / fps), "--end", str(cuts[k + 1] / fps),
                   "--fps", str(fps), "--out", seg, "--segment"]
            procs.append(subprocess.Popen(cmd))
        for p in procs:
            p.wait()
            assert p.returncode == 0, "segment failed"
        lst = os.path.join(seg_dir, "list.txt")
        with open(lst, "w", encoding="utf-8") as f:
            for sg in segs:
                f.write(f"file '{sg}'\n")
        video = out + ".video.mp4"
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video],
                       check=True)
        mux(build_dir, video, out, args.start, end)
        print("wrote", os.path.abspath(out), "in", round(time.time() - t_start), "s")
        if share_out and full:
            share(out, share_out)
        return
    beats_p = os.path.join(build_dir, "beats.json")
    beats = json.load(open(beats_p, encoding="utf-8")) if os.path.exists(beats_p) else dict(kicks=[], accents=[])
    r = Renderer(tl, beats, registry, transitions, sub_style, fx, hide)
    if setup:
        setup(r)
    if args.still:
        sd = os.path.join(build_dir, "stills")
        os.makedirs(sd, exist_ok=True)
        for ts in args.still.split(","):
            t = float(ts)
            raw = r.frame(t, int(t * FPS))
            img = Image.frombytes("RGB", (W, H), raw).transpose(Image.FLIP_TOP_BOTTOM)
            p = os.path.join(sd, f"still_{t:07.2f}.png")
            img.save(p)
            print(p)
        return
    if args.segment:
        render_range(r, args.start, end, fps, out)
        return
    video = out + ".video.mp4"
    t_start = time.time()
    render_range(r, args.start, end, fps, video)
    mux(build_dir, video, out, args.start, end)
    print("wrote", os.path.abspath(out), "in", round(time.time() - t_start), "s")
    if share_out and full:
        share(out, share_out)

