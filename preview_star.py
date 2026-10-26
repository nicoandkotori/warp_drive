"""python preview_star.py [--stills-only]：巡航/等待/抵达静帧、6 秒贴面视频及 GPU 计时。"""
import json
from pathlib import Path
import subprocess
import sys

import config
import numpy as np
from PIL import Image
from opusvid.gl import Camera, Engine
from opusvid.settings import W, H, FFMPEG
import star_model
from wfx import install_post
from warpshot import WarpShot


def main():
    out = Path(config.BUILD) / "star"
    out.mkdir(parents=True, exist_ok=True)
    eng = Engine()
    install_post(eng)
    close = Camera((-13, 6, -11), (4, -2.5, 12), fov=42)
    center = (0, -514, 0)
    shot = WarpShot(eng)
    params = dict(color=(0.16, 0.48, 1.0), bright=0.5, blue=1.0,
                  spots=0.25, granules=1500.0, corona=0.35)

    def frame(cam, ctr, t, timing=False):
        eng.time, eng.frame = t, round(t*60)
        tex, fbo = eng.targets[0]
        fbo.use()
        eng.ctx.viewport = (0, 0, W, H)
        fbo.clear(0, 0, 0, 0)
        if timing:
            query = eng.ctx.query(time=True)
            with query:
                star_model.star(eng, cam, ctr, 500, **params)
            eng.ctx.finish()
            return query.elapsed / 1e6
        star_model.star(eng, cam, ctr, 500, **params)
        eng.flush()
        eng.composite(tex, dict(uBloomAmt=0.3, uExposure=1, uCA=0, uGrain=0, uVignette=0))
        return eng.read()

    views = [("arrival", close, center),
             ("waiting", Camera((5, 2.2, 17), (0, 0.3, 0), fov=40), center),
             ("cruise", shot.camera(31), tuple(shot.target_a(31)))]
    for px in (1, 80, 400):
        cam = Camera((0, 0, 0), (0, 0, 1), fov=42)
        views.append((f"radius_{px}px", cam, (0, 0, 500*cam.pix/px)))
    for name, cam, ctr in views:
        img = Image.frombytes("RGB", (W, H), frame(cam, ctr, 40.8))
        img.transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(out / f"{name}.png")
    # 编译及首次驱动调度不计入稳定帧耗时。
    for i in range(8):
        frame(close, center, 40.8+i/60, True)
    times = [frame(close, center, 40.8+i/60, True) for i in range(60)]
    a = frame(close, center, 41.2)
    frame(close, center, 44.0)
    deterministic = a == frame(close, center, 41.2)
    report = dict(gpu=eng.ctx.info["GL_RENDERER"], median_ms=float(np.median(times)),
                  p95_ms=float(np.percentile(times, 95)), max_ms=max(times),
                  jump_frame_identical=deterministic)
    frame(close, center, 40.8)
    hdr = np.frombuffer(eng.targets[0][1].read(components=4, dtype="f4"), dtype=np.float32).reshape(H, W, 4)
    surface = hdr[hdr[:, :, 3] > 0.99, :3]
    report["hdr_finite"] = bool(np.isfinite(hdr).all())
    report["surface_hdr_max"] = float(surface.max())
    report["surface_hdr_peak_p99"] = float(np.percentile(surface.max(axis=1), 99))
    report["views_ms"] = {}
    for name, cam, ctr in views[:3]:
        samples = [frame(cam, ctr, 40.8+i/60, True) for i in range(30)]
        report["views_ms"][name] = dict(median=float(np.median(samples)), p95=float(np.percentile(samples, 95)))
    (out / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    if "--stills-only" not in sys.argv:
        path = out / "star_closeup_6s.mp4"
        cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{W}x{H}", "-r", "60", "-i", "-", "-vf", "vflip", "-an",
               "-c:v", "h264_nvenc", "-b:v", "24M", "-pix_fmt", "yuv420p", str(path)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        try:
            for i in range(360):
                proc.stdin.write(frame(close, (0, -514, -i/60), 40.8+i/60))
        finally:
            proc.stdin.close()
            code = proc.wait()
        if code:
            raise RuntimeError("恒星预览编码失败")
        print(path, flush=True)
        # 聊天内直接展示 GIF；另提供浏览器普遍支持的 H.264/faststart 文件。
        compatible = out / "plasma_preview.mp4"
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(path),
                        "-vf", "scale=960:540", "-r", "30", "-an", "-c:v", "libx264",
                        "-profile:v", "baseline", "-level", "3.1", "-pix_fmt", "yuv420p",
                        "-crf", "20", "-movflags", "+faststart", str(compatible)], check=True)
        gif = out / "plasma_preview.gif"
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(compatible),
                        "-filter_complex", "fps=12,scale=768:-1:flags=lanczos,split[a][b];"
                        "[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=sierra2_4a",
                        "-loop", "0", str(gif)], check=True)
        print(gif, flush=True)


if __name__ == "__main__":
    main()
