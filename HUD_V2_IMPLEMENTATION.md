# HUD V2 实现与审阅

已实现无人声开场的空间 HUD，`SHIP_AI=False`。旧代码位于 `build/backup_before_hud_v2/`。

## 审阅文件

- `build/hud_v2/hud_v2_silent_preview.mp4`：46 秒、1920×1080、30fps 无声预览。
- `build/hud_v2/contact_sheet.jpg`：14 张实际渲染关键帧总览，同目录有全分辨率 PNG。
- `references/hud_v2/`：7 个镜头，每镜头两张 image_gen 候选，编号不带候选后缀的是选定参考。提示词见 `prompts.json` 与原设计文档。
- `build/hud_v2/validation.json`：GPU、时间边界、跳帧一致性与光速阈值检查结果。

## 实现

`navhud.py` 保留真实近邻恒星星表，以统一刚体变换摆进舰桥前方空间，删除旧仪表盘、球体网格、战术面与边框。选星、光年刻度航线、两行航时钩子按 cues 编排。目标框在锁定时移到实际绘制的 α A 恒星上。

`spacehud.py` 提供投影线条、环外量规、船头空间线条倒数、航线注入、距离门、光速读数和恒星引线。距离门先于飞船绘制；近处可能被船挡住的门不显示文字。终点门在目的地固定并散开。

`ship.py` / `ship_model.py` 增加默认关闭的倒数参数，环上三格一组依次熄灭，每一拍末恢复全亮。旧调用无需修改。

`warpshot.py` 接入空间 HUD，保留现有模型、跃迁分镜及片名。`cues.C['hud_lightcross']` 和 `cues.C['hud_gates']` 为后续新增音效预留统一时刻。

## 验证

- 14 张实际关键帧已渲染并检查代表画面。
- 78 个阶段边界附近的帧无 NaN/Inf。
- 5 个代表时刻乱序重渲染逐字节一致。
- 1 c 阈值前/中/后为 0.972222 / 1.0 / 1.006880。
- pyflakes 检查新 HUD、导航、warpshot 与预览脚本通过。
- 正式入口 `python projects/warp_drive/make.py render --still 8.6,18.9,29.4,41.7` 通过。

## 下一阶段

按原设计第四节，先审阅关键帧再接新音效。本次不改 `music.py`，不重混原配乐，不覆盖根目录母版；新距离门低频与越过 1 c 的重音尚未接入。

重新生成：`python projects/warp_drive/preview_hud_v2.py --video`。
