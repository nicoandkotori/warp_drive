# -*- coding: utf-8 -*-
"""edge-tts 配音：每句一个音频，附逐词时间戳。"""
import asyncio, json, os, subprocess
import edge_tts
from .settings import FFMPEG, SR


async def _synth(lid, text, out_dir, voice, rate, pitch, force):
    mp3 = os.path.join(out_dir, lid + ".mp3")
    js = os.path.join(out_dir, lid + ".json")
    wav = os.path.join(out_dir, lid + ".wav")
    if os.path.exists(wav) and os.path.exists(js) and not force:
        return
    words = []
    for attempt in range(4):
        try:
            com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
            words = []
            with open(mp3, "wb") as f:
                async for chunk in com.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        words.append(dict(text=chunk["text"], start=chunk["offset"] / 1e7, dur=chunk["duration"] / 1e7))
            break
        except Exception as e:
            print("retry", lid, e)
            await asyncio.sleep(2)
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", mp3, "-ac", "1", "-ar", str(SR), wav], check=True)
    with open(js, "w", encoding="utf-8") as f:
        json.dump(dict(text=text, words=words), f, ensure_ascii=False, indent=1)
    print(lid, len(words), "words")


def synth_sections(sections, out_dir, voice, rate="+0%", pitch="+0Hz", force=False):
    """sections: [{lines: [(id, 字幕, 配音文本或None, 停顿拍数)]}]"""
    os.makedirs(out_dir, exist_ok=True)

    async def run():
        for sec in sections:
            for lid, sub, tts, gap in sec["lines"]:
                await _synth(lid, tts or sub, out_dir, voice, rate, pitch, force)

    asyncio.run(run())
