# 曲率引擎 · Warp Drive

一部程序化生成的科幻短片：画面由 GPU 着色器实时渲染（Python + moderngl，1920×1080，60 fps），配乐由代码合成，配音用 edge-tts。

## 目录

| 路径 | 内容 |
|---|---|
| `opusvid/` | 公共引擎：HDR 渲染、泛光、粒子、文字动画、音频合成、配音、时间轴、混音、编码 |
| `make.py` | 构建入口 |
| `script.py` / `cues.py` | 解说文本、分段；声画共用的卡点表 |
| `scenes_*.py` | 各段场景 |
| `warpfield.py`、`warpshot.py`、`wfx.py`、`shiphud.py`、`galaxy*.py`、`ship*.py`、`star_model.py` | 跃迁特效、飞船、HUD、星系、恒星等组件 |
| `music.py`、`fwd_voice.py` | 配乐合成、尾声配音拼接 |
| `blender/` | Blender 构建/渲染脚本（`.blend` 是产物，不入库） |
| `references/` | AI 生成的设计参考图 |
| `*.md` | 开发过程中的设计说明与交接记录 |

## 运行

需要 Python 3.11+，支持 OpenGL 3.3 的显卡；配音需联网（edge-tts）。

```bash
pip install -r requirements.txt
python make.py all                       # 全流程：配音 → 时间轴 → 配乐 → 混音 → 渲染
python make.py render --still 12.5,40    # 只渲染几帧静帧到 build/stills/
python make.py render --jobs 3           # 多进程并行渲染
```

成片输出到本目录的 `曲率引擎.mp4` 和 `曲率引擎_分享版.mp4`，中间产物都在 `build/`。

**字体**：`opusvid/settings.py` 的 `FONTS` 和 `wfx.py` 的 `MONO` 写的是 Windows 字体路径（Noto Sans/Serif SC、思源宋体 Heavy、Bahnschrift、Cascadia Mono），在其他系统上请改成本机字体。

## 素材与署名

- 星系数据 `blender/sketchfab_6000/viewer/data.js` 来自 Sketchfab 模型 [Free simple 3d galaxy composed of 6000 stars](https://sketchfab.com/3d-models/free-simple-3d-galaxy-composed-of-6000-stars-46c390591651438abe3ccb2396d16e6b)，作者 caton.laubergiste，[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)；本项目重新着色并加了程序化星云，详见 `blender/sketchfab_6000/ATTRIBUTION.txt`。
- `blender/animated_star/`、`blender/blenderkit_galaxy/` 下的脚本针对 BlenderKit 素材（royalty-free，不可再分发），素材本身不在仓库里，需要自行从 BlenderKit 获取，来源见 `PROVENANCE.txt`。
- 跃迁音效 `跃迁引擎音效_3.wav`、`跃迁结束音效.wav` 为作者自制。
- 配音由 edge-tts（Microsoft 神经网络语音）在构建时生成，不随仓库分发。
