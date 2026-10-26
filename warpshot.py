# -*- coding: utf-8 -*-
"""开场 v3 的镜头：舰桥（导航 HUD 的背景）-> 拉开露出飞船 -> 充能 -> 空间扭曲 -> 跃迁分镜 -> 超光速巡航 -> 抵达分镜
-> 镜头绕到侧后方露出巨大的恒星 -> 片名。导航段（shiphud.BridgeHUD）用的也是这台镜头在舰桥上的那一帧，所以星空完全接得上。

所有运动都由 cues.C 里的时刻驱动：
  速度 v(t)：跃迁前为 0（慢动作窗口里向前蠕动一点）；跃迁瞬间飞船被"弹射"出去（V_SNAP 的尖峰，约 0.3 秒
       缩成远处一个光点），同时巡航速度在镜头追上之前升满；抵达时是同一条包络的镜像：冲过来、在 C["dropout"] 猛地刹住。
  行程 s(t) = ∫v dt、曲率环转角 spin(t) = ∫转速 dt：启动时按 1/240 秒的步长预先积分成表，插值读取（只依赖 t）。
  镜头：飞船固定在原点、船头朝 +z，镜头的位置都是相对飞船的。
       跃迁前、巡航、绕行露出恒星这几段用"位置 + 注视点 + 视场角"的关键帧做单调三次插值；
       跃迁分镜里镜头留在原地（相对飞船，以飞船飞出的距离往后退），C["chase"] 起追上去，C["catch"] 停在船尾后方；
       追上飞船以后镜头一直跟着它，沿同一个方向（俯视顺时针）绕船转：左后方 -> 正后方 -> 右后方 -> 右侧 -> 船头前方
       -> 急停 -> 左侧 -> 左后上方，不来回折返。
  目标恒星：巨大的蓝色恒星（star_model.py，另一个模型做的），飞船最后停在它正上方；位置 = 停下时的位置 + 剩余行程。
       镜头跟着飞船的时候，远处的距离额外拉长，所以它只是前方一个小光点；急停之前镜头在船头前方仰看，恒星在镜头背后下方，
       不入画；急停后镜头绕过去、往下转，才把它引出来。抵达后飞船以 V_DRIFT 继续缓慢前进。

跃迁分镜（第 11 小节，共 2.4 秒）：
  · C["freeze"]（跃迁前 0.3 秒，配乐同时静音"吸气"）：慢动作——曲率环、电弧、泡纹几乎停住（动画时钟 tw 只走
    FREEZE_RATE 倍速），镜头不再颤，画面褪色；飞船慢慢向前拉长、蠕动，身后留下三个淡淡的重影。
  · C["warpjump"]：飞船被弹射出去；身后留下一道长长的航迹和一串渐隐的青色残影，第 0、3 个残影的两道曲率环
    各留下一圈透明激波环；发射点冲出两道透明激波环（都只扭曲背景、不发光），外加一圈随冲击波球面扩散的折射涟漪。
  · C["punch"]：飞船在消失点缩成一个光点，闪一下。C["shockhit"]：冲击波扫过镜头，第二下（更大的）震动。
  · C["chase"]：镜头沿着航迹追上去，与飞船的距离按指数缩小（画面上飞船匀速"长大"），视场角拉大，
    整幅画面经过 rush 形变（径向拖影 + 外圈拉伸 + 色散），星空出现星虹。C["catch"]：在船尾后方停稳。
抵达（第 14-17 小节，一镜到底）：
  · C["swing"]：镜头从右后方经右侧绕到船头前方偏右、略低处，仰看飞船；背景是身后红移变暗的星空，恒星不入画。
  · C["approach"]：最后一冲，速度读数从 13 c 一路降到 0。
  · C["dropout"]：飞船冲出超光速、猛地刹住。残影往前收拢进船身；身后的航迹从远到近熄灭；
    曲率泡 0.1 秒内塌进船身（周围的空间被往里一吸），随即反弹出一层透明的球形冲击波（arrival_shock）：
    只折射、不发光，从船身鼓出去、越胀越大，C["arr_hit"] 扫过镜头——整幅画面鼓一下、来回回弹几次（余震），
    镜头猛震；之后船身周围还有几圈越来越弱的涟漪，空间慢慢平静。（原来是一束高能粒子朝镜头喷，用户嫌"射线放射式喷"很 low。）
    船体被下方看不见的光源照成冷蓝色——先有光，后见星。
  · 镜头在原地停一会儿（看着余波平息），C["reveal"] 才起步：慢慢升起，从飞船左上方翻过去（俯视飞船时画面跟着转过半圈，像翻了个跟头），落到船后对准船头；
    恒星在船头前下方，翻的过程中一直在镜头背后，转过来对准船头、视线慢慢抬平时，星面才从画面下方铺开，
    最后停在船后上方：飞船压在发光的星面上，弧形的地平线在画面上部，片名在上方暗处。

超光速时看到的宇宙（科学示意 + 艺术夸张）：
  · 光行差把整片星空压向正前方，多普勒频移把它染成一圈彩虹——"星虹"（relstars 的 bow 参数）；身后的星空红移变暗。
    星虹只跟镜头的运动有关：镜头不动的分镜里看到的是普通星空。
  · 两层三维星场（远处的星、近处的尘埃）迎面掠过，近快远慢；每小节左右一颗恒星擦身而过，照亮飞船。
  · 曲率环：充能时开始转，跃迁后前后反向高速旋转；两环之间电弧跳动；曲率泡外壳显形，前沿堆积蓝白色的光，
    每一拍一道能量脉冲从船头沿外壳跑到船尾（与配乐的底鼓同拍）。
"""
import math
import numpy as np
from opusvid.gl import ease_in_out, ease_out_expo, smooth, lin, W, H, Camera
from config import BEAT, SHIP_AI
from cues import C, AI, SECS, charge_phase
from wfx import (CYAN, WHITE, ICE, darkspot, pulse, vis, Offscreen, glitch_text, stamp, bodies,
                 blit, streaks)
from ship import ship, ship_frame, roll, relstars, lens
import warpfield as F
import warpseq
import star_model
import shiphud

V_MAX = 260.0                    # 巡航速度（星场单位/秒）
V_SNAP = 8000.0                  # 跃迁弹射 / 抵达急停的峰值速度：飞船约 0.3 秒就从眼前缩成远处一个光点
SNAP_RISE = 0.25                 # 弹射从 0 升到峰值（急停从峰值降到 0）用的时间（秒）
WARP_C = 13.0                    # 巡航时显示的"光速倍数"（4.37 光年 / 约 4 个月）
SHUTTER = 0.03                   # 拖尾对应的"曝光时间"（秒）
FREEZE_RATE = 0.12               # 跃迁前慢动作窗口里动画（环的转动、电弧、泡纹）的速度
CREEP = 1.2                      # 慢动作窗口里飞船向前蠕动的距离
# 抵达时 α A 相对飞船停下处的位置与半径：半径 800，星心在船头前方 900、偏右 300、下方 700。
# 镜头翻过飞船、俯视它的时候恒星在镜头背后不入画；转到船后对准船头时星面才铺开；
# 最后的镜头里星心在画面外、只露一角（约占画面 58%），飞船整个压在发光的星面上，左上片名区是暗的（数值验证见 _keys_reveal）
A_RADIUS = 800.0
A_FINAL = np.array([-300.0, -700.0, 900.0])
V_DRIFT = 4.0                              # 抵达后飞船继续缓慢前进的速度（1.0 时完全看不出在动，用户要"保持缓速前进"）
HOLD_LAG = 0.6                             # 急停后镜头停着等的时候只跟上飞船前进的四成：飞船在画面里慢慢朝镜头滑过来；运镜途中逐渐跟上
EXIT_LEAD = 0.45                           # 退出超光速：急停前这么久，背景的径向拖线就从黑里亮起来（用户嫌触发太晚）
EXIT_DUR = 1.6                             # 急停后拖线从最长收成星点用的时间（参考《星球大战》跃出超空间；0.8 秒时用户说注意不到）
B_FINAL = np.array([-300.0, 120.0, 900.0])  # α B（较小、较远，橙色；离航线远，镜头拉向目的地时不会从它旁边擦过）
B_RADIUS = 7.0
PROXIMA = np.array([-420.0, -60.0, 2600.0])
# 巡航中掠过的恒星：(横向位置 x, y, 半径, 颜色)，与 C["flybys"] 一一对应
# 离航线很近（几十个单位），以巡航速度不到一秒就从画面一侧呼啸而过，并把飞船照亮
FLYBYS = [((-48.0, 14.0), 7.0, (0.7, 0.82, 1.0)), ((62.0, -10.0), 13.0, (1.0, 0.45, 0.2)),
          ((-36.0, 40.0), 5.0, (1.0, 0.95, 0.9)), ((52.0, 30.0), 8.0, (1.0, 0.8, 0.45))]
