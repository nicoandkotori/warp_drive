# -*- coding: utf-8 -*-
"""卡点表：画面与配乐共用的关键时刻（全部由时间轴推导，修改解说后自动更新）。
C[名字] 是全片绝对秒数，多数量化到 16 分音符；场景和 music.py 都只从这里取重音时刻。"""
import json, os
import numpy as np
from config import BUILD, BEAT, BAR
from script import AI_LINES

TL = json.load(open(os.path.join(BUILD, "timeline.json"), encoding="utf-8"))
SECS = {s["id"]: s for s in TL["sections"]}
LINES = {l["id"]: l for s in TL["sections"] for l in s["lines"]}
STEP = BEAT / 4


def q16(t):
    return round(t / STEP) * STEP


def ls(lid):
    return LINES[lid]["start"]


def le(lid):
    return LINES[lid]["end"]


def wt(lid, sub, end=False, off=0):
    """lid 句中子串 sub 的发声时刻（off：再往后数 off 个字；end=True 取子串最后一个字的结束）。"""
    L = LINES[lid]
    txt, idx = "", []
    for k, w in enumerate(L["words"]):
        txt += w["text"]
        idx += [k] * len(w["text"])
    i = txt.find(sub)
    assert i >= 0, (lid, sub, txt)
    if end:
        return L["words"][idx[i + len(sub) - 1]]["end"]
    return L["words"][idx[i + off]]["start"]


def downbeat(lid):
    """用 bar 选项对齐到小节线的句子，其对齐字所在的强拍。"""
    d = LINES[lid]["downbeat"]
    assert d is not None, lid
    return d


def sec(sid):
    return SECS[sid]["start"], SECS[sid]["end"]


C = {}
# ---- 开场（23 小节）
w0 = SECS["warp"]["start"]
C["warp"] = w0
# 导航（第 0-8 小节，galaxynav.py）：
#   银河从黑暗里浮现、缓缓旋转（主角镜头），第 1 小节出字"银河系"
#   -> 第 2 小节在外侧旋臂上标出"太阳系 · 我们在这里"，镜头朝它移动
#   -> 第 3 小节缩放潜入太阳邻域（视野宽度读数从 10 万光年降到几十光年，银河化作背景光带，不消失）
#   -> 第 4 小节到达邻域、近邻恒星逐颗标出 -> 光标每停一颗候选星，镜头就推近到它（各两拍）
#   -> 第 6 小节选中半人马座 α（推近看到 A、B、比邻星）-> 规划航线 -> 第 7 小节强拍锁定
#   -> 第 8 小节"准备就绪"，星图收起，回到舰桥前方的真实星空
C["gal_title"] = w0 + BAR
C["sun_mark"] = w0 + 2 * BAR
C["zoom"] = w0 + 3 * BAR
C["local"] = w0 + 4 * BAR
C["ai_nav"] = w0 + STEP * 2
C["cands"] = [w0 + 4 * BAR + 2 * BEAT + k * 2 * BEAT for k in range(3)]
C["select"] = w0 + 6 * BAR
C["switch"] = w0 + 6 * BAR + 2 * BEAT
C["lock"] = w0 + 7 * BAR
C["eta"] = w0 + 7 * BAR + 2 * BEAT
C["engage"] = w0 + 8 * BAR + BEAT
# 从星图到飞船：星图收起（扫描线扫过、淡出），露出舰桥前方的真实星空，金色锁定框落在真实的半人马座 α 上
#   -> 镜头从舰桥向后上方拉开，船头滑入画面（一镜到底，不切）
C["collapse"] = w0 + 8 * BAR + 2 * BEAT
C["handoff"] = w0 + 8 * BAR + 3 * BEAT
# 导航之后的部分：小节号沿用导航只有 6 小节时的写法，统一加在后移了 3 小节的 wn 上（彼此之间的节奏不变）
wn = w0 + 3 * BAR
# 充能（第 6-8 小节）：充能条从 0 到 100%，充满时一次闪光；镜头从前侧绕到后上方
C["charge"] = wn + 6 * BAR
C["ai_charge"] = C["charge"] + BEAT
C["charge_on"] = C["charge"] + BEAT
C["charge_full"] = wn + 8 * BAR + BEAT * 2
C["ai_full"] = C["charge_full"]
# 空间扭曲（第 9 小节，取代原来的 3-2-1 倒数，用户嫌倒数 low）：充满后停一拍半，第 9 小节强拍曲率场开始成形——
#   两道环推出一圈扭曲波，环周围的空间越拧越弯、曲率泡显形、星空一点点被拽向飞船，一小节后跃迁
C["distort"] = wn + 9 * BAR
C["ai_distort"] = C["distort"]
# 充能脉冲：配乐里那串越来越快的低频脉冲、画面上沿曲率环追逐的光弧，都按 charge_phase 走（声画同拍）。
# 频率从 C["charge_on"] 的 2 次/秒按指数加快到 C["charge_full"] 的 16 次/秒，之后保持；整数相位处是一次脉冲。
CHARGE_RATE = (2.0, 16.0)


