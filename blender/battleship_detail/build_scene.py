"""Blender 后台构建：影片同源网格、金属材质和三视角 Cycles 预览。

blender -b --python build_scene.py
网格按材质拆分可编辑；充能和双环运动仍在影片源代码中控制。
"""
from pathlib import Path
import math
import bpy
import numpy as np
from mathutils import Vector, Matrix

ROOT=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
s=bpy.context.scene
s.render.engine='CYCLES'
s.cycles.samples=48
s.cycles.use_denoising=True
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX'; prefs.get_devices()
for dev in prefs.devices: dev.use=dev.type=='OPTIX'
s.cycles.device='GPU'
s.render.resolution_x=1800; s.render.resolution_y=1200; s.render.resolution_percentage=100
s.world.color=(0.07,0.07,0.07)
s.view_settings.view_transform='AgX'

def material(name,color,metallic,rough,emit=0):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    n=m.node_tree.nodes; l=m.node_tree.links; bs=n.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(*color,1)
    bs.inputs['Metallic'].default_value=metallic
    bs.inputs['Roughness'].default_value=rough
    if emit:
        bs.inputs['Emission Color'].default_value=(*color,1)
        bs.inputs['Emission Strength'].default_value=emit
    else:
        tex=n.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value=180
        bump=n.new('ShaderNodeBump'); bump.inputs['Strength'].default_value=.16
        bump.inputs['Distance'].default_value=.002
        l.new(tex.outputs['Fac'],bump.inputs['Height']); l.new(bump.outputs['Normal'],bs.inputs['Normal'])
        ramp=n.new('ShaderNodeMapRange'); ramp.inputs['To Min'].default_value=rough-.07
        ramp.inputs['To Max'].default_value=rough+.09
        l.new(tex.outputs['Fac'],ramp.inputs['Value']); l.new(ramp.outputs['Result'],bs.inputs['Roughness'])
    return m

mats={
    1:material('Titanium armor',(.24,.29,.34),.72,.36),
    2:material('Warp ring titanium',(.14,.22,.29),.78,.30),
    3:material('Machined nozzle and fasteners',(.32,.37,.42),.85,.28),
    4:material('Recessed graphite mechanics',(.035,.052,.07),.65,.43),
    5:material('Engine plasma',(.15,.62,1),.15,.24,3),
    6:material('Recessed cyan energy rails',(.12,.64,1),.25,.25,1.8),
    8:material('Ring segment armor',(.20,.25,.31),.8,.34),
}
data=np.load(ROOT/'ship_mesh.npz'); vertices=data['vertices']; faces=data['faces']; ids=data['materials']
for mid in sorted(mats):
    selected=faces[ids==mid]
    if len(selected)==0: continue
    used,inverse=np.unique(selected,return_inverse=True)
    mesh=bpy.data.meshes.new(mats[mid].name)
    mesh.from_pydata(vertices[used].tolist(),[],inverse.reshape(-1,3).tolist()); mesh.update()
    obj=bpy.data.objects.new(mats[mid].name,mesh); s.collection.objects.link(obj)
    obj.data.materials.append(mats[mid])
    # 高密度等值面采用平滑法线，防止曲面显露采样三角形。
    mesh.polygons.foreach_set('use_smooth',np.ones(len(mesh.polygons),dtype=bool))

# Blender 的 y 为船体竖直方向，模型轴与影片一致。
def aim(obj,target):
    forward=(Vector(target)-obj.location).normalized()
    right=forward.cross(Vector((0,1,0))).normalized()
    up=right.cross(forward).normalized()
    obj.rotation_euler=Matrix((right,up,-forward)).transposed().to_euler()
for name,pos,power,size,color in [
    ('Key softbox',(2,7,4),1800,7,(.80,.88,1)),
    ('Warm rim',(-5,3,-4),2100,5,(1,.80,.60)),
    ('Front fill',(5,1,6),900,5,(.50,.70,1)),
]:
    light=bpy.data.lights.new(name,'AREA'); light.energy=power; light.shape='DISK'; light.size=size; light.color=color
    obj=bpy.data.objects.new(name,light); s.collection.objects.link(obj); obj.location=pos; aim(obj,(0,0,0))
camdata=bpy.data.cameras.new('Review camera'); cam=bpy.data.objects.new('Review camera',camdata)
s.collection.objects.link(cam); s.camera=cam; camdata.lens=48
s.render.image_settings.file_format='PNG'
views=[('front',(10,7.5,12)),('rear',(-9,6,-12)),('bridge',(4,3.5,-.2))]
cam.location=views[0][1]; aim(cam,(0,0,.5))
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'battleship_detail.blend'))
for name,pos in views:
    cam.location=pos; aim(cam,(0,.35,-.8) if name=='bridge' else (0,0,.5))
    s.render.filepath=str(ROOT/f'cycles_{name}.png')
    bpy.ops.render.render(write_still=True)
print('BLENDER_SHIP_COMPLETE',flush=True)