NEB_HALF = 520.0                           # 星云沿航线的半长
BUBBLE = 6.5                               # 曲率泡的世界半径（屏幕空间透镜用）
BRIDGE = (0.0, 1.0, 3.25)                  # 舰桥镜头的位置（导航 HUD 的视点）
STERN = 4.1                                # 船尾到飞船原点的距离（航迹从这里拖出去）
BOW = 5.0                                  # 船头到原点的距离（光障光环、冲击波、倾泻的粒子从这里出去）
GHOSTS, GHOST_DT = 6, 0.035                # 弹射时留下的残影：个数、相邻两个的时间间隔（秒）
ARR_WAVES = ((0.0, 1.0), (0.1, 0.5), (0.22, 0.28))   # 抵达冲击波：主波和两道余波（比主波晚多少秒、相对强度）
# 急停前后的镜头（相对飞船）：船头前方偏右、略低，仰看飞船。仰角让下方恒星的地平线落在画面下沿以外，恒星不入画
FRONT = ((5.0, -3.0, 17.0), (0.0, 1.5, 0.0), 40.0)


def _keys():
    """跃迁前的镜头关键帧：(时刻, 镜头位置, 注视点, 视场角)，世界坐标（飞船在原点、船头 +z）。位置、注视点逐分量单调三次插值。"""
    return [
        (C["warp"], BRIDGE, (0.0, 0.85, 60.0), 46.0),
        (C["handoff"], BRIDGE, (0.0, 0.85, 60.0), 46.0),                          # 舰桥，看着前方的半人马座 α
        # 从舰桥出来：垂直升起 -> 直接向后上方拉开，停在船尾后上方看充能（不绕到侧面，用户要的是"直接开始充能"）
        (C["handoff"] + 1.0, (0.0, 3.4, 2.2), (0.0, 0.6, 40.0), 46.0),             # 先垂直升起，越过舰桥上层建筑
        (C["charge"] + 2.2, (-3.0, 5.2, -11.0), (0.0, 0.0, 8.0), 46.0),           # 向后上方拉开：飞船从画面下方滑入，两道曲率环正对镜头
        (C["distort"], (-9.14, 5.17, -14.0), (0.3, 0.0, 9.0), 44.0),   # 充能期间缓缓移到后上方偏一侧，跃迁就从这里看
        (C["warpjump"], (-8.64, 4.58, -12.67), (0.3, 0.0, 9.0), 44.0),           # 跃迁时停在这里，看着飞船飞走
    ]


def _keys_cruise():
    """镜头追上飞船之后的关键帧：跟拍巡航时从左后方慢慢绕到正后方、右后方 -> 经右侧绕到船头前方（FRONT），停在那里。"""
    return [
        (C["catch"], (-5.07, 2.07, -7.76), (0.2, 0.2, 7.0), 74.0),           # 广角贴近船尾：背景透视拉得很开
        (C["catch"] + 3.0, (0.0, 3.2, -9.5), (0.0, 0.3, 8.0), 68.0),         # 慢慢绕到正后方
        (C["swing"], (5.75, 2.5, -8.43), (-0.3, 0.2, 8.0), 64.0),            # 右后方
        (C["swing"] + 0.6, (13.0, 2.5, 3.0), (0.0, 0.5, 3.0), 52.0),         # 右侧
        (C["swing"] + 1.2,) + FRONT,
    ]


def _keys_reveal():
    """急停之后的"翻跟头"：船头前方仰看 -> 升起越过船头 -> 飞船左上方俯视（顶点，视线朝向从船后转到船前，
    画面跟着转过半圈）-> 沿船后的弧线慢慢降下、视线慢慢抬向船头 -> 船后上方对准船头（第一帧就是 FRONT）。
    数值验证（恒星占画面比例，按 A_FINAL / A_RADIUS）：顶点之前一直是 0；过了顶点开始露出、很快铺到六成多，
    镜头抬平以后地平线和星空进画，停在约 58%，星心在画面外。全程飞船都在画面里。
    这里的时刻只决定路线和先后顺序；实际节奏由 WarpShot.reveal_tau 按路程重新分配（全程渐慢）。"""
    dp = C["dropout"]
    return [
        (dp + 0.4,) + FRONT,
        (dp + 1.1, (-3.0, 8.5, 9.5), (0.0, 0.5, 0.5), 42.0),       # 升起，越过船头
        (dp + 1.8, (-6.0, 13.0, 1.0), (0.0, 0.0, 0.0), 44.0),      # 顶点：飞船左上方俯视
        (dp + 2.5, (-5.5, 13.0, -4.5), (0.0, 0.0, 1.0), 44.0),     # 开始往船后降，视线转向船头
        (dp + 3.2, (-5.0, 11.0, -9.0), (0.0, 0.0, 3.0), 44.0),
        (dp + 3.9, (-4.0, 8.0, -12.5), (0.3, -0.3, 8.0), 44.0),    # 视线慢慢抬平：星面铺开，地平线进画
        (dp + 4.6, (-2.5, 5.0, -15.0), (0.5, -1.0, 14.0), 44.0),   # 船后上方对准船头：飞船压在星面上，片名在上方暗处
        (C["arrive"] + 9.6, (-2.8, 5.2, -15.0), (0.5, -0.9, 14.0), 44.0),
    ]


def hermite(keys, t, idx):
    """对第 idx 个分量做三次 Hermite 插值。切线用单调保形（Fritsch-Carlson）的取法：
    相邻两段斜率异号时切线为 0，否则取两段斜率的调和平均。这样关键帧间隔不均匀时也不会冲过头。"""
    ts = [k[0] for k in keys]
    if t <= ts[0]:
        return np.asarray(keys[0][idx], np.float64)
    if t >= ts[-1]:
        return np.asarray(keys[-1][idx], np.float64)
    i = max(j for j in range(len(ts) - 1) if ts[j] <= t)
    t0, t1 = ts[i], ts[i + 1]
    p0, p1 = np.asarray(keys[i][idx], np.float64), np.asarray(keys[i + 1][idx], np.float64)

    def tangent(j):
        if j == 0 or j == len(keys) - 1:
            return np.zeros_like(p0)
        pa, pj, pb = (np.asarray(keys[x][idx], np.float64) for x in (j - 1, j, j + 1))
        d0, d1 = (pj - pa) / (ts[j] - ts[j - 1]), (pb - pj) / (ts[j + 1] - ts[j])
        same = d0 * d1 > 0
        return np.where(same, 2.0 / (1.0 / np.where(same, d0, 1.0) + 1.0 / np.where(same, d1, 1.0)), 0.0)

    h = t1 - t0
    u = (t - t0) / h
    m0, m1 = tangent(i) * h, tangent(i + 1) * h
    return ((2 * u ** 3 - 3 * u ** 2 + 1) * p0 + (u ** 3 - 2 * u ** 2 + u) * m0 + (-2 * u ** 3 + 3 * u ** 2) * p1
            + (u ** 3 - u ** 2) * m1)


def key_pose(keys, t):
    return hermite(keys, t, 1), hermite(keys, t, 2), float(hermite(keys, t, 3))


