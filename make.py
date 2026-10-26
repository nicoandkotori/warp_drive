# -*- coding: utf-8 -*-
"""《曲率引擎》构建入口。

python make.py tts         生成配音和飞船 AI 语音（已有则跳过；--force 重新生成）
python make.py ai          只生成飞船 AI 的英文语音
python make.py timeline    把解说排进节拍网格（--estimate：还没配音的句子按语速估算）
python make.py music       合成配乐 + 卡点数据（build/music.wav, build/beats.json）
python make.py mix         人声 + 配乐混音
python make.py audio       = timeline + music + mix
python make.py render [--still 12,40] [--start a --end b] [--out x.mp4] [--jobs 3] [--share-only]
python make.py all         全流程（母版 + 分享版）
"""
import os, sys
import config
from config import BUILD, TTS_DIR, BEAT, VOICE, VOICE_RATE, VOICE_PITCH, OUTPUT, SHARE, H
from script import SECTIONS, NO_SUB, AI_LINES, AI_VOICE, AI_RATE

AI_DIR = os.path.join(BUILD, "ai")


def step_tts(force=False):
    from opusvid.tts import synth_sections
    # opusvid.tts 只认 4 元组，去掉第 5 项（小节对齐选项）
    secs = [dict(s, lines=[l[:4] for l in s["lines"]]) for s in SECTIONS]
    synth_sections(secs, TTS_DIR, VOICE, VOICE_RATE, VOICE_PITCH, force=force)
    # 尾声"前进！前进！！不择手段地前进！！！"不用整句合成的版本，分段合成后按节拍重拼（见 fwd_voice.py）
    import fwd_voice
    fwd_voice.build(force=force)


def step_ai(force=False):
    """飞船 AI 的英文语音（每句一个 wav + 逐词时间），music.py 把它们排进配乐。"""
    from opusvid.tts import synth_sections
    secs = [dict(lines=[(lid, en, None, 0) for lid, en, zh, cue in AI_LINES])]
    synth_sections(secs, AI_DIR, AI_VOICE, AI_RATE, "+0Hz", force=force)


def step_timeline(estimate=False):
    from opusvid.timeline import build
    build(SECTIONS, TTS_DIR, os.path.join(BUILD, "timeline.json"), BEAT, estimate=estimate)


def step_music():
    import music
    music.main()


def step_mix():
    from opusvid.mix import mix
    mix(os.path.join(BUILD, "timeline.json"), TTS_DIR, os.path.join(BUILD, "music.wav"), os.path.join(BUILD, "mix.wav"))


def step_render(argv):
    from opusvid.render import cli
    from scenes import REGISTRY, TRANSITIONS, setup_renderer
    cli(BUILD, REGISTRY, TRANSITIONS, OUTPUT, argv, share_out=SHARE, sub_style=dict(size=38, font="sans_m", y=H - 70),
        hide=NO_SUB, setup=setup_renderer)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    rest = sys.argv[2:]
    if cmd == "tts":
        step_tts("--force" in rest)
        step_ai("--force" in rest)
    elif cmd == "ai":
        step_ai("--force" in rest)
    elif cmd == "timeline":
        step_timeline("--estimate" in rest)
    elif cmd == "music":
        step_music()
    elif cmd == "mix":
        step_mix()
    elif cmd == "audio":
        step_timeline(); step_music(); step_mix()
    elif cmd == "render":
        step_render(rest)
    elif cmd == "all":
        step_tts(); step_ai(); step_timeline(); step_music(); step_mix(); step_render(rest)
    else:
        print(__doc__)
