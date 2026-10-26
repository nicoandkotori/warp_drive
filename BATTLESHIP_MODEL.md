# 双刃曲率战列舰（2026-10-16）

## 2026-10-17：撤回 V3 造型方向，回到用户选定的 V2

- 用户否定 V3 的突出甲块和过度堆叠，明确表示更喜欢 V2 整体图。**后续以 `reference_refined_v2/battleship_reference_refined_v2.blend` 为外形基准**；不要重新引入 V3 的大设备盒、反复出现的方形开口或加高屋顶。
- V3 只保存在 `blender/battleship_detail/reference_refined_v3/` 作为被否定的尝试，未覆盖 V2，也没有接入影片。
- 独立的轻修订候选：`blender/battleship_detail/reference_refined_v4/battleship_reference_subtle_v4.blend`。从 V2 原文件直接制作，V2 全部网格和原布光不变，只加 80 个薄覆板/齐平检修口细节/小型管线接头；材质保留原银灰色，仅改善粗糙度变化和极浅拉丝，不使用 V3 大斑驳材质。
- 双环、支撑、锁扣的几何、位置、原始材质与绑定均未动；重新打开后的校验记录在 V4 目录的 `reopen_verification.json`。V2 和 V4 均完整保留，V4 尚未得到用户评价。

## 2026-10-17：按原图在 Blender 中细化，曲率环保持原样

- 成品工程：`blender/battleship_detail/reference_refined_v2/battleship_reference_refined_v2.blend`。从现有 `battleship_detail.blend` 继续制作，另存副本，原工程保留。
- 双刃舰艏新增收窄的分层覆甲、连续肩部斜面、检修门、百叶、紧固件、舷侧机械槽和细管线；中央槽新增四段加速器线圈及窄蓝色芯管。
- 舰桥增加分层观察窗和齐平仪器，继续保留无高桅杆的轮廓。六台错位发动机增加暴露管束、冷却片和多层八边形喷口。
- 新增约 1500 个实体零件，合并为 89 个按模块/材质分组的可编辑网格；倒角保留为修改器。原网格仍是高密度等值面网格，并没有重新布线。
- **两只曲率环及支撑的顶点、拓扑、位置和材质均保持原样**。原有 7 个网格对象逐字节比对通过；仅纯船体装甲对象改用独立复制的较深钛灰材质，原始材质数据块全部保留。校验记录：`preservation_report.json`，重新打开成品后的校验：`reopen_verification.json`。
- `01_hero.png`、`02_aft.png`、`03_dorsal.png`、`04_prow_detail.png`、`05_engine_detail.png` 为 Cycles/OptiX 1920×1080 多角度实渲。`00_before_same_view.png` 为相同相机、灯光下的原模型对照；`comparison_before_after.png` 是前后并排图。
- 原参考图打包在工程内；新增相机可切换检查。重建脚本：`blender/battleship_detail/refine_reference.py -- --final`，验收脚本：`review_reference.py`（均用 Blender 后台运行）。
- 此轮只完成 Blender 建模资产，影片的 SDF 模型与现有成片尚未替换。

## 2026-10-17 细化与去桅杆

- 移除舰桥十字桅杆及两侧细杆，改为低矮齐平传感器。
- 影片实际使用的 SDF 新增双列分层甲板、紧固件、舰桥散热百叶、环段锁扣/导轨、发动机冷却片和喷口内衬。
- `build/battleship/` 的三视图与 8 秒环绕视频已重渲染；完整成片尚未重渲染。
- `export_ship_mesh.py` 以 0.012 单位采样同一几何并提取三角网格，保存到 `blender/battleship_detail/ship_mesh.npz`；约 340 万顶点、558 万三角面。它是高密度等值面网格，不是手工布线模型。
- `blender/battleship_detail/build_scene.py` 将网格按材质拆分、配置金属和发光材质、OptiX 灯光与相机，生成 `battleship_detail.blend` 和三张 `cycles_*.png`。
- Blender 是静态可编辑资产；影片仍直接渲染 SDF，充能、双环旋转与跃迁接口保持原调用方式。Blender 材质为独立重建，未逐项复制影片着色器。
- 修改前源文件备份在 `build/backup_before_detail_v4/`。

参考 `references/battleship_C.png`，已接入 `ship.py` 原有调用接口。
用户否定第一版过度简化模型，随后要求更精细、更酷，并进一步拉长舰艏。

## 当前实现

- `battleship_geometry.py`：SDF 三维几何；舰艏由 z=3.08 延伸到 4.95，前段长度增加约 63%。
- `ship_model.py`：金属装甲、检修面板、细小窗灯、双曲率环、充能轨、引擎材质。包围球扩大到 5.2，避免新舰艏被截断。
- 分层斜切装甲、四座双联装炮塔、中央加速器、舷侧机械槽、管线、舰桥与天线、分段环装甲、镂空支撑和四个推进器。
- 双环轴向位置为 0.25 / -1.65，半径仍为 1.72。
- 旧圆筒飞船备份：`build/backup_before_battleship/ship_model.py`。

## 验证及预览

`python preview_battleship.py --video` 生成前、后、侧三张 1080p 图及 8 秒 1080p30 环绕视频，位于 `build/battleship/`。

已用成片渲染入口成功生成 5.5、10、15、28、55、180、320 秒静帧；检查了充能特写、跟拍、侧面和待命镜头。

完整 MP4 尚未重新渲染。此次只改模型；PLAN_warp_v3.md 中的开场时长、HUD、连续跃迁镜头等工作仍未实施。

这是当前 GPU 视频引擎直接渲染的程序化模型，不是 Blender/OBJ 网格资产。

## 后续外观与充能更新

舰尾已改成六台纵向错位发动机、中央收束动力段、八边形喷口外壳，用户认可这一轮轮廓。
曲率环新增 `ship(..., charge=0..1, charge_flash=0..1)`，32 格同步显示充能。
用户否定大面积矩形灯箱，当前版本使用装甲边缘细蓝光缝、降低泛光与充满闪光幅度。
`preview_charge.py` 输出 15 秒预览：1–9 秒充能，9 秒单次闪光，10/11.2/12.4 秒倒数，配低频提示音。
随后根据用户反馈改为前环从顶部向两侧展开、后环从底部反向展开；后环起始错开约半拍，最终同时闭合，刚点亮的细缝有轻微提亮。
最新展示文件是 `build/battleship/charge_preview_crossflow.mp4`；前一版保存在 `charge_preview_elegant.mp4`。
充能接口及独立预览已完成，原片时间轴尚未接入新充能/倒数编排。