def wobble(t, seed):
    """手持感的抖动波形（几组不成倍数的频率叠加，约 -1..1）。"""
    return (math.sin(t * 23.0 + seed) + 0.6 * math.sin(t * 37.7 + 1.3 * seed + 1.0)
            + 0.35 * math.sin(t * 61.3 + 2.1 * seed + 2.0)) / 1.95


class WarpShot:
    def __init__(self, e):
        self.e = e
        self.stream = F.StarStream(e)
        # 近处的尘埃：离航线更近、更暗更小，高速时从镜头边上呼啸而过（速度感的主要来源）
        self.dust = F.StarStream(e, n=4500, L=240.0, R=30.0, hole=4.8, seed=9)
        self.flow = F.RingFlow(e)
        self.sdust = F.ShockDust(e)
        self.keys, self.keys2, self.keys3 = _keys(), _keys_cruise(), _keys_reveal()
        # 急停后运镜的路程表（见 reveal_tau）：沿 keys3 采样，路程 = 镜头位移 + 8 × 视线转过的角度（弧度）
        tv = np.linspace(self.keys3[0][0], self.keys3[-1][0], 4000)
        eye = np.array([key_pose(self.keys3, x)[0] for x in tv])
        look = np.array([key_pose(self.keys3, x)[1] for x in tv]) - eye
        look /= np.linalg.norm(look, axis=1, keepdims=True)
        ds = (np.linalg.norm(np.diff(eye, axis=0), axis=1)
              + 8.0 * np.arccos(np.clip((look[1:] * look[:-1]).sum(1), -1.0, 1.0)))
        arc = np.concatenate([[0.0], np.cumsum(ds)])
        self.rv_t, self.rv_s = tv, arc / arc[-1]
        # 运镜的速度曲线（见 reveal_tau）：起步约 0.4 秒内从静止提起来，之后按 (1-x)^3 一路变慢，最后停稳
        x = np.linspace(0.0, 1.0, 4001)
        v = (1 - np.exp(-x / 0.04)) * (1 - x) ** 3
        f = np.concatenate([[0.0], np.cumsum((v[1:] + v[:-1]) * 0.5)])
        self.rv_x, self.rv_f = x, f / f[-1]
        self.tg = np.arange(C["charge"] - 1.0, C["arrive"] + 12.0, 1.0 / 240)
        v = np.array([self.speed(x) for x in self.tg])
        self.sg = np.concatenate([[0.0], np.cumsum((v[1:] + v[:-1]) * 0.5 * np.diff(self.tg))])
        vc = np.array([V_MAX * self.cruise(x) for x in self.tg])          # 只算巡航部分的行程（航程条用）
        self.scg = np.concatenate([[0.0], np.cumsum((vc[1:] + vc[:-1]) * 0.5 * np.diff(self.tg))])
        w = np.array([self.spin_rate(x) for x in self.tg])
        self.spg = np.concatenate([[0.0], np.cumsum((w[1:] + w[:-1]) * 0.5 * np.diff(self.tg))])
        self.s_jump = self.s(C["warpjump"])
        self.s_stop = self.s(C["dropout"])
        self.s_swing = self.s(C["swing"])
        self.s_neb = self.s(C["nebula"])
        self.s_fly = [self.s(x) for x in C["flybys"]]
        # 跃迁那一刻镜头相对飞船的位姿：跃迁分镜里镜头就停在这里
        self.launch = key_pose(self.keys, C["warpjump"])
        # 抵达冲击波：从船身鼓出，C["arr_hit"] 时正好扫到镜头（镜头这时停在 FRONT，离飞船这么远）
        self.arr_d = float(np.linalg.norm(self.pose(C["arr_hit"])[0]))
        # 冲击波从船头冲出，正好在 C["shockhit"] 扫过镜头
        self.shock_r = float(np.linalg.norm(self.launch[0] - np.array([0.0, 0.0, BOW])))
        # 追赶：剩余距离按 exp(-chase_k·x) 缩小，x 走到 0.75 左右时飞船已经回到眼前
        self.chase_k = math.log(max(self.s(C["catch"]) - self.s_jump, 20.0) / 1.5)

    # ------------------------------------------------ 运动学
    @staticmethod
    def cruise(t):
        """巡航程度 0..1：跃迁后到镜头追上之间升满；急停前 0.3 秒降到 0。"""
        up = ease_in_out(lin(C["warpjump"], C["catch"], t))
        down = 1 - ease_in_out(lin(C["dropout"] - 0.3, C["dropout"], t))
        return up * down

    @staticmethod
    def snap_env(tau, span):
        """弹射的速度包络 0..1（tau：离弹射时刻的秒数）：SNAP_RISE 秒内按三次方升到峰值，之后 span 秒内回落。
        抵达急停用同一条包络，把 tau 换成离急停时刻还有多少秒（时间上的镜像）。"""
        if tau <= 0:
            return 0.0
        return min(tau / SNAP_RISE, 1.0) ** 3 * (1 - smooth(SNAP_RISE, span, tau))

    def speed(self, t):
        j, d = C["warpjump"], C["dropout"]
        creep = CREEP / (j - C["freeze"]) if C["freeze"] <= t < j else 0.0
        return (V_MAX * self.cruise(t) + V_SNAP * self.snap_env(t - j, C["catch"] - j)
                + V_SNAP * self.snap_env(d - t, d - C["approach"]) + creep + V_DRIFT * smooth(d - 0.3, d, t))

    @staticmethod
    def fx(t):
        """曲率场的工作强度 0..1（环的转速与发光、泡的显形……）：跃迁那一下拉满，急停时熄灭。"""
        return smooth(C["warpjump"] - 0.1, C["warpjump"] + 0.15, t) * (1 - smooth(C["dropout"] - 0.05, C["dropout"] + 0.5, t))

    @staticmethod
    def tw(t):
        """动画时钟：跃迁前的慢动作窗口里只走 FREEZE_RATE 倍速（环、电弧、泡纹几乎停住），之后整体落后一个常数。"""
        a, j = C["freeze"], C["warpjump"]
        if t < a:
            return t
        if t < j:
            return a + (t - a) * FREEZE_RATE
        return t - (j - a) * (1 - FREEZE_RATE)

    def spin_rate(self, t):
        """曲率环转速（弧度/秒）：充能时慢慢转起来，空间扭曲时越转越快，超光速时飞转，抵达后回到怠速。"""
        return 0.6 * self.charge(t) + 1.0 * self.distort(t) + 3.2 * self.fx(t)

    @staticmethod
    def distort(t):
        """空间扭曲 0..1：C["distort"] 起越来越强（先慢后快），慢动作开始时最强，跃迁后归零（跃迁有自己的冲击波）。"""
        return smooth(C["distort"], C["freeze"], t) ** 1.5 * (1 - smooth(C["warpjump"], C["warpjump"] + 0.2, t))

    def s(self, t):
        return float(np.interp(t, self.tg, self.sg))

    def spin(self, t):
        return float(np.interp(t, self.tg, self.spg))

    @staticmethod
    def stretch(t):
        """飞船沿船轴向前拉长（船尾不动）：慢动作里慢慢拉长一点，弹射时猛地拉长，飞远以后恢复。"""
        j = C["warpjump"]
        tau = t - j
        if tau < 0:
            return 1.0 + 0.5 * ease_in_out(lin(C["freeze"], j, t))
        return 1.0 + (0.5 + 1.5 * smooth(0.0, 0.08, tau)) * (1 - smooth(0.3, 0.8, tau))

    @staticmethod
    def pull(t):
        """跃迁前一拍"吸气"：空间被拽向飞船、星空被拽向前方，跃迁时 0.25 秒内弹回。"""
        j = C["warpjump"]
        return smooth(j - 0.8, j, t) * (1 - smooth(j, j + 0.25, t))

    def pose(self, t):
        """镜头相对飞船的（位置, 注视点, 视场角），不含抖动。"""
        j = C["warpjump"]
        if t < j:
            return key_pose(self.keys, t)
        if t >= C["dropout"]:
            # 急停后飞船以 V_DRIFT 缓缓前进。镜头停着等的时候落后 HOLD_LAG（飞船朝镜头滑过来，看得出在动），
            # 运镜途中按运镜进度逐渐跟上，最后一帧回到 keys3 的构图（s_stop - s 停下后是负数）
            e3, g3, f3 = key_pose(self.keys3, self.reveal_tau(t))
            lag = HOLD_LAG * smooth(C["dropout"], C["dropout"] + 0.6, t) * (1 - self.reveal_f(t))
            off = np.array([0.0, 0.0, (self.s_stop - self.s(t)) * lag])
            return e3 + off, g3 + off, f3
        back = np.array([0.0, 0.0, self.s(t) - self.s_jump])       # 飞船跃迁后飞出的距离
        e0, g0, f0 = self.launch
        if t < C["chase"]:                                           # 镜头留在原地
            return e0 - back, g0 - back, f0
        e1, g1, f1 = key_pose(self.keys2, t)
        if t >= C["catch"]:
            return e1, g1, f1
        # 追赶：剩余距离先按指数缩小（飞船在画面上匀速变大），最后线性收到 0，停在船尾后方
        x = ease_in_out(lin(C["chase"], C["catch"], t))
        w = (1 - x) * math.exp(-self.chase_k * x)
        return e1 + (e0 - back - e1) * w, g1 + (g0 - back - g1) * w, f0 + (f1 - f0) * x

    def reveal_tau(self, t):
        """急停后运镜的时间重映射：keys3 只管路线，镜头实际走过的路程按 rv_f 分配到 C["reveal"] .. 段落结束。
        急停后镜头先停在原地看冲击波和余波（用户要"过一小会再开始运镜"），C["reveal"] 起约 0.4 秒内提起速度，
        之后一路连续变慢，最后一帧正好停稳（关键帧等间隔时 Hermite 插值近似匀速，用户嫌"像匀速的"，要渐慢）。"""
        return float(np.interp(self.reveal_f(t), self.rv_s, self.rv_t))

    def reveal_f(self, t):
        """急停后运镜的进度 0..1（C["reveal"] 之前为 0，段落结束为 1）。"""
        t0, t1 = C["reveal"], SECS["warp"]["end"]
        x = min(max((t - t0) / (t1 - t0), 0.0), 1.0)
        return float(np.interp(x, self.rv_x, self.rv_f))

    def shake(self, t):
        """镜头抖动强度：空间扭曲越来越强时开始发颤（慢动作里停住），跃迁一下、冲击波扫过镜头一下（更大），
        追赶时持续颤动，巡航时轻微；抵达时等待的镜头微微发颤，急停时一震，抵达冲击波扫过镜头时更大的一震。"""
        j, d = C["warpjump"], C["dropout"]
        pre = 0.15 * self.distort(t) * (t < C["freeze"])
        return (pre + 0.7 * pulse(t, j, 0.15) + 1.0 * pulse(t, C["shockhit"], 0.4)
                + 0.3 * vis(t, C["chase"], C["catch"] + 0.2, 0.3, 0.4) + 0.06 * self.cruise(t)
                + 0.12 * smooth(C["approach"], d, t) * (t < d) + 0.6 * pulse(t, d, 0.2) + 1.4 * pulse(t, C["arr_hit"], 0.45))

    def camera(self, t):
        eye, tgt, fov = self.pose(t)
        a = self.shake(t)
        if a > 1e-4:
            # 旋转抖动：注视点在垂直视线的平面里晃（a=1 时约 0.016 弧度，1080p 下二十来个像素），再加一点平移
            f = tgt - eye
            dist = float(np.linalg.norm(f))
            r = np.cross(f, (0.0, 1.0, 0.0))
            r /= np.linalg.norm(r)
            u = np.cross(r, f) / dist
            jx, jy = wobble(t, 0.0), wobble(t, 2.7)
            tgt = tgt + (r * jx + u * jy) * dist * 0.016 * a
            eye = eye + (r * jy + u * jx) * 0.06 * a
        return Camera(tuple(eye), tuple(tgt), fov=fov)

    def cam_z(self, t):
        """镜头在星场里走过的距离（飞船行程 + 镜头相对飞船的 z）。"""
        return self.s(t) + float(self.pose(t)[0][2])

    def cam_k(self, t):
        """镜头相对星空的"速度感" 0..1（星虹、光行差），按镜头在星场里的实际速度算：
        跃迁、抵达分镜里镜头不动为 0，追赶、拉向目的地时迅速升满，巡航时约等于 1。低于 20 单位/秒的慢速移动不算。"""
        if t < C["chase"]:
            return 0.0
        h = 1.0 / 240
        v = abs(self.cam_z(t + h) - self.cam_z(t - h)) / (2 * h)
        return min(1.0, max(0.0, (v - 20.0) / (V_MAX - 20.0)))

    @staticmethod
    def rush_amt(t):
        """追赶飞船时的全画面形变强度：中段最强，两头归零。"""
        x = lin(C["chase"], C["catch"], t)
        return math.sin(math.pi * x ** 0.8) ** 1.5 if 0 < x < 1 else 0.0

    @staticmethod
    def freeze_amt(t):
        """慢动作窗口的"褪色"程度：窗口开始时迅速褪色，跃迁那一下颜色猛地回来。"""
        return smooth(C["freeze"], C["freeze"] + 0.08, t) * (t < C["warpjump"])

    @staticmethod
    def charge(t):
        return float(np.clip((t - C["charge_on"]) / (C["charge_full"] - C["charge_on"]), 0.0, 1.0))

    @staticmethod
    def flash(t):
        """充满时的一次闪光。"""
        x = t - C["charge_full"]
        return math.sin(math.pi * min(x / 0.45, 1.0)) ** 2 if x >= 0 else 0.0

    def target_a(self, t):
        """α A 当前相对飞船的位置（剩余行程 r 越短越近）。
        半径 500 的恒星按真实行程摆，4 光年外就已经是个大圆盘；所以把远处的距离额外拉长成 r·(1 + r/100)，
        巡航时它只是前方一个小光点。镜头绕到船头前方以后（恒星在镜头背后下方、不入画）才慢慢收回成真实行程，
        急停时已经完全收回，之后恒星相对世界不动。"""
        r = self.s_stop - self.s(t)
        far = 1 - smooth(C["swing"] + 1.2, C["dropout"] - 0.3, t)
        return A_FINAL + np.array([0.0, 0.0, r * (1 + far * max(r, 0.0) / 100.0)])

    # ------------------------------------------------ 背景星空（导航段也用它，保证接得上）
    @staticmethod
    def exit_amt(t):
        """退出超光速的拖线长度 1..0：急停前 EXIT_LEAD 秒起为 1，急停后 EXIT_DUR 秒内先快后慢地降到 0；更早为 0。"""
        dp = C["dropout"]
        if t < dp - EXIT_LEAD:
            return 0.0
        return (1 - lin(dp, dp + EXIT_DUR, t)) ** 1.6

    def sky(self, cam, t):
        # 退出超光速期间画没有光行差的真实星空（之后经径向拖影出现）；不然急停前倒着看，光行差下是一片黑
        k = 0.0 if self.exit_amt(t) > 0 else self.cam_k(t)
        pull = self.pull(t)
        # 跃迁前一拍：整片星空被拽向正前方；追赶、巡航：接近光速的光行差 + 星虹
        beta = max(0.985 * k ** 0.6, 0.75 * pull ** 1.5)
        relstars(self.e, cam, beta=beta, stars=0.85 - 0.35 * k, neb=0.4, gal=(0.25, 0.9, -0.3), bow=0.6 * min(1.0, 1.2 * k))

    # ------------------------------------------------ 画面
    def navigation_sky(self, cam, t):
        """导航时也画实景目标，锁定框不能落在一颗未渲染的星上。"""
        self.sky(cam, t)
        self.stars(cam, t, self.s(t))

    def render(self, t):
        e = self.e
        cam = self.camera(t)
        ra = self.rush_amt(t)
        d = self.s(t) - self.s_jump if t >= C["warpjump"] else 0.0
        rip = self.ripple(t, cam, d)
        rings = self.shock_rings(t, d)
        shells, bulge = self.arrival_shock(t)
        if ra > 0.002 or rip or rings or shells or bulge:
            # 冲击波和追赶形变作用在整幅画面上（航迹、飞船、星云一起被扭弯）：只扭背景的话，
            # 稀疏的黑色星空上几乎看不出来（用户反映"跃迁时的圆环扭曲冲击波没有"）
            with Offscreen(e, 1) as frame:
                self.world(t, cam)
            src = frame
            if rip:
                # 折射涟漪：沿径向推开再拉回，不发光（跃迁时随冲击波球面扩散，急停时从飞船处散开）
                with Offscreen(e, 3) as rtex:
                    lens(e, src, rip[0], 1.0, (1.0, 0.0), warp=0.0, rim=0.0, chroma=0.0, tint=0.0, ripple=rip[1])
                src = rtex
            if rings:
                with Offscreen(e, 4) as rw:
                    drawn = F.ring_warp(e, cam, src, rings, chroma=0.2)
                if drawn:
                    src = rw
            if shells or bulge:
                with Offscreen(e, 5) as sw:
                    drawn = F.shock(e, cam, src, (0.0, 0.0, 0.0), shells, bulge, chroma=0.015, haze=0.16)
                if drawn:
                    src = sw
            if ra > 0.002:
                # 追赶：形变中心取镜头运动方向的消失点（星星拖线汇聚的地方）；
                # 取别处的话径向拖影和星星自己的拖线方向交叉，会把每条拖线抹成平行四边形
                foe = cam.project(tuple(np.asarray(cam.eye) + np.array([0.0, 0.0, 1000.0])))
                F.rush(e, src, foe[:2] if foe else (W / 2, H / 2), ra, zoom=0.25)
            else:
                blit(e, src)
        else:
            self.world(t, cam)
        self.hud(t)

    def ship_kw(self, t):
        """t 时刻飞船的绘制参数（残影用它们过去时刻的值）。环的转角、相位走动画时钟 tw（慢动作里几乎停住）。"""
        k = self.fx(t)
        tw = self.tw(t)
        lvl = self.charge(t)
        flash = self.flash(t)
        dist = self.distort(t)
        wave = pulse(t, C["distort"], 0.4)
        jump = pulse(t, C["warpjump"], 0.45)
        pull = self.pull(t)
        arrived = smooth(C["dropout"] - 0.2, C["dropout"] + 0.6, t)
        sun, sun_col = self.light(t, self.s(t))
        # 环槽的光：充能时随脉冲一下一下搏动（与配乐同拍），越充越亮
        beat = self.charge_amt(t) * lvl * (1.0 + 5.0 * self.charge_pulse(t))
        # 急停：曲率场积攒的能量从环里泄掉——环猛地一亮（也照亮船体），1 秒多慢慢冷却
        beat += 2.5 * pulse(t, C["dropout"], 0.6)
        return dict(ring=0.35 + 0.6 * lvl + 0.8 * flash + 0.6 * dist + 0.5 * wave + 1.0 * k + 0.6 * jump + 0.6 * pull + beat,
                    charge=lvl, charge_flash=flash, phase=tw * (2 + 12 * lvl + 20 * k), engine=0.3 + 0.5 * lvl + 0.6 * k,
                    flow=lvl * 0.8 * (1 - arrived), stretch=self.stretch(t), sun=sun, sun_col=sun_col, spin=self.spin(tw),
                    warp_on=min(1.0, 0.25 * (t >= C["charge_full"]) + 0.75 * dist + pull + jump + k) * (1 - arrived),
                    fill=tuple(np.array([0.22, 0.27, 0.36]) * (1 - arrived) + np.array([0.24, 0.30, 0.42]) * arrived))

    def ghost(self, cam, R, tg, z, a, tint):
        """飞船在 tg 时刻的样子画在相对现在飞船 z 处，染色后叠加（残影、重影）。"""
        e = self.e
        kw = self.ship_kw(tg)
        with Offscreen(e, 2) as gt:
            ship(e, cam, (0.0, 0.0, z + STERN * (kw["stretch"] - 1.0)), R, 1.0, **kw)
        blit(e, gt, a, tint=tint)

    def world(self, t, cam):
        e = self.e
        j, dp = C["warpjump"], C["dropout"]
        tau = t - j
        k = self.fx(t)
        tw = self.tw(t)
        s = self.s(t)
        lvl = self.charge(t)
        flash = self.flash(t)
        dist = self.distort(t)
        wave = pulse(t, C["distort"], 0.4)
        jump = pulse(t, j, 0.45)
        pull = self.pull(t)
        arrived = smooth(dp - 0.2, dp + 0.6, t)
        cruise = smooth(C["catch"] - 0.3, C["catch"] + 0.5, t) * (1 - smooth(dp - 0.3, dp, t))
        d = s - self.s_jump if tau >= 0 else 0.0                # 飞船跃迁后飞出的距离；发射点在 (0, 0, -d)
        R = roll(ship_frame((0, 0, 1)), 0.05 * math.sin(t * 0.4))
        # 抵达分镜里镜头在飞船前方：身后的航迹、往前收拢的残影都在飞船后面，要先画、让飞船挡住
        front = C["swing"] <= t and cam.eye[2] > -STERN
        # ---- 背景（进离屏缓冲，再经过冲击波涟漪和曲率泡透镜）
        with Offscreen(e, 0) as bg:
            self.sky(cam, t)
            # 三维星场只在镜头动起来以后出现（镜头不动时看到的就是普通星空）；星场盒子跟着镜头走
            # 镜头开始运镜、转向恒星以后三维星场淡出：飞船还在缓缓前进，近处的星星会一直朝镜头涌过来（用户反映）
            calm = 1 - smooth(C["reveal"], C["reveal"] + 1.5, t)
            on = (smooth(C["chase"] - 0.1, C["chase"] + 0.4, t) * (1 - 0.7 * smooth(C["approach"] - 0.05, C["approach"], t))
                  * calm)
            if on > 0:
                z0 = cam.eye[2]
                ds = self.cam_z(t) - self.cam_z(t - SHUTTER)
                self.stream.draw(cam, s, ds, gain=2.2 * on, size=1.4, z0=z0)
                # 急停后近处的尘埃再淡入一些：星空在无穷远，只有它们的视差看得出飞船还在缓缓前进
                dg = 1.1 * on * cruise * (t < C["approach"]) + 0.9 * smooth(C["dropout"] + 0.3, C["dropout"] + 1.2, t) * calm
                self.dust.draw(cam, s, ds, gain=dg, size=0.7, max_len=60.0, z0=z0)
            F.nebula(e, cam, self.s_neb - s, half=NEB_HALF, amt=0.14 * smooth(C["catch"] - 0.4, C["catch"] + 1.2, t), seed=3.0)
            self.stars(cam, t, s)
        src = bg
        ex = self.exit_amt(t)
        if ex > 0.003:
            # 退出超光速：急停那一刻镜头的速度没了，光行差一下子消失，星空和星云会在同一帧里突然冒出来（用户反映）。
            # 改成参考视频里跃出超空间的样子：背景先是一根根朝消失点（镜头身后运动方向的反方向，就在飞船背后）的
            # 径向长拖线：急停前 EXIT_LEAD 秒从黑里亮起来，急停后 EXIT_DUR 秒内先快后慢地收成一个个星点；
            # 拖线越长越暗，用 gain 补亮（再多给一些，用户嫌"不仔细看都注意不到"）
            dp = C["dropout"]
            foe = cam.project(tuple(np.asarray(cam.eye) - np.array([0.0, 0.0, 1000.0])))
            with Offscreen(e, 7) as xt:
                F.rush(e, src, foe[:2] if foe else (W / 2, H / 2), 1.0, zoom=0.96 * ex, stretch=0.3 * ex, twist=0.0,
                       chroma=0.008 * ex, gain=(1.0 + 8.0 * ex ** 1.3) * smooth(dp - EXIT_LEAD, dp - EXIT_LEAD + 0.25, t))
            src = xt
        disks = self.ring_disks(t)
        if disks:
            # 充能：两道环周围的星空被拧弯（只折射，不发光）
            with Offscreen(e, 6) as rl:
                drawn = F.ring_lens(e, cam, src, disks)
            if drawn:
                src = rl
        sp = cam.project((0.0, 0.0, 0.0))
        fw = cam.project((0.0, 0.0, 1.0))
        if sp is None or fw is None:          # 镜头在舰桥上时飞船中心在镜头后方：背景原样画出
            blit(e, src)
        else:
            # 曲率泡：充能时开始轻微扭曲 -> 空间扭曲时越来越强 -> 跃迁前一拍把周围空间往里吸 -> 跃迁时鼓一下 -> 巡航保持 -> 急停时消退
            warp = (0.05 * lvl + 0.3 * dist + 0.3 * pull + 0.35 * jump + 0.22 * k) * (1 - arrived)
            rp = BUBBLE / sp[2] * cam.pix
            lens(e, src, sp[:2], rp * (1.0 + 0.6 * jump + 0.3 * pull), (fw[0] - sp[0], fw[1] - sp[1]), warp=warp,
                 rim=0.0, chroma=0.003, tint=0.25, sigma=1.4)
        if front:
            self.arrival_behind(t, cam, R)
        # ---- 曲率泡外壳（背面）-> 飞船 -> 外壳（正面）-> 电弧
        bub = ((0.2 * lvl + 0.35 * dist + 0.35 * wave + 0.5 * pull + 0.3 * jump + 0.55 * k) * (1 - arrived)
               * smooth(C["charge"], C["charge"] + 1.0, t) + 0.3 * pulse(t, dp, 0.1))
        # 急停：曲率泡 0.1 秒内塌进船身、边缘亮一下随即消失；塌缩反弹出的球形冲击波见 arrival_shock
        shrink = 1 - 0.75 * smooth(dp - 0.03, dp + 0.1, t)
        flow_t = 1.5 * tw + s / 25.0
        pls = -2.0
        if cruise > 0.2:                                  # 巡航：每一拍一道脉冲从船头跑到船尾
            pls = 1.15 - 2.6 * (((t - j) / BEAT) % 1.0)
        bkw = dict(cap=0.2 * pull + 0.4 * k * (1 - arrived), pulse=pls, pulse_w=0.08,
                   flash=0.25 * jump + 0.3 * flash + 0.3 * pulse(t, dp, 0.1), axes=(3.0 * shrink, 3.0 * shrink, 6.2 * shrink))
        # 充能：能量微粒螺旋着卷进两道环（远侧一半先画、被船体挡住，近侧一半后画）
        ph = float(charge_phase(tw))
        famt = 1.1 * self.charge_amt(t) * (0.3 + 0.7 * lvl) * (0.7 + 0.6 * self.charge_pulse(t))
        self.flow.draw(cam, R, ph, famt, 1.0)
        # 抵达冲击波扫过的星际尘埃（远侧一半先画、被船体挡住）
        # 波前越胀越大，同样的能量摊到更大的面上：亮度按 (3.5/R)^1.5 变暗——贴着飞船时是一层密的亮壳，铺满画面时只剩一层薄纱
        fronts = [(R, 0.45 * wd, g * (3.5 / R) ** 1.5) for R, wd, g in self.arr_fronts(t)]
        self.sdust.draw(cam, (0.0, 0.0, 0.0), fronts, 2.4, 1.0)
        F.bubble(e, cam, 0, bub, flow_t, **bkw)
        kw = self.ship_kw(t)
        ship(e, cam, (0.0, 0.0, STERN * (kw["stretch"] - 1.0)), R, 1.0, **kw)
        F.bubble(e, cam, 1, bub, flow_t, **bkw)
        self.flow.draw(cam, R, ph, famt, -1.0)
        self.sdust.draw(cam, (0.0, 0.0, 0.0), fronts, 2.4, -1.0)
        arc_amt = (0.35 * (t >= C["charge_full"]) + 1.0 * dist + 1.6 * pull + 1.5 * jump + 0.8 * k) * (1 - arrived)
        F.arcs(e, cam, tw, arc_amt, n=2 + int(2 * k + 4 * pull))
        if C["freeze"] <= t < j + 0.12:
            # 慢动作里的重影：飞船刚才蠕动经过的位置上留着三个淡淡的影子
            for i in range(3):
                tg = C["freeze"] + i * 0.1
                if t > tg + 0.02:
                    self.ghost(cam, R, tg, self.s(tg) - s, 0.22 * (1 - smooth(j, j + 0.12, t)), (0.8, 1.2, 1.8))
        if 0 <= tau and t < C["catch"]:
            self.departure(t, cam, d, R)
        if C["swing"] <= t < C["arrive"] + 3.0:
            if not front:
                self.arrival_behind(t, cam, R)
            self.arrival_front(t, cam)

    def ripple(self, t, cam, d):
        """当前的折射涟漪：(屏幕中心, (半径 px, 位移幅度 px, 宽度 px))，没有时为 None。
        跃迁：涟漪跟着冲击波球面扩散，正好在 C["shockhit"] 扫过镜头（急停的冲击波见 arrival_shock）。"""
        tau = t - C["warpjump"]
        if 0 <= tau < C["shockhit"] - C["warpjump"] + 0.2:
            c = np.array([0.0, 0.0, BOW - d])
            q = cam.project(tuple(c))
            if q:
                dist = float(np.linalg.norm(np.asarray(cam.eye) - c))
                rpx = cam.pix * math.tan(math.asin(min(self.shock_radius(t) / dist, 0.999)))
                return q[:2], (rpx, 34.0 * math.exp(-tau / 0.5), 50.0 + 160.0 * tau)
        return None

    @staticmethod
    def charge_amt(t):
        """充能特效（环里的空间扭曲、卷进环的微粒、环槽随脉冲搏动）的总开关：充能开始时淡入，跃迁时熄灭。"""
        return smooth(C["charge_on"] - 0.2, C["charge_on"] + 0.6, t) * (1 - smooth(C["warpjump"] - 0.05, C["warpjump"] + 0.2, t))

    def charge_pulse(self, t):
        """充能脉冲的包络 0..1：整数相位处是一下（与配乐 music.charge_spinup 同拍）。相位走动画时钟 tw，慢动作里几乎停住。"""
        return (0.5 + 0.5 * math.cos(2 * math.pi * float(charge_phase(self.tw(t))))) ** 6

    def ring_disks(self, t):
        """两道环周围的空间扭曲（F.ring_lens 的参数）：随充能加强，每个脉冲拧一下；空间扭曲阶段越拧越弯，
        跃迁前的"吸气"里猛地往里收。前后两道环拧的方向相反（和环的转向一致）。"""
        ca = self.charge_amt(t)
        if ca <= 0.001:
            return []
        lvl = self.charge(t)
        pl = self.charge_pulse(t)
        dist = self.distort(t)
        a = ca * ((0.12 + 0.3 * lvl) * (0.75 + 0.5 * pl) + 0.45 * dist)
        m = ca * (0.03 + 0.08 * lvl * (0.6 + 0.4 * pl) + 0.15 * dist + 0.35 * self.pull(t))
        return [(0.25, 1.72, a, m), (-1.65, 1.72, -a, m)]

    def shock_rings(self, t, d):
        """透明激波环：(所在平面 z, 半径, 环带半宽, 最大位移像素)。
        空间扭曲开始：两道曲率环各推出一圈。跃迁：发射点船头冲出三道，留在原地扩散；第 0、3 个残影的两道曲率环各留下一圈小的，慢慢扩大。"""
        rings = []
        j = C["warpjump"]
        # 空间扭曲开始：两道环各推出一圈扭曲波
        age = t - C["distort"]
        if 0 < age < 1.4:
            for zr in (0.25, -1.65):
                rings.append((zr, 1.72 * (1 + 4.0 * age ** 0.7), 0.3 + 1.0 * age,
                              30.0 * math.exp(-age / 0.45) * smooth(0.0, 0.03, age)))
        for i in (0, 3):
            tg = j + i * GHOST_DT
            age = t - tg
            if 0 < age < 1.2:
                zg = self.s(tg) - self.s_jump - d
                a = math.exp(-age / 0.3) * (1 - i / (GHOSTS + 1))
                for zr in (0.25, -1.65):
                    rings.append((zg + zr, 1.72 * (1 + 1.2 * age), 0.3 + 0.5 * age, 22.0 * a * smooth(0.0, 0.03, age)))
        # 跃迁：发射点三道（间隔 0.15 秒左右），位移大、扩散慢（约 1 秒才扫出画面），依次扫过航迹光柱和星云、把它们折弯；
        # 扩散太快的话 0.3 秒就冲出画面，只是一闪（用户反映看不到）
        for i, dl in enumerate((0.0, 0.15, 0.32)):
            tj = t - j - dl
            if 0 < tj < 2.0:
                rings.append((BOW - d + 1.5 * i, 3.0 + 18.0 * tj ** 0.7, 0.8 + 2.0 * tj,
                              85.0 * math.exp(-tj / 0.9) * (1 - 0.3 * i) * smooth(0.0, 0.04, tj)))
        return rings

    def arr_fronts(self, t):
        """抵达冲击波此刻还没扫过镜头的波前：[(半径, 壳厚, 强度 0..1)]（折射和被照亮的尘埃共用）。
        急停后 0.06 秒从泡的大小（半径 3.5）鼓出，C["arr_hit"] 正好扫过镜头。半径按 x^1.2 增长：
        镜头离飞船只有十几个单位，先快后慢的话不到 0.1 秒就冲出画面，看不清；稍微先慢后快，
        冲击波先在飞船周围鼓起来、占满画面，再扑向镜头。"""
        dp = C["dropout"]
        R0 = 3.5
        T = C["arr_hit"] - dp - 0.06                       # 每道波从发出到扫过镜头都用这么久
        out = []
        for dl, g in ARR_WAVES:
            tau = t - dp - 0.06 - dl
            if 0 < tau < T:
                x = tau / T
                out.append((R0 + (self.arr_d - R0) * x ** 1.2, 1.2 + 1.6 * x, g * smooth(0.0, 0.05, tau) * (1 - smooth(0.8, 1.0, x))))
        return out

    def arrival_shock(self, t):
        """急停的球形冲击波（F.shock 的参数）：(球壳列表, 整幅画面的鼓胀量)，球心在飞船中心。
          塌缩   急停那 0.1 秒：曲率泡塌进船身，周围的空间被往里吸（半径 0、位移为负的一层）。
          主波   紧接着反弹出来（arr_fronts），C["arr_hit"] 正好扫过镜头；后面跟两道弱一些的（ARR_WAVES）。
                 波前扫过的星际尘埃同时被照亮（world 里的 ShockDust）。
          余震   每道波扫过镜头，整幅画面先往外鼓、再来回回弹几下（阻尼振荡）。
          余波   之后飞船周围隔 0.4 秒左右再荡开一圈小涟漪，一圈比一圈弱，C["reveal"] 之前平息。"""
        dp = C["dropout"]
        if not dp - 0.05 < t < dp + 3.0:
            return [], 0.0
        shells, bulge = [], 0.0
        u = lin(dp - 0.04, dp + 0.1, t)
        if 0 < u < 1:
            shells.append((0.0, 3.5, -55.0 * math.sin(math.pi * u), 0.0))
        for R, wd, g in self.arr_fronts(t):
            # 折射带比尘埃层宽一倍：窄了会把波前上的光点和星星拉成径向的短线（又像放射的射线）。
            # 纹影和边缘薄雾随半径变淡：球胀到占满画面时还那么亮，整幅画面会蒙上一层灰雾
            shells.append((R, 2.0 * wd, 70.0 * g, 0.3 * g * (3.5 / R) ** 1.2))
        T = C["arr_hit"] - dp - 0.06
        for dl, g in ARR_WAVES:
            th = t - dp - 0.06 - dl - T                    # 扫过镜头之后：画面鼓一下再回弹
            if th > 0:
                bulge += 0.05 * g * math.exp(-th / 0.3) * math.sin(2 * math.pi * th / 0.34)
        for dl, g in ((0.55, 1.0), (0.95, 0.55), (1.35, 0.3)):
            tau = t - dp - dl
            if 0 < tau < 1.4:
                shells.append((3.0 + 9.0 * tau ** 0.6, 0.7 + 1.4 * tau, 18.0 * g * math.exp(-tau / 0.5) * smooth(0.0, 0.08, tau),
                               0.06 * g * math.exp(-tau / 0.5)))
        return shells, bulge

    def shock_radius(self, t):
        """冲击波球壳的半径：从船头冲出，C["shockhit"] 时正好扫到镜头。"""
        tau = max(t - C["warpjump"], 0.0)
        return self.shock_r * (tau / (C["shockhit"] - C["warpjump"])) ** 0.6

    def departure(self, t, cam, d, R):
        """跃迁分镜里留在原地的东西：航迹、残影（连同两道曲率环的光环）、冲击波球壳、飞船缩成光点时的闪光。"""
        e = self.e
        j = C["warpjump"]
        tau = t - j
        fade = 1 - smooth(C["chase"] + 0.2, C["catch"] - 0.3, t)     # 镜头追上去时航迹淡出
        F.trail(e, cam, (0.0, 0.0, -d - STERN), (0.0, 0.0, -STERN), fade * smooth(0.0, 0.05, tau), tau, seed=2.0)
        # 残影：飞船在 j + i·GHOST_DT 时刻的样子留在当时的位置上，青色、渐隐（越早留下的越大、越亮）
        for i in range(GHOSTS):
            tg = j + i * GHOST_DT
            if t < tg:
                break
            age = t - tg
            a = 0.6 * math.exp(-age / 0.3) * (1 - i / (GHOSTS + 1))
            if a < 0.01:
                continue
            zg = self.s(tg) - self.s_jump - d                      # 残影相对现在飞船的位置
            # 船体本身偏暗，残影按 2 倍左右提亮才读得出轮廓
            self.ghost(cam, R, tg, zg, a, (1.0, 1.6, 2.2) if i else (1.3, 1.6, 1.8))
            # 第 0、3 个残影的曲率环留下的是透明激波环（shock_rings），不再画发光的环
        # 飞船在消失点缩成一个光点：闪一下，带横向星芒
        pa = pulse(t, C["punch"], 0.12) * smooth(C["punch"] - 0.05, C["punch"], t)
        if pa > 0.01:
            q = cam.project((0.0, 0.0, 0.0))
            if q:
                bodies(e, [(q[0], q[1], 22.0, 3.0 * pa, (0.7, 0.88, 1.0), 1.0)])

    def arrival_behind(self, t, cam, R):
        """抵达时飞船身后的东西：航迹（急停后从远到近熄灭）、刹住后慢慢收拢进船身的残影。"""
        e = self.e
        dp = C["dropout"]
        s = self.s(t)
        # 航迹：从镜头开始绕向船头时飞船所在处一直拖到船尾；急停后被冲击波吹散——远端往船尾缩，1 秒左右熄灭
        #（原来拖 2 秒多，镜头停着等的时候像船尾插着一根光柱）
        far = (s - self.s_swing) * (1 - ease_in_out(lin(dp + 0.1, dp + 1.0, t)))
        if far > 0.5:
            F.trail(e, cam, (0.0, 0.0, -far - STERN), (0.0, 0.0, -STERN), 1 - smooth(dp + 0.5, dp + 1.1, t), 0.15,
                    seed=6.0)
        # 残影：飞船在 t - i·0.035 秒时的位置；冲过来时一串排在身后（越早的离得越远）。
        # 刹住以后不立刻消失（用户要"身后应该有残影"）：停在刹住那一刻的位置上，约 0.9 秒的时间常数往船身收拢，
        # 1.2 秒的时间常数变淡，镜头开始运镜时还隐约看得到
        win = smooth(dp - 0.3, dp - 0.15, t)
        if win > 0.01:
            tau = max(t - dp, 0.0)
            for i in range(1, GHOSTS):
                tg = min(t, dp) - i * GHOST_DT
                z = (self.s(tg) - self.s(min(t, dp))) * math.exp(-tau / 0.9)
                a = 0.5 * win * (1 - i / (GHOSTS + 1)) * math.exp(-tau / 1.2)
                if a > 0.01:
                    self.ghost(cam, R, tg, z, a, (1.0, 1.6, 2.2))

    def arrival_front(self, t, cam):
        """抵达时飞船前方的东西：冲过来时远处的光点。
        急停那一刻不画闪光球、不喷粒子——用户嫌"很廉价""射线放射式喷很 low"；急停改由曲率泡塌缩、环的能量泄出
        和球形冲击波（arrival_shock）来讲。"""
        e = self.e
        dp = C["dropout"]
        q = cam.project((0.0, 0.0, BOW))
        # 远处的飞船：离镜头一百多个单位、看不清船体以后是一个光点，冲过来时越来越亮、微微闪烁
        if t < dp and q:
            dist = float(np.linalg.norm(np.asarray(cam.eye)))
            pa = smooth(120.0, 500.0, dist) * (0.4 + 2.6 * smooth(C["approach"], dp - 0.25, t)) * (1 - smooth(dp - 0.12, dp, t))
            pa *= 0.85 + 0.15 * math.sin(t * 61.0)
            bodies(e, [(q[0], q[1], 6.0 + 10.0 * smooth(dp - 0.6, dp - 0.1, t), pa, (0.65, 0.85, 1.0), 0.35)])

    def stars(self, cam, t, s):
        """目标恒星 α A、α B、比邻星，以及巡航中掠过的恒星。"""
        a = self.target_a(t)
        b = B_FINAL + np.array([0.0, 0.0, self.s_stop - s])
        star_model.star(self.e, cam, tuple(b), B_RADIUS, color=(1.0, 0.5, 0.2), bright=0.6, corona=0.7, prom=0.5, seed=4.0)
        # α A：艺术化蓝巨星（参数见 STAR_MODEL.md）。半径 500、镜头贴着星面，米粒密度要按这个尺度加大
        # corona 调低：镜头贴着星面时 star_model 的日冕在天空里切出一条直线边界（已写进 STAR_REFINE_PROMPT.md，等重做）
        star_model.star(self.e, cam, tuple(a), A_RADIUS, color=(0.16, 0.48, 1.0), bright=0.5, blue=1.0, spots=0.25,
                        seed=1.0, granules=1500.0, corona=0.35)
        q = cam.project(tuple(PROXIMA))
        if q:
            bodies(self.e, [(q[0], q[1], 1.6, 0.7, (1.0, 0.25, 0.15), 0.3)])
        # 掠过的恒星只在超光速巡航时出现（跃迁前它们远在光年之外，看不见）
        fa = smooth(C["chase"], C["catch"], t) * (t < C["approach"])
        for (xy, rad, col), sf in zip(FLYBYS, self.s_fly):
            zf = sf - s
            if fa > 0 and -1200 < zf < 4000:
                star_model.star(self.e, cam, (xy[0], xy[1], zf), rad, color=col, bright=0.8 * fa, corona=0.8, prom=0.4,
                                seed=7.0 + rad)

    def light(self, t, s):
        k = self.fx(t)
        # 平时：侧上方的冷白光；巡航：被前方蓝移的星光从正前方照亮
        base = np.array([0.35, 0.75, 0.55]) * (1 - k) + np.array([0.1, 0.35, 1.0]) * k
        col = np.array([1.5, 1.5, 1.6]) * (1 - k) + np.array([1.2, 1.7, 2.6]) * k
        arrived = smooth(C["approach"], C["dropout"], t)
        a = self.target_a(t)
        # 抵达：巨大的蓝色恒星在船头前下方，冷蓝的光从前下方照过来（盘面很大，光来自整片星面，往上偏一点）
        sun_dir = a / np.linalg.norm(a) + np.array([0.0, 0.25, 0.0])
        base = base * (1 - arrived) + sun_dir / np.linalg.norm(sun_dir) * arrived
        col = col * (1 - arrived) + np.array([1.5, 2.2, 3.4]) * arrived
        # 掠过的恒星：靠近时把飞船照亮
        for (xy, rad, c), sf in zip(FLYBYS, self.s_fly):
            p = np.array([xy[0], xy[1], sf - s])
            near = math.exp(-abs(p[2]) / 90.0) * 0.9
            if near > 0.01:
                base = base * (1 - near) + p / np.linalg.norm(p) * near
                col = col + np.array(c) * 2.2 * near
        return tuple(base), tuple(col)

    def post(self, t):
        """后期参数：慢动作里褪色变暗，跃迁、光点闪光、急停时曝光猛地一跳；冲击波扫过镜头、追赶形变时色差加大。"""
        j, dp = C["warpjump"], C["dropout"]
        fr = self.freeze_amt(t)
        arrived = smooth(C["arrive"] - 2.0, C["arrive"], t)
        # 抵达后巨大的恒星占掉半个画面：泛光收一点，否则整片盘面的光晕会把左边的星空糊成灰雾
        return dict(uBloomAmt=0.5 - 0.2 * arrived, uVignette=0.8 + 0.25 * fr, uSat=1.12 - 0.6 * fr,
                    uExposure=(1.0 - 0.18 * fr) * (1.0 + 0.5 * pulse(t, j, 0.08) + 0.35 * pulse(t, C["punch"], 0.1)
                                                   + 0.15 * pulse(t, dp, 0.1)),
                    uCA=0.006 + 0.02 * self.cam_k(t) + 0.03 * pulse(t, C["shockhit"], 0.25) + 0.02 * self.rush_amt(t)
                    + 0.01 * pulse(t, dp, 0.15) + 0.03 * pulse(t, C["arr_hit"], 0.3))

    # ------------------------------------------------ 飞船遥测（shiphud.py）：充能、超光速航速与航程、抵达标签
    def hud(self, t):
        e = self.e
        cam = self.camera(t)
        shiphud.charge_panel(e, t, self.charge(t), self.flash(t), self.spin_rate(t) * 600.0)
        shiphud.ftl_panel(e, self, t)
        shiphud.arrival_label(e, cam, self, t, A_RADIUS)
        # 片名（落在抵达画面上）
        t0 = C["title"]
        # 进冷开场的转场在段落结尾前 0.5 秒开始；片名的小字在清晰文字层、不跟着转场走，所以整个片名在那之前自己淡出
        t_end = SECS["warp"]["end"] - 0.5
        if t >= t0 - 0.05:
            ta = smooth(t0 - 0.05, t0 + 0.1, t) * (1 - smooth(t_end - 0.5, t_end, t))
            x, y = W * 0.27, 260
            darkspot(e, x, y + 30, 760, 260, 0.45 * ta)
            sc = stamp(t, t0, 0.5, 1.18)
            glitch_text(e, "曲率引擎", x, y, 170, "serif", WHITE, ta, t, seed=3, amt=0.2 * pulse(t, t0, 0.6) + 0.03,
                        tracking=0.2, scale=sc, intensity=1.2)
            e.text("WARP  DRIVE", x, y + 128, 30, "latin_m", ICE, ta, "mm", 0.9, 1.5, t=t, start=t0 + 0.3, dur=0.9,
                   stagger=0.03, kind="spread")
            lw = 260 * ease_out_expo(lin(t0 + 0.5, t0 + 1.5, t)) * ta
            if lw > 1:
                # 片名下的细线：中间最亮、向两端渐隐收细（原来是等宽的发光线，被泛光晕成一根灯管）
                streaks(e, [dict(tail=(x + sgn * lw, y + 166), head=(x, y + 166), color=CYAN, a=1.1 * ta, width=2.0, taper=0.2)
                            for sgn in (-1, 1)])
            e.text("从《三体》到广义相对论", x, y + 208, 28, "sans_m", WHITE, vis(t, t0 + 0.8, t_end, 0.5, 0.5),
                   "mm", 0.3, 1.1, t=t, start=t0 + 0.8, dur=0.6, stagger=0.03)
        if SHIP_AI:
            warpseq.ai_caption(e, t, AI, t_end)
