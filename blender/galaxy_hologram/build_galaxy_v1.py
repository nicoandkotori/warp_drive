"""Standalone editable holographic galaxy. Run with Blender --background --python.

All geometry is procedural: six spiral filaments grouped into four main arms,
stellar disk, central bar/bulge, dimensional instrument cage, and SOL locator.
This is an artistic Milky Way overview, not a catalogue of individual stars.
"""
import bpy
import math
import random
import os
import sys
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
random.seed(17017)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 24
scene.cycles.use_denoising = True
# GPU device selection is verified by Blender; fallback remains usable on CPU.
prefs = bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == 'OPTIX'
    if any(d.type == 'OPTIX' for d in prefs.devices):
        scene.cycles.device = 'GPU'
except Exception as exc:
    print('GPU fallback:', exc)
scene.world.color = (0.001, 0.001, 0.001)
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.001,0.003,0.008,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.15
scene.view_settings.view_transform = 'AgX'
scene.render.resolution_x = 1600
scene.render.resolution_y = 1100
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.film_transparent = False


def material(name, color, strength):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color,1)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*color,1)
    em.inputs['Strength'].default_value = strength
    nt.links.new(em.outputs[0],out.inputs[0])
    return m


ice = material('01 Ice-blue stars', (0.22,0.65,1.0),3.0)
blue = material('02 Blue spiral dust', (0.055,0.26,0.65),1.8)
core = material('03 Pearl stellar core', (0.65,0.87,1.0),2.5)
grid = material('04 Holographic cyan grid', (0.04,0.43,0.58),1.15)
dim = material('05 Faint instrument grid', (0.018,0.11,0.19),1.1)
gold = material('06 SOL amber', (1.0,0.49,0.12),3.0)
white = material('07 Lettering', (0.45,0.7,0.85),1.8)

galaxy = bpy.data.objects.new('GALAXY / rotate this group',None)
scene.collection.objects.link(galaxy)
rig = bpy.data.objects.new('HOLOGRAPHIC REFERENCE FRAME',None)
scene.collection.objects.link(rig)


def points(name, values, mat):
    verts, faces = [], []
    octa = ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
    tris = ((0,2,4),(2,1,4),(1,3,4),(3,0,4),(2,0,5),(1,2,5),(3,1,5),(0,3,5))
    for x,y,z,r in values:
        n = len(verts)
        verts.extend((x+dx*r,y+dy*r,z+dz*r) for dx,dy,dz in octa)
        faces.extend(tuple(n+i for i in f) for f in tris)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts,[],faces)
    mesh.materials.append(mat)
    ob = bpy.data.objects.new(name,mesh)
    scene.collection.objects.link(ob)
    ob.parent = galaxy
    return ob


def curve(name, coords, mat, width=0.008, parent=rig):
    data = bpy.data.curves.new(name,'CURVE')
    data.dimensions = '3D'
    data.bevel_depth = width
    data.bevel_resolution = 2
    poly = data.splines.new('POLY')
    poly.points.add(len(coords)-1)
    for p,co in zip(poly.points,coords):
        p.co = (*co,1)
    ob = bpy.data.objects.new(name,data)
    scene.collection.objects.link(ob)
    data.materials.append(mat)
    ob.parent = parent
    return ob


# Four arms with clumped stellar associations and diffuse outer filaments.
for arm in range(4):
    stars,dust = [],[]
    for j in range(8200):
        r = 0.85+5.65*random.random()**0.65
        theta = arm*math.pi/2 + 1.8*math.log(r+0.2)
        theta += random.gauss(0,0.10+0.015*r)
        rad = r+random.gauss(0,0.08)
        x,y = rad*math.cos(theta),rad*math.sin(theta)
        z = random.gauss(0,0.055+0.012*r)
        size = random.uniform(0.008,0.023)
        stars.append((x,y,z,size))
        if j%2 == 0:
            dust.append((x+random.gauss(0,0.12),y+random.gauss(0,0.12),z*1.5,size*1.3))
    points(f'Arm {arm+1} / stars',stars,ice)
    points(f'Arm {arm+1} / diffuse filaments',dust,blue)

bulge = []
for j in range(5500):
    x,y,z = random.gauss(0,0.67),random.gauss(0,0.34),random.gauss(0,0.20)
    bulge.append((x,y,z,random.uniform(0.008,0.021)))
