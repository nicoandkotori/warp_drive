"""参照双刃战列舰原图，在现有 Blender 网格上添加可编辑的硬表面细节。

不重建、不重采样原网格。两只曲率环、支撑、锁扣及其所有共用材质
逐字节保留；只有纯船体装甲对象换用独立复制的材质。新增零件按模块
和材质分组，装甲缝、散热片、管线、紧固件均为真实几何。

blender -b --python refine_reference.py -- --preview
blender -b --python refine_reference.py -- --final
"""
from pathlib import Path
import hashlib
import json
import math
import random
import sys
import time

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'reference_refined_v2'
OUT.mkdir(exist_ok=True)
FINAL = '--final' in sys.argv
RNG = random.Random(1207)
T0 = time.time()
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'battleship_detail.blend'), use_scripts=False)
S = bpy.context.scene
BASE = [o for o in S.objects if o.type == 'MESH']


def mesh_digest(obj):
    mesh = obj.data
    co = np.empty(len(mesh.vertices) * 3, np.float32)
    vi = np.empty(len(mesh.loops), np.int32)
    sizes = np.empty(len(mesh.polygons), np.int32)
    mesh.vertices.foreach_get('co', co)
    mesh.loops.foreach_get('vertex_index', vi)
    mesh.polygons.foreach_get('loop_total', sizes)
    h = hashlib.sha256()
    for a in (co, vi, sizes, np.array(obj.matrix_world, np.float64)):
        h.update(a.tobytes())
    return h.hexdigest()


def mat_digest(mat):
    def plain(v):
        if isinstance(v, (str, int, float, bool)) or v is None:
            return v
        try:
            return list(v)
        except TypeError:
            return str(v)
    data = {'diffuse': list(mat.diffuse_color), 'nodes': [], 'links': []}
    if mat.use_nodes:
        for n in mat.node_tree.nodes:
            data['nodes'].append((n.name, n.bl_idname,
                                  [(i.name, plain(i.default_value)) for i in n.inputs if hasattr(i, 'default_value')]))
        data['links'] = [(l.from_node.name, l.from_socket.name, l.to_node.name, l.to_socket.name)
                         for l in mat.node_tree.links]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


before = {o.name: mesh_digest(o) for o in BASE}
protected_materials = {m.name: mat_digest(m) for o in BASE for m in o.data.materials}
for o in BASE:
    for m in o.data.materials:
        m.use_fake_user = True
original_collection = bpy.data.collections.new('00 | ORIGINAL MESH - rings preserved')
S.collection.children.link(original_collection)
for o in BASE:
    for c in list(o.users_collection):
        c.objects.unlink(o)
    original_collection.objects.link(o)
    o['original_mesh_sha256'] = before[o.name]
    o.hide_select = True


