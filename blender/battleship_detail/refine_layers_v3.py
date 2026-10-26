"""在 V2 上重做错层装甲、开放机械夹层与多尺度金属，严格保留曲率环。

用 Blender 运行：--background --python refine_layers_v3.py -- --preview / --final
V2 工程保持原样；新增 V3 工程和同灯光前后对照写入 reference_refined_v3。
"""
from pathlib import Path
import ast
import hashlib
import json
import math
import sys
import time

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'reference_refined_v3'; OUT.mkdir(exist_ok=True)
FINAL='--final' in sys.argv
T0=time.time()
SOURCE=ROOT/'reference_refined_v2/battleship_reference_refined_v2.blend'
TARGET=OUT/'battleship_reference_refined_v3.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE),use_scripts=False)
S=bpy.context.scene

# 仅复用 V2 文件中的纯几何函数，不执行其任何场景构建/保存/渲染代码。
names={'mesh_digest','mat_digest','add','prism','box','top_plate','cylinder','annulus',
       'bolt','blade_width','deck_height','aim'}
tree=ast.parse((ROOT/'refine_reference.py').read_text(encoding='utf-8'))
library=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
exec(compile(library,str(ROOT/'refine_reference.py'),'exec'),globals())

original_report=json.loads((ROOT/'reference_refined_v2/preservation_report.json').read_text(encoding='utf-8'))
BASE_NAMES=list(original_report['original_mesh_sha256'])
base_hashes={name:mesh_digest(bpy.data.objects[name]) for name in BASE_NAMES}
protected_mats=original_report['protected_material_sha256']
assert base_hashes==original_report['original_mesh_sha256']
assert all(mat_digest(bpy.data.materials[n])==h for n,h in protected_mats.items())
v2_state={o.name:{'hide_render':o.hide_render,
                  'materials':[m.name for m in o.data.materials] if o.type in ('MESH','FONT') else []}
          for o in S.objects}
GROUPS={}; PART_COUNT={}


def pbr_metal(name,base,rough=.35,metal=.88,wear=.20):
    """反射率变化与几何微表面分离，避免把高强度噪声变成砂纸/木纹。"""
    m=bpy.data.materials.new(name); m.use_nodes=True; m.diffuse_color=(*base,1)
    nodes=m.node_tree.nodes; links=m.node_tree.links
    bs=nodes.get('Principled BSDF')
    bs.inputs['Metallic'].default_value=metal
    bs.inputs['Roughness'].default_value=rough
    bs.inputs['Anisotropic'].default_value=.23
    bs.inputs['Coat Weight'].default_value=.055
    bs.inputs['Coat Roughness'].default_value=.35
    geom=nodes.new('ShaderNodeNewGeometry'); geom.location=(-1000,0)

    def noise(scale,detail=2):
        n=nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value=scale
        n.inputs['Detail'].default_value=detail
        links.new(geom.outputs['Position'],n.inputs['Vector']); return n
    cloud=noise(9,3); fine=noise(165,2)
    tint=nodes.new('ShaderNodeValToRGB')
    tint.color_ramp.elements[0].position=.12
    tint.color_ramp.elements[0].color=(*(v*.88 for v in base),1)
    tint.color_ramp.elements[1].position=.87
    tint.color_ramp.elements[1].color=(*(v*1.05 for v in base),1)
    links.new(cloud.outputs['Fac'],tint.inputs['Fac'])
    # 曲率磨损只在小范围凸缘抬亮反射，宽面保留钛灰。
    edge=nodes.new('ShaderNodeValToRGB')
    edge.color_ramp.elements[0].position=.495
    edge.color_ramp.elements[0].color=(0,0,0,1)
    edge.color_ramp.elements[1].position=.555
    edge.color_ramp.elements[1].color=(wear,wear,wear,1)
    links.new(geom.outputs['Pointiness'],edge.inputs['Fac'])
    mix=nodes.new('ShaderNodeMixRGB'); mix.blend_type='MIX'
    links.new(edge.outputs['Color'],mix.inputs[0]); links.new(tint.outputs['Color'],mix.inputs[1])
    mix.inputs[2].default_value=(.35,.37,.39,1)
    # 夹层暗部由 Cycles 的真实遮挡产生，避免材质 AO 在高密网格上重复压黑。
    links.new(mix.outputs['Color'],bs.inputs['Base Color'])
    # 宽面的擦拭/油膜斑只改变粗糙度；微划痕沿船轴拉开。
    roughmap=nodes.new('ShaderNodeMapRange')
    roughmap.inputs['To Min'].default_value=max(.13,rough-.065)
    roughmap.inputs['To Max'].default_value=min(.68,rough+.095)
    links.new(cloud.outputs['Fac'],roughmap.inputs['Value'])
    links.new(roughmap.outputs['Result'],bs.inputs['Roughness'])
    stretch=nodes.new('ShaderNodeVectorMath'); stretch.operation='MULTIPLY'
    stretch.inputs[1].default_value=(1200,1700,28)
    links.new(geom.outputs['Position'],stretch.inputs[0])
    scratches=nodes.new('ShaderNodeTexNoise'); scratches.inputs['Scale'].default_value=1
    scratches.inputs['Detail'].default_value=2
    links.new(stretch.outputs['Vector'],scratches.inputs['Vector'])
    scratch_ramp=nodes.new('ShaderNodeValToRGB')
    scratch_ramp.color_ramp.elements[0].position=.69
    scratch_ramp.color_ramp.elements[1].position=.79
    links.new(scratches.outputs['Fac'],scratch_ramp.inputs['Fac'])
    micro=nodes.new('ShaderNodeBump'); micro.inputs['Distance'].default_value=.00013
    micro.inputs['Strength'].default_value=.19
    links.new(fine.outputs['Fac'],micro.inputs['Height'])
    bump=nodes.new('ShaderNodeBump'); bump.inputs['Distance'].default_value=.00010
    bump.inputs['Strength'].default_value=.20
    links.new(scratch_ramp.outputs['Color'],bump.inputs['Height'])
    links.new(micro.outputs['Normal'],bump.inputs['Normal'])
    links.new(bump.outputs['Normal'],bs.inputs['Normal'])
    return m


