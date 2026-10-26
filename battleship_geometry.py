"""双刃战列舰 SDF 几何。+z 舰艏，尺寸兼容原视频镜头。

拉长的双楔形舰艏、嵌入式机械层、装甲覆板、炮塔、双环和四引擎。
大中细三级结构分开，细微面板缝和金属粗糙度由材质生成。
"""

BATTLESHIP_MAP = r"""
// 斜面楔形的保守距离；归一化斜面法线，避免步进穿过舰艏。
float armorWedge(vec3 p, float z0, float z1, float w0, float w1, float h0, float h1){
    float t = clamp((p.z-z0)/(z1-z0),0.0,1.0);
    float sx=(w1-w0)/(z1-z0), sy=(h1-h0)/(z1-z0);
    float dx=(abs(p.x)-mix(w0,w1,t))/sqrt(1.0+sx*sx);
    float dy=(abs(p.y)-mix(h0,h1,t))/sqrt(1.0+sy*sy);
    float bevel=(abs(p.x)+abs(p.y)-mix(w0+h0,w1+h1,t)+0.07)*0.60;
    return max(max(dx,dy),max(bevel,max(z0-p.z,p.z-z1)));
}

vec2 map(vec3 p){
    // 宽阔后舰体和贯穿龙骨；双舰艏之间留出可辨认的中央武器槽。
    float hull=armorWedge(p,-2.65,0.65,0.82,0.91,0.34,0.28);
    vec3 blade=vec3(abs(p.x)-0.60,p.y,p.z);
    hull=min(hull,armorWedge(blade,0.10,4.95,0.49,0.018,0.34,0.025));
    // 舷侧机械槽穿进主装甲而不是贴一条发光贴纸。
    float trench=sdBox(vec3(abs(p.x)-0.98,p.y+0.01,p.z+0.95),vec3(0.16,0.09,1.48));
    hull=max(hull,-trench);
    vec3 plate=vec3(abs(p.x)-0.60,p.y-0.15,p.z);
    float upper=armorWedge(plate,0.20,4.55,0.42,0.015,0.20,0.015);
    // 横向甲板块的浅缝是真实几何，近景有接触阴影。
    float joint=0.009-abs(mod(p.z+0.11,0.58)-0.29);
    upper=max(upper,joint);
    hull=min(hull,upper);
    hull=min(hull,armorWedge(p-vec3(0,0.34,0),-2.32,0.20,0.65,0.55,0.12,0.10));
    // 舷侧装甲带，略微错层，靠块面而不是密集零件制造尺度。
    float belt=armorWedge(vec3(abs(p.x)-0.87,p.y+0.18,p.z),-2.45,0.72,0.18,0.12,0.15,0.09);
    belt=max(belt,0.012-abs(mod(p.z,0.47)-0.235));
    hull=min(hull,belt);
    vec2 res=vec2(hull,1.0);
    float spine=sdBox(p-vec3(0,-0.04,1.53),vec3(0.13,0.12,1.35));
    res=opU(res,vec2(spine,4.0));
    float rail=sdBox(vec3(abs(p.x)-0.12,p.y-0.09,p.z-1.58),vec3(0.018,0.024,1.24));
    res=opU(res,vec2(rail,6.0));
    // 加速器横肋和中部舷侧机械层。
    float accelerator=sdBox(vec3(p.x,p.y-0.02,mod(p.z,0.17)-0.085),vec3(0.20,0.10,0.023));
    accelerator=max(accelerator,abs(p.z-1.55)-1.20);
    vec3 machinery=vec3(abs(p.x)-0.88,p.y+0.005,mod(p.z,0.24)-0.12);
    float machineryD=sdBox(machinery,vec3(0.075,0.07,0.085));
    machineryD=max(machineryD,abs(p.z+0.95)-1.42);
    res=opU(res,vec2(min(accelerator,machineryD),4.0));
    float piping=sdCapsule(vec3(abs(p.x),p.y,p.z),vec3(0.94,0.05,-2.25),vec3(0.94,0.05,0.45),0.017);
    res=opU(res,vec2(piping,3.0));
    // 低矮阶梯舰桥，避免过高上层建筑与曲率环相交。
    float bridge=armorWedge(p-vec3(0,0.53,0),-1.55,-0.70,0.38,0.28,0.14,0.11);
    bridge=min(bridge,armorWedge(p-vec3(0,0.72,0),-1.45,-0.92,0.25,0.19,0.09,0.045));
    bridge=min(bridge,armorWedge(p-vec3(0,0.85,0),-1.35,-1.10,0.13,0.08,0.065,0.025));
    res=opU(res,vec2(bridge,1.0));
    float glass=sdBox(p-vec3(0,0.74,-0.914),vec3(0.17,0.012,0.012));
    res=opU(res,vec2(glass,6.0));
    // 齐平传感器取代十字桅杆及两侧细天线，保持干净的舰桥轮廓。
    float sensor=armorWedge(p-vec3(0,0.905,0),-1.33,-1.12,0.10,0.065,0.018,0.012);
    res=opU(res,vec2(sensor,3.0));
    // 双舰艏的独立覆板：随楔面收窄并降低，接缝可产生真实阴影。
    float deckT=clamp((p.z-0.20)/4.35,0.0,1.0);
    float deckY=0.35-0.185*deckT;
    float deckW=mix(0.42,0.015,deckT);
    vec3 panelP=vec3(abs(p.x)-0.60,p.y-deckY-0.012,mod(p.z-0.20,0.43)-0.215);
    float plates=sdBox(panelP,vec3(max(0.012,deckW-0.045),0.018,0.197))-0.006;
    plates=max(plates,max(0.24-p.z,p.z-4.30));
    // 中心细槽把宽面板分成两列；局部保持大块留白。
    plates=max(plates,0.012-abs(abs(p.x)-0.60));
    res=opU(res,vec2(plates,1.0));
    float fasteners=sdBox(vec3(abs(abs(p.x)-0.60)-max(0.02,deckW-0.075),
        p.y-deckY-0.035,mod(p.z-0.245,0.43)-0.215),vec3(0.014,0.009,0.018));
    fasteners=max(fasteners,max(0.30-p.z,p.z-3.75));
    res=opU(res,vec2(fasteners,3.0));
    // 舰桥后方成组散热百叶，深色底座与亮边叶片分层。
    vec3 cooling=vec3(abs(p.x)-0.43,p.y-0.478,p.z+0.66);
    float bed=sdBox(cooling,vec3(0.105,0.018,0.36));
    res=opU(res,vec2(bed,4.0));
    float fins=sdBox(vec3(cooling.xy,mod(cooling.z,0.07)-0.035),vec3(0.09,0.026,0.012));
    fins=max(fins,abs(cooling.z)-0.34);
    res=opU(res,vec2(fins,3.0));
    // 四座斜切低轮廓双联装炮塔，前后分级，避免盒子堆叠。
    float gunZ=p.z>1.65?2.25:0.93;
    float gunY=p.z>1.65?0.28:0.39;
    vec3 gun=vec3(abs(p.x)-0.61,p.y-gunY,p.z-gunZ);
    float turret=armorWedge(gun,-0.22,0.20,0.16,0.11,0.09,0.055);
    res=opU(res,vec2(turret,1.0));
    vec3 barrel=vec3(abs(gun.x)-0.065,gun.y-0.01,gun.z);
    float barrels=sdCone(barrel,0.14,0.62,0.027,0.018);
    barrels=min(barrels,sdBox(barrel-vec3(0,0,0.58),vec3(0.032,0.027,0.065)));
    res=opU(res,vec2(barrels,3.0));
    // 舰艏装甲上的内嵌散热格栅：有限重复以保持步进稳定。
    vec3 vent=vec3(abs(p.x)-0.73,p.y-0.363,p.z-0.68);
    float vents=sdBox(vent,vec3(0.08,0.012,0.15));
    res=opU(res,vec2(vents,4.0));
    vec3 aftVent=vec3(abs(p.x)-0.48,p.y-0.48,p.z+2.04);
    res=opU(res,vec2(sdBox(aftVent,vec3(0.11,0.015,0.20)),4.0));
    // 双环沿用原来的半径，拉开轴向间距以强化战列舰比例。环加厚，支撑变成装甲梁。
    float rings=1e9,nodes=1e9,struts=1e9;
    for(int k=0;k<2;k++){
        float zc=k==0?RZ0:RZ1;
        vec3 q=p-vec3(0,0,zc);
        // 曲率环转动（前后环反向）：环体、装甲块和节点跟着转，支撑梁不转
        vec3 qs=q; qs.xy=rot2(-uSpin*(k==0?1.0:-1.0))*q.xy;
        vec2 band=abs(vec2(length(q.xy)-RR,q.z))-vec2(0.085,0.14);
        float rb=length(max(band,0.0))+min(max(band.x,band.y),0.0)-0.012;
        float groove=length(vec2(length(q.xy)-(RR-0.085),q.z))-0.035;
        rings=min(rings,max(rb,-groove));
        vec2 panel=sectorRep(qs.xy,16.0,0.0);
        nodes=min(nodes,sdBox(vec3(panel.x-RR-0.075,panel.y,q.z),vec3(0.045,0.20,0.105))-0.008);
        // 环面上的装甲块、暗色接缝和成对机械扣件。
        vec2 panels=sectorRep(qs.xy,32.0,0.0);
        float cover=sdBox(vec3(panels.x-RR,panels.y,abs(q.z)-0.153),vec3(0.075,0.11,0.012));
        nodes=min(nodes,cover);
        // 每个环段增加外沿锁扣与双层导轨，保留内圈充能槽。
        float latch=sdBox(vec3(panels.x-RR-0.088,panels.y,abs(q.z)-0.17),vec3(0.026,0.035,0.022));
        nodes=min(nodes,latch);
        float race=sdTorusZ(vec3(q.xy,abs(q.z)-0.115),RR+0.094,0.012);
        struts=min(struts,race);
        vec2 support=sectorRep(q.xy,4.0,PI/4.0);
        float beam=sdBox(vec3(support.x-1.15,support.y,q.z),vec3(0.51,0.045,0.075))-0.01;
        float slot=sdBox(vec3(support.x-1.19,support.y,q.z),vec3(0.31,0.021,0.12));
        struts=min(struts,max(beam,-slot));
        float footing=sdBox(vec3(support.x-0.73,support.y,q.z),vec3(0.13,0.085,0.14));
        struts=min(struts,footing);
    }
    res=opU(res,vec2(rings,2.0));
    res=opU(res,vec2(nodes,8.0));
    res=opU(res,vec2(struts,4.0));
    // 参考图的舰尾是向后延伸的装甲动力段，不能是四个贴在尾板上的方盒。
    // 中央脊柱逐级收束，两侧六台纵向发动机以装甲肩部与主舰体相连。
    float aft=armorWedge(p,-3.55,-2.05,0.40,0.81,0.24,0.34);
    aft=min(aft,armorWedge(p-vec3(0,0.33,0),-3.18,-1.95,0.30,0.63,0.10,0.13));
    float deckSplit=sdBox(p-vec3(0,0.42,-2.70),vec3(0.12,0.08,0.53));
    aft=max(aft,-deckSplit);
    res=opU(res,vec2(aft,1.0));
    float aftSpine=sdBox(p-vec3(0,0.365,-2.74),vec3(0.08,0.035,0.51));
    res=opU(res,vec2(aftSpine,4.0));
    // 三层错位动力舱：中层最长，上下两层略短，尾部轮廓不再整齐一刀切。
    float pods=1e9,mechanics=1e9,nozzles=1e9,glows=1e9;
    for(int k=0;k<3;k++){
        float yy=float(k-1)*0.34;
        float rear=k==1?-4.02:-3.74;
        vec3 ep=vec3(abs(p.x)-0.73,p.y-yy,p.z);
        float shell=armorWedge(ep,rear+0.15,-2.02,0.22,0.30,0.145,0.18);
        // 装甲只覆住发动机两端，中段内凹露出纵向传动杆及冷却管。
        float serviceBay=sdBox(vec3(abs(ep.x)-0.255,ep.y,p.z+2.88),vec3(0.085,0.09,0.37));
        shell=max(shell,-serviceBay);
        float armorJoint=0.009-abs(mod(p.z+0.02,0.42)-0.21);
        shell=max(shell,armorJoint);
        float exhaustBore=max(length(ep.xy)-0.124,abs(p.z-(rear+0.03))-0.26);
        shell=max(shell,-exhaustBore);
        pods=min(pods,shell);
        // 末端以八边形装甲包住圆形喷口，与舰艏的斜切块面呼应。
        vec3 nq=vec3(ep.xy,p.z-rear);
        float oct=max(max(abs(nq.x),abs(nq.y)),(abs(nq.x)+abs(nq.y))*0.7071)-0.164;
        float collar=max(oct,abs(nq.z-0.15)-0.20);
        float hole=max(length(nq.xy)-0.124,abs(nq.z-0.02)-0.24);
        nozzles=min(nozzles,max(collar,-hole));
        float rim=sdTorusZ(nq-vec3(0,0,-0.045),0.142,0.016);
        nozzles=min(nozzles,rim);
        float core=max(length(nq.xy)-0.111,abs(nq.z-0.15)-0.018);
        glows=min(glows,core);
        // 发动机纵向机械肋，避免旧版的整排巨大散热片。
        vec3 aq=vec3(abs(ep.x)-0.23,abs(ep.y)-0.085,p.z+2.90);
        mechanics=min(mechanics,sdBox(aq,vec3(0.012,0.014,0.43)));
        float tube=sdCapsule(ep,vec3(0.26,0,-3.28),vec3(0.26,0,-2.47),0.022);
        mechanics=min(mechanics,tube);
        // 检修区的冷却片和喷口内衬提供中等尺度机械细节。
        float radiator=sdBox(vec3(abs(ep.x)-0.268,ep.y,mod(p.z+2.88,0.085)-0.0425),vec3(0.016,0.067,0.015));
        radiator=max(radiator,abs(p.z+2.88)-0.31);
        mechanics=min(mechanics,radiator);
        vec2 vane=sectorRep(ep.xy,12.0,0.0);
        float liner=sdBox(vec3(vane.x-0.113,vane.y,p.z-rear-0.065),vec3(0.012,0.012,0.105));
        nozzles=min(nozzles,liner);
    }
    res=opU(res,vec2(pods,1.0));
    res=opU(res,vec2(mechanics,4.0));
    res=opU(res,vec2(nozzles,3.0));
    res=opU(res,vec2(glows,5.0));
    // 中央尾板有窄散热口与小型辅助推进器，而不是一整块平板。
    float grille=sdBox(vec3(p.x,p.y,mod(p.z+3.40,0.09)-0.045),vec3(0.27,0.17,0.015));
    grille=max(grille,abs(p.z+3.47)-0.10);
    res=opU(res,vec2(grille,4.0));
    vec3 aux=vec3(abs(p.x)-0.22,p.y,p.z+3.61);
    res=opU(res,vec2(sdTorusZ(aux,0.065,0.018),3.0));
    float auxGlow=max(length(aux.xy)-0.049,abs(aux.z-0.018)-0.012);
    res=opU(res,vec2(auxGlow,5.0));
    return res;
}
"""
