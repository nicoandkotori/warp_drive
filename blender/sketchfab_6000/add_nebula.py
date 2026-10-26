"""Add real volumetric clouds and absorbing dust fitted to the source stars.
Four-arm logarithmic phase fitted from the downloaded star positions.
Original star meshes, locations and color materials are preserved.
"""
import bpy,os,math
from mathutils import Vector
ROOT=os.path.dirname(__file__)
s=bpy.context.scene
p=bpy.context.preferences.addons['cycles'].preferences;p.compute_device_type='OPTIX';p.get_devices()
for d in p.devices:d.use=d.type=='OPTIX'
s.cycles.device='GPU';s.cycles.samples=128;s.cycles.use_denoising=False
s.cycles.volume_step_rate=.5;s.cycles.volume_max_steps=256
clouds=bpy.data.collections.new('Nebula and dust - volumetric');s.collection.children.link(clouds)
bpy.ops.mesh.primitive_cube_add(size=2)
box=bpy.context.object;box.name='Four spiral arms - gas and absorbing dust';box.scale=(24,24,3)
for c in list(box.users_collection):c.objects.unlink(box)
clouds.objects.link(box)
bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
m=bpy.data.materials.new('Layered stellar haze and dust');m.use_nodes=True;box.data.materials.append(m)
n=m.node_tree.nodes;n.clear();links=m.node_tree.links
def node(typ):return n.new(typ)
def wire(value,socket):
 if isinstance(value,(float,int,tuple)):socket.default_value=value
 else:links.new(value,socket)
def calc(op,a,b=None):
 q=node('ShaderNodeMath');q.operation=op;wire(a,q.inputs[0])
 if b is not None:wire(b,q.inputs[1])
 return q.outputs[0]
def mul(a,b):return calc('MULTIPLY',a,b)
def add(a,b):return calc('ADD',a,b)
def gauss(a,width):return calc('EXPONENT',mul(calc('POWER',calc('DIVIDE',a,width),2),-1))
pos=node('ShaderNodeNewGeometry').outputs['Position'];sep=node('ShaderNodeSeparateXYZ');links.new(pos,sep.inputs[0]);x,y,z=sep.outputs
r=calc('SQRT',add(mul(x,x),mul(y,y)));safe=calc('MAXIMUM',r,.15)
theta=calc('ARCTAN2',y,x)
noise=node('ShaderNodeTexNoise');links.new(pos,noise.inputs['Vector']);noise.inputs['Scale'].default_value=.65;noise.inputs['Detail'].default_value=5;noise.inputs['Roughness'].default_value=.72
fine=node('ShaderNodeTexNoise');links.new(pos,fine.inputs['Vector']);fine.inputs['Scale'].default_value=5;fine.inputs['Detail'].default_value=3
phase=add(add(mul(theta,4),mul(calc('LOGARITHM',safe,math.e),9.3)),-2.078)
phase=add(phase,mul(add(noise.outputs['Fac'],-.5),1.8))
arm=calc('POWER',mul(add(calc('COSINE',phase),1),.5),5)
taper=mul(gauss(r,20),calc('SUBTRACT',1,gauss(r,2.2)))
taper=mul(taper,calc('POWER',calc('MAXIMUM',calc('SUBTRACT',1,calc('POWER',calc('DIVIDE',r,22),6)),0),2))
vertical=gauss(z,.45)
clumps=mul(calc('POWER',noise.outputs['Fac'],2),add(.4,mul(fine.outputs['Fac'],1.4)))
gas=mul(mul(mul(arm,taper),vertical),clumps)
core=mul(gauss(r,3.0),gauss(z,.8))
disk=mul(gauss(r,13),gauss(z,.25))
dustphase=add(phase,.65)
dust=mul(mul(calc('POWER',mul(add(calc('COSINE',dustphase),1),.5),22),taper),gauss(z,.27))
dust=mul(dust,add(.2,mul(noise.outputs['Fac'],1.6)))
color=node('ShaderNodeValToRGB');links.new(calc('DIVIDE',r,16),color.inputs[0])
cr=color.color_ramp;cr.elements.remove(cr.elements[1]);cr.elements[0].position=0;cr.elements[0].color=(1,.55,.22,1)
for t,c in [(.22,(.63,.49,.42,1)),(.45,(.25,.37,.68,1)),(1,(.11,.28,.65,1))]:cr.elements.new(t).color=c
v=node('ShaderNodeVolumePrincipled');links.new(color.outputs['Color'],v.inputs['Emission Color'])
links.new(add(add(mul(gas,.65),mul(core,.18)),mul(disk,.008)),v.inputs['Emission Strength'])
links.new(add(mul(gas,.06),mul(dust,1.9)),v.inputs['Density']);v.inputs['Color'].default_value=(.055,.032,.02,1);v.inputs['Anisotropy'].default_value=.15
out=node('ShaderNodeOutputMaterial');links.new(v.outputs['Volume'],out.inputs['Volume'])
cam=s.camera
views=[('01_oblique',(30,-40,32),59),('02_top',(0,-.001,60),59),('03_low_angle',(32,-40,9),59),('04_detail',(12,-16,14),23)]
for label,eye,scale in views:
 cam.location=eye;cam.rotation_euler=(-Vector(eye)).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
 s.render.filepath=os.path.join(ROOT,'nebula_'+label+'.png')
 if label=='01_oblique':
  for screen in bpy.data.screens:
   for area in screen.areas:
    if area.type=='VIEW_3D':area.spaces.active.shading.type='RENDERED'
  bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT,'galaxy_6000_nebula.blend'))
 bpy.ops.render.render(write_still=True);print('FINISHED',label,flush=True)