ARMOR=[pbr_metal(f'V3 | forged titanium {i:02}',(v,v*1.015,v*1.045),.31+i*.013)
       for i,v in enumerate((.125,.155,.18,.205,.235,.17,.14,.195))]
STEEL=pbr_metal('V3 | brushed stainless fasteners',(.29,.305,.32),.27,.94,.12)
STRUCTURE=pbr_metal('V3 | blackened steel structure',(.039,.047,.054),.43,.86,.16)
DARK=pbr_metal('V3 | recessed oily mechanics',(.014,.019,.024),.36,.78,.08)
BLACK=pbr_metal('V3 | heat resistant graphite',(.011,.014,.018),.56,.52,.05)
COPPER=pbr_metal('V3 | subdued heat exchanger copper',(.105,.063,.033),.37,.86,.10)
BRASS=pbr_metal('V3 | service latch brass',(.16,.13,.064),.39,.75,.12)

# 所有 V2 独立装甲换成新材质，环共用的原始材质不在替换表内。
replacement={f'V2 | titanium plate {i+1:02}':ARMOR[i] for i in range(6)}
replacement.update({'V2 | original hull darker titanium':ARMOR[2],
                    'V2 | machined edges':STEEL,'V2 | dark structural steel':STRUCTURE,
                    'V2 | carbon recess':DARK,'V2 | ceramic vent interior':BLACK})
for obj in S.objects:
    if obj.type=='MESH':
        for i,m in enumerate(obj.data.materials):
            if m.name in replacement:
                m.use_fake_user=True
                obj.data.materials[i]=replacement[m.name]

# 新的三维层叠结构取代这几组旧的齐平拼片；V2 本体文件仍完整保留。
replaced_modules=('01 |','03 |','08 |','11 |','14 |','24 |','25 |','26 |','27 |','30 |')
for obj in S.objects:
    if obj.type in ('MESH','FONT') and obj.name.startswith(replaced_modules):
        obj.hide_render=True; obj.hide_set(True)


def tube(module,mat,points,r=.012):
    for a,b in zip(points,points[1:]):
        cylinder(module,mat,a,b,r,segments=12)


