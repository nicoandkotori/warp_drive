import bpy, math, sys
from mathutils import Vector
from pathlib import Path
p=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(p/'preview.blend'),use_scripts=False)
s=bpy.context.scene
s.render.resolution_x=1920;s.render.resolution_y=1080;s.cycles.samples=64
s.cycles.adaptive_threshold=0.02
s.render.fps=24
s.render.use_motion_blur=False
# Match the original warp-drive arrival camera, converting Y-up to Blender Z-up.
r=8.115
cam=s.camera
cam.location=Vector((-13,11,520))*(r/500)
target=Vector((4,-12,511.5))*(r/500)
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.sensor_fit='HORIZONTAL'
cam.data.lens=cam.data.sensor_width/(2*math.tan(math.radians(42)/2)*(1920/1080))
cam.data.clip_start=0.001
for n in s.compositing_node_group.nodes:
 if n.type=='GLARE':n.inputs['Strength'].default_value=0.04
pref=bpy.context.preferences.addons['cycles'].preferences;pref.compute_device_type='OPTIX';pref.get_devices()
for d in pref.devices:d.use=d.type=='OPTIX'
s.cycles.device='GPU'
(p/'arrival_final_frames').mkdir(exist_ok=True)
# Evaluate only the original simple frame/property driver expressions.
root=bpy.data.objects['Animated Star - variable color']
root['Prominence Size']=0.18
bpy.data.objects['Corona'].hide_render=True
bpy.data.objects['Solar_Fire'].hide_render=True
bpy.data.objects['Solar_Prominences'].hide_render=True
# Adapt only the preview material spatial scale for the extreme close camera.
for n in bpy.data.materials['Solar_Surface'].node_tree.nodes:
 if n.type=='MAPPING' and not n.inputs['Scale'].is_linked:n.inputs['Scale'].default_value=(1,1,1)
values={'Animation_Speed':root['Animation Speed'],'Material_Seed':root['Material Seed'],
        'Geometry_Seed':root['Geometry Seed'],'Prominences':root['Prominences'],
        'Prominence_Size':root['Prominence Size'],'Prominence_Mask':root['Prominence Mask']}
drivers=[]
for g in bpy.data.node_groups:
 if g.animation_data:
  for f in list(g.animation_data.drivers):
   expr=f.driver.expression
   if expr not in values and expr!='frame':raise RuntimeError('Unknown driver: '+expr)
   path,attr=f.data_path.rsplit('.',1)
   target=g.path_resolve(path)
   drivers.append((g,target,attr,expr))
   g.driver_remove(f.data_path)
for i in range(1 if "--still" in sys.argv else 48):
 s.frame_set(40+i)
 for g,target,attr,expr in drivers:
  setattr(target,attr,float(s.frame_current if expr=='frame' else values[expr]));g.update_tag()
 bpy.context.view_layer.update()
 s.render.filepath=str(p/'arrival_final_frames'/f'{i:03}.png')
 if not Path(s.render.filepath).exists():bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(p/'arrival_hd_preview.blend'))
print('ANIMATION_COMPLETE',flush=True)
