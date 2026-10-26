"""Render the original BlenderKit volumetric Milky Way from four directions.
Source material and geometry remain unchanged; only cameras/render settings added.
"""
import bpy
import os
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
s = bpy.context.scene
s.render.engine = 'CYCLES'
p = bpy.context.preferences.addons['cycles'].preferences
p.compute_device_type = 'OPTIX'
p.get_devices()
for d in p.devices:
    d.use = d.type == 'OPTIX'
s.cycles.device = 'GPU'
s.cycles.samples = 40
s.cycles.use_denoising = True
s.cycles.volume_step_rate = 0.25
s.cycles.volume_max_steps = 128
s.render.resolution_x = 1200
s.render.resolution_y = 900
s.render.resolution_percentage = 100
s.render.image_settings.file_format = 'PNG'
s.render.film_transparent = False
s.view_settings.view_transform = 'AgX'
s.view_settings.exposure = 1.2
s.world = bpy.data.worlds.new('Preview black space')
s.world.use_nodes = True
s.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0
bpy.ops.object.camera_add(location=(22,-30,26))
cam = bpy.context.object
cam.name = 'Preview Camera'
cam.data.type = 'ORTHO'
cam.data.ortho_scale = 34
s.camera = cam

# Modest glare for emissive volume. No recoloring or synthetic stars added.
nt = bpy.data.node_groups.new('Preview glow','CompositorNodeTree')
s.compositing_node_group = nt
nt.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
rl = nt.nodes.new('CompositorNodeRLayers')
g = nt.nodes.new('CompositorNodeGlare')
g.inputs['Type'].default_value = 'Fog Glow'
g.inputs['Quality'].default_value = 'High'
g.inputs['Strength'].default_value = 0.18
g.inputs['Threshold'].default_value = 1.5
out = nt.nodes.new('NodeGroupOutput')
nt.links.new(rl.outputs['Image'],g.inputs['Image'])
nt.links.new(g.outputs['Image'],out.inputs['Image'])

views = [('01_oblique',(22,-30,26)),('02_top',(0,-0.01,40)),
         ('03_low_angle',(24,-32,7)),('04_side',(0,-40,0))]
for label,eye in views:
    cam.location = eye
    cam.rotation_euler = (-Vector(eye)).to_track_quat('-Z','Y').to_euler()
    if label == '01_oblique':
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    area.spaces.active.region_3d.view_distance = 35
                    area.spaces.active.region_3d.view_rotation = cam.rotation_euler.to_quaternion()
                    area.spaces.active.shading.type = 'RENDERED'
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT,'milky_way_preview.blend'))
    s.render.filepath = os.path.join(ROOT,label+'.png')
    bpy.ops.render.render(write_still=True)
    print('FINISHED',label,flush=True)