def charge_phase(t):
    """充能脉冲的相位 = 频率的积分（解析式，t 可以是标量或 numpy 数组）。"""
    t = np.asarray(t, np.float64)
    t0, t1 = C["charge_on"], C["charge_full"]
    r0, r1 = CHARGE_RATE
    k, T = r1 / r0, t1 - t0
    u = np.clip((t - t0) / T, 0.0, 1.0)
    return r0 * T * (k ** u - 1) / np.log(k) + r1 * np.maximum(t - t1, 0.0)

# 跃迁及之后：取消倒数后整体提前 1 小节。小节号沿用原来的写法，统一加在 wj 上
wj = wn - BAR
C["warpjump"] = wj + 11 * BAR
# 跃迁前的慢动作（与配乐的"吸气"静音同一段）：曲率环、电弧几乎停住，飞船慢慢拉长、向前蠕动，画面褪色
C["freeze"] = C["warpjump"] - 2 * STEP
# 跃迁分镜（第 11 小节）：镜头留在原地，飞船被弹射出去，留下航迹、残影和冲击波（warpjump）
#   -> 飞船缩成远处一个光点、闪一下（punch）-> 冲击波扫过镜头，第二下震动（shockhit）
#   -> 镜头追上去，全画面形变（chase）-> 在船尾后方停稳，鼓点进来，进入巡航（catch，第 12 小节强拍）
C["punch"] = C["warpjump"] + 2 * STEP
C["shockhit"] = C["warpjump"] + 3 * STEP
C["chase"] = C["warpjump"] + 2 * BEAT
C["catch"] = C["warpjump"] + BAR
# 巡航（第 12-15 小节）-> 抵达分镜（第 15-16 小节）-> 镜头绕到侧后方露出恒星（第 17 小节强拍）-> 片名（第 18 小节强拍）
C["nebula"] = wj + 13 * BAR                                  # 穿过星云的中点
# 巡航中接连掠过的恒星（离飞船最近的时刻）
C["flybys"] = [wj + 12 * BAR + 2 * BEAT, wj + 13 * BAR + 2 * BEAT, wj + 14 * BAR + BEAT, wj + 14 * BAR + 3 * BEAT]
# 抵达（一镜到底，镜头始终跟着飞船、沿同一个方向绕船转，恒星在急停之前不入画）：
#   swing     镜头从船尾右后方经右侧绕到船头前方，低机位仰看飞船（恒星在镜头背后下方）
#   approach  最后一冲：飞船再次加速到极限，速度读数随即一路降到 0
#   dropout   飞船冲出超光速、猛地刹住（第 16 小节强拍，配乐是用户的"跃迁结束音效"里那一记"咚"）：残影往前收拢进船身，
#             航迹从远到近熄灭，曲率泡塌进船身、反弹出一层球形的空间扭曲冲击波
#   arr_hit   冲击波扫过镜头：整幅画面鼓一下、来回回弹（余震），镜头猛震
#   reveal    镜头停在原地看余波平息，到这里才开始运镜（用户要"过一小会再开始运镜看恒星"）
#   arrive    镜头升起、翻到飞船后上方，往下转，引出下方占半个画面的恒星：明亮的大和弦 + AI"已抵达"
C["swing"] = wj + 14 * BAR + 2 * BEAT
C["approach"] = wj + 15 * BAR + 2 * BEAT
C["dropout"] = wj + 16 * BAR
C["arr_hit"] = C["dropout"] + BEAT
C["reveal"] = C["dropout"] + 3 * BEAT
C["arrive"] = wj + 17 * BAR
C["ai_arrive"] = C["arrive"]
C["title"] = wj + 18 * BAR
# 超光速读数越过 1 c 的时刻（shiphud.velocity 与画面同源）；hud_gates 是 HUD 第二版距离门的卡点，留作备用。
C["hud_lightcross"] = C["catch"] + BEAT
C["hud_gates"] = [C["catch"] + 2*BEAT + k*BEAT for k in range(8)]
# ---- 冷开场：飞船 -> 距离
C["cold"] = SECS["cold"]["start"]
C["target"] = q16(wt("C01", "半人马座"))
C["dist"] = q16(wt("C01", "四光年"))
C["voyager"] = ls("C02")
C["fleet"] = ls("C03")
# ---- 回到半人马座 α
C["back"] = SECS["arrive"]["start"]
C["months"] = q16(wt("C04", "几个月"))
C["name"] = q16(wt("C05", "曲率驱动"))
C["real"] = ls("C06")
C["einstein"] = q16(wt("C06", "爱因斯坦"))
C["eq"] = q16(wt("C06", "方程"))

