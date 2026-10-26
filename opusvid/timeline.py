# -*- coding: utf-8 -*-
"""opusvid.timeline — 把解说排进节拍网格：每句话的第一个字落在拍点上，段落边界落在小节强拍上。

line 可带第 5 项选项 dict：bar=(子串, 字下标) 让该字落在下一个小节强拍上（用于结论卡强拍）。
estimate=True 时，缺少配音的句子按语速估算逐字时间（配音前先出关键帧用）。"""
import json, math, os, re

PUNCT = "，。：；！？、—…"
SPLIT_RE = re.compile(r"([，。：；！？]|——|……)")


PAUSE = {"，": 0.28, "、": 0.2, "：": 0.3, "；": 0.36, "。": 0.45, "？": 0.45, "！": 0.45, "—": 0.12, "…": 0.18}


def estimate_words(text, cps=5.1):
    """没有配音时的逐字时间估算：汉字按 cps 字/秒，拉丁字母/数字串按每字符 0.12 秒，标点加停顿。
    （按 edge-tts 云希 -1% 语速的实测结果校准，误差约 ±7%）"""
    words, t, i = [], 0.05, 0
    while i < len(text):
        ch = text[i]
        if ch.isascii() and ch.isalnum():
            j = i
            while j < len(text) and text[j].isascii() and text[j].isalnum():
                j += 1
            d = 0.12 * (j - i) + 0.1
        elif "一" <= ch <= "鿿":
            j, d = i + 1, 1.0 / cps
        else:
            t += PAUSE.get(ch, 0.0) * 0.9
            i += 1
            continue
        words.append(dict(text=text[i:j], start=round(t, 4), dur=round(d * 0.92, 4)))
        t += d
        i = j
    return words


def load_words(tts_dir, lid, text=None, estimate=False):
    p = os.path.join(tts_dir, lid + ".json")
    if estimate and not os.path.exists(p):
        return dict(text=text, words=estimate_words(text), estimated=True)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def char_times(text, words):
    """tts 文本中每个字符的发声时间（相对音频开头）。标点继承前一个字的结束时间。"""
    times = [None] * len(text)
    pos = 0
    for w in words:
        k = text.find(w["text"], pos)
        if k < 0:
            continue
        n = len(w["text"])
        for j in range(n):
            times[k + j] = w["start"] + w["dur"] * j / n
        pos = k + n
    last = words[0]["start"]
    for i in range(len(times)):
        if times[i] is None:
            times[i] = last
        last = times[i]
    return times


def chunks(text):
    """按标点切分，返回 [(片段文本, 起始字符下标)]。"""
    out, pos = [], 0
    parts = SPLIT_RE.split(text)
    buf, start = "", 0
    for p in parts:
        if not p:
            continue
        if SPLIT_RE.fullmatch(p):
            buf += p
            out.append((buf, start))
            pos += len(p)
            buf, start = "", pos
        else:
            if not buf:
                start = pos
            buf += p
            pos += len(p)
    if buf:
        out.append((buf, start))
    return out


def clean_sub(s):
    s = s.strip()
    s = re.sub(r"[，。；：！]+$", "", s)
    s = s.replace("——", " ").replace("，", "  ").replace("。", "  ").replace("；", "  ").replace("：", "  ")
    return s.strip()


def build(sections, tts_dir, out_path, beat, estimate=False):
    BEAT, BAR = beat, beat * 4
    n_est = 0
    t_bar = 0
    out_secs = []
    for sec in sections:
        s0 = t_bar * BAR
        cursor = s0 + sec.get("lead", 0) * BEAT
        lines = []
        for line in sec["lines"]:
            lid, sub, tts, gap = line[:4]
            opts = line[4] if len(line) > 4 else {}
            tts = tts or sub
            d = load_words(tts_dir, lid, tts, estimate)
            n_est += bool(d.get("estimated"))
            words = d["words"]
            onset = words[0]["start"]
            beat_idx = math.ceil((cursor - 1e-6) / BEAT)
            t_on = beat_idx * BEAT
            place = t_on - onset
            ct = char_times(tts, words)
            downbeat = None
            if "bar" in opts:
                # 让指定的字落在下一个小节强拍上
                word, k = opts["bar"]
                pos = tts.find(word)
                assert pos >= 0, (lid, word)
                t_word = place + ct[pos + k]
                downbeat = math.ceil((t_word - 1e-6) / BAR) * BAR
                place += downbeat - t_word
                t_on = place + onset
            end = place + words[-1]["start"] + words[-1]["dur"]
            # 字幕：子片段一一对应（sub 与 tts 的标点序列一致）
            sc, tc = chunks(sub), chunks(tts)
            assert len(sc) == len(tc), (lid, sc, tc)
            segs, cur, cur_t = [], "", None
            for (stxt, _), (ttxt, tpos) in zip(sc, tc):
                tt = place + ct[tpos]
                n_cur, n_new = len(clean_sub(cur)), len(clean_sub(cur + stxt))
                short = n_cur < 5 or len(clean_sub(stxt)) < 5
                if cur and n_new > (26 if short else 21):
                    segs.append([clean_sub(cur), cur_t])
                    cur, cur_t = "", None
                if cur_t is None:
                    cur_t = tt
                cur += stxt
            if cur:
                segs.append([clean_sub(cur), cur_t])
            sub_segs = []
            for i, (txt, st) in enumerate(segs):
                en = segs[i + 1][1] - 0.05 if i + 1 < len(segs) else end + 0.35
                sub_segs.append(dict(text=txt, start=round(st - 0.08, 3), end=round(en, 3)))
            lines.append(dict(id=lid, sub=sub, tts=tts, place=round(place, 4), start=round(t_on, 4),
                              end=round(end, 4), downbeat=None if downbeat is None else round(downbeat, 4),
                              words=[dict(text=w["text"], start=round(place + w["start"], 4),
                                          end=round(place + w["start"] + w["dur"], 4)) for w in words],
                              subs=sub_segs))
            cursor = end + gap * BEAT + 0.2
        if lines:
            cursor = lines[-1]["end"] + sec.get("tail", 0) * BEAT
        n_bars = math.ceil((cursor - s0) / BAR - 1e-6)
        n_bars = max(n_bars, sec.get("min_bars", 0))
        out_secs.append(dict(id=sec["id"], bar=t_bar, bars=n_bars, start=round(s0, 4),
                             end=round(s0 + n_bars * BAR, 4), lines=lines))
        t_bar += n_bars
    tl = dict(bpm=60 / BEAT, beat=BEAT, bar=BAR, total_bars=t_bar, duration=t_bar * BAR, sections=out_secs,
              estimated=n_est > 0)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(tl, f, ensure_ascii=False, indent=1)
    for s in out_secs:
        print(f"{s['id']:6s} bar {s['bar']:3d}  {s['bars']:2d} bars  {s['start']:7.2f} - {s['end']:7.2f}")
    print("total", tl["duration"], "s", f"({n_est} lines estimated, no voice yet)" if n_est else "")
    return tl