def hatch(module,x,z,y,wx,lz):
    top_plate(module,DARK,x-wx,x+wx,z-lz,z+lz,y,.024,.014)
    top_plate(module,ARMOR[1],x-wx+.010,x+wx-.010,z-lz+.012,z+lz-.012,y+.009,.014,.012)
    for dz in (-lz+.025,lz-.025):
        bolt(module,x-wx+.021,y+.014,z+dz,.004)
        bolt(module,x+wx-.021,y+.014,z+dz,.004)
    cylinder(module,STEEL,(x-.021,y+.019,z),(x+.021,y+.019,z),.004,segments=8)


def surface_plate(module,mat,outline,point,thick=.025):
    prism(module,mat,[point(u,z) for u,z in outline],(0,-thick,0))


def shoulder_point(sign,edge,u,z,raise_y=0):
    w=blade_width(z)
    return (sign*(.6+edge*w*(.68+.38*u)),
            deck_height(z)+.042+raise_y-(.28-.028*z)*u,z)


# 每片的高度、搭接方向和接缝均有变化，宏观轮廓先于微小零件。
CUTS=[.51,.98,1.48,2.03,2.57,3.10,3.58,4.02,4.30]
RISE=[.031,.026,.082,.033,.078,.045,.056,.025]
for sign in (-1,1):
    for lane in (-1,1):
        for i,(za,zb) in enumerate(zip(CUTS,CUTS[1:])):
            offset=.065 if lane==1 and i>0 else 0
            z0=za+offset+.012; z1=zb+offset-.025
            if z1>4.30:
                z1=4.30
            w0=blade_width(z0)*.68; w1=blade_width(z1)*.68
            xa0=.6+(-w0 if lane<0 else .013)
            xa1=.6+(-w1 if lane<0 else .013)
            xb0=.6+(-.013 if lane<0 else w0)
            xb1=.6+(-.013 if lane<0 else w1)
            # 后沿更高，前沿向下咬合；部分侧边切出真实阶梯缺口。
            rise=RISE[i]+(.014 if lane==1 and i%2==0 else 0)
            def roof(z,za=za,rise=rise):
                return deck_height(z)+rise-.026*(z-za)
            outline=[(xa0+.012,z0),(xb0-.015,z0),(xb0,z0+.023)]
            if i in (2,4,6):
                zz=z0+(z1-z0)*.63
                xx=xb0+(xb1-xb0)*.63
                outline += [(xx,zz-.045),(xx-.025,zz-.045),(xx-.025,zz+.045),(xx,zz+.045)]
            outline += [(xb1,z1-.02),(xb1-.012,z1),(xa1+.012,z1),(xa1,z1-.022),(xa0,z0+.021)]
            # 下层暗色承力板与上层甲片之间留出可见的阴影边。
            poly=[(sign*x,deck_height(z)+.006,z) for x,z in outline]
            prism('31 | prow armor underlayers',STRUCTURE,poly,(0,-.024,0))
            poly=[(sign*x,roof(z),z) for x,z in outline]
            prism('32 | staggered thick prow armor',ARMOR[(i+lane+2*sign)%8],poly,(0,-.029,0))
            # 单独的压板、阶梯护边和沉头螺栓。
            for z in (z0+.055,z1-.055):
                w=blade_width(z)*.68
                x=sign*(.6+lane*w*.78)
                bolt('33 | armor retaining hardware',x,roof(z)+.004,z,.0055)
            if i in (0,2,4,6):
                z=(z0+z1)*.5; w=blade_width(z)*.68
                x=sign*(.6+lane*w*.52)
                hatch('34 | inset access hatches',x,z,roof(z)+.009,min(.040,w*.27),min(.095,(z1-z0)*.23))
            elif i in (1,3,5):
                z=z1-.12; x=sign*(.6+lane*blade_width(z)*.43)
                top_plate('35 | recessed radiator cassettes',DARK,x-.036,x+.036,z-.077,z+.077,roof(z)+.014,.025,.009)
                for j in range(6):
                    zz=z-.06+j*.024
                    box('35 | recessed radiator cassettes',STRUCTURE,(x,roof(zz)+.024,zz),(.052,.012,.008))
            # 甲片尾端暴露的夹层有横梁与短段液压管。
            if i<6:
                zz=zb-.006
                center=sign*(.6+lane*blade_width(zz)*.40)
                box('36 | exposed deck interlayers',DARK,(center,deck_height(zz)+.011,zz),
                    (blade_width(zz)*.52,.027,.063))
                for j in (-1,0,1):
                    x=center+j*blade_width(zz)*.13
                    cylinder('36 | exposed deck interlayers',STEEL,
                             (x,deck_height(zz)+.022,zz-.025),(x,deck_height(zz)+.022,zz+.025),.007,segments=10)

    # 斜面装甲真正挖空一部分，分成边框、深色背板和夹层管路。
    for edge in (-1,1):
        for i,(za,zb) in enumerate(zip(CUTS,CUTS[1:])):
            za+=.013; zb-=.025
            p=lambda u,z:shoulder_point(sign,edge,u,z,.012 if i%3==0 else 0)
            mat=ARMOR[(i+edge+3)%8]
            if i in (1,3,5):
                hz0=za+(zb-za)*.22; hz1=za+(zb-za)*.78
                for u0,u1,z0,z1 in ((0,1,za,hz0),(0,1,hz1,zb),(0,.26,hz0,hz1),(.80,1,hz0,hz1)):
                    surface_plate('37 | open sloped armor frames',mat,[(u0,z0),(u1,z0),(u1,z1),(u0,z1)],p,.030)
                backing=lambda u,z:Vector(p(u,z))+Vector((0,-.062,0))
                surface_plate('38 | shoulder mechanical cavities',DARK,
                              [(.25,hz0),(.81,hz0),(.81,hz1),(.25,hz1)],backing,.014)
                for u in (.36,.65):
                    a=Vector(p(u,hz0+.015))+Vector((0,-.025,0))
                    b=Vector(p(u,hz1-.015))+Vector((0,-.025,0))
                    cylinder('38 | shoulder mechanical cavities',STEEL,a,b,.009,segments=12)
                for z in (hz0+.02,hz1-.02):
                    a=Vector(p(.29,z))+Vector((0,-.007,0))
                    b=Vector(p(.77,z))+Vector((0,-.007,0))
                    cylinder('38 | shoulder mechanical cavities',STRUCTURE,a,b,.014,segments=10)
                # 外侧框的防撞护条与低反射紧固件。
                a=p(.12,za+.03); b=p(.12,zb-.03)
                cylinder('33 | armor retaining hardware',STEEL,a,b,.006,segments=8)
            else:
                surface_plate('39 | faceted overlapping shoulder plates',mat,
                              [(0,za+.018),(.86,za),(1,za+.034),(1,zb-.026),(.92,zb),(0,zb)],p,.031)
                z=(za+zb)*.5
                pa=Vector(p(.4,z-.05))+Vector((0,.008,0)); pb=Vector(p(.4,z+.05))+Vector((0,.008,0))
                cylinder('33 | armor retaining hardware',STEEL,pa,pb,.004,segments=8)

    # 舷侧凸出的分段护裙与更深的机械走廊形成第二层轮廓。
    for i in range(7):
        za=.65+i*.46; zb=za+.345
        x0=sign*(.6+blade_width(za)+.032)
        x1=sign*(.6+blade_width(zb)+.032)
        y0=.12-.024*za
        poly=[(x0,y0,za),(x1,y0-.012,zb),(x1,-.046,zb-.035),
              (x0+sign*.038,-.046,za+.045),(x0+sign*.038,.065,za)]
        prism('40 | layered flank splinter shields',ARMOR[(i+4)%8],poly,(sign*.020,0,0))
        # 外露承力杆上的套筒，与上层装甲保留空隙。
        for z in (za+.08,za+.24):
            x=sign*(.6+blade_width(z)+.071)
            cylinder('41 | flank hydraulic hardware',STEEL,(x,-.04,z),(x,.05,z),.009,segments=10)
            cylinder('41 | flank hydraulic hardware',STRUCTURE,(x,-.018,z),(x,.021,z),.015,segments=12)

