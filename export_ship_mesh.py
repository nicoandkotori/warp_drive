"""把影片的同一 SDF 采样为 Blender 网格，不依赖额外的网格库。

python export_ship_mesh.py；GPU 分片采样，marching tetrahedra 提取表面。
材质编号随三角形保存；程序化灯光动画仍由影片着色器负责。
"""
from pathlib import Path
import itertools
import numpy as np
import moderngl
import config
from opusvid.gl import GLSL_COMMON
from ship_model import SHIP_MODEL_GLSL

OUT = Path(config.ROOT) / 'blender' / 'battleship_detail'
STEP = 0.012


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ctx = moderngl.create_standalone_context(require=430)
    helpers = SHIP_MODEL_GLSL.split('const float RZ0')[1].split('vec3 calcNormal')[0]
    shader = ctx.compute_shader(GLSL_COMMON + '\nuniform float uSpin;\nconst float RZ0' + helpers + '''
layout(local_size_x=256) in;
layout(std430,binding=0) readonly buffer Input { vec4 points[]; };
layout(std430,binding=1) writeonly buffer Output { vec2 values[]; };
uniform uint count;
void main(){uint i=gl_GlobalInvocationID.x;if(i<count)values[i]=map(points[i].xyz);}
''')

    def evaluate(points):
        p = np.zeros((len(points),4),np.float32); p[:,:3]=points
        a=ctx.buffer(p.tobytes()); b=ctx.buffer(reserve=len(p)*8)
        a.bind_to_storage_buffer(0); b.bind_to_storage_buffer(1)
        shader['count']=len(p); shader['uSpin']=0
        shader.run((len(p)+255)//256); ctx.memory_barrier()
        result=np.frombuffer(b.read(),np.float32).reshape(-1,2).copy()
        a.release(); b.release()
        return result

    xs=np.arange(-1.96,1.96+STEP,STEP,dtype=np.float32)
    ys=xs.copy(); zs=np.arange(-4.20,5.10+STEP,STEP,dtype=np.float32)
    offsets=np.array(list(itertools.product((0,1),repeat=3)),np.int32)
    # Consistent body diagonal prevents cracks between adjacent grid cells.
    tets=((0,1,3,7),(0,3,2,7),(0,2,6,7),(0,6,4,7),(0,4,5,7),(0,5,1,7))
    triangles=[]
    for start in range(0,len(zs)-1,10):
        zz=zs[start:min(start+11,len(zs))]
        grid=np.stack(np.meshgrid(xs,ys,zz,indexing='ij'),axis=-1)
        field=evaluate(grid.reshape(-1,3))[:,0].reshape(grid.shape[:-1])
        corners=np.stack([field[i:len(xs)-1+i,j:len(ys)-1+j,k:len(zz)-1+k]
                          for i,j,k in offsets],axis=-1)
        crossing=(corners.min(axis=-1)<0)&(corners.max(axis=-1)>=0)
        ids=np.argwhere(crossing)
        vals=corners[crossing]
        positions=grid[ids[:,0],ids[:,1],ids[:,2]][:,None,:]+offsets[None,:,:]*STEP
        for tet in tets:
            v=vals[:,tet]; p=positions[:,tet,:]
            mask=((v<0)*np.array([1,2,4,8])).sum(axis=1)
            for case in range(1,15):
                selected=mask==case
                if not selected.any(): continue
                vv=v[selected]; pp=p[selected]
                inside=[i for i in range(4) if case&(1<<i)]
                outside=[i for i in range(4) if not case&(1<<i)]
                def edge(i,j):
                    t=vv[:,i]/(vv[:,i]-vv[:,j])
                    return pp[:,i]+t[:,None]*(pp[:,j]-pp[:,i])
                if len(inside)==2:
                    a,b=inside; c,d=outside
                    ac,ad,bc,bd=edge(a,c),edge(a,d),edge(b,c),edge(b,d)
                    batch=[np.stack((ac,ad,bc),axis=1),np.stack((ad,bd,bc),axis=1)]
                else:
                    single=inside if len(inside)==1 else outside
                    other=outside if len(inside)==1 else inside
                    batch=[np.stack([edge(single[0],j) for j in other],axis=1)]
                direction=pp[:,outside,:].mean(axis=1)-pp[:,inside,:].mean(axis=1)
                for tri in batch:
                    flip=(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])*direction).sum(axis=1)<0
                    tri[flip]=tri[flip][:,[0,2,1],:]
                    triangles.append(tri.astype(np.float32))
        if start%100==0: print(f'Mesh sampling {start}/{len(zs)}',flush=True)
    tri=np.concatenate(triangles)
    vertices,inverse=np.unique(np.round(tri.reshape(-1,3),6),axis=0,return_inverse=True)
    faces=inverse.reshape(-1,3).astype(np.int32)
    valid=(faces[:,0]!=faces[:,1])&(faces[:,1]!=faces[:,2])&(faces[:,2]!=faces[:,0])
    faces=faces[valid]
    centers=vertices[faces].mean(axis=1)
    materials=np.concatenate([evaluate(centers[i:i+200000])[:,1] for i in range(0,len(centers),200000)])
    np.savez_compressed(OUT/'ship_mesh.npz',vertices=vertices,faces=faces,materials=materials.astype(np.int32))
    print(f'Saved {len(vertices):,} vertices / {len(faces):,} triangles',flush=True)


if __name__=='__main__': main()
