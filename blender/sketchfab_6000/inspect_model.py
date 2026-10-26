import bpy,json,os
from mathutils import Vector
root=os.path.dirname(__file__)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=os.path.join(root,'original/source/Galaxie3-real.fbx'))
info=[]
for o in bpy.context.scene.objects:
 if o.type=='MESH':
  info.append(dict(name=o.name,verts=len(o.data.vertices),dims=list(o.dimensions),location=list(o.location),materials=[m.name for m in o.data.materials]))
print('MESHES',len(info),'SAMPLE',json.dumps(info[:8]))
print('MATERIALS',[(m.name, list(m.diffuse_color)) for m in bpy.data.materials])
json.dump(info,open(os.path.join(root,'inspection.json'),'w'),indent=2)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(root,'original_import.blend'))