# 主舰体肩部与侧面采用三个尺度：厚覆甲、镂空设备架、小型管束。
MID=[(-2.52,-1.91),(-1.38,-.91),(-.87,-.42),(-.38,-.05)]
for sign in (-1,1):
    for i,(za,zb) in enumerate(MID):
        # 不是等高屋顶：梯形甲片在中段突起，侧面露出下层支架。
        top=.58+(.035 if i in (0,2) else 0)
        # 甲板的三块实体面分别构成坡面，避免非平面大 n-gon。
        za2=za+.06; zb2=zb-.045
        top_plate('42 | stepped midship shoulder armor',ARMOR[(i+1)%8],
                  min(sign*.46,sign*.77),max(sign*.46,sign*.77),za2,zb2,
                  lambda z,top=top,za2=za2:top-.045*(z-za2),.040,.028)
        for edge,xx,yy in ((0,.46,top),(1,.77,top-.01)):
            outer=.39 if edge==0 else .92; oy=.485 if edge==0 else .32
            prism('42 | stepped midship shoulder armor',ARMOR[(i+edge+2)%8],
                  [(sign*xx,yy,za2),(sign*xx,yy-.025,zb2),(sign*outer,oy,zb),(sign*outer,oy,za)],
                  (0,-.025,0))
        box('43 | midship equipment subframes',DARK,(sign*.63,.49,(za+zb)*.5),(.41,.08,zb-za))
        for zz in (za+.02,zb-.02):
            box('43 | midship equipment subframes',STEEL,(sign*.63,.527,zz),(.36,.025,.025))
        # 中央可拆卸的低矮散热组件，纵向冷却管和细密的横向片。
        z=(za+zb)*.5; x=sign*.61
        top_plate('44 | multilayer heat exchanger trays',DARK,x-.086,x+.086,z-.15,z+.15,top+.025,.025,.014)
        for j in range(9):
            zz=z-.115+j*.029
            box('44 | multilayer heat exchanger trays',STRUCTURE,(x,top+.039,zz),(.143,.026,.011))
        for dx in (-.052,.052):
            cylinder('44 | multilayer heat exchanger trays',COPPER,(x+dx,top+.050,z-.13),(x+dx,top+.050,z+.13),.008,segments=10)
        # 上下护裙错位；斜边框在服务槽外形成明显的悬挑和暗部。
        for yy,up in ((.22,1),(-.235,-1)):
            xx=sign*(1.075+(.02 if i%2 else .05))
            poly=[(xx,yy-.074,za+.03),(xx,yy+.066,za+.03),
                  (xx-sign*.032,yy+.095,za+.11),(xx-sign*.032,yy+.095,zb-.03),
                  (xx,yy-.074,zb-.03)]
            prism('45 | interlocking midship side armor',ARMOR[(i+up+2)%8],poly,(sign*.035,0,0))
        for zz in (za+.13,zb-.13):
            cylinder('46 | midship exposed actuators',STRUCTURE,(sign*1.08,-.055,zz),(sign*1.08,.092,zz),.025,segments=12)
            cylinder('46 | midship exposed actuators',STEEL,(sign*1.08,.015,zz),(sign*1.08,.102,zz),.012,segments=12)
            bolt('33 | armor retaining hardware',sign*1.135,.231,zz,.006,sign)
        tube('46 | midship exposed actuators',STEEL,
             [(sign*1.028,.055,za+.035),(sign*1.067,.055,za+.08),(sign*1.067,.055,zb-.08),(sign*1.028,.055,zb-.035)],.010)

    # 舰桥脚下增加斜切装甲裙和管线，仍维持原低矮传感器顶线。
    for za,zb in ((-1.38,-1.06),(-1.02,-.75)):
        prism('47 | bridge foundation armor',ARMOR[3],
              [(sign*.36,.64,za),(sign*.36,.64,zb),(sign*.48,.51,zb-.025),(sign*.48,.51,za+.025)],
              (0,-.026,0))
        box('47 | bridge foundation armor',STRUCTURE,(sign*.43,.525,(za+zb)*.5),(.11,.045,zb-za-.045))
        cylinder('47 | bridge foundation armor',STEEL,(sign*.455,.55,za+.03),(sign*.455,.55,zb-.03),.007,segments=10)

    # 推进器顶部的开架机械舱与错层防护板，补足尾部轮廓层次。
    for layer in range(3):
        y=(layer-1)*.34; x=sign*.73
        for j,(za,zb) in enumerate(((-3.47,-3.19),(-2.99,-2.67),(-2.55,-2.26))):
            lift=.033 if j%2 else .064
            top_plate('48 | raised engine armor shells',ARMOR[(j+layer+2)%8],x-.16,x+.16,za,zb,
                      y+.18+lift,.037,.035)
            for dx in (-.122,.122):
                box('49 | engine mounting yokes',STRUCTURE,(x+dx,y+.179,(za+zb)*.5),(.035,.07,zb-za-.04))
                bolt('33 | armor retaining hardware',x+dx,y+.187+lift,za+.055,.005)
        for yy in (-.065,.066):
            tube('50 | multi diameter engine pipe looms',STEEL,
                 [(sign*.99,y+yy,-3.42),(sign*1.09,y+yy,-3.28),
                  (sign*1.09,y+yy,-2.57),(sign*1.00,y+yy,-2.40)],.014)
        cylinder('50 | multi diameter engine pipe looms',STRUCTURE,
                 (sign*1.065,y,-3.29),(sign*1.065,y,-2.55),.033,segments=20)
        cylinder('50 | multi diameter engine pipe looms',STEEL,
                 (sign*1.065,y,-3.05),(sign*1.065,y,-2.69),.021,segments=20)
        for zz in (-3.18,-2.82,-2.59):
            box('49 | engine mounting yokes',STRUCTURE,(sign*1.09,y,zz),(.075,.186,.029))
            for yy in (-.067,.067):
                bolt('33 | armor retaining hardware',sign*1.132,y+yy,zz,.005,sign)
        # 液压蓄能罐置于两片顶甲之间，圆柱与平甲互相衬托。
        for zz in (-3.095,-2.615):
            cylinder('51 | engine pressure accumulators',DARK,(x,y+.18,zz-.041),(x,y+.18,zz+.041),.061,segments=24)
            annulus('51 | engine pressure accumulators',STEEL,x,y+.18,zz-.043,zz-.030,.066,.056,24)
            annulus('51 | engine pressure accumulators',STEEL,x,y+.18,zz+.030,zz+.043,.066,.056,24)
            for dx in (-.035,.035):
                tube('51 | engine pressure accumulators',COPPER,
                     [(x+dx,y+.20,zz-.09),(x+dx,y+.24,zz-.055),(x+dx,y+.24,zz+.055),(x+dx,y+.20,zz+.09)],.005)