points('Central bar and raised stellar bulge',bulge,core)
disk = []
for j in range(5000):
    r = 6.5*math.sqrt(random.random())
    v = random.random()*math.tau
    disk.append((r*math.cos(v),r*math.sin(v),random.gauss(0,0.17),random.uniform(0.005,0.013)))
points('Sparse background disk',disk,blue)

N = 240
angles = [math.tau*i/N for i in range(N+1)]
for radius in (2.3,4.6,7.1,7.35):
    curve(f'Projection ring {radius}',[(radius*math.cos(a),radius*math.sin(a),-0.48) for a in angles],
          grid if radius>=7.1 else dim,0.007)
for i in range(120):
    a = math.tau*i/120
    r = 7.1
    r1 = r+(0.23 if i%10 == 0 else 0.11 if i%5 == 0 else 0.045)
    curve(f'Azimuth tick {i:03d}',[(r*math.cos(a),r*math.sin(a),-0.48),
                                (r1*math.cos(a),r1*math.sin(a),-0.48)],grid,0.009)
for axis in (0,math.pi/2):
    curve('Volumetric meridian',[(7.15*math.cos(a)*math.cos(axis),7.15*math.cos(a)*math.sin(axis),
                                 3.8*math.sin(a)-0.48) for a in angles],dim,0.006)
for axis in range(8):
    a = axis*math.tau/8
    curve('Reference spoke',[(0,0,-0.48),(7.1*math.cos(a),7.1*math.sin(a),-0.48)],dim,0.004)

# SOL marker sits about halfway out along a spiral arm, deliberately distinct.
sun = Vector((3.85,-1.3,0.15))
points('SOL / location beacon',[(*sun,0.055)],gold)
curve('SOL / vertical locator',[tuple(sun),tuple(sun+Vector((0,0,1.25)))],gold,0.009,galaxy)
curve('SOL / locator ring',[(sun.x+0.23*math.cos(a),sun.y+0.23*math.sin(a),sun.z) for a in angles],gold,0.009,galaxy)

bpy.ops.object.camera_add(location=(11,-17,13))
camera = bpy.context.object
camera.name = 'Preview camera'
scene.camera = camera
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 19.5
camera.rotation_euler = (Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler()

def label(text,location,size,mat):
    data = bpy.data.curves.new(text,'FONT')
    data.body = text
    data.size = size
    data.extrude = 0
    ob = bpy.data.objects.new(text,data)
    scene.collection.objects.link(ob)
    ob.location = location
    ob.rotation_euler = camera.rotation_euler
    data.materials.append(mat)
    return ob

label('SOL',sun+Vector((0.08,0,1.35)),0.23,gold)

# Glow is a compositing effect; editable geometry and emissive materials remain in the model.
nt = bpy.data.node_groups.new('Hologram glow','CompositorNodeTree')
scene.compositing_node_group = nt
nt.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
rl = nt.nodes.new('CompositorNodeRLayers')
glow = nt.nodes.new('CompositorNodeGlare')
glow.inputs['Type'].default_value = 'Fog Glow'
glow.inputs['Quality'].default_value = 'High'
glow.inputs['Strength'].default_value = 0.35
if 'Threshold' in glow.inputs:
    glow.inputs['Threshold'].default_value = 1.8
out = nt.nodes.new('NodeGroupOutput')
nt.links.new(rl.outputs['Image'],glow.inputs['Image'])
nt.links.new(glow.outputs['Image'],out.inputs['Image'])

# A useful material-preview viewport is stored in the .blend as well.
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.shading.type = 'MATERIAL'
            area.spaces.active.region_3d.view_distance = 22

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT,'galaxy_hologram.blend'))
scene.render.filepath = os.path.join(ROOT,'galaxy_hologram_perspective.png')
bpy.ops.render.render(write_still=True)
camera.location = (0,-0.01,24)
camera.rotation_euler = (Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath = os.path.join(ROOT,'galaxy_hologram_top.png')
bpy.ops.render.render(write_still=True)
camera.location = (12,-19,6)
camera.rotation_euler = (Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath = os.path.join(ROOT,'galaxy_hologram_low.png')
bpy.ops.render.render(write_still=True)
print('GALAXY_MODEL_READY',ROOT,flush=True)
