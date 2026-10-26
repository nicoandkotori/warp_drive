"""撤下用户否定的 V3 堆叠甲块，从用户指定的 V2 做克制的贴合细化。

不改变 V2 的轮廓、面板排布、舰桥、双环和布光。
新增细节限于薄覆板、接缝、少量齐平机械口；原始共用材质不改。
blender -b --python refine_subtle_v4.py -- --preview / --final
"""
from pathlib import Path
import ast
import hashlib
import json
import math
import sys
import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'reference_refined_v4'; OUT.mkdir(exist_ok=True)
FINAL='--final' in sys.argv
SOURCE=ROOT/'reference_refined_v2/battleship_reference_refined_v2.blend'
TARGET=OUT/'battleship_reference_subtle_v4.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE),use_scripts=False)
S=bpy.context.scene
names={'mesh_digest','mat_digest','add','prism','box','top_plate','cylinder','annulus',
       'bolt','blade_width','deck_height','aim'}
tree=ast.parse((ROOT/'refine_reference.py').read_text(encoding='utf-8'))
library=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
exec(compile(library,str(ROOT/'refine_reference.py'),'exec'),globals())
report_v2=json.loads((ROOT/'reference_refined_v2/preservation_report.json').read_text(encoding='utf-8'))
base_names=list(report_v2['original_mesh_sha256'])
v2_state={o.name:{'hide_render':o.hide_render,
                  'materials':[m.name for m in o.data.materials] if o.type in ('MESH','FONT') else []}
          for o in S.objects}
source_meshes={o.name:mesh_digest(o) for o in S.objects if o.type=='MESH'}
GROUPS={}; PART_COUNT={}


def refined_metal(source,rough):
    """保留原来的银灰色，不加大斑驳；主要用粗糙度和细拉丝改善反射。"""
    mat=source.copy(); mat.name='V4 | '+source.name
    n=mat.node_tree.nodes; l=mat.node_tree.links
    bs=n.get('Principled BSDF')
    color=tuple(bs.inputs['Base Color'].default_value)
    for node in list(n):
        if node.type not in ('BSDF_PRINCIPLED','OUTPUT_MATERIAL'):
            n.remove(node)
    bs.inputs['Base Color'].default_value=color
    bs.inputs['Metallic'].default_value=min(.9,max(.76,bs.inputs['Metallic'].default_value))
    bs.inputs['Anisotropic'].default_value=.14
    geometry=n.new('ShaderNodeNewGeometry')
    patch=n.new('ShaderNodeTexNoise'); patch.inputs['Scale'].default_value=22
    patch.inputs['Detail'].default_value=2
    l.new(geometry.outputs['Position'],patch.inputs['Vector'])
    r=n.new('ShaderNodeMapRange'); r.inputs['To Min'].default_value=rough-.035
    r.inputs['To Max'].default_value=rough+.055
    l.new(patch.outputs['Fac'],r.inputs['Value']); l.new(r.outputs['Result'],bs.inputs['Roughness'])
    # 划痕极浅，远景保持完整大块面和干净的金属反射。
    stretch=n.new('ShaderNodeVectorMath'); stretch.operation='MULTIPLY'
    stretch.inputs[1].default_value=(850,1300,24)
    l.new(geometry.outputs['Position'],stretch.inputs[0])
    scratch=n.new('ShaderNodeTexNoise'); scratch.inputs['Scale'].default_value=1
    scratch.inputs['Detail'].default_value=2
    l.new(stretch.outputs['Vector'],scratch.inputs['Vector'])
    bump=n.new('ShaderNodeBump'); bump.inputs['Strength'].default_value=.11
    bump.inputs['Distance'].default_value=.000055
    l.new(scratch.outputs['Fac'],bump.inputs['Height']); l.new(bump.outputs['Normal'],bs.inputs['Normal'])
    mat['source_material']=source.name
    return mat


replacements={}
for name in [f'V2 | titanium plate {i+1:02}' for i in range(6)]+['V2 | original hull darker titanium',
            'V2 | machined edges','V2 | dark structural steel']:
    m=bpy.data.materials[name]; m.use_fake_user=True
    rough=.32 if name=='V2 | machined edges' else .36
    replacements[name]=refined_metal(m,rough)
for obj in S.objects:
    if obj.type=='MESH':
        for i,m in enumerate(obj.data.materials):
            if m.name in replacements:
                obj.data.materials[i]=replacements[m.name]
ARMOR=[replacements[f'V2 | titanium plate {i+1:02}'] for i in range(6)]
STEEL=replacements['V2 | machined edges']
STRUCTURE=replacements['V2 | dark structural steel']
DARK=bpy.data.materials['V2 | carbon recess']

