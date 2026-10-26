import json,numpy as np,base64
from scipy.ndimage import gaussian_filter,map_coordinates
from pathlib import Path
root=Path(__file__).resolve().parent
rng=np.random.default_rng(6021)
stars=json.loads((root.parent/'inspection.json').read_text())
pal=np.array([[.35,.62,1],[.6,.78,1],[1,.9,.72],[1,.65,.3],[1,.32,.14]])
data=[]
for o in stars:
 if o['name']=='etoile.6001':continue
 p=o['location'];r=np.hypot(p[0],p[1]);weights=np.array([12,20,36,24,8] if r<6 else [24,32,23,14,7]);c=pal[rng.choice(5,p=weights/weights.sum())]
 data.extend([*p,*c,max(o['dims'])])
nx,ny,nz=384,384,64
z,y,x=np.meshgrid(np.linspace(-2.5,2.5,nz,dtype=np.float32),np.linspace(-24,24,ny,dtype=np.float32),np.linspace(-24,24,nx,dtype=np.float32),indexing='ij')
r=np.hypot(x,y);th=np.arctan2(y,x);tw=th+.7*np.log(np.maximum(r,.15))
u=r*np.cos(tw);v=r*np.sin(tw)
def noise(scale,seed):
 rr=np.random.default_rng(seed);grid=gaussian_filter(rr.random((64,64,64),dtype=np.float32),.35);grid=(grid-grid.mean())/grid.std()*.16+.5
 coords=np.array([(z*.25*scale+23)%62,(v*scale+31)%62,(u*scale+31)%62])
 return np.clip(map_coordinates(grid,coords,order=1,mode='wrap'),0,1)
n=.44*noise(1.35,1)+.36*noise(4,2)+.2*noise(10,7);f=noise(8,3)
phase=4*th+9.3*np.log(np.maximum(r,.15))-2.078+(n-.5)*3.2
arm=.25+.75*((np.cos(phase)+1)/2)**1.35
taper=np.exp(-(r/20)**2)*(1-np.exp(-(r/1.1)**2))*np.maximum(1-(r/22)**6,0)**2
vert=np.exp(-(z/(.28+.55*np.exp(-(r/6)**2)))**2)
clump=np.maximum((n-.22)*3.2,0)**1.9*(.24+f**3*3.8)
gas=arm*taper*vert*clump
core=np.exp(-(r/3.3)**2-(z/.65)**2);disk=np.exp(-(r/11)**2-(z/.35)**2);pin=np.exp(-(r/.48)**2-(z/.3)**2)
em=gas*2.8+core*.42+disk*.06+pin*7
dust=((np.cos(phase+.65)+1)/2)**3*taper*np.exp(-(z/.4)**2)*np.maximum((.64-n)*3.3,0)**2
dust*=.4+noise(5,9)*1.8
density=gas*.1+dust*11
# Break emissive banks with fine opaque-looking dust creases as well as absorption.
em*=np.exp(-dust*1.7)
pink=np.clip((noise(2.6,21)-.61)*9,0,1)*np.clip((r-4)/4,0,1)
vol=np.stack([np.clip(np.log1p(em)/np.log(17),0,1),np.clip(density/4,0,1),pink],axis=-1)
enc=lambda a:base64.b64encode(a.tobytes()).decode()
(root/'data.js').write_text('const GALAXY={dims:[384,384,64],stars:"'+enc(np.array(data,dtype=np.float32))+'",volume:"'+enc((vol*255).astype(np.uint8))+'"};')
print('Wrote stars and 3D density texture',len(data)//7)
