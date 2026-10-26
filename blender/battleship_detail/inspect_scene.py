"""只读查看既有 Blender 资产，便于在不改动曲率环的前提下细化船体。"""
from pathlib import Path
import bpy
import json

root = Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(root / 'battleship_detail.blend'), use_scripts=False)
report = []
for obj in bpy.context.scene.objects:
    report.append(dict(name=obj.name, type=obj.type,
                       vertices=len(obj.data.vertices) if obj.type == 'MESH' else 0,
                       polygons=len(obj.data.polygons) if obj.type == 'MESH' else 0,
                       materials=[m.name for m in obj.data.materials] if obj.type == 'MESH' else [],
                       dimensions=list(obj.dimensions)))
print(json.dumps(report, indent=2), flush=True)
