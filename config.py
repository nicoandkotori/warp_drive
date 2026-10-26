# -*- coding: utf-8 -*-
"""《曲率引擎》项目配置。公共引擎在本目录的 opusvid/ 里。"""
import os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = ROOT                # 成片和配音试听都输出到本目录（已在 .gitignore 里排除）
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from opusvid.settings import W, H, FPS, SR, FFMPEG  # noqa: E402

BUILD = os.path.join(ROOT, "build")
TTS_DIR = os.path.join(BUILD, "tts")
os.makedirs(TTS_DIR, exist_ok=True)
OUTPUT = os.path.join(REPO, "曲率引擎.mp4")
SHARE = os.path.join(REPO, "曲率引擎_分享版.mp4")

BPM = 100.0
BEAT = 60.0 / BPM          # 0.6 s
BAR = BEAT * 4             # 2.4 s

# 用户在前两部片子里都选了云健（低沉激昂），语速 -2%
VOICE = "zh-CN-YunjianNeural"
VOICE_RATE = "-2%"
VOICE_PITCH = "+0Hz"

# 开场的飞船 AI 英文语音和中英字幕（script.AI_LINES）。用户觉得人声太俗，想试"无人声版"：
# False 时开场不放 AI 语音、不出字幕，信息全靠画面（HUD、读数、镜头）传递；改回 True 即恢复，不用重新生成语音
SHIP_AI = False