def material(name, color, metal=.76, rough=.38, emit=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Metallic'].default_value = metal
    bs.inputs['Roughness'].default_value = rough
    if emit:
        bs.inputs['Emission Color'].default_value = (*color, 1)
        bs.inputs['Emission Strength'].default_value = emit
    else:
        n = m.node_tree.nodes.new('ShaderNodeTexNoise')
        n.inputs['Scale'].default_value = 260
        n.inputs['Detail'].default_value = 2
        texcoord = m.node_tree.nodes.new('ShaderNodeNewGeometry')
        m.node_tree.links.new(texcoord.outputs['Position'], n.inputs['Vector'])
        bump = m.node_tree.nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = .12
        bump.inputs['Distance'].default_value = .0006
        m.node_tree.links.new(n.outputs['Fac'], bump.inputs['Height'])
        m.node_tree.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
        ramp = m.node_tree.nodes.new('ShaderNodeMapRange')
        ramp.inputs['To Min'].default_value = rough - .045
        ramp.inputs['To Max'].default_value = rough + .055
        m.node_tree.links.new(n.outputs['Fac'], ramp.inputs['Value'])
        m.node_tree.links.new(ramp.outputs['Result'], bs.inputs['Roughness'])
    return m


ARMOR = [material(f'V2 | titanium plate {i+1:02}', (v, v*1.025, v*1.07), .78, .36+i*.009)
         for i, v in enumerate((.16, .185, .21, .24, .265, .19))]
DARK = material('V2 | carbon recess', (.013, .018, .024), .55, .49)
STRUCTURE = material('V2 | dark structural steel', (.045, .055, .065), .82, .4)
STEEL = material('V2 | machined edges', (.25, .28, .31), .88, .3)
BLACK = material('V2 | ceramic vent interior', (.008, .012, .017), .25, .58)
BRASS = material('V2 | muted service markings', (.24, .17, .075), .65, .43)
WHITE = material('V2 | stencilled ceramic', (.46, .47, .46), .12, .65)
CYAN = material('V2 | narrow blue energy guides', (.08, .48, .68), .3, .28, 2.8)
WINDOW = material('V2 | individual warm windows', (.67, .46, .23), .1, .38, 1.5)
GLASS = material('V2 | smoked observation glass', (.009, .022, .033), .65, .19)

# 只复制纯船体材质；原始材质数据块全部保持原值，环和共用金属不受影响。
hull = bpy.data.objects['Titanium armor']
hull_mat = hull.data.materials[0].copy()
hull_mat.name = 'V2 | original hull darker titanium'
hull_mat.diffuse_color = (.18, .19, .21, 1)
bs = hull_mat.node_tree.nodes.get('Principled BSDF')
bs.inputs['Base Color'].default_value = (.18, .19, .21, 1)
bs.inputs['Metallic'].default_value = .78
for n in hull_mat.node_tree.nodes:
    if n.type == 'BUMP':
        n.inputs['Distance'].default_value = .00065
hull.data.materials[0] = hull_mat

GROUPS = {}
COLLECTIONS = {}
PART_COUNT = {}


def add(module, mat, verts, faces, smooth=False):
    key = (module, mat.name)
    batch = GROUPS.setdefault(key, [[], [], [], mat])
    offset = len(batch[0])
    batch[0].extend(verts)
    batch[1].extend([tuple(i+offset for i in f) for f in faces])
    batch[2].extend([smooth] * len(faces))
    PART_COUNT[module] = PART_COUNT.get(module, 0) + 1


def prism(module, mat, polygon, direction):
    p = [Vector(v) for v in polygon]
    d = Vector(direction)
    n = len(p)
    verts = [tuple(v) for v in p] + [tuple(v+d) for v in p]
    faces = [tuple(range(n-1, -1, -1)), tuple(range(n, 2*n))]
    faces += [(i, (i+1) % n, (i+1) % n+n, i+n) for i in range(n)]
    add(module, mat, verts, faces)


def box(module, mat, center, size):
    x, y, z = center
    a, b, c = [v*.5 for v in size]
    polygon = [(x-a, y-b, z-c), (x+a, y-b, z-c), (x+a, y-b, z+c), (x-a, y-b, z+c)]
    prism(module, mat, polygon, (0, 2*b, 0))


def top_plate(module, mat, x0, x1, z0, z1, height, thick=.018, cut=.018):
    c = min(cut, (x1-x0)*.19, (z1-z0)*.19)
    outline = [(x0+c,z0),(x1-c,z0),(x1,z0+c),(x1,z1-c),
               (x1-c,z1),(x0+c,z1),(x0,z1-c),(x0,z0+c)]
    f = height if callable(height) else lambda z: height
    prism(module, mat, [(x, f(z)-thick, z) for x,z in outline], (0, thick, 0))


def cylinder(module, mat, a, b, radius, r2=None, segments=12):
    a, b = Vector(a), Vector(b)
    w = (b-a).normalized()
    u = w.cross(Vector((0,1,0)) if abs(w.y)<.95 else Vector((1,0,0))).normalized()
    v = w.cross(u)
    r2 = radius if r2 is None else r2
    verts = []
    for origin, rad in ((a, radius), (b, r2)):
        verts += [tuple(origin+rad*(math.cos(t*math.tau/segments)*u+math.sin(t*math.tau/segments)*v))
                  for t in range(segments)]
    faces = [tuple(range(segments-1,-1,-1)), tuple(range(segments,2*segments))]
    faces += [(i,(i+1)%segments,(i+1)%segments+segments,i+segments) for i in range(segments)]
    add(module, mat, verts, faces, True)


def annulus(module, mat, x, y, z0, z1, ro, ri, segments=32):
    verts=[]
    for z, r in ((z0,ro),(z1,ro),(z0,ri),(z1,ri)):
        verts.extend([(x+r*math.cos(i*math.tau/segments), y+r*math.sin(i*math.tau/segments),z)
                      for i in range(segments)])
    faces=[]
    for i in range(segments):
        j=(i+1)%segments
        faces.extend([(i,j,segments+j,segments+i),
                      (2*segments+i,3*segments+i,3*segments+j,2*segments+j),
                      (i,2*segments+i,2*segments+j,j),
                      (segments+i,segments+j,3*segments+j,3*segments+i)])
    add(module,mat,verts,faces)


def bolt(module, x, y, z, r=.006, side=0):
    if side:
        cylinder(module, STEEL, (x,y,z), (x+side*.004,y,z), r, segments=6)
    else:
        cylinder(module, STEEL, (x,y-.001,z), (x,y+.004,z), r, segments=6)


def blade_width(z):
    return .49 - .472 * (z-.1)/4.85


def deck_height(z):
    return .35 - .185 * max(0,min(1,(z-.2)/4.35)) + .055


def blade_side(module, mat, sign, z0, z1, y0, y1, offset=.009, thick=.012):
    poly=[]
    for z,y in ((z0,y0),(z1,y0*.78),(z1,y1*.78),(z0,y1)):
        poly.append((sign*(.6+blade_width(z)+offset), y, z))
    prism(module, mat, poly, (sign*thick,0,0))


# 双刃顶面：错缝的大覆板、窄副板和少量检修盖，保留宏观干净块面。
for sign in (-1,1):
    module='01 | twin prow layered armor'
    cuts=[.53,.92,1.37,1.91,2.41,2.98,3.49,3.96,4.29]
    for i,(z0,z1) in enumerate(zip(cuts,cuts[1:])):
        for lane in (-1,1):
            inset=.024
            def shape(z, lane=lane):
                w=max(.019,blade_width(z)*.78-inset*.55)
                return (.6+(.012 if lane>0 else -w), .6+(w if lane>0 else -.012))
            xa,xb=shape(z0+.012); xc,xd=shape(z1-.012)
            # 梯形随舰艏收窄，切角与斜向分缝提供真实的层次。
            raw=[(xa+.013,z0+.012),(xb-.013,z0+.012),(xb,z0+.033),
                 (xd,z1-.033),(xd-.01,z1-.012),(xc+.01,z1-.012),
                 (xc,z1-.031),(xa,z0+.031)]
            poly=[(sign*x,deck_height(z)-.016,z) for x,z in raw]
            prism(module, ARMOR[(i+lane+sign)%len(ARMOR)], poly,(0,.021,0))
            if i<6:
                for x,z in ((xa+.026,z0+.048),(xd-.02,z1-.048)):
                    bolt('02 | recessed fasteners',sign*x,deck_height(z)+.006,z,.005)
        if i in (1,3,5):
            z=(z0+z1)*.5
            x=sign*(.6+blade_width(z)*.44)
            top_plate('03 | service hatches',STRUCTURE,x-.042,x+.042,z-.069,z+.069,
                      deck_height,.014,.013)
            top_plate('03 | service hatches',ARMOR[1],x-.032,x+.032,z-.053,z+.053,
                      lambda zz:deck_height(zz)+.009,.012,.008)
            box('03 | service hatches',STEEL,(x,deck_height(z)+.015,z-.018),(.023,.004,.006))
    # 大装甲的肩部斜面沿船艏连续下降，避免宽覆板悬在侧舷形成台阶。
    for edge in (-1,1):
        for i,(za,zb) in enumerate(zip(cuts,cuts[1:])):
            poly=[]
            for z,factor,is_top in ((za+.01,.78,True),(zb-.01,.78,True),
                                   (zb-.01,.99,False),(za+.01,.99,False)):
                xx=sign*(.60+edge*blade_width(z)*factor)
                yy=deck_height(z)-.012 if is_top else .18-.031*z
                poly.append((xx,yy,z))
            prism('24 | continuous sloped prow shoulders',ARMOR[(i+edge+2)%6],poly,(0,-.013,0))
            if i<6:
                z=(za+zb)*.5
                xx=sign*(.60+edge*blade_width(z)*.86)
                yy=deck_height(z)*.70+(.18-.031*z)*.30
                cylinder('24 | continuous sloped prow shoulders',STEEL,
                         (xx,yy,z-.047),(xx,yy,z+.047),.005,segments=8)
    # 次级细节集中在部分覆板：小检修门、埋入式百叶、细接缝与拉手。
    for i,(za,zb) in enumerate(zip(cuts,cuts[1:])):
        z=(za+zb)*.5
        if z>3.9:
            continue
        w=blade_width(z)*.78
        for lane in (-1,1):
            x=sign*(.6+lane*w*.48)
            if i%3==0:
                half=min(.050,w*.29)
                top_plate('25 | inset deck panels',DARK,x-half,x+half,z-.10,z+.10,
                          lambda zz:deck_height(zz)+.007,.006,.012)
                top_plate('25 | inset deck panels',ARMOR[1],x-half+.009,x+half-.009,z-.085,z+.085,
                          lambda zz:deck_height(zz)+.011,.006,.008)
                for off in (-.06,.06):
                    bolt('02 | recessed fasteners',x,deck_height(z+off)+.013,z+off,.0035)
                box('25 | inset deck panels',STEEL,(x,deck_height(z)+.015,z),(.020,.004,.007))
            elif i%3==1:
                half=min(.034,w*.25)
                top_plate('26 | embedded prow louvers',BLACK,x-half,x+half,z-.084,z+.084,
                          lambda zz:deck_height(zz)+.008,.006,.009)
                for j in range(6):
                    zz=z-.064+j*.025
                    box('26 | embedded prow louvers',STRUCTURE,(x,deck_height(zz)+.012,zz),
                        (half*1.6,.005,.009))
            else:
                # 一条细的折线分缝，比例比主装甲接缝小一级。
                for off in (-.055,.055):
                    box('27 | deck seam inlays',STRUCTURE,(x,deck_height(z+off)+.007,z+off),
                        (max(.018,w*.48),.002,.003))
                box('27 | deck seam inlays',BRASS,(x,deck_height(z)+.009,z),(.025,.003,.008))
    # 末端采用封闭的实心过渡壳，填合旧上层甲板的终止台阶。
    # 用三段截面贴回原尖端，避免薄面板在尖端上方形成第二个叉尖。
    tip_vertices=[]
    for zz,ww,yt in ((4.27,.084,.224),(4.49,.064,.184),(4.94,.019,.030)):
        yb=-(.34-.315*(zz-.1)/4.85)-.003
        c=min(.012,ww*.30,(yt-yb)*.20)
        cross=[(-ww+c,yb),(ww-c,yb),(ww,yb+c),(ww,yt-c),
               (ww-c,yt),(-ww+c,yt),(-ww,yt-c),(-ww,yb+c)]
        tip_vertices.extend([(sign*(.6+x),y,zz) for x,y in cross])
    tip_faces=[tuple(range(7,-1,-1)),tuple(range(16,24))]
    for k in range(2):
        tip_faces.extend([(8*k+j,8*k+(j+1)%8,8*(k+1)+(j+1)%8,8*(k+1)+j) for j in range(8)])
    add('28 | tapered prow tips',ARMOR[1],tip_vertices,tip_faces)
    # 肩部少量深色检修盖打断整片长斜面，保持不同尺度的细节密度。
    for edge in (-1,1):
        for i in (1,3,5):
            za,zb=cuts[i]+.09,cuts[i+1]-.09
            poly=[]
            for z,t in ((za,.28),(zb,.28),(zb,.72),(za,.72)):
                factor=.78+.21*t
                y=(deck_height(z)-.012)*(1-t)+(.18-.031*z)*t+.015
                poly.append((sign*(.6+edge*blade_width(z)*factor),y,z))
            prism('30 | sloped inspection pockets',STRUCTURE,poly,(0,-.004,0))
    # 舷侧覆板分为上下装甲带，中间凹入的机械层显出纵深。
    for i in range(10):
        za=.48+i*.365; zb=za+.341
        h=.34-.315*(za-.1)/4.85
        blade_side('04 | prow flank armor',ARMOR[(i+2)%6],sign,za,zb,.055,h*.68)
        blade_side('04 | prow flank armor',ARMOR[i%6],sign,za,zb,-h*.81,-.063)
        blade_side('05 | prow recessed mechanics',DARK,sign,za+.008,zb-.008,-.052,.043,.011,.008)
        for j in range(3):
            zz=za+.055+j*.088
            x=sign*(.6+blade_width(zz)+.026)
            box('05 | prow recessed mechanics',STEEL,(x,-.007,zz),(.012,.029,.011))
            if i<7 and j!=1:
                box('06 | tiny flank windows',WINDOW,(x+sign*.008,-h*.57,zz),(.004,.006,.025))
        if i%2==0:
            zz=za+.13
            bolt('02 | recessed fasteners',sign*(.6+blade_width(zz)+.023),h*.54,zz,.004,sign)
    # 两层细管线沿外舷的斜面收窄，不把灯带铺满整个船体。
    for yy in (-.021,.019):
        for za,zb in ((.57,1.57),(1.65,2.65),(2.73,3.62)):
            cylinder('05 | prow recessed mechanics',STEEL,
                     (sign*(.6+blade_width(za)+.026),yy,za),
                     (sign*(.6+blade_width(zb)+.026),yy,zb),.007,segments=8)
    # 内舷的深槽与分段能量导轨。
    for i in range(7):
        z=.67+i*.37
        x=sign*(.6-blade_width(z)-.006)
        box('07 | accelerator bay',STRUCTURE,(x,.095,z),(.026,.11,.28))
        box('07 | accelerator bay',STEEL,(x-sign*.016,.106,z),(.012,.018,.23))
    # 顶部散热器和矮传感器，延续之前去掉高桅杆的轮廓。
    for z in (1.42,2.92):
        x=sign*.61
        y=deck_height(z)+.012
        top_plate('08 | prow cooling',BLACK,x-.072,x+.072,z-.12,z+.12,y,.018)
        for j in range(8):
            zz=z-.1+j*.028
            box('08 | prow cooling',STRUCTURE,(x,y+.006,zz),(.117,.008,.01))
    for z in (.92,2.25):
        # 保留原炮塔外形，添加炮塔侧裙、后部散热片和炮管套箍。
        yy=.39 if z<1.5 else .28
        for offset in (-.12,.12):
            top_plate('09 | turret details',ARMOR[1],sign*.61+offset-.024,
                      sign*.61+offset+.024,z-.12,z+.02,yy+.065,.018,.008)
        for j in range(4):
            box('09 | turret details',DARK,(sign*.61,yy+.078,z-.165+j*.021),(.105,.01,.008))
        for dx in (-.065,.065):
            annulus('09 | turret details',STRUCTURE,sign*.61+dx,yy+.01,z+.28,z+.315,.033,.027,12)

# 中央加速器：轴承、独立圆柱线圈与窄发光芯管，替代单一梯子式观感。
for z0,z1 in ((.68,1.18),(1.26,1.81),(1.89,2.43),(2.51,2.79)):
    cylinder('07 | accelerator bay',STRUCTURE,(0,.156,z0),(0,.156,z1),.105,segments=32)
    for ang in (0,math.pi/2,math.pi,math.pi*1.5):
        x=.108*math.cos(ang); y=.156+.108*math.sin(ang)
        cylinder('07 | accelerator bay',STEEL,(x,y,z0+.025),(x,y,z1-.025),.011,segments=10)
    for x in (-.064,.064):
        cylinder('10 | accelerator luminous cores',CYAN,(x,.239,z0+.047),(x,.239,z1-.047),.007,segments=10)
    for z in (z0+.025,z1-.025):
        annulus('07 | accelerator bay',STEEL,0,.156,z-.016,z+.016,.122,.098,32)
        for dx in (-.143,.143):
            box('07 | accelerator bay',STRUCTURE,(dx,.095,z),(.04,.16,.044))

# 主舰体：顶部肩部装甲、底裙、舷侧凹槽、桁架、检修管路。
for sign in (-1,1):
    for i,(z0,z1) in enumerate(((-2.48,-2.12),(-2.08,-1.89),(-1.39,-.98),(-.94,-.53),(-.49,-.04))):
        # 环前后留出实际支撑的空间，不在环支撑根部叠加覆板。
        for xa,xb in ((.49,.72),(.735,.84)):
            top_plate('11 | midship shoulder armor',ARMOR[(i+1)%6],
                      min(sign*xa,sign*xb),max(sign*xa,sign*xb),z0,z1,.478,.026,.025)
        x=sign*1.045
        for yy,hh in ((.179,.104),(-.226,.131)):
            box('12 | midship belt armor',ARMOR[(i+sign)%6],(x,yy,(z0+z1)*.5),(.032,hh,z1-z0-.014))
        box('13 | deep service trenches',BLACK,(sign*.979,-.004,(z0+z1)*.5),(.026,.142,z1-z0))
        for y in (-.048,.045):
            cylinder('13 | deep service trenches',STEEL,(sign*1.008,y,z0+.02),
                     (sign*1.008,y,z1-.02),.008,segments=10)
        for j in range(max(1,int((z1-z0)/.1))):
            z=z0+.045+j*.1
            box('13 | deep service trenches',STRUCTURE,(sign*1.027,-.003,z),(.02,.115,.019))
            bolt('02 | recessed fasteners',sign*1.048,.18,z,.005,sign)
            if j%3!=1:
                box('06 | tiny flank windows',WINDOW,(sign*1.067,-.216,z),(.003,.008,.034))
        # 侧裙有独立的检修门与斜边加强件，避免连成一条平直白色装甲带。
        z=(z0+z1)*.5
        xx=sign*1.069
        box('29 | midship belt access panels',DARK,(xx,-.230,z),(.006,.067,min(.15,z1-z0-.04)))
        box('29 | midship belt access panels',ARMOR[1],(xx+sign*.005,-.230,z),
            (.008,.052,min(.13,z1-z0-.06)))
        for yy in (-.254,-.206):
            bolt('02 | recessed fasteners',xx+sign*.011,yy,z,.004,sign)
    # 背部冷却组、分级检修舱。
    for x in (.355,.61):
        for z0,z1 in ((-2.41,-1.93),(-.63,-.19)):
            sx=sign*x
            y=.487 if x>.5 else .489
            top_plate('14 | midship thermal exchangers',BLACK,sx-.072,sx+.072,z0,z1,y,.018,.012)
            for i in range(13):
                zz=z0+.025+i*(z1-z0-.05)/12
                box('14 | midship thermal exchangers',STRUCTURE,(sx,y+.009,zz),(.115,.013,.012))
    for z in (-1.12,-.52):
        box('15 | lower keel maintenance',DARK,(sign*.61,-.353,z),(.36,.026,.29))
        for j in range(5):
            box('15 | lower keel maintenance',STEEL,(sign*.61,-.372,z-.10+j*.05),(.28,.013,.008))

# 舰桥既有三层轮廓不拔高，只加贴合的装甲裙和连续观察带。
for sign in (-1,1):
    for y,z0,z1,x in ((.57,-1.47,-.76,.354),(.735,-1.40,-.97,.223)):
        box('16 | bridge observation decks',GLASS,(sign*x,y,(z0+z1)*.5),(.016,.045,z1-z0))
        for i in range(int((z1-z0)/.042)):
            z=z0+.025+i*.042
            box('16 | bridge observation decks',STRUCTURE,(sign*(x+.01),y,z),(.008,.05,.01))
            if i%4!=0:
                box('16 | bridge observation decks',WINDOW,(sign*(x+.015),y-.005,z+.015),(.003,.008,.019))
        box('16 | bridge observation decks',STEEL,(sign*(x+.018),y+.034,(z0+z1)*.5),(.012,.012,z1-z0+.035))
    for z in (-1.31,-1.15):
        top_plate('17 | flush bridge instruments',STRUCTURE,sign*.145-.03,sign*.145+.03,
                  z-.05,z+.05,.816,.014,.011)
        box('17 | flush bridge instruments',GLASS,(sign*.145,.826,z),(.043,.003,.065))
top_plate('17 | flush bridge instruments',ARMOR[2],-.073,.073,-1.31,-1.14,.931,.012,.018)
for i in range(5):
    box('17 | flush bridge instruments',DARK,(-.045+i*.022,.934,-1.22),(.006,.006,.106))

# 六台错位动力舱：分片顶甲、暴露的管线、散热片和多层喷口。
for sign in (-1,1):
    for layer in range(3):
        y=(layer-1)*.34
        rear=-4.02 if layer==1 else -3.74
        x=sign*.73
        for j,(za,zb) in enumerate(((rear+.32,rear+.56),(-3.13,-2.80),(-2.70,-2.31))):
            if za<rear+.3:
                continue
            top_plate('18 | engine cowlings',ARMOR[(layer+j)%6],x-.142,x+.142,
                      za,zb,y+.171,.025,.031)
            for zz in (za+.045,zb-.045):
                bolt('02 | recessed fasteners',x-.112,y+.176,zz,.0045)
                bolt('02 | recessed fasteners',x+.112,y+.176,zz,.0045)
        for yy in (-.056,.048):
            cylinder('19 | engine feed plumbing',STEEL,(sign*1.005,y+yy,-3.35),
                     (sign*1.035,y+yy,-2.32),.010,segments=12)
            for zz in (-3.18,-2.92,-2.47):
                box('19 | engine feed plumbing',STRUCTURE,(sign*1.036,y+yy,zz),(.031,.038,.046))
        for j in range(11):
            zz=-3.29+j*.066
            box('20 | engine heat sinks',DARK,(sign*1.008,y,zz),(.025,.185,.021))
            box('20 | engine heat sinks',STEEL,(sign*1.026,y,zz),(.012,.127,.012))
        annulus('21 | octagonal exhaust shrouds',STRUCTURE,x,y,rear-.076,rear+.014,.166,.129,8)
        annulus('21 | octagonal exhaust shrouds',STEEL,x,y,rear-.081,rear-.067,.159,.133,8)
        annulus('21 | octagonal exhaust shrouds',DARK,x,y,rear-.067,rear+.067,.128,.102,32)
        annulus('21 | octagonal exhaust shrouds',CYAN,x,y,rear-.061,rear-.054,.108,.098,48)
        for j in range(16):
            a=j*math.tau/16
            xx=x+.116*math.cos(a); yy=y+.116*math.sin(a)
            cylinder('21 | octagonal exhaust shrouds',STEEL,(xx,yy,rear-.057),(xx,yy,rear+.045),.006,segments=6)
        for j in range(8):
            a=(j+.5)*math.tau/8
            cylinder('21 | octagonal exhaust shrouds',STEEL,
                     (x+.15*math.cos(a),y+.15*math.sin(a),rear-.083),
                     (x+.15*math.cos(a),y+.15*math.sin(a),rear-.087),.005,segments=6)

# 尾部中央脊柱与两侧管束。
for sign in (-1,1):
    for j in range(4):
        za=-3.44+j*.292
        top_plate('22 | aft central backbone',ARMOR[(j+2)%6],
                  min(sign*.13,sign*.33),max(sign*.13,sign*.33),za,za+.263,.445,.022,.024)
    for x in (.09,.22):
        cylinder('22 | aft central backbone',STRUCTURE,(sign*x,.278,-3.50),(sign*x,.30,-2.34),.016,segments=12)

# 可读但克制的检修标记，几何贴花可以在 Blender 中单独编辑文字。
decal_collection=bpy.data.collections.new('23 | editable maintenance stencils')
S.collection.children.link(decal_collection)
for sign in (-1,1):
    for txt,z,dx,scale in (('07',3.35,0,.065),('CAUTION',1.76,.18,.017),('SERVICE',-2.25,0,.021)):
        data=bpy.data.curves.new('Stencil '+txt,'FONT')
        data.body=txt; data.size=scale; data.extrude=0; data.align_x='CENTER'
        obj=bpy.data.objects.new('Stencil '+txt,data); decal_collection.objects.link(obj)
        obj.location=(sign*(.60+dx), deck_height(z)+.008 if z>0 else .482,z)
        obj.rotation_euler=(-math.pi/2,0,0)
        data.materials.append(WHITE if txt=='07' else BRASS)

# 建立模块网格；每组零件的倒角保留为可编辑修改器。
for (module,matname),(verts,faces,smooth,mat) in GROUPS.items():
    if module not in COLLECTIONS:
        c=bpy.data.collections.new(module); S.collection.children.link(c); COLLECTIONS[module]=c
    mesh=bpy.data.meshes.new(module+' | '+matname)
    mesh.from_pydata(verts,[],faces); mesh.update()
    bm=bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(mesh); bm.free()
    mesh.polygons.foreach_set('use_smooth',np.array(smooth,dtype=bool))
    obj=bpy.data.objects.new(module+' | '+matname,mesh); COLLECTIONS[module].objects.link(obj)
    obj.data.materials.append(mat)
    if mat not in (CYAN,WINDOW,GLASS):
        bevel=obj.modifiers.new('Machined edge bevel - editable','BEVEL')
        bevel.width=.0017 if 'fasteners' in module else .0025
        bevel.segments=2; bevel.limit_method='ANGLE'
        bevel.angle_limit=.45
        bevel.harden_normals=True
    obj['detail_parts']=PART_COUNT[module]

after={o.name:mesh_digest(o) for o in BASE}
assert before==after,'Original geometry changed; refuse to save.'
assert all(mat_digest(bpy.data.materials[name])==digest for name,digest in protected_materials.items()), 'Original material changed.'
report={
    'source':str(ROOT/'battleship_detail.blend'),
    'output':str(OUT/'battleship_reference_refined_v2.blend'),
    'original_meshes_unchanged':before==after,
    'original_material_data_blocks_unchanged':True,
    'hull_only_material_copy':'V2 | original hull darker titanium',
    'original_mesh_sha256':before,
    'protected_material_sha256':protected_materials,
    'warp_ring_centers_z':[.25,-1.65], 'warp_ring_radius':1.72,
    'ring_geometry_transform_materials':'UNCHANGED',
    'new_physical_parts':sum(PART_COUNT.values()),
    'parts_per_module':PART_COUNT,
    'new_mesh_objects':len(GROUPS),
    'new_vertices':sum(len(b[0]) for b in GROUPS.values()),
    'new_polygons':sum(len(b[1]) for b in GROUPS.values()),
}
(OUT/'preservation_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

# 原图随工程打包，移交后也能在图像编辑器里对照。
reference=ROOT/'reference_original.png'
if reference.exists():
    im=bpy.data.images.load(str(reference),check_existing=True)
    im.use_fake_user=True; im.pack()


def aim(obj,target):
    forward=(Vector(target)-obj.location).normalized()
    right=forward.cross(Vector((0,1,0))).normalized()
    up=right.cross(forward).normalized()
    obj.rotation_euler=Matrix((right,up,-forward)).transposed().to_euler()


# 中性银灰主光和暖边光使装甲层次清晰；所有变化只属于预览布光。
for o in [o for o in S.objects if o.type=='LIGHT']:
    bpy.data.objects.remove(o,do_unlink=True)
for name,pos,power,size,color in [
    ('V2 Key',(1,7,2),1350,5,(.88,.93,1)),
    ('V2 Warm rim',(-5,2,-4),1750,4,(1,.83,.63)),
    ('V2 Front fill',(6,2,5),650,5,(.64,.78,1)),
    ('V2 Aft edge',(3,-1,-6),850,3,(.49,.68,1)),
]:
    data=bpy.data.lights.new(name,'AREA'); data.energy=power; data.shape='DISK'
    data.size=size; data.color=color
    obj=bpy.data.objects.new(name,data); S.collection.objects.link(obj); obj.location=pos; aim(obj,(0,0,.3))
S.world.use_nodes=True
S.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.055,.07,.095,1)
S.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.24
S.render.engine='CYCLES'; S.cycles.samples=64 if FINAL else 24
S.cycles.use_denoising=True; S.cycles.adaptive_threshold=.035
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX'; prefs.get_devices()
for d in prefs.devices:
    d.use=d.type=='OPTIX'
S.cycles.device='GPU'
S.render.resolution_x=1920 if FINAL else 1440
S.render.resolution_y=1080 if FINAL else 810
S.render.resolution_percentage=100
S.render.image_settings.file_format='PNG'; S.render.film_transparent=False
S.view_settings.view_transform='AgX'; S.view_settings.exposure=.15
CAM=S.camera; CAM.data.type='ORTHO'; CAM.data.ortho_scale=9.9
CAM.data.clip_start=.01; CAM.data.clip_end=300
VIEWS=[('01_hero',(13,6.2,9.5),(0,0,.45),10.3),
       ('02_aft',(-9,5.3,-12),(0,0,-.1),9.9),
       ('03_dorsal',(7,13,9),(0,0,.45),14.4),
       ('04_prow_detail',(5,3.7,7.8),(0,.08,2.05),5.4),
       ('05_engine_detail',(-5,2.6,-8),(0,.05,-2.8),4.5)]
CAM.location=VIEWS[0][1]; aim(CAM,VIEWS[0][2]); CAM.data.ortho_scale=VIEWS[0][3]
for name,pos,target,scale in VIEWS[1:]:
    data=CAM.data.copy(); data.name='V2 camera '+name; data.ortho_scale=scale
    obj=bpy.data.objects.new('V2 camera '+name,data); S.collection.objects.link(obj)
    obj.location=pos; aim(obj,target)
S['reference_refinement']='Hull details added from original reference; existing warp rings preserved byte-for-byte.'
S['coordinate_system']='Y up, +Z bow; same axes as original video ship.'

# 开文件即可看到材质模型；原始高密网格锁选，新细节可按模块编辑。
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.shading.type='MATERIAL'
            area.spaces.active.overlay.show_overlays=False
bpy.ops.object.select_all(action='DESELECT')
S.render.filepath=str(OUT/'01_hero.png')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'battleship_reference_refined_v2.blend'))
print('MODEL_SAVED',json.dumps({'parts':sum(PART_COUNT.values()),'objects':len(GROUPS),'seconds':round(time.time()-T0,1)}),flush=True)
for name,pos,target,scale in VIEWS if FINAL else VIEWS[:1]:
    CAM.location=pos; aim(CAM,target); CAM.data.ortho_scale=scale
    S.render.filepath=str(OUT/(name+('.png' if FINAL else '_preview.png')))
    bpy.ops.render.render(write_still=True)
    print('VIEW_COMPLETE',name,flush=True)
print('REFERENCE_REFINEMENT_COMPLETE',flush=True)
