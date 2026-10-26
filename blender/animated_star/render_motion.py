import bpy
from pathlib import Path
p=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(p/'preview.blend'),use_scripts=False)
s=bpy.context.scene
s.render.resolution_x=480;s.render.resolution_y=360;s.cycles.samples=12
pref=bpy.context.preferences.addons['cycles'].preferences;pref.compute_device_type='OPTIX';pref.get_devices()
for d in pref.devices:d.use=d.type=='OPTIX'
s.cycles.device='GPU'
(p/'video_frames').mkdir(exist_ok=True)
# Evaluate only the original simple frame/property driver expressions.
root=bpy.data.objects['Animated Star - variable color']
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
for i in range(48):
 s.frame_set(40+i*2)
 for g,target,attr,expr in drivers:
  setattr(target,attr,float(s.frame_current if expr=='frame' else values[expr]));g.update_tag()
 bpy.context.view_layer.update()
 s.render.filepath=str(p/'video_frames'/f'{i:03}.png');bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(p/'animated_preview.blend'))
print('ANIMATION_COMPLETE',flush=True)