# 中央加速器增加分段护罩与接头，保持窄蓝芯管可见。
for zz in (.91,1.52,2.14,2.62):
    for sign in (-1,1):
        box('52 | accelerator service blocks',STRUCTURE,(sign*.155,.18,zz),(.054,.072,.11))
        box('52 | accelerator service blocks',ARMOR[1],(sign*.158,.225,zz),(.065,.022,.13))
        for z in (zz-.037,zz+.037):
            bolt('33 | armor retaining hardware',sign*.16,.238,z,.004)

collections={}
for (module,matname),(verts,faces,smooth,mat) in GROUPS.items():
    if module not in collections:
        c=bpy.data.collections.new('V3 '+module); S.collection.children.link(c); collections[module]=c
    mesh=bpy.data.meshes.new('V3 '+module+' '+matname)
    mesh.from_pydata(verts,[],faces); mesh.update()
    bm=bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(mesh); bm.free()
    mesh.polygons.foreach_set('use_smooth',np.array(smooth,dtype=bool))
    obj=bpy.data.objects.new('V3 '+module+' '+matname,mesh); collections[module].objects.link(obj)
    mesh.materials.append(mat)
    bevel=obj.modifiers.new('Small machined edge radii','BEVEL')
    bevel.width=.0014 if any(s in module for s in ('hardware','pipe','pressure')) else .0032
    bevel.segments=3; bevel.limit_method='ANGLE'; bevel.angle_limit=.4; bevel.harden_normals=True