# 飞船 AI 语音：每句的起止时刻（第一个词落在卡点上），给配乐排语音、给画面出字幕
AI = []
for _lid, _en, _zh, _cue in AI_LINES:
    _w = json.load(open(os.path.join(BUILD, "ai", _lid + ".json"), encoding="utf-8"))["words"]
    _t = C[_cue]
    AI.append(dict(id=_lid, en=_en, zh=_zh, t=_t, place=_t - _w[0]["start"],
                   end=_t + _w[-1]["start"] + _w[-1]["dur"] - _w[0]["start"]))

# ---- 第一章：光速之墙
C["why"] = ls("A01")
C["law"] = q16(wt("A02", "铁律"))
C["climit"] = q16(wt("A02", "超越光速"))
C["curve"] = ls("A03")
C["harder"] = q16(wt("A03", "越难"))
C["inf"] = q16(wt("A03", "无穷大"))
C["wall"] = q16(wt("A04", "墙"))
C["trapped"] = q16(wt("A04", "太阳系"))
C["gap"] = q16(wt("A05", "缝隙"))
C["loophole"] = ls("A05")
C["motion"] = q16(wt("A06", "运动"))
C["space_itself"] = downbeat("A06")
# ---- 第二章：空间本身
C["stage"] = q16(wt("B01", "舞台"))
C["bend"] = q16(wt("B01", "弯曲"))
C["stretch"] = q16(wt("B01", "伸缩"))
C["mass"] = ls("B02")
C["dent"] = q16(wt("B02", "凹陷"))
C["gravity"] = q16(wt("B02", "引力"))
C["expand"] = q16(wt("B03", "膨胀"))
C["bigger"] = q16(wt("B03", "变大"))
C["galaxies"] = ls("B04")
C["ftl"] = q16(wt("B04", "超过光速"))
C["notviol"] = ls("B05")
C["between"] = q16(wt("B05", "之间"))
C["ride_q"] = ls("B06")
C["ride"] = q16(wt("B06", "顺风车"))
# ---- 第三章：肥皂船
C["fairy"] = q16(wt("D01", "童话"))
C["boat"] = ls("D02")
C["soap"] = q16(wt("D02", "香皂"))
C["sail"] = q16(wt("D02", "飞驰"))
C["tension"] = q16(wt("D03", "表面张力"))
C["front_water"] = q16(wt("D03", "前方"))
C["pull"] = q16(wt("D03", "拉了过去"))
C["decode"] = ls("D04")
C["iron"] = q16(wt("D04", "熨平"))
C["curved"] = q16(wt("D04", "弯曲"))
C["pullship"] = q16(wt("D04", "拉向前方"))
C["curvature"] = downbeat("D05")
# ---- 第四章：曲率泡
C["coincide"] = ls("E01")
C["year"] = ls("E02")
C["alc"] = q16(wt("E02", "阿库别瑞"))
C["solution"] = q16(wt("E02", "一个解"))
C["contract"] = q16(wt("E03", "收缩"))
C["expand2"] = q16(wt("E03", "膨胀"))
C["bubble"] = q16(wt("E04", "曲率泡"))
C["surf"] = q16(wt("E04", "冲浪"))
C["pushed"] = q16(wt("E04", "推着"))
C["inside"] = ls("E05")
C["accel"] = q16(wt("E05", "加速"))
C["clock"] = q16(wt("E05", "时间"))
C["ftl2"] = downbeat("E06")
# ---- 第五章：代价
C["ticket"] = q16(wt("F01", "贵得惊人"))
C["neg"] = q16(wt("F02", "负能量"))
C["vacuum"] = q16(wt("F02", "真空"))
C["est"] = ls("F03")
C["universe"] = q16(wt("F03", "可观测宇宙"))
C["bigger_u"] = q16(wt("F03", "大得多"))
C["improve"] = ls("F04")
C["suns"] = q16(wt("F04", "几个太阳"))
C["probe"] = q16(wt("F04", "探测器"))
C["casimir_q"] = ls("F05")
C["casimir"] = q16(wt("F05", "卡西米尔"))
C["exists"] = q16(wt("F05", "答案存在", off=2))
C["tiny"] = q16(wt("F05", "少得可怜"))
C["horizon"] = ls("F06")
C["superluminal"] = q16(wt("F06", "超光速"))
C["causal"] = q16(wt("F06", "因果联系"))
C["noswitch"] = q16(wt("F06", "关掉"))
C["sweep"] = ls("F07")
C["stop"] = q16(wt("F07", "停下"))
C["burst"] = q16(wt("F07", "倾泻"))
C["destroy"] = q16(wt("F07", "摧毁"))
# ---- 第六章：航迹
C["built"] = q16(wt("G01", "曲率驱动"))
C["foil"] = ls("G02")
C["flatten"] = q16(wt("G02", "压成"))
C["painting"] = q16(wt("G02", "巨大的画"))
C["halo"] = ls("G03")
C["ignite"] = q16(wt("G03", "启动"))
C["trail"] = ls("G04")
C["long_trail"] = q16(wt("G04", "长长"))
C["slowlight"] = q16(wt("G05", "光速变慢"))
C["stack"] = q16(wt("G05", "叠加"))
C["blackdomain"] = q16(wt("G05", "黑域"))
C["cage_line"] = ls("G06")
C["cage"] = q16(wt("G06", "牢笼"))
# ---- 尾声
C["paper"] = ls("H01")
C["positive"] = q16(wt("H02", "不需要负能量"))
C["slower"] = q16(wt("H02", "比光慢"))
C["maybe"] = ls("H03")
C["never"] = q16(wt("H03", "永远"))
C["wade"] = q16(wt("H04", "维德"))
C["fwd"] = [downbeat("H05"), q16(wt("H05", "前进", off=2)), q16(wt("H05", "不择手段"))]
C["fwd_last"] = q16(wt("H05", "地前进", off=1))
C["end"] = SECS["end"]["start"]
