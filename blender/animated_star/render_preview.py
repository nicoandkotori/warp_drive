import bpy
from pathlib import Path
from mathutils import Vector
p=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(p/'original.blend'),use_scripts=False)
s=bpy.context.scene
s.render.engine='CYCLES'
pref=bpy.context.preferences.addons['cycles'].preferences
pref.compute_device_type='OPTIX';pref.get_devices()
for d in pref.devices:d.use=d.type=='OPTIX'
s.cycles.device='GPU';s.cycles.samples=32;s.cycles.use_denoising=True;s.cycles.transparent_max_bounces=100
s.render.resolution_x=960;s.render.resolution_y=720;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.film_transparent=False
s.view_settings.view_transform='AgX';s.view_settings.exposure=0
s.world=bpy.data.worlds.new('Preview black');s.world.use_nodes=True
s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=0
bpy.ops.object.camera_add(location=(0,-38,12));cam=bpy.context.object;cam.data.lens=45;s.camera=cam
cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler()
s.frame_set(40)
nt=bpy.data.node_groups.new('Preview glow','CompositorNodeTree');s.compositing_node_group=nt
nt.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
r=nt.nodes.new('CompositorNodeRLayers');g=nt.nodes.new('CompositorNodeGlare');o=nt.nodes.new('NodeGroupOutput')
g.inputs['Type'].default_value='Fog Glow';g.inputs['Quality'].default_value='High';g.inputs['Strength'].default_value=0.12;g.inputs['Threshold'].default_value=2
nt.links.new(r.outputs['Image'],g.inputs['Image']);nt.links.new(g.outputs['Image'],o.inputs['Image'])
bpy.ops.wm.save_as_mainfile(filepath=str(p/'preview.blend'))
s.render.filepath=str(p/'01_original_overview.png');bpy.ops.render.render(write_still=True)
cam.location=(0,-13,6);target=Vector((0,-4,3));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=40
s.render.filepath=str(p/'02_original_closeup.png');bpy.ops.render.render(write_still=True)
print('PREVIEWS_COMPLETE',flush=True)
