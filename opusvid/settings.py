# -*- coding: utf-8 -*-
"""全局输出参数与字体表（项目可在导入其他模块前修改）。"""
import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

W, H = 1920, 1080
FPS = 60
SR = 48000

FONTS = {
    "serif": (r"C:\Windows\Fonts\NotoSerifSC-VF.ttf", 900),
    "serif_m": (r"C:\Windows\Fonts\NotoSerifSC-VF.ttf", 600),
    "heavy": (r"C:\Windows\Fonts\Source Han Serif SC Heavy (TrueType).ttf", None),
    "sans": (r"C:\Windows\Fonts\NotoSansSC-VF.ttf", 400),
    "sans_l": (r"C:\Windows\Fonts\NotoSansSC-VF.ttf", 250),
    "sans_m": (r"C:\Windows\Fonts\NotoSansSC-VF.ttf", 500),
    "sans_b": (r"C:\Windows\Fonts\NotoSansSC-VF.ttf", 700),
    "latin": (r"C:\Windows\Fonts\bahnschrift.ttf", 300),
    "latin_m": (r"C:\Windows\Fonts\bahnschrift.ttf", 400),
    "latin_b": (r"C:\Windows\Fonts\bahnschrift.ttf", 600),
}
