"""重新打开成品验证原始网格/材质，并渲染同灯光、同机位的细化前图。

这是资产验收脚本；不保存对已完成 Blender 工程的临时显示更改。
blender -b --python review_reference.py
"""
from pathlib import Path
import hashlib
import json
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'reference_refined_v2'
report=json.loads((OUT/'preservation_report.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=report['output'],use_scripts=False)


def mesh_digest(obj):
    m=obj.data
    co=np.empty(len(m.vertices)*3,np.float32)
    vi=np.empty(len(m.loops),np.int32)
    sizes=np.empty(len(m.polygons),np.int32)
    m.vertices.foreach_get('co',co)
    m.loops.foreach_get('vertex_index',vi)
    m.polygons.foreach_get('loop_total',sizes)
    h=hashlib.sha256()
    for a in (co,vi,sizes,np.array(obj.matrix_world,np.float64)):
        h.update(a.tobytes())
    return h.hexdigest()


def mat_digest(mat):
    def plain(v):
        if isinstance(v,(str,int,float,bool)) or v is None:
            return v
        try:
            return list(v)
        except TypeError:
            return str(v)
    data={'diffuse':list(mat.diffuse_color),'nodes':[],'links':[]}
    if mat.use_nodes:
        for n in mat.node_tree.nodes:
            data['nodes'].append((n.name,n.bl_idname,
                                  [(i.name,plain(i.default_value)) for i in n.inputs if hasattr(i,'default_value')]))
        data['links']=[(l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in mat.node_tree.links]
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


meshes={name:mesh_digest(bpy.data.objects[name])==digest
        for name,digest in report['original_mesh_sha256'].items()}
materials={name:mat_digest(bpy.data.materials[name])==digest
           for name,digest in report['protected_material_sha256'].items()}
assert all(meshes.values()),meshes
assert all(materials.values()),materials
for name in ('Warp ring titanium','Ring segment armor','Recessed graphite mechanics',
             'Machined nozzle and fasteners','Recessed cyan energy rails','Engine plasma'):
    assert bpy.data.objects[name].data.materials[0].name==name
check={'reopened_saved_file':True,'original_mesh_checks':meshes,
       'original_material_checks':materials,'ring_material_assignments_preserved':True,
       'packed_reference_images':[i.name for i in bpy.data.images if i.packed_file]}
(OUT/'reopen_verification.json').write_text(json.dumps(check,indent=2),encoding='utf-8')
print('SAVED_FILE_VERIFIED',json.dumps(check),flush=True)

# 细化前对照：沿用成品相机和灯光，只恢复原网格、原装甲材质。
for o in bpy.context.scene.objects:
    if o.type in ('MESH','FONT') and o.name not in meshes:
        o.hide_render=True
bpy.data.objects['Titanium armor'].data.materials[0]=bpy.data.materials['Titanium armor']
s=bpy.context.scene
s.render.filepath=str(OUT/'00_before_same_view.png')
bpy.ops.render.render(write_still=True)
print('SAME_VIEW_COMPARISON_RENDERED',flush=True)
