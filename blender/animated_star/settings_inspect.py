import bpy
bpy.ops.wm.open_mainfile(filepath='D:/opusvideos/projects/warp_drive/blender/animated_star/original.blend',use_scripts=False)
for gname in ['Settings','Animation','Animation_Speed']:
 g=bpy.data.node_groups[gname]
 print('GROUP',gname)
 for n in g.nodes:
  print(n.name,n.type,[(s.name,tuple(s.default_value) if hasattr(s.default_value,'__len__') else s.default_value) for s in n.outputs if hasattr(s,'default_value')])
print('SCENE',[(o.name,o.hide_render) for o in bpy.context.scene.objects])
print('DRIVERS',[(g.name,[f.driver.expression for f in g.animation_data.drivers]) for g in bpy.data.node_groups if g.animation_data])