# 薄层覆板只出现在少数甲片内部，最大增加 0.012，保留既有流线轮廓。
for sign in (-1,1):
    for i,(z,side) in enumerate(((1.72,-1),(2.70,1),(3.63,-1))):
        w=blade_width(z)*.78
        x=sign*(.6+side*w*.43)
        half=min(.055,w*.26); length=.15 if z<3 else .095
        # 一边带阶梯缺口的贴合薄甲，避免大矩形堆叠。
        coords=[(x-half+.010,z-length),(x+half-.012,z-length),
                (x+half,z-length+.018),(x+half,z+.025),
                (x+half-.014,z+.025),(x+half-.014,z+length-.012),
                (x-half+.012,z+length),(x-half,z+length-.02),(x-half,z-length+.015)]
        poly=[(xx,deck_height(zz)+.008,zz) for xx,zz in coords]
        prism('61 | thin fitted armor overlays',ARMOR[(i+2)%6],poly,(0,.006,0))
        for zz in (z-length+.034,z+length-.034):
            bolt('62 | flush retaining screws',x-half+.018,deck_height(zz)+.014,zz,.0033)
        # 小尺寸内侧缝，只在接合处露出暗色金属边。
        cylinder('63 | inset seam detailing',STRUCTURE,
                 (x+half-.013,deck_height(z)+.016,z-.04),
                 (x+half-.013,deck_height(z+.045)+.016,z+.045),.0018,segments=8)

    # 保持 V2 黑色检修盖的位置，仅在其中两个口内补入低矮细片。
    for za,zb,edge in ((2.00,2.32,1),(3.07,3.40,-1)):
        for j in range(5):
            z=za+.045+j*(zb-za-.09)/4
            points=[]
            for t in (.40,.61):
                factor=.78+.21*t
                yy=(deck_height(z)-.012)*(1-t)+(.18-.031*z)*t+.021
                points.append((sign*(.6+edge*blade_width(z)*factor),yy,z))
            cylinder('64 | flush inspection port inserts',STRUCTURE,points[0],points[1],.0025,segments=8)

    # 主体原来宽阔的甲板只补少量薄检修门，保留主要留白。
    for z,x,y in ((-.32,.59,.478),(-2.20,.62,.478)):
        xx=sign*x
        top_plate('65 | low profile access covers',DARK,xx-.046,xx+.046,z-.077,z+.077,y+.006,.006,.014)
        top_plate('65 | low profile access covers',ARMOR[1],xx-.037,xx+.037,z-.065,z+.065,y+.011,.005,.012)
        cylinder('62 | flush retaining screws',STEEL,(xx-.014,y+.016,z),(xx+.014,y+.016,z),.0025,segments=8)

# 尾部仅增加原管线旁的小接头，不再加高屋顶和设备箱。
for sign in (-1,1):
    for layer in range(3):
        yy=(layer-1)*.34
        for z in (-3.16,-2.59):
            cylinder('66 | pipe junction collars',STRUCTURE,
                     (sign*1.031,yy+.048,z-.016),(sign*1.031,yy+.048,z+.016),.014,segments=12)
            cylinder('66 | pipe junction collars',STEEL,
                     (sign*1.031,yy+.048,z-.003),(sign*1.031,yy+.048,z+.003),.015,segments=12)

collections={}
for (module,matname),(verts,faces,smooth,mat) in GROUPS.items():
    if module not in collections:
        c=bpy.data.collections.new('V4 '+module); S.collection.children.link(c); collections[module]=c
    mesh=bpy.data.meshes.new('V4 '+module+' '+matname); mesh.from_pydata(verts,[],faces); mesh.update()
    bm=bmesh.new(); bm.from_mesh(mesh); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(mesh); bm.free()
    mesh.polygons.foreach_set('use_smooth',np.array(smooth,dtype=bool))
    obj=bpy.data.objects.new('V4 '+module+' '+matname,mesh); collections[module].objects.link(obj); mesh.materials.append(mat)
    bevel=obj.modifiers.new('Fine edge radius','BEVEL'); bevel.width=.0008; bevel.segments=2
    bevel.limit_method='ANGLE'; bevel.harden_normals=True

assert {n:mesh_digest(bpy.data.objects[n]) for n in source_meshes}==source_meshes
assert all(mat_digest(bpy.data.materials[n])==h for n,h in report_v2['protected_material_sha256'].items())
for n in base_names:
    if n!='Titanium armor':
        assert [m.name for m in bpy.data.objects[n].data.materials]==v2_state[n]['materials']
im=bpy.data.images.load(str(ROOT/'reference_preferred_v2.png'),check_existing=True)
im.use_fake_user=True; im.pack()
S.cycles.samples=64 if FINAL else 24; S.cycles.adaptive_threshold=.025
pref=bpy.context.preferences.addons['cycles'].preferences; pref.compute_device_type='OPTIX'; pref.get_devices()
for d in pref.devices:
    d.use=d.type=='OPTIX'
S.cycles.device='GPU'
S.render.resolution_x=1920 if FINAL else 1440; S.render.resolution_y=1080 if FINAL else 810
CAM=S.camera
VIEWS=[('01_hero',(13,6.2,9.5),(0,0,.45),10.3),
       ('02_prow_detail',(5,3.7,7.8),(0,.08,2.05),5.4),
       ('03_aft',(-9,5.3,-12),(0,0,-.1),9.9)]
CAM.location=VIEWS[0][1]; aim(CAM,VIEWS[0][2]); CAM.data.ortho_scale=VIEWS[0][3]
S.render.filepath=str(OUT/'01_hero.png')
S['preferred_baseline']='User selected V2. V3 protruding armor treatment rejected; this file starts from V2.'
report={'source':str(SOURCE),'output':str(TARGET),'original_mesh_sha256':report_v2['original_mesh_sha256'],
        'all_v2_mesh_sha256':source_meshes,'protected_material_sha256':report_v2['protected_material_sha256'],
        'v2_object_state':v2_state,'ring_geometry_transform_materials':'UNCHANGED',
        'v2_geometry_unchanged':True,'added_parts_v4':sum(PART_COUNT.values()),
        'maximum_new_armor_thickness':.012,'new_mesh_objects':len(GROUPS),
        'v3_geometry_used':False,'lighting_changed_from_v2':False}
(OUT/'preservation_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(TARGET))
print('SUBTLE_V4_SAVED',sum(PART_COUNT.values()),flush=True)
for name,pos,target,scale in VIEWS if FINAL else VIEWS[:2]:
    CAM.location=pos; aim(CAM,target); CAM.data.ortho_scale=scale
    S.render.filepath=str(OUT/(name+('.png' if FINAL else '_preview.png')))
    bpy.ops.render.render(write_still=True); print('VIEW_COMPLETE',name,flush=True)
print('SUBTLE_V4_COMPLETE',flush=True)
