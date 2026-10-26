"""程序化恒星：解析光球、对流元胞、纤维黑子及临边磁环。

star(e, cam, center, radius, color, bright, corona, prom, seed) 与旧接口一致。
granules 控制每单位球面元胞密度，loop_height 控制主日珥高度/半径，
loop_angle 为三维磁环的世界切向旋转（弧度，2.7 为默认朝向），spots 控制黑子强度。
blue=1 使用连续湍流光球及蓝巨星配色，granules 此时控制细纹尺度。
默认 0 保留暖色元胞。只使用场景时间。
"""
import math
import wfx


STAR_FS = wfx.CAM_GLSL + r"""
uniform vec3 uC, uCol;
uniform float uR, uBright, uCorona, uProm, uSeed, uPixAng;
uniform float uGranules, uLoopHeight, uLoopAngle, uSpots, uBlue;
in vec2 vUV; out vec4 fragColor;

// 表面纹理全部采样球面世界位置；像素足迹包含掠射透视伸长。
float cells(vec3 p){
    vec3 ip=floor(p), fp=fract(p);
    float a=10.0,b=10.0,id=0.0;
    for(int x=-1;x<=1;x++) for(int y=-1;y<=1;y++) for(int z=-1;z<=1;z++){
        vec3 g=vec3(x,y,z), h=hash33(ip+g);
        vec3 d=g+0.5+0.30*sin(h*TAU+uTime*0.21)-fp;
        float v=dot(d,d);
        if(v<a){b=a;a=v;id=h.x;} else b=min(b,v);
    }
    return 0.38+0.51*exp(-a*3.8)+0.18*smoothstep(0.01,0.12,sqrt(b)-sqrt(a))+0.22*id;
}
float filteredNoise(vec3 n,float scale,float fp){
    float lod=1.0-smoothstep(0.15,0.65,fp*scale);
    if(lod<0.001) return 0.5;
    return mix(0.5,vnoise3(n*scale+uSeed*13.0+vec3(0,uTime*0.025,0)),lod);
}
// 连续域扭曲取代径向元胞亮核；三维采样让纹理固定在球面上，无经纬接缝。
float plasmaHeat(vec3 n,float fp){
    vec3 drift=vec3(0.013,-0.009,0.006)*uTime;
    vec3 p=n*240.0+uSeed*13.0+drift;
    vec3 bend=vec3(vnoise3(p),vnoise3(p+17.3),vnoise3(p+39.7))-0.5;
    vec3 q=n+bend*0.003;
    // 扭曲后的实际像素足迹也参与过滤，防止近景细纹在地平线闪烁。
    float qfp=max(fp,max(length(dFdx(q)),length(dFdy(q))));
    vec3 flow=q*vec3(0.8,1.3,1.0);
    float flowfp=qfp*1.3;
    float large=filteredNoise(q,110.0,qfp);
    // 多频段共同构成热场，最高频在近处仍有实际对比，不用大团柔噪声冒充细节。
    float field=0.24*filteredNoise(flow,480.0,flowfp)
               +0.28*filteredNoise(flow+0.017,1300.0,flowfp)
               +0.23*filteredNoise(q-0.031,3000.0,qfp)
               +0.15*filteredNoise(q+0.059,6500.0,qfp)
               +0.10*filteredNoise(q-0.083,max(14000.0,uGranules*9.0),qfp);
    float resolved=1.0-smoothstep(0.12,0.7,flowfp*480.0);
    float hot=smoothstep(0.22,0.78,field);
    // 窄的等温带切出不规则亮丝，按热场导数展宽并随远景淡出，避免闪烁。
    float width=max(0.018,fwidth(field)*1.2);
    float threads=1.0-smoothstep(width,width*2.5,abs(field-0.52));
    return clamp(0.60+0.12*(large-0.5)
                 +1.10*(hot-0.5)+resolved*0.045*(threads-0.3),0.0,1.0);
}
void main(){
    vec3 rd=camRay(vUV), ro=(uEye-uC)/uR;
    float b=dot(ro,rd), c=dot(ro,ro)-1.0, disc=b*b-c;
    float impact=length(ro-rd*b), aa=max(fwidth(impact),1e-6);
    float hit=-b-sqrt(max(disc,0.0));
    float cover=(b<0.0 && hit>0.0)?1.0-smoothstep(1.0-aa*0.5,1.0+aa*0.5,impact):0.0;
    float limit=cover>0.5?hit:1e5;
    vec3 n=normalize(ro+rd*max(hit,0.0));
    float fp=max(length(dFdx(n)),length(dFdy(n)));
    vec3 col=vec3(0);
    if(cover>0.0){
        float mu=max(dot(n,-rd),0.0);
        float broad=filteredNoise(n,38.0,fp);
        float network=filteredNoise(n,160.0,fp);
        float middle=filteredNoise(n,480.0,fp);
        float lod=1.0-smoothstep(0.14,0.7,fp*uGranules);
        float g=0.80;
        if(lod>0.001 && uBlue<1.0){
            vec3 p=n*uGranules+uSeed*9.0;
            p+=0.34*vec3(vnoise3(p*1.5),vnoise3(p*1.5+17.0),vnoise3(p*1.5+39.0));
            g=mix(g,cells(p),lod);
        }
        float heat=clamp(0.38+0.52*g+0.34*(broad-0.5)+0.33*(network-0.5)+0.22*(middle-0.5),0.0,1.0);
        if(uBlue>0.0) heat=mix(heat,plasmaHeat(n,fp),uBlue);
        // 自发光由局部温度控制，临边律只压地平线，避免贴面时全盘变成暗青色。
        float limb=0.27+0.73*pow(mu,0.42);
        vec3 blueTint=mix(vec3(0.13,0.19,0.65),vec3(0.34,0.54,1.0),smoothstep(0.38,1.0,heat));
        blueTint=mix(vec3(0.10,0.10,0.50),blueTint,smoothstep(0.0,0.20,mu));
        vec3 tint=mix(pow(uCol,vec3(1.3)),blueTint,uBlue);
        float intensity=(0.58+1.15*heat)*limb*(uBright/0.5);
        col=tint*intensity;
        float fac=smoothstep(0.57,0.79,network)*(1.0-mu);
        col+=mix(uCol,vec3(0.26,0.45,1.0),uBlue)*fac*0.13*uBright;
        // 上半球活动区朝向最终飞船位置，半影纤维同样按像素过滤。
        for(int j=0;j<2;j++){
            vec3 sn=normalize(vec3(-0.033+float(j)*0.023,1.0,0.075+float(j)*0.012));
            vec3 sx=normalize(cross(sn,vec3(0,0,1))),sy=cross(sn,sx);
            vec2 p=vec2(dot(n-sn,sx),dot(n-sn,sy));
            float sz=0.012-float(j)*0.003, d=length(p)/sz, a=atan(p.y,p.x);
            float wav=0.05*sin(a*7.0)+0.03*sin(a*13.0);
            float pen=1.0-smoothstep(0.75+wav,1.08+wav,d);
            float umb=1.0-smoothstep(0.34+wav,0.48+wav,d);
            float fiber=sin(a*43.0+d*12.0)*(1.0-smoothstep(0.03,0.12,fp/sz));
            col*=1.0-uSpots*pen*(0.50+0.1*fiber);
            col=mix(col,tint*0.055,umb*uSpots);
        }
        col*=cover;
    }
    // 有限大气壳内积分，起点夹到镜头；不以 tc 的正负截断天空。
    float outer=1.14, dh=b*b-(dot(ro,ro)-outer*outer);
    if(dh>0.0){
        float start=max(0.0,-b-sqrt(dh)), end=min(-b+sqrt(dh),limit);
        if(end>start){
            float sum=0.0, hair=0.0, baseGlow=0.0;
            for(int i=0;i<48;i++){
                float f=(float(i)+0.5)/48.0;
                // 二次分配把更多采样放在镜头附近，无随机抖动便于静帧/跳帧验收。
                float t=start+(end-start)*f*f, dt=(end-start)*2.0*f/48.0;
                vec3 p=ro+rd*t;
                float h=max(length(p)-1.0,0.0);
                vec3 radial=normalize(p);
                // 径向拉长的密度通道形成不均匀的日冕流；镜头处在壳内也连续。
                float streams=0.55+0.9*vnoise3(radial*65.0+uSeed+vec3(0,uTime*0.015,0));
                sum+=exp(-h/0.014)*streams*dt;
                baseGlow+=exp(-h/0.0035)*dt;
                if(h<0.012){
                    vec3 sn=normalize(p);
                    float footprint=max(t*uPixAng*950.0,0.001);
                    float mask=0.0;
                    if(footprint<0.7){
                        vec3 q=sn*950.0+uSeed;
                        float fil=vnoise3(q);
                        float height=0.002+0.006*vnoise3(sn*170.0+uSeed);
                        mask=smoothstep(0.63,0.85,fil)*(1.0-smoothstep(height*0.5,height,h));
                        mask*=1.0-smoothstep(0.15,0.7,footprint);
                    }
                    hair+=mask*exp(-h/0.007)*dt;
                }
            }
            vec3 atm=mix(vec3(1.0,0.22,0.07),vec3(0.22,0.16,1.0),uBlue);
            vec3 baseTint=mix(vec3(1.0,0.13,0.08),vec3(0.16,0.43,1.0),uBlue);
            col+=atm*sum*9.0*uCorona*uBright;
            col+=baseTint*(baseGlow*3.5+hair*5.0)*uBright;
        }
    }
    // 固定在球面上的磁环平面。椭圆隐式距离投影到射线法面，避免逐像素遍历折线段。
    if(uProm>0.001){
        for(int k=0;k<2;k++){
            vec3 anchor=normalize(k==0?vec3(0.23,1.0,0.43):vec3(-0.12,1.0,0.33));
            vec3 tx=normalize(cross(vec3(0,0,1),anchor)), tz=cross(anchor,tx);
            vec3 tangent=tx*cos(uLoopAngle-2.7)+tz*sin(uLoopAngle-2.7);
            vec3 side=cross(anchor,tangent);
            float denom=dot(rd,side);
            if(abs(denom)>0.0001){
                float glow=0.0;
                for(int j=0;j<4;j++){
                    float f=float(j)/3.0;
                    vec3 origin=anchor*0.998+side*(f-0.5)*0.004;
                    float t=dot(origin-ro,side)/denom;
                    if(t>0.0 && t<limit){
                        vec3 p=ro+rd*t-origin;
                        float width=0.060+0.019*f;
                        float height=uLoopHeight*(k==0?0.36:0.25)*(0.82+0.18*f);
                        vec2 q=vec2(dot(p,tangent)/width,dot(p,anchor)/height);
                        float phase=atan(q.y,q.x);
                        if(q.y>0.0 && length(q)<1.4){
                            float resolved=1.0-smoothstep(0.15,0.65,t*uPixAng*30.0/height);
                            float eddy=mix(0.45,fbm2(vec2(phase*5.0-uTime*0.15,f*9.0+uSeed),3),resolved);
                            float wobble=0.075*sin(phase*5.0+f*9.0+uTime*0.18)
                                        +0.11*(eddy-0.45);
                            float implicit=length(q)-1.0-wobble;
                            vec3 grad=normalize(tangent*q.x/width+anchor*q.y/height);
                            float d=abs(implicit)/max(length(q/vec2(width,height)),0.01);
                            d*=abs(denom)/sqrt(denom*denom+pow(dot(grad,rd),2.0));
                            // 宽的湍流鞘内再分裂出细丝；不再绘制等宽、等亮的闭合电线。
                            float thick=0.0013+eddy*0.0022, px=max(thick,t*uPixAng*0.65);
                            if(d<px*3.0){
                                float flow=mix(0.45,fbm2(vec2(phase*18.0-uTime*0.65,f*17.0+implicit*43.0+uSeed),4),resolved);
                                float threads=smoothstep(0.28,0.68,flow);
                                float breaks=smoothstep(0.30,0.62,eddy);
                                glow+=exp(-d*d/(px*px))*thick/px*threads*breaks;
                            }
                        }
                    }
                }
                col+=mix(vec3(1.0,0.25,0.06),vec3(0.13,0.30,1.0),uBlue)*glow*uProm*uBright*2.2;
            }
        }
    }
    fragColor=vec4(col,cover);
}
"""