# 校验包含支撑和环锁扣的整组原始对象，避免共享网格/材质被间接更改。
assert {name:mesh_digest(bpy.data.objects[name]) for name in BASE_NAMES}==base_hashes
assert all(mat_digest(bpy.data.materials[n])==h for n,h in protected_mats.items())
for name in BASE_NAMES:
    if name!='Titanium armor':
        assert [m.name for m in bpy.data.objects[name].data.materials]==v2_state[name]['materials']

# 同一套侧光用于 V2/V3 对照，既能看见厚度，也能看清金属反射梯度。
for o in list(S.objects):
    if o.type=='LIGHT':
        bpy.data.objects.remove(o,do_unlink=True)
for name,pos,power,size,color in [
    ('V3 broad neutral key',(1.5,7,3),1450,4.3,(1,.96,.90)),
    ('V3 narrow warm rim',(-5,3,-4),1850,3.5,(1,.83,.65)),
    ('V3 cool side fill',(6,1.5,5),340,4.0,(.70,.82,1)),
    ('V3 engine edge',(3,2,-6),720,3,(.64,.77,1)),
]:
    data=bpy.data.lights.new(name,'AREA'); data.energy=power; data.shape='DISK'; data.size=size; data.color=color
    obj=bpy.data.objects.new(name,data); S.collection.objects.link(obj); obj.location=pos; aim(obj,(0,.05,.3))
