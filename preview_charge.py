"""32 格曲率环充能预览：8 秒充能、一次闪光、1.2 秒倒数。

python preview_charge.py；输出到 build/battleship/charge_preview.mp4。
时间驱动，支持任意跳帧。配低频提示音，不包含跃迁过场。
"""
import math
from pathlib import Path
import subprocess
import wave

import config
import numpy as np
from PIL import Image
from opusvid.gl import Camera, Engine
from opusvid.settings import W, H, FFMPEG
from ship import ship, ship_frame, relstars
from wfx import install_post

FPS = 30
DURATION = 15
FULL = 9.0
COUNTDOWN = (10.0, 11.2, 12.4)


def state(t):
    charge = min(1.0, max(0.0, (t-1.0)/8.0))
    # 一次有起落的短脉冲；倒数开始前已经恢复稳定蓝光。
    d = t-FULL
    flash = math.sin(math.pi*d/0.45)**2 if 0 <= d <= 0.45 else 0.0
    count = next((str(3-i) for i, start in enumerate(COUNTDOWN) if start <= t < start+1.2), None)
    return charge, flash, count


def main():
    out = Path(config.BUILD)/"battleship"
    out.mkdir(parents=True, exist_ok=True)
    eng = Engine()
    install_post(eng)
    silent = out/"charge_preview_silent.mp4"
    proc = subprocess.Popen([FFMPEG,"-y","-loglevel","error","-f","rawvideo","-pix_fmt","rgb24",
        "-s",f"{W}x{H}","-r",str(FPS),"-i","-","-vf","vflip","-an","-c:v","h264_nvenc",
        "-b:v","15M","-pix_fmt","yuv420p",str(silent)],stdin=subprocess.PIPE)
    snaps = {90:"charge_25",150:"charge_50",210:"charge_75",270:"charge_100",277:"charge_flash",306:"countdown"}
    for i in range(FPS*DURATION):
        t=i/FPS
        level, flash, count=state(t)
        eng.time=t
        eng.frame=i
        tex,fbo=eng.targets[0]
        fbo.use()
        eng.ctx.viewport=(0,0,W,H)
        fbo.clear(0,0,0,1)
        # 慢移的前侧视角：两道环面和外缘同时可读，避免旋转掩盖进度。
        a=0.80+0.10*t/DURATION
        cam=Camera((11.8*math.sin(a),5.8,11.8*math.cos(a)),(0,0,0.3),fov=36)
        relstars(eng,cam,stars=0.08,neb=0.02)
        ship(eng,cam,(0,0,0),ship_frame((0,0,1)),ring=0.35+0.35*level,
             charge=level,charge_flash=flash,engine=0.2+0.4*level,phase=t*3,
             flow=level*0.7,sun=(-0.5,0.8,0.5),sun_col=(2.4,2.3,2.2),fill=(0.3,0.36,0.45))
        title="曲率环 · 交错充能" if t<FULL else ("充能完成" if t<10 else "跃迁倒数")
        eng.text(title,100,100,38,"sans_m",(0.55,0.8,1),anchor="lm")
        eng.text("前环向下展开 / 后环向上展开",100,155,26,"sans",(0.5,0.6,0.7),anchor="lm")
        eng.text(f"{round(level*100):d}%",W-115,115,56,"latin_b",(0.4,0.85,1),anchor="rm")
        if count:
            eng.text(count,W/2,165,100,"latin_b",(0.65,0.9,1))
        if t>=13.6:
            eng.text("跃迁就绪",W/2,165,48,"sans_b",(0.65,0.9,1))
        eng.flush()
        eng.composite(tex,dict(uBloomAmt=0.17,uExposure=1.1,uCA=0,uGrain=0.005,uVignette=0.15))
        raw=eng.read()
        proc.stdin.write(raw)
        if i in snaps:
            Image.frombytes("RGB",(W,H),raw).transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(out/(snaps[i]+".png"))
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError("充能预览编码失败")
    # 低频提示音：逐格轻响、充满重音、倒数三次，遵循项目声音偏好。
    sr=48000
    audio=np.zeros(DURATION*sr,dtype=np.float64)
    def tone(start,freq,gain,length):
        tt=np.arange(int(length*sr))/sr
        envelope=(1-np.exp(-tt/0.012))*np.exp(-tt/(length*0.25))
        data=gain*np.sin(2*math.pi*freq*tt)*envelope
        begin=round(start*sr)
        audio[begin:begin+len(data)]+=data[:len(audio)-begin]
    for k in range(1,18):
        tone(1+8*k/17,110+k*2,0.10,0.20)
        tone(1+8*(0.0375+0.9625*k/17),90+k*2,0.08,0.20)
    tone(9,65,0.45,0.7)
    for at in COUNTDOWN:
        tone(at,120,0.35,0.4)
    tone(13.6,80,0.3,0.7)
    wav=out/"charge_preview.wav"
    with wave.open(str(wav),"wb") as f:
        f.setparams((1,2,sr,0,"NONE","not compressed"))
        f.writeframes((np.clip(audio,-1,1)*32767).astype("<i2").tobytes())
    dest=out/"charge_preview.mp4"
    subprocess.run([FFMPEG,"-y","-loglevel","error","-i",str(silent),"-i",str(wav),
                    "-c:v","copy","-c:a","aac","-b:a","192k","-movflags","+faststart",str(dest)],check=True)
    print(dest)


if __name__=="__main__":
    main()
