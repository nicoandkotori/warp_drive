"""重开 V3 做原始环/支撑校验，并恢复 V2 状态渲染相同机位的对照。

验收过程不保存对场景的临时更改。--verify-only 只做数据校验。
"""
from pathlib import Path
import ast
import hashlib
import json
import sys
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'reference_refined_v3'
report=json.loads((OUT/'preservation_report.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=report['output'],use_scripts=False)
tree=ast.parse((ROOT/'refine_reference.py').read_text(encoding='utf-8'))
library=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('mesh_digest','mat_digest')],type_ignores=[])
exec(compile(library,str(ROOT/'refine_reference.py'),'exec'),globals())
meshes={n:mesh_digest(bpy.data.objects[n])==h for n,h in report['original_mesh_sha256'].items()}
mats={n:mat_digest(bpy.data.materials[n])==h for n,h in report['protected_material_sha256'].items()}
assert all(meshes.values()),meshes
assert all(mats.values()),mats
slots={n:[m.name for m in bpy.data.objects[n].data.materials]==report['v2_object_state'][n]['materials']
       for n in report['original_mesh_sha256'] if n!='Titanium armor'}
assert all(slots.values()),slots
packed=[i.name for i in bpy.data.images if i.packed_file]
assert 'reference_original.png' in packed
geometry={o.name:{'vertices':len(o.data.vertices),'polygons':len(o.data.polygons),
                  'zero_area_polygons':sum(p.area<1e-12 for p in o.data.polygons)}
          for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('V3 ')}
check={'reopened_saved_file':True,'original_mesh_checks':meshes,'original_material_checks':mats,
       'ring_and_support_material_slots':slots,'packed_reference_images':packed,
       'new_geometry':geometry}
(OUT/'reopen_verification.json').write_text(json.dumps(check,indent=2),encoding='utf-8')
print('V3_SAVED_FILE_VERIFIED',all(meshes.values()),all(mats.values()),all(slots.values()),flush=True)
if '--verify-only' not in sys.argv:
    for obj in bpy.context.scene.objects:
        if obj.name in report['v2_object_state']:
            state=report['v2_object_state'][obj.name]
            obj.hide_render=state['hide_render']
            if obj.type in ('MESH','FONT'):
                for i,n in enumerate(state['materials']):
                    obj.data.materials[i]=bpy.data.materials[n]
        elif obj.type in ('MESH','FONT'):
            obj.hide_render=True
    bpy.context.scene.render.filepath=str(OUT/'00_v2_same_lighting.png')
    bpy.ops.render.render(write_still=True)
    print('V2_COMPARISON_RENDERED',flush=True)
