// 着色器由 export_galaxy_web.py 从影片源码导出，网页只负责相机、上传和显示。
'use strict';
const canvas=document.getElementById('space');
const status=document.getElementById('status');
const $=id=>document.getElementById(id);
const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
const header='#version 300 es\nprecision highp float;\n';
const fullscreen=header+`out vec2 vUV;void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);vUV=p;gl_Position=vec4(p*2.-1.,0,1);}`;
const identity=new Float32Array([1,0,0,0,1,0,0,0,1]);
const sun=[11*Math.cos(2.53),11*Math.sin(2.53),0];

async function start(){
 if(!gl)throw Error('浏览器未启用 WebGL2，请用支持 WebGL2 的浏览器打开。');
 if(!gl.getExtension('EXT_color_buffer_float'))throw Error('此浏览器不支持 HDR 渲染目标。');
 const root='build/galaxy/web/';
 async function fetchFile(name,json=false){const r=await fetch(root+name);if(!r.ok)throw Error(name+' 加载失败：'+r.status);return json?r.json():r.arrayBuffer()}
 const [source,stars,volume,noise,mist,dither]=await Promise.all([
   fetchFile('shaders.json',true),...['stars.bin','volume.bin','noise.bin','mist.bin','dither.bin'].map(x=>fetchFile(x))]);
 function program(v,f,attributes=[]){
   const p=gl.createProgram();
   for(const [type,text] of [[gl.VERTEX_SHADER,v],[gl.FRAGMENT_SHADER,f]]){
     const s=gl.createShader(type);gl.shaderSource(s,text);gl.compileShader(s);
     if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));
     gl.attachShader(p,s);gl.deleteShader(s);
   }
   attributes.forEach((name,i)=>gl.bindAttribLocation(p,i,name));gl.linkProgram(p);
   if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(p));
   return {p,locations:new Map()};
 }
 function loc(p,name){if(!p.locations.has(name))p.locations.set(name,gl.getUniformLocation(p.p,name));return p.locations.get(name)}
 function f(p,n,x){gl.uniform1f(loc(p,n),x)}
 function vec(p,n,x){gl.uniform3fv(loc(p,n),x)}
 const star=program(source.STAR_VS,source.STAR_FS,['in_pos','in_col','in_size']);
 const dust=program(fullscreen,source.CLOUD_FS);
 const tiny=program(source.MIST_STAR_VS,source.MIST_STAR_FS,['in_pos','in_energy']);
 // 与影片相同的 ACES、gamma、黑位及 S 曲线；网页不添加逐帧胶片噪点。
 const post=program(fullscreen,header+`in vec2 vUV;out vec4 fragColor;uniform sampler2D image;
 void main(){vec3 c=texture(image,vUV).rgb;c=clamp((c*(2.51*c+.03))/(c*(2.43*c+.59)+.14),0.,1.);
 c=pow(max(c,vec3(0)),vec3(1./2.2));c=max(c-.035,0.)/.965;c=mix(c,c*c*(3.-2.*c),.22);
 float lum=dot(c,vec3(.2126,.7152,.0722));c=mix(vec3(lum),c,1.12);fragColor=vec4(max(c,vec3(0)),1);}`);
 const empty=gl.createVertexArray();
 function points(data,stride,sizes){
   const vao=gl.createVertexArray();gl.bindVertexArray(vao);
   const buf=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buf);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);
   let offset=0;sizes.forEach((size,i)=>{gl.enableVertexAttribArray(i);gl.vertexAttribPointer(i,size,gl.FLOAT,false,stride*4,offset*4);offset+=size});
   gl.bindVertexArray(null);return vao;
 }
 const starVAO=points(new Float32Array(stars),7,[3,3,1]);
 const mistVAO=points(new Float32Array(mist),4,[3,1]);
 function texture3D(unit,dims,internal,format,type,data,repeat){
   const t=gl.createTexture();gl.activeTexture(gl.TEXTURE0+unit);gl.bindTexture(gl.TEXTURE_3D,t);
   gl.pixelStorei(gl.UNPACK_ALIGNMENT,1);gl.texImage3D(gl.TEXTURE_3D,0,internal,...dims,0,format,type,data);
   for(const n of [gl.TEXTURE_MIN_FILTER,gl.TEXTURE_MAG_FILTER])gl.texParameteri(gl.TEXTURE_3D,n,gl.LINEAR);
   for(const n of [gl.TEXTURE_WRAP_S,gl.TEXTURE_WRAP_T,gl.TEXTURE_WRAP_R])gl.texParameteri(gl.TEXTURE_3D,n,repeat?gl.REPEAT:gl.CLAMP_TO_EDGE);
   return t;
 }
 const field=texture3D(0,source.dims,gl.RGB8,gl.RGB,gl.UNSIGNED_BYTE,new Uint8Array(volume),false);
 // 半精度浮点纹理支持 WebGL2 核心线性过滤，避免依赖 float-linear 扩展。
 const detail=texture3D(1,[128,128,128],gl.R16F,gl.RED,gl.HALF_FLOAT,new Uint16Array(noise),true);
 const jitter=gl.createTexture();gl.activeTexture(gl.TEXTURE2);gl.bindTexture(gl.TEXTURE_2D,jitter);
 gl.texImage2D(gl.TEXTURE_2D,0,gl.R32F,128,128,0,gl.RED,gl.FLOAT,new Float32Array(dither));
 for(const n of [gl.TEXTURE_MIN_FILTER,gl.TEXTURE_MAG_FILTER])gl.texParameteri(gl.TEXTURE_2D,n,gl.NEAREST);
 const hdr=gl.createTexture(),target=gl.createFramebuffer();
 let az=-1.08,el=.7,dist=61,center=[0,0,0],inside=false,dirty=true,last=0;
 const pointers=new Map();let pinch=0;
 function resize(){
   const maxHeight=Number($('quality').value),ratio=Math.min(devicePixelRatio,1920/canvas.clientWidth,maxHeight/canvas.clientHeight);
   canvas.width=Math.max(1,Math.round(canvas.clientWidth*ratio));canvas.height=Math.max(1,Math.round(canvas.clientHeight*ratio));
   gl.activeTexture(gl.TEXTURE3);gl.bindTexture(gl.TEXTURE_2D,hdr);
   gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA16F,canvas.width,canvas.height,0,gl.RGBA,gl.HALF_FLOAT,null);
   for(const n of [gl.TEXTURE_MIN_FILTER,gl.TEXTURE_MAG_FILTER])gl.texParameteri(gl.TEXTURE_2D,n,gl.NEAREST);
   gl.bindFramebuffer(gl.FRAMEBUFFER,target);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,hdr,0);
   if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw Error('HDR 缓冲创建失败');
   gl.bindFramebuffer(gl.FRAMEBUFFER,null);dirty=true;
 }
 function setView(kind){
   inside=kind==='inside';center=inside?[...sun]:[0,0,0];
   az=inside?2.53:-1.08;el=kind==='top'?1.56:kind==='side'?.05:inside?.02:.7;
   dist=inside?.08:kind==='close'?27:61;dirty=true;
   document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===kind)));
 }
 document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>setView(b.dataset.view));
 $('reset').onclick=()=>{setView('oblique');$('cloud').value=$('star').value=1;$('cv').value=$('sv').value='1.0';$('spin').checked=false};
 for(const [id,out] of [['cloud','cv'],['star','sv']])$(id).oninput=e=>{$(out).value=Number(e.target.value).toFixed(1);dirty=true};
 $('quality').onchange=resize;$('spin').onchange=()=>dirty=true;
 const zoom=scale=>{dist=Math.max(inside?.015:.2,Math.min(180,dist*scale));dirty=true};
 canvas.onpointerdown=e=>{canvas.focus();canvas.setPointerCapture(e.pointerId);pointers.set(e.pointerId,[e.clientX,e.clientY]);pinch=0};
 canvas.onpointermove=e=>{
   if(!pointers.has(e.pointerId))return;
   const prev=pointers.get(e.pointerId);pointers.set(e.pointerId,[e.clientX,e.clientY]);
   if(pointers.size===1){az-=(e.clientX-prev[0])*.006;el=Math.max(-1.56,Math.min(1.56,el+(e.clientY-prev[1])*.006))}
   else{const p=[...pointers.values()],d=Math.hypot(p[0][0]-p[1][0],p[0][1]-p[1][1]);if(pinch&&d>0)zoom(pinch/d);pinch=d}
   dirty=true;
 };
 canvas.onpointerup=canvas.onpointercancel=e=>{pointers.delete(e.pointerId);pinch=0};
 canvas.addEventListener('wheel',e=>{e.preventDefault();zoom(Math.exp(Math.max(-300,Math.min(300,e.deltaY))*.001))},{passive:false});
 canvas.onkeydown=e=>{
   if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','=','-'].includes(e.key))return;e.preventDefault();
   if(e.key==='ArrowLeft')az-=.1;if(e.key==='ArrowRight')az+=.1;
   if(e.key==='ArrowUp')el=Math.min(1.56,el+.1);if(e.key==='ArrowDown')el=Math.max(-1.56,el-.1);
   if(e.key==='+'||e.key==='=')zoom(.85);if(e.key==='-')zoom(1/.85);dirty=true;
 };
 function camera(p,eye,forward,right,up){
   gl.useProgram(p.p);vec(p,'uEye',eye);vec(p,'uF',forward);vec(p,'uR',right);vec(p,'uU',up);
   f(p,'uK',1/Math.tan(25*Math.PI/180));f(p,'uAspect',canvas.width/canvas.height);
   gl.uniformMatrix3fv(loc(p,'uSpin'),false,identity);f(p,'uH',canvas.height);f(p,'uHeight',canvas.height);
 }
 function draw(t){
   if(document.hidden){last=t;requestAnimationFrame(draw);return}
   if($('spin').checked&&!pointers.size){az+=Math.min(t-last,50)*.00006;dirty=true}last=t;
   if(dirty){
     dirty=false;
     const ce=Math.cos(el),se=Math.sin(el),ca=Math.cos(az),sa=Math.sin(az);
     const eye=[center[0]+dist*ce*ca,center[1]+dist*ce*sa,center[2]+dist*se];
     const forward=[-ce*ca,-ce*sa,-se],right=[-sa,ca,0],up=[-se*ca,-se*sa,ce];
     const clouds=Number($('cloud').value),starsGain=Number($('star').value);
     gl.bindFramebuffer(gl.FRAMEBUFFER,target);gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(0,0,0,1);gl.clear(gl.COLOR_BUFFER_BIT);
     gl.enable(gl.BLEND);gl.blendFunc(gl.ONE,gl.ONE);
     camera(star,eye,forward,right,up);f(star,'uGain',starsGain*(inside?.45:1));f(star,'uRef',0);f(star,'uNear',inside?.3:0);vec(star,'uCenter',sun);
     gl.bindVertexArray(starVAO);gl.drawArrays(gl.POINTS,0,source.stars);
     camera(tiny,eye,forward,right,up);f(tiny,'uGain',clouds*.12);gl.bindVertexArray(mistVAO);gl.drawArrays(gl.POINTS,0,source.mist);
     gl.blendFunc(gl.ONE,gl.ONE_MINUS_SRC_ALPHA);camera(dust,eye,forward,right,up);
     vec(dust,'uSun',sun);f(dust,'uClear',inside?2.5:0);f(dust,'uEm',inside?.15:1);f(dust,'uGain',clouds);f(dust,'uOpacity',clouds>0?1:0);
     for(const [unit,name,type,tex] of [[0,'uField',gl.TEXTURE_3D,field],[1,'uNoise',gl.TEXTURE_3D,detail],[2,'uDither',gl.TEXTURE_2D,jitter]]){
       gl.activeTexture(gl.TEXTURE0+unit);gl.bindTexture(type,tex);gl.uniform1i(loc(dust,name),unit);
     }
     gl.bindVertexArray(empty);gl.drawArrays(gl.TRIANGLES,0,3);gl.disable(gl.BLEND);
     gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.useProgram(post.p);gl.activeTexture(gl.TEXTURE3);gl.bindTexture(gl.TEXTURE_2D,hdr);gl.uniform1i(loc(post,'image'),3);gl.drawArrays(gl.TRIANGLES,0,3);
     const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('WebGL 渲染错误 '+error);
     status.textContent=`新版星云已就绪 · ${inside?'太阳邻域':'银河全景'} · ${canvas.width} × ${canvas.height}`;
     canvas.dataset.azimuth=az.toFixed(3);canvas.dataset.elevation=el.toFixed(3);canvas.dataset.distance=dist.toFixed(3);canvas.dataset.ready='true';
   }
   requestAnimationFrame(safeDraw);
 }
 function safeDraw(t){try{draw(t)}catch(e){fail(e)}}
 canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();fail(Error('图形上下文已中断，请刷新页面重新加载。'))});
 new ResizeObserver(()=>{try{resize()}catch(e){fail(e)}}).observe(canvas);
 setView('oblique');resize();requestAnimationFrame(safeDraw);
}
function fail(e){status.textContent='预览未能完成';$('error').textContent=e.message;console.error(e)}
start().catch(fail);
