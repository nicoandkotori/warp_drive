# -*- coding: utf-8 -*-
"""场景注册表、转场设置、渲染器初始化。"""
from opusvid.scene import Scene
from script import CHAPTERS
import wfx

Scene.chapters = CHAPTERS

from scenes_open import Cold                 # noqa: E402
from scenes_warp import Warp, Arrive         # noqa: E402
from scenes_ch12 import Ch1, Ch2             # noqa: E402
from scenes_ch34 import Ch3, Ch4             # noqa: E402
from scenes_ch5 import Ch5                   # noqa: E402
from scenes_ch6 import Ch6                   # noqa: E402
from scenes_end import Outro, End            # noqa: E402

REGISTRY = dict(warp=Warp, cold=Cold, arrive=Arrive, ch1=Ch1, ch2=Ch2, ch3=Ch3, ch4=Ch4, ch5=Ch5, ch6=Ch6, outro=Outro, end=End)

# 转场：(出场前秒数, 入场后秒数, 类型)
# 类型见 wfx.TRANSITION_WD：0 曲率冲刺 1 泡泡透镜 2 黑场 3 白闪穿越 4 信号故障 5 虹彩溶解 6 青溶解
TRANSITIONS = {
    "cold": (0.5, 0.5, 2), "arrive": (0.5, 0.6, 0), "ch1": (0.6, 0.6, 0), "ch2": (0.6, 0.7, 1), "ch3": (0.7, 0.8, 5),
    "ch4": (0.6, 0.6, 0), "ch5": (0.5, 0.6, 4), "ch6": (0.7, 0.8, 6), "outro": (0.8, 0.8, 2), "end": (0.4, 0.6, 3),
}


def setup_renderer(r):
    """渲染前调用（make.py 经 cli(setup=...) 传入）：换上本项目的转场与后期（去灰雾），开启小字清晰层。"""
    wfx.install(r.eng)
    wfx.install_post(r.eng)
    # ≤30 像素的 HUD/标注文字走清晰层（不受泛光、色差影响）；这些字要在段落结束前自己淡出
    r.eng.ui_text_max = 30
    # 开场第一帧就是全息星图 + 重击，只留 0.06 秒淡入
    r.fade_in = 0.06
