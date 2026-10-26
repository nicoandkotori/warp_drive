"""python preview_galaxy.py [标签]：单独渲染开场银河（不画 HUD）的 10 个关键时刻，用来改进 galaxy.py 时对比前后。

镜头和 galaxy.draw 的参数取自 galaxynav.GalaxyNav.galaxy_args(t)，和成片逐帧一致；后期参数与 scenes_warp.Warp.post 的导航段相同。
输出到 build/galaxy/<标签>/（默认标签 current）：
  <时刻名>.png        整帧 1920×1080
  sheet.png           全部时刻的缩略拼图
  crops_100.png       四处 100% 原尺寸局部（远景、近景、盘内光带、锁定时的背景光带）——"糊不糊"主要看这张
  report.json         每个时刻的 GPU 耗时（毫秒）、同一时刻渲染两次是否逐字节相同、HDR 缓冲里有没有 NaN/Inf
另外，如果 build/galaxy/before/ 存在，且这次的标签不是 before，会生成 compare_crops.png：上排 before、下排这次。"""
import json
from pathlib import Path
import sys

import config
import numpy as np
from PIL import Image
from opusvid.gl import Engine
from opusvid.settings import W, H
from wfx import install_post
from galaxynav import GalaxyNav

# (名字, 时刻)：时刻对应 cues.C 里的导航分镜，见 galaxynav.py 模块说明
VIEWS = [("01_hero_far", 0.3), ("02_hero", 4.5), ("03_approach", 7.2), ("04_close", 7.6), ("05_dive", 8.0),
         ("06_inside", 9.9), ("07_candidate", 11.0), ("08_select", 14.7), ("09_route", 16.0), ("10_lock", 18.3)]
# 100% 局部：(时刻名, 左, 上, 右, 下)，图像坐标（左上原点）
CROPS = [("02_hero", 760, 380, 1400, 740), ("04_close", 300, 300, 940, 660),
         ("07_candidate", 500, 100, 1140, 460), ("10_lock", 100, 200, 740, 560)]
POST = dict(uBloomAmt=0.35, uVignette=0.55, uCA=0.0, uGrain=0.02)      # 与 scenes_warp.Warp.post（导航段）一致


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "current"
    root = Path(config.BUILD) / "galaxy"
    out = root / tag
    out.mkdir(parents=True, exist_ok=True)
    eng = Engine()
    install_post(eng)
    nav = GalaxyNav(eng)

    def frame(t, timing=False):
        eng.time, eng.frame = t, round(t * 60)
        tex, fbo = eng.targets[0]
        fbo.use()
        eng.ctx.viewport = (0, 0, W, H)
        fbo.clear(0, 0, 0, 1)
        gc, kw = nav.galaxy_args(t)
        if timing:
            query = eng.ctx.query(time=True)
            with query:
                nav.g.draw(gc, **kw)
            eng.ctx.finish()
            return query.elapsed / 1e6
        nav.g.draw(gc, **kw)
        eng.flush()
        eng.composite(tex, POST)
        return eng.read()

    imgs = {}
    for name, t in VIEWS:
        img = Image.frombytes("RGB", (W, H), frame(t)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        img.save(out / f"{name}.png")
        imgs[name] = img
    sheet = Image.new("RGB", (1920, 810))                          # 4 列 × 3 行，每格 480×270
    for i, (name, _) in enumerate(VIEWS):
        sheet.paste(imgs[name].resize((480, 270)), ((i % 4) * 480, (i // 4) * 270))
    sheet.save(out / "sheet.png")
    crops = Image.new("RGB", (1280, 720))
    for i, (name, *box) in enumerate(CROPS):
        crops.paste(imgs[name].crop(box), ((i % 2) * 640, (i // 2) * 360))
    crops.save(out / "crops_100.png")

    # 编译和首次调度不计入耗时
    for name, t in VIEWS:
        frame(t, True)
    report = dict(gpu=eng.ctx.info["GL_RENDERER"], views_ms={})
    for name, t in VIEWS:
        ms = [frame(t, True) for _ in range(12)]
        report["views_ms"][name] = dict(median=round(float(np.median(ms)), 2), max=round(max(ms), 2))
    a = frame(11.0)
    report["deterministic"] = a == frame(11.0)
    frame(11.0)
    hdr = np.frombuffer(eng.targets[0][1].read(components=4, dtype="f4"), dtype=np.float32)
    report["hdr_finite"] = bool(np.isfinite(hdr).all())
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)

    before = root / "before" / "crops_100.png"
    if tag != "before" and before.exists():
        cmp_ = Image.new("RGB", (1280, 1440))
        cmp_.paste(Image.open(before), (0, 0))
        cmp_.paste(crops, (0, 720))
        cmp_.save(out / "compare_crops.png")
    print("wrote", out)


if __name__ == "__main__":
    main()
