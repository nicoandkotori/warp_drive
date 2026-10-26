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
s.cycles.device='GPU';s.cycles.samples=96;s.cycles.use_denoising=False
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
# Twist the texture domain with the arms: cloud filaments follow rotation.
twist=add(theta,mul(calc('LOGARITHM',safe,math.e),.7))
domain=node('ShaderNodeCombineXYZ')
links.new(mul(calc('COSINE',twist),r),domain.inputs['X'])
links.new(mul(calc('SINE',twist),r),domain.inputs['Y'])
links.new(mul(z,.25),domain.inputs['Z'])
noise=node('ShaderNodeTexNoise');links.new(domain.outputs[0],noise.inputs['Vector']);noise.inputs['Scale'].default_value=1.35;noise.inputs['Detail'].default_value=7;noise.inputs['Roughness'].default_value=.8
fine=node('ShaderNodeTexNoise');links.new(domain.outputs[0],fine.inputs['Vector']);fine.inputs['Scale'].default_value=9;fine.inputs['Detail'].default_value=3
phase=add(add(mul(theta,4),mul(calc('LOGARITHM',safe,math.e),9.3)),-2.078)
phase=add(phase,mul(add(noise.outputs['Fac'],-.5),3.2))
arm=add(.055,mul(calc('POWER',mul(add(calc('COSINE',phase),1),.5),2.5),.945))
taper=mul(gauss(r,20),calc('SUBTRACT',1,gauss(r,1.1)))
taper=mul(taper,calc('POWER',calc('MAXIMUM',calc('SUBTRACT',1,calc('POWER',calc('DIVIDE',r,22),6)),0),2))
vertical=gauss(z,add(.28,mul(gauss(r,6),.55)))
clumps=mul(calc('POWER',calc('MAXIMUM',mul(add(noise.outputs['Fac'],-.35),3.5),0),3.2),add(.07,mul(calc('POWER',fine.outputs['Fac'],3),5)))
gas=mul(mul(mul(arm,taper),vertical),clumps)
core=mul(gauss(r,3.3),gauss(z,.65))
disk=mul(gauss(r,11),gauss(z,.35))
dustphase=add(phase,.65)
dust=mul(mul(calc('POWER',mul(add(calc('COSINE',dustphase),1),.5),3),taper),gauss(z,.4))
dust=mul(dust,calc('POWER',calc('MAXIMUM',mul(add(.64, mul(noise.outputs['Fac'],-1)),3.3),0),2))
color=node('ShaderNodeValToRGB');links.new(calc('DIVIDE',r,16),color.inputs[0])
cr=color.color_ramp;cr.elements.remove(cr.elements[1]);cr.elements[0].position=0;cr.elements[0].color=(1,.68,.43,1)
for t,c in [(.18,(.65,.34,.23,1)),(.4,(.36,.32,.4,1)),(.65,(.22,.3,.53,1)),(1,(.12,.22,.48,1))]:cr.elements.new(t).color=c
pinknoise=node('ShaderNodeTexNoise');links.new(pos,pinknoise.inputs['Vector']);pinknoise.inputs['Scale'].default_value=1.7;pinknoise.inputs['Detail'].default_value=2
pinkmask=mul(calc('GREATER_THAN',pinknoise.outputs['Fac'],.72),.7)
base=node('ShaderNodeVectorMath');base.operation='SCALE';links.new(color.outputs['Color'],base.inputs[0]);links.new(calc('SUBTRACT',1,pinkmask),base.inputs['Scale'])
rose=node('ShaderNodeVectorMath');rose.operation='SCALE';rose.inputs[0].default_value=(.7,.08,.17);links.new(pinkmask,rose.inputs['Scale'])
mix=node('ShaderNodeVectorMath');mix.operation='ADD';links.new(base.outputs[0],mix.inputs[0]);links.new(rose.outputs[0],mix.inputs[1])
v=node('ShaderNodeVolumePrincipled');links.new(mix.outputs[0],v.inputs['Emission Color'])
pin=mul(gauss(r,.48),gauss(z,.3))
links.new(add(add(add(mul(gas,3),mul(core,.32)),mul(disk,.018)),mul(pin,10)),v.inputs['Emission Strength'])
links.new(add(mul(gas,.1),mul(dust,6)),v.inputs['Density']);v.inputs['Color'].default_value=(.055,.032,.02,1);v.inputs['Anisotropy'].default_value=.15
out=node('ShaderNodeOutputMaterial');links.new(v.outputs['Volume'],out.inputs['Volume'])
cam=s.camera
# The source particle prototype is a large sphere at the origin, not a star.
bpy.data.objects['etoile.6001'].hide_render=True
views=[('01_oblique',(18,-34,32),52),('02_top',(0,-.001,60),59),('03_low_angle',(32,-40,9),53),('04_detail',(12,-16,14),23)]
if os.environ.get('GALAXY_PREVIEW')=='1':views=views[:1]
for label,eye,scale in views:
 cam.location=eye;cam.rotation_euler=(-Vector(eye)).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
 s.render.filepath=os.path.join(ROOT,'reference_'+label+'.png')
 if label=='01_oblique':
  for screen in bpy.data.screens:
   for area in screen.areas:
    if area.type=='VIEW_3D':area.spaces.active.shading.type='RENDERED'
  bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT,'galaxy_reference_nebula.blend'))
 bpy.ops.render.render(write_still=True);print('FINISHED',label,flush=True)
