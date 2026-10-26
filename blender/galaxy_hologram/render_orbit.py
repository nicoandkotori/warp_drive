"""Render a six-second camera orbit and a fully framed top view."""
import bpy
import math
import os
from mathutils import Vector
ROOT = os.path.dirname(os.path.abspath(__file__))
scene = bpy.context.scene
cam = scene.camera
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type == 'OPTIX'
scene.cycles.device = 'GPU'
cam.location = (0,-0.01,24)
cam.rotation_euler = (-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.ortho_scale = 24
bpy.data.objects['SOL'].rotation_euler = cam.rotation_euler
scene.render.filepath = os.path.join(ROOT,'galaxy_hologram_top.png')
bpy.ops.render.render(write_still=True)
scene.render.resolution_x = 960
scene.render.resolution_y = 660
scene.cycles.samples = 8
cam.data.ortho_scale = 21
os.makedirs(os.path.join(ROOT,'orbit_frames'),exist_ok=True)
for i in range(96):
    theta = -1.0 + math.tau*i/96
    cam.location = (20*math.cos(theta),20*math.sin(theta),13)
    cam.rotation_euler = (-cam.location).to_track_quat('-Z','Y').to_euler()
    bpy.data.objects['SOL'].rotation_euler = cam.rotation_euler
    scene.render.filepath = os.path.join(ROOT,'orbit_frames',f'{i:04d}.png')
    bpy.ops.render.render(write_still=True)
print('ORBIT_READY',flush=True)
