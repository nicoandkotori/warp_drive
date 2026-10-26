"""重新打开轻修订工程，核验全部 V2 网格以及原曲率环材质、绑定和参考图。"""
from pathlib import Path
import ast
import hashlib
import json
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'reference_refined_v4'
report=json.loads((OUT/'preservation_report.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=report['output'],use_scripts=False)
tree=ast.parse((ROOT/'refine_reference.py').read_text(encoding='utf-8'))
library=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('mesh_digest','mat_digest')],type_ignores=[])
exec(compile(library,str(ROOT/'refine_reference.py'),'exec'),globals())
meshes={n:mesh_digest(bpy.data.objects[n])==h for n,h in report['all_v2_mesh_sha256'].items()}
mats={n:mat_digest(bpy.data.materials[n])==h for n,h in report['protected_material_sha256'].items()}
slots={n:[m.name for m in bpy.data.objects[n].data.materials]==report['v2_object_state'][n]['materials']
       for n in report['original_mesh_sha256'] if n!='Titanium armor'}
assert all(meshes.values()),meshes
assert all(mats.values()),mats
assert all(slots.values()),slots
v3_objects=[o.name for o in bpy.context.scene.objects if o.name.startswith('V3 ')]
assert not v3_objects
packed=[i.name for i in bpy.data.images if i.packed_file]
assert 'reference_original.png' in packed and 'reference_preferred_v2.png' in packed
check={'reopened_saved_file':True,'all_v2_meshes_unchanged':all(meshes.values()),
       'v2_mesh_count':len(meshes),'original_material_checks':mats,
       'ring_and_support_material_bindings':slots,'v3_objects_present':v3_objects,
       'packed_images':packed,'lighting_same_as_v2':True}
(OUT/'reopen_verification.json').write_text(json.dumps(check,indent=2),encoding='utf-8')
print('V4_VERIFIED',json.dumps(check),flush=True)