S.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.035,.046,.062,1)
S.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.22
S.view_settings.view_transform='AgX'; S.view_settings.exposure=-.1
S.cycles.samples=80 if FINAL else 24; S.cycles.use_denoising=True; S.cycles.adaptive_threshold=.025
pref=bpy.context.preferences.addons['cycles'].preferences; pref.compute_device_type='OPTIX'; pref.get_devices()
for d in pref.devices:
    d.use=d.type=='OPTIX'
S.cycles.device='GPU'
S.render.resolution_x=1920 if FINAL else 1440; S.render.resolution_y=1080 if FINAL else 810
S.render.resolution_percentage=100
CAM=S.camera
VIEWS=[('01_hero',(13,6.2,9.5),(0,0,.45),10.3),
       ('02_prow_layers',(5,3.6,7.8),(0,.15,2.0),5.4),
       ('03_midship_layers',(5,4.1,2),(0,.2,-.65),4.35),
       ('04_engine_detail',(-5,2.6,-8),(0,.1,-2.85),4.7),
       ('05_aft',(-9,5.3,-12),(0,0,-.1),10.2)]
for name,pos,target,scale in VIEWS:
    if name=='01_hero':
        cam=CAM
    else:
        data=CAM.data.copy(); data.name='V3 camera '+name
        cam=bpy.data.objects.new('V3 camera '+name,data); S.collection.objects.link(cam)
    cam.location=pos; aim(cam,target); cam.data.ortho_scale=scale
CAM.location=VIEWS[0][1]; aim(CAM,VIEWS[0][2]); CAM.data.ortho_scale=VIEWS[0][3]
S.render.filepath=str(OUT/'01_hero.png')
S['reference_refinement_v3']='Staggered thick armor, open mechanical cavities, multiscale physically based metals. Original warp rings unchanged.'
report={'source':str(SOURCE),'output':str(TARGET),'original_mesh_sha256':base_hashes,
        'protected_material_sha256':protected_mats,'ring_geometry_transform_materials':'UNCHANGED',
        'original_meshes_unchanged':True,'ring_material_assignments_unchanged':True,
        'added_parts_v3':sum(PART_COUNT.values()),'parts_per_module':PART_COUNT,
        'new_mesh_objects':len(GROUPS),'new_vertices':sum(len(v[0]) for v in GROUPS.values()),
        'new_polygons':sum(len(v[1]) for v in GROUPS.values()),
        'v2_object_state':v2_state}
(OUT/'preservation_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(TARGET))
print('V3_MODEL_SAVED',sum(PART_COUNT.values()),'parts',len(GROUPS),'meshes',round(time.time()-T0,1),'seconds',flush=True)
for name,pos,target,scale in VIEWS if FINAL else VIEWS[:2]:
    CAM.location=pos; aim(CAM,target); CAM.data.ortho_scale=scale
    S.render.filepath=str(OUT/(name+('.png' if FINAL else '_preview.png')))
    bpy.ops.render.render(write_still=True); print('VIEW_COMPLETE',name,flush=True)
print('V3_COMPLETE',flush=True)
