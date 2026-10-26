"""Color the downloaded star meshes, preserving positions and geometry."""
import bpy,os,random,json,math
from mathutils import Vector
ROOT=os.path.dirname(__file__)
s=bpy.context.scene
stars=sorted([o for o in s.objects if o.type=='MESH'],key=lambda o:o.name)
rng=random.Random(6021)
palette=[('Blue',(0.16,0.40,1,1)),('BlueWhite',(0.42,0.67,1,1)),('WarmWhite',(1,.86,.63,1)),('Gold',(1,.52,.16,1)),('OrangeRed',(1,.19,.055,1))]
mats=[]
for name,col in palette:
 group=[]
 for j,power in enumerate((5,12,24)):
  m=bpy.data.materials.new('Star_'+name+'_'+str(j));m.diffuse_color=col;m.use_nodes=True
  n=m.node_tree.nodes;n.clear();em=n.new('ShaderNodeEmission');em.inputs['Color'].default_value=col;em.inputs['Strength'].default_value=power
  out=n.new('ShaderNodeOutputMaterial');m.node_tree.links.new(em.outputs[0],out.inputs['Surface']);group.append(m)
 mats.append(group)
for o in stars:
 r=math.hypot(o.matrix_world.translation.x,o.matrix_world.translation.y)
 weights=(12,20,36,24,8) if r<6 else (24,32,23,14,7)
 ci=rng.choices(range(5),weights)[0];bi=rng.choices(range(3),(50,40,10))[0]
 o.material_slots[0].link='OBJECT';o.material_slots[0].material=mats[ci][bi]
s.render.engine='CYCLES';p=bpy.context.preferences.addons['cycles'].preferences;p.compute_device_type='OPTIX';p.get_devices()
for d in p.devices:d.use=d.type=='OPTIX'
s.cycles.device='GPU';s.cycles.samples=64;s.cycles.use_denoising=False
s.render.resolution_x=1600;s.render.resolution_y=1200;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.view_settings.view_transform='AgX';s.view_settings.exposure=0
s.world=bpy.data.worlds.new('Black Space');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=0
bpy.ops.object.camera_add();cam=bpy.context.object;cam.name='Galaxy Preview Camera';cam.data.type='ORTHO';cam.data.ortho_scale=59;s.camera=cam
nt=bpy.data.node_groups.new('Gentle stellar glow','CompositorNodeTree');s.compositing_node_group=nt
nt.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
rl=nt.nodes.new('CompositorNodeRLayers');g=nt.nodes.new('CompositorNodeGlare');g.inputs['Type'].default_value='Fog Glow';g.inputs['Quality'].default_value='High';g.inputs['Strength'].default_value=.35;g.inputs['Threshold'].default_value=.7
out=nt.nodes.new('NodeGroupOutput');nt.links.new(rl.outputs['Image'],g.inputs['Image']);nt.links.new(g.outputs['Image'],out.inputs['Image'])
views=[('01_oblique',(30,-40,32),59),('02_top',(0,-.001,60),59),('03_low_angle',(32,-40,9),59),('04_detail',(12,-16,14),18)]
for label,eye,scale in views:
 cam.location=eye;cam.rotation_euler=(-Vector(eye)).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
 s.render.filepath=os.path.join(ROOT,label+'.png')
 if label=='01_oblique':
  for screen in bpy.data.screens:
   for area in screen.areas:
    if area.type=='VIEW_3D':
     sp=area.spaces.active;sp.region_3d.view_distance=55;sp.region_3d.view_location=(0,0,0);sp.region_3d.view_rotation=cam.rotation_euler.to_quaternion();sp.shading.type='MATERIAL'
  bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT,'galaxy_6000_colored.blend'))
 bpy.ops.render.render(write_still=True)
 print('FINISHED',label,flush=True)
