# -*- coding: utf-8 -*-
"""双刃战列舰：适配现有视频的程序化三维模型。

几何在 battleship_geometry.py；+z 舰艏，约 8.1 单位长，双环半径 1.72。
保留原有相机、充能、曲率环、推进器和拉伸接口。材质编号：
1 钛灰装甲，2 曲率环，3 引擎外壳，4 深色结构，5 喷口，6 能量轨/舰桥窗，8 环装甲。
旧模型备份在 build/backup_before_battleship/ship_model.py。
"""
from battleship_geometry import BATTLESHIP_MAP


SHIP_MODEL_GLSL = r"""
uniform vec3 uPos; uniform mat3 uRot; uniform float uScale;
uniform vec3 uSun; uniform vec3 uSunCol; uniform vec3 uFill;
uniform float uRing; uniform float uPhase; uniform float uEngine; uniform float uAmt; uniform float uPixAng;
uniform vec3 uRingCol; uniform float uStretch;
uniform float uCharge; uniform float uChargeFlash;
uniform float uCountdown; uniform float uCountdownPhase;
uniform float uFlow;          // 充能：能量沿船体上的四条导管从引擎流向曲率环
uniform int uSS;              // 每像素采样数的平方根（1 或 2）
uniform float uSpin;         // 曲率环转角（弧度，前环正转、后环反转）
uniform float uWarpOn;       // 曲率场运行中：环的发光槽全亮，沿环流动的能量条纹
in vec2 vUV; out vec4 fragColor;

const float RZ0 = 0.25, RZ1 = -1.65, RR = 1.72;

float sdTorusZ(vec3 p, float R, float r){ vec2 q = vec2(length(p.xy) - R, p.z); return length(q) - r; }
float sdBox(vec3 p, vec3 b){ vec3 q = abs(p) - b; return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0); }
float smin(float a, float b, float k){ float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0); return mix(b, a, h) - k * h * (1.0 - h); }
float sdEllipsoid(vec3 p, vec3 r){ float k0 = length(p / r); float k1 = length(p / (r * r)); return k0 * (k0 - 1.0) / k1; }
float sdTaper(vec3 p, float z0, float z1, float r0, float r1){
    float h = clamp((p.z - z0) / (z1 - z0), 0.0, 1.0);
    vec3 q = vec3(p.xy, p.z - mix(z0, z1, h));
    return length(q) - mix(r0, r1, h);
}
float sdCone(vec3 p, float z0, float z1, float r0, float r1){
    float h = clamp((p.z - z0) / (z1 - z0), 0.0, 1.0);
    return max(length(p.xy) - mix(r0, r1, h), max(z0 - p.z, p.z - z1));
}
float sdCapsule(vec3 p, vec3 a, vec3 b, float r){ vec3 pa = p - a, ba = b - a; float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0); return length(pa - ba * h) - r; }
// 角向重复：把 xy 转到 n 等分扇区的中线上（x 为径向，y 为切向）
vec2 sectorRep(vec2 xy, float n, float offs){
    float sec = TAU / n;
    float a = mod(atan(xy.y, xy.x) + offs + sec * 0.5, sec) - sec * 0.5;
    return length(xy) * vec2(cos(a), sin(a));
}
vec2 opU(vec2 a, vec2 b){ return a.x < b.x ? a : b; }

__BATTLESHIP_MAP__

vec3 calcNormal(vec3 p){
    vec2 e = vec2(1.0, -1.0) * 0.0012;
    return normalize(e.xyy * map(p + e.xyy).x + e.yyx * map(p + e.yyx).x + e.yxy * map(p + e.yxy).x + e.xxx * map(p + e.xxx).x);
}
float calcAO(vec3 p, vec3 n){
    float occ = 0.0, sca = 1.0;
    for (int i = 0; i < 5; i++){
        float h = 0.015 + 0.07 * float(i);
        occ += (h - map(p + n * h).x) * sca; sca *= 0.75;
    }
    return clamp(1.0 - 2.8 * occ, 0.0, 1.0);
}
float softShadow(vec3 ro, vec3 rd){
    float res = 1.0, t = 0.02;
    for (int i = 0; i < 48; i++){
        float h = map(ro + rd * t).x;
        res = min(res, 14.0 * h / t);
        t += clamp(h, 0.01, 0.2);
        if (res < 0.005 || t > 6.0) break;
    }
    return clamp(res, 0.0, 1.0);
}
// 环境反射：深空的冷色渐变 + 一缕星云色，让金属面不再是一片死灰
vec3 envCol(vec3 r){
    float n = vnoise3(r * 2.5) * 0.6 + vnoise3(r * 6.0) * 0.4;
    vec3 c = mix(vec3(0.012, 0.016, 0.035), vec3(0.05, 0.07, 0.14), 0.5 + 0.5 * r.y);
    c += vec3(0.25, 0.1, 0.3) * pow(n, 3.0) * 0.5 + vec3(0.1, 0.2, 0.4) * pow(1.0 - abs(r.y), 6.0) * 0.15;
    return c;
}
float D_GGX(float nh, float a){ float a2 = a * a; float d = nh * nh * (a2 - 1.0) + 1.0; return a2 / (PI * d * d); }
float G_Smith(float nv, float nl, float a){ float k = a * 0.5; return nv / (nv * (1.0 - k) + k) * nl / (nl * (1.0 - k) + k); }

// 一条射线：返回预乘颜色 + 覆盖率
vec4 shade(vec2 uv){
    vec3 rdw = camRay(uv);
    vec3 ro = transpose(uRot) * (uEye - uPos) / uScale;
    vec3 rd = transpose(uRot) * rdw;
    ro.z /= uStretch; rd.z /= uStretch;           // 跃迁时沿船轴拉长（距离只会被低估，步进仍然安全）
    float A = dot(rd, rd);
    float b = dot(ro, rd), c = dot(ro, ro) - 5.2 * 5.2;
    float h = b * b - A * c;
    if (h < 0.0) return vec4(0);
    h = sqrt(h);
    float t = max((-b - h) / A, 0.0), tEnd = (-b + h) / A;
    float minRatio = 1e9, tm = t;
    vec2 hit = vec2(-1.0);
    for (int i = 0; i < 200; i++){
        vec2 d = map(ro + rd * t);
        float ratio = d.x / (t * uPixAng / float(uSS));
        if (ratio < minRatio){ minRatio = ratio; tm = t; }
        if (d.x < 0.00025 * t){ hit = vec2(t, d.y); break; }
        t += d.x * 0.9;
        if (t > tEnd) break;
    }
    float cov = hit.x > 0.0 ? 1.0 : clamp(1.0 - minRatio / 1.2, 0.0, 1.0);
    if (cov <= 0.0) return vec4(0);
    float tt = hit.x > 0.0 ? hit.x : tm;
    vec3 p = ro + rd * tt;
    float mat = hit.x > 0.0 ? hit.y : map(p).y;
    vec3 n = calcNormal(p);
    vec3 V = -normalize(rd);
    vec3 L = normalize(transpose(uRot) * uSun);
    float foot = tt * uPixAng;                      // 这一像素在模型表面上的大小（用来给细纹理去锯齿）
    float ang = atan(p.y, p.x);
    float rr = length(p.xy);
    float aftRing=step(abs(p.z-RZ1),abs(p.z-RZ0));
    // 环上的花纹（充能格、接缝、节点）跟着环一起转：用环自身坐标系里的角度
    float angR = ang - uSpin * mix(1.0, -1.0, aftRing);
    vec2 pR = rot2(-uSpin * mix(1.0, -1.0, aftRing)) * p.xy;
    // 前环从顶部双向展开；后环从底部双向展开并延迟半拍。
    // 延迟在归一化进度内重映射，保证两环到 100% 时同时闭合。
    float sector=mod(floor((PI*0.5-angR)*32.0/TAU+0.5),32.0);
    float localSector=mod(sector+16.0*aftRing,32.0);
    float rank=min(localSector,32.0-localSector);
    float progress=mix(uCharge,clamp((uCharge-0.0375)/0.9625,0.0,1.0),aftRing);
    float threshold=(rank+1.0)/17.0;
    float charged=step(threshold,progress+0.00001);
    float ignition=charged*exp(-max(progress-threshold,0.0)/0.018)*step(uCharge,0.999);
    float cell=abs(fract(angR*32.0/TAU+0.5)-0.5);
    float segmentMask=1.0-smoothstep(0.37,0.43,cell);
    float chargeLight=(charged+0.4*ignition)*(1.0+1.4*uChargeFlash);
    // 三格为一组，依倒数熄灭 1/3、2/3、全部；每拍末恢复全亮。
    if (uCountdown > 0.5){
        float group=mod(floor(sector/3.0),3.0);
        float dark=1.0-step(3.5-uCountdown,group);
        float restore=smoothstep(0.65,0.9,uCountdownPhase);
        chargeLight*=mix(1.0, mix(0.04,1.0,restore),dark);
    }
    vec3 base; float rough; float metal; vec3 emit = vec3(0);
    if (mat < 1.5){
        // 大块钛灰装甲；平面分缝比原来的圆柱展开贴图更适合战列舰。
        vec2 grid=vec2(p.z*4.0,(abs(n.y)>0.6?p.x:p.y)*7.0);
        grid.x+=floor(grid.y)*0.37;
        vec2 cell=abs(fract(grid)-0.5);
        float seam=smoothstep(0.475,0.495,max(cell.x,cell.y));
        float fade=1.0-smoothstep(0.008,0.035,foot);
        float panel=hash12(floor(grid));
        base=vec3(0.14,0.17,0.20)*(0.78+0.35*panel);
        base*=1.0-0.50*seam*fade;
        // 次级检修盖、螺栓和涂装色块只占小面积，避免大网格的玩具感。
        vec2 local=fract(grid);
        float hatch=step(0.67,local.x)*step(local.x,0.93)*step(0.22,local.y)*step(local.y,0.72)*step(0.65,panel);
        base*=1.0-0.20*hatch*fade;
        float bolts=(1.0-smoothstep(0.022,0.045,length(local-vec2(0.09,0.12))))*fade;
        base+=vec3(0.055)*bolts;
        float grain=vnoise3(p*140.0);
        rough=0.36+0.14*panel+0.08*grain; metal=0.55;
        float windows=step(abs(p.y+0.12),0.008)*step(0.78,fract(p.z*28.0))*step(0.40,hash12(vec2(floor(p.z*28.0),0.0)));
        emit+=vec3(0.70,0.85,1.0)*windows*0.38;
        float duct=exp(-pow((abs(p.x)-0.73)/0.022,2.0))*step(-2.4,p.z)*step(p.z,0.5);
        float pulse=pow(0.5+0.5*sin(p.z*9.0-uPhase*1.5),6.0);
        emit+=uRingCol*uFlow*duct*(0.25+1.5*pulse);
    } else if (mat < 2.5){
        // 曲率环：深色拉丝金属；内侧凹槽里是流动的能量，外侧两道细发光缝
        base = vec3(0.16, 0.17, 0.19); rough = 0.35 + 0.12 * vnoise2(vec2(ang * 120.0, p.z * 4.0)); metal = 0.75;
        float ringSeam=1.0-smoothstep(0.008,0.025,abs(fract(angR*32.0/TAU)-0.5));
        base*=1.0-ringSeam*0.55;
        float zl = min(abs(p.z - RZ0), abs(p.z - RZ1));
        float inGroove = smoothstep(RR - 0.03, RR - 0.07, rr) * step(zl, 0.06);
        float flow = 0.5 + 0.5 * sin(ang * 22.0 - uPhase) * sin(ang * 7.0 + uPhase * 0.43);
        // 进度藏在装甲边缘的双道窄槽中，保持整块金属面不发光。
        float outerBand=step(RR+0.045,rr)*(1.0-smoothstep(0.004,0.009,abs(zl-0.045)));
        emit += uRingCol * uRing * inGroove * (0.15+uCharge*0.40) * (0.6 + flow*0.3)*(1.0+0.8*uChargeFlash);
        emit += vec3(0.18,0.52,0.8)*outerBand*segmentMask*chargeLight*1.25;
        // 曲率场运行：发光槽全亮，外缘细缝上有沿环飞驰的能量条纹（转速远快于环本身）
        float streak = pow(0.5 + 0.5 * sin(angR * 12.0 - uPhase * 3.0), 10.0);
        emit += uWarpOn * (vec3(0.45, 0.85, 1.0) * inGroove * (1.4 + 2.0 * streak) + vec3(0.6, 0.9, 1.0) * outerBand * (0.6 + 2.5 * streak));
    } else if (mat < 3.5){
        base=vec3(0.16,0.19,0.23); rough=0.36; metal=0.7;
    } else if (mat < 4.5){
        float rib=step(0.48,fract(p.z*38.0));
        base = vec3(0.055, 0.065, 0.075) * (0.6 + 0.6 * rib); rough = 0.45; metal = 0.65;
    } else if (mat < 5.5){
        base=vec3(0.04,0.12,0.2); rough=0.3; metal=0.4;
        emit=vec3(0.25,0.65,1.0)*(0.2+3.0*uEngine*uEngine);
    } else if (mat < 7.5){
        base=vec3(0.025,0.07,0.10); rough=0.2; metal=0.65;
        emit=uRingCol*(0.25+0.6*uFlow);
    } else {
        // 环上的发射节点：深色，顶端一点亮光；左红右绿航行灯，顶部白色频闪
        base = vec3(0.1, 0.105, 0.115); rough = 0.35; metal = 0.85;
        vec2 q24 = sectorRep(pR, 16.0, 0.0);
        float zc = abs(p.z - RZ0) < abs(p.z - RZ1) ? RZ0 : RZ1;
        float tip = smoothstep(RR + 0.1, RR + 0.115, rr);
        float dot_ = smoothstep(0.022, 0.012, length(vec2(q24.y, p.z - zc) * vec2(1.0, 0.6)));
        float zl=abs(p.z-zc);
        float faceBand=step(0.145,zl)*(1.0-smoothstep(0.003,0.008,abs(rr-(RR+0.052))));
        float outerBand=step(RR+0.095,rr)*(1.0-smoothstep(0.004,0.009,abs(zl-0.045)));
        emit += vec3(0.18,0.52,0.8)*segmentMask*(faceBand+outerBand)*chargeLight*1.25;
        emit += uRingCol * tip * dot_ * (chargeLight*0.12 + uWarpOn * 2.5);
        float side = step(0.96, abs(p.x) / rr) * tip * dot_;
        emit += (p.x < 0.0 ? vec3(1.0, 0.1, 0.05) : vec3(0.1, 1.0, 0.3)) * side * 4.0;
    }
    // ---- 光照
    float a = rough * rough;
    vec3 H2 = normalize(L + V);
    float nl = max(dot(n, L), 0.0), nv = max(dot(n, V), 1e-3), nh = max(dot(n, H2), 0.0), vh = max(dot(V, H2), 0.0);
    vec3 F0 = mix(vec3(0.04), base, metal);
    vec3 F = F0 + (1.0 - F0) * pow(1.0 - vh, 5.0);
    float sh = nl > 0.0 ? softShadow(p + n * 0.006, L) : 0.0;
    float ao = calcAO(p, n);
    vec3 spec = D_GGX(nh, max(a, 0.002)) * G_Smith(nv, nl, a) * F / (4.0 * nv * max(nl, 1e-3) + 1e-4);
    vec3 diff = base * (1.0 - metal) / PI * 3.0;
    vec3 col = (diff + spec) * nl * uSunCol * sh;
    vec3 Fv = F0 + (1.0 - F0) * pow(1.0 - nv, 5.0);
    vec3 r = reflect(-V, n);
    col += envCol(r) * Fv * (1.0 - 0.6 * rough) * ao * 2.0;
    col += diff * uFill * (0.55 + 0.45 * n.y) * ao * 0.9;
    col += diff * vec3(0.5, 0.45, 0.42) * max(dot(n, -L), 0.0) * ao * 0.12;     // 背光侧一点暖色反光
    // 曲率环把船体照亮（距离两道环越近越亮）
    float selfLit = (mat > 1.5 && mat < 2.5) || mat > 7.5 ? 0.0 : 1.0;    // 环和环上的节点不被自己照亮
    float rl = exp(-length(vec2(rr - RR, min(abs(p.z - RZ0), abs(p.z - RZ1)))) * 1.6) * uRing * selfLit;
    col += (diff + F0 * 0.5) * uRingCol * rl * 0.35 * ao;
    col += emit;
    return vec4(col * cov, cov);
}

void main(){
    if (uAmt <= 0.0){ fragColor = vec4(0); return; }
    vec4 acc = vec4(0);
    for (int i = 0; i < 2; i++) for (int j = 0; j < 2; j++){
        if (i >= uSS || j >= uSS) continue;
        vec2 o = (vec2(float(i), float(j)) + 0.5) / float(uSS) - 0.5;
        acc += shade(vUV + o / uRes);
    }
    acc /= float(uSS * uSS);
    fragColor = acc * uAmt;
}
"""

SHIP_MODEL_GLSL = SHIP_MODEL_GLSL.replace("__BATTLESHIP_MAP__", BATTLESHIP_MAP)