def star(e, cam, center, radius, color=(1.0, 0.72, 0.38), bright=0.75,
         corona=1.0, prom=1.0, seed=1.0, granules=240.0,
         loop_height=0.20, loop_angle=2.70, spots=1.0, blue=0.0):
    """绘制恒星，返回与旧模型一致的投影半径（像素）。"""
    q = cam.project(tuple(center))
    # 星心在镜头背后时 project 返回 None，但镜头贴着的巨大恒星（视半径几十度）盘面照样可能占掉大半个画面，必须照画；
    # 视半径小的（擦身而过的恒星）星心在身后时整个都在画面外，跳过（照画的话着色器偶尔算出单个 NaN 像素，被泛光扩成黑块）
    dist = math.dist(cam.eye, center)
    ang = math.asin(min(radius / max(dist, 1e-6), 0.999))
    if q is None:
        if ang < 0.5:
            return 0.0
        rpx = cam.pix * math.tan(ang)
    else:
        rpx = radius / q[2] * cam.pix
    if q is not None and rpx < 2.5:
        wfx.bodies(e, [(q[0], q[1], max(rpx, 1.2), min(3.0, 0.6+rpx)*bright*0.6, color, 0.8)])
        return rpx
    u = wfx.cam_uniforms(cam)
    u.update(uC=tuple(center), uR=float(radius), uCol=tuple(color),
             uBright=float(bright), uCorona=float(corona), uProm=float(prom),
             uSeed=float(seed), uGranules=float(granules), uLoopHeight=float(loop_height),
             uLoopAngle=float(loop_angle), uSpots=float(spots), uBlue=float(blue))
    e.draw_fs("wd_star_model", STAR_FS, u, blend="over")
    return rpx

