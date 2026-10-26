import bpy,json
from pathlib import Path
p=Path('D:/opusvideos/projects/warp_drive/blender/animated_star')
bpy.ops.wm.open_mainfile(filepath=str(p/'original.blend'),use_scripts=False)
d={'objects':[],'materials':[],'groups':[]}
for o in bpy.data.objects:
 d['objects'].append({'name':o.name,'type':o.type,'location':list(o.location),'dimensions':list(o.dimensions),'props':{k:str(o[k]) for k in o.keys()},'modifiers':[(m.name,m.type) for m in o.modifiers]})
for m in bpy.data.materials:
 d['materials'].append({'name':m.name,'nodes':[(n.name,n.type,[(i.name,str(i.default_value)) for i in n.inputs if hasattr(i,'default_value')]) for n in m.node_tree.nodes] if m.node_tree else []})
for g in bpy.data.node_groups:
 d['groups'].append({'name':g.name,'inputs':[(i.name,str(getattr(i,'default_value',None))) for i in g.interface.items_tree if i.item_type=='SOCKET' and i.in_out=='INPUT']})
(p/'inspect.json').write_text(json.dumps(d,indent=2),encoding='utf-8')
print(json.dumps(d,indent=2))
