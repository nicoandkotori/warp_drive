"""渲染新战列舰的三视角预览和可选环绕视频。

python preview_battleship.py [--video]；使用成片同一模型与后期。
"""
import math
from pathlib import Path
import subprocess
import sys

import config
from PIL import Image
from opusvid.gl import Camera, Engine
from opusvid.settings import W, H, FFMPEG
from ship import ship, ship_frame, relstars
from wfx import install_post


def main():
    output = Path(config.BUILD) / "battleship"
    output.mkdir(parents=True, exist_ok=True)
    eng = Engine()
    install_post(eng)

    def frame(eye, t=0):
        eng.time = t
        eng.frame = round(t * 30)
        tex, fbo = eng.targets[0]
        fbo.use()
        eng.ctx.viewport = (0, 0, W, H)
        fbo.clear(0, 0, 0, 1)
        cam = Camera(eye, (0, 0, 0.70), fov=33)
        relstars(eng, cam, beta=0, stars=0.12, neb=0.025)
        ship(eng, cam, (0, 0, 0), ship_frame((0, 0, 1)),
             ring=0.65, engine=0.65, phase=t*2, flow=0.45,
             sun=(-0.5, 0.8, 0.5), sun_col=(2.4, 2.3, 2.2), fill=(0.3, 0.36, 0.45))
        eng.flush()
        eng.composite(tex, dict(uBloomAmt=0.15, uExposure=1.15, uCA=0,
                               uGrain=0.006, uVignette=0.15))
        return eng.read()

    views = [("front", (9, 6.5, 10)), ("rear", (-8, 5.5, -11)),
             ("side", (12, 5, 2))]
    for name, eye in views:
        img = Image.frombytes("RGB", (W, H), frame(eye)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        img.save(output / f"{name}.png")
        print(output / f"{name}.png", flush=True)
    if "--video" in sys.argv:
        path = output / "battleship_turntable.mp4"
        cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{W}x{H}", "-r", "30", "-i", "-", "-vf", "vflip", "-an",
               "-c:v", "h264_nvenc", "-b:v", "12M", "-pix_fmt", "yuv420p", str(path)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for i in range(240):
            t=i/30
            a=0.7+t/8*math.tau
            proc.stdin.write(frame((12*math.sin(a), 6, 0.7+12*math.cos(a)), t))
        proc.stdin.close()
        if proc.wait():
            raise RuntimeError("环绕视频编码失败")
        print(path, flush=True)


if __name__ == "__main__":
    main()
