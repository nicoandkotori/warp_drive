const canvas=document.getElementById('space'),status=document.getElementById('status');
const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
const gallery=document.getElementById('gallery');
document.getElementById('photos').onclick=()=>gallery.classList.add('open');document.getElementById('close').onclick=()=>gallery.classList.remove('open');
if(!gl){status.textContent='当前浏览器未启用 WebGL2，请用 Chrome / Edge 打开。';gallery.classList.add('open');}else{try{start()}catch(e){status.textContent='渲染失败：'+e.message;console.error(e)}}
function start(){
 const decode=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
 const verts=new Float32Array(decode(GALAXY.stars).buffer);
 const header='#version 300 es\nprecision highp float;\n';
 function program(v,f){const p=gl.createProgram();for(const [type,src]of[[gl.VERTEX_SHADER,v],[gl.FRAGMENT_SHADER,f]]){const sh=gl.createShader(type);gl.shaderSource(sh,header+src);gl.compileShader(sh);if(!gl.getShaderParameter(sh,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(sh));gl.attachShader(p,sh)}gl.linkProgram(p);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(p));return p}
 const camera='uniform vec3 eye,right,up,forward;uniform float aspect;';
 // A compact white core and a wider, much weaker colored halo. Keep peaks
 // below clipping so even bright stars retain a visible radial gradient.
 const star=program(camera+`layout(location=0)in vec3 pos;layout(location=1)in vec3 color;layout(location=2)in float size;uniform float height;out vec3 col;out float energy;void main(){vec3 d=pos-eye;float depth=dot(d,forward);gl_Position=vec4(dot(d,right)*1.9/aspect, dot(d,up)*1.9,depth*.99,depth);float seed=fract(sin(dot(pos,vec3(12.9898,78.233,39.425)))*43758.5453);energy=.55+1.6*pow(seed,4.);gl_PointSize=clamp(size*height/depth*6.5+3.,5.5,16.)*(.85+.2*sqrt(energy));col=color;}`,`in vec3 col;in float energy;uniform float brightness;out vec4 outColor;void main(){float r=length(gl_PointCoord-.5)*2.;if(r>=1.)discard;float core=1.7*exp(-r*r*65.);float halo=.14*exp(-r*r*6.)*(1.-smoothstep(.65,1.,r));vec3 light=(mix(col,vec3(1.),.4)*core+col*halo)*energy*brightness;outColor=vec4(vec3(1.)-exp(-light),1);}`);
 const volume=program(`out vec2 uv;void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);uv=p;gl_Position=vec4(p*2.-1.,0,1);}`,camera+`precision highp sampler3D;in vec2 uv;uniform sampler3D field;uniform float brightness;uniform float height;out vec4 outColor;
float hash31(vec3 p){return fract(sin(dot(p,vec3(127.1,311.7,74.7)))*43758.5453);}
float grain(vec3 p){vec3 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(mix(hash31(i),hash31(i+vec3(1,0,0)),f.x),mix(hash31(i+vec3(0,1,0)),hash31(i+vec3(1,1,0)),f.x),f.y),mix(mix(hash31(i+vec3(0,0,1)),hash31(i+vec3(1,0,1)),f.x),mix(hash31(i+vec3(0,1,1)),hash31(i+vec3(1,1,1)),f.x),f.y),f.z);}
vec3 colorAt(float r){vec3 a=vec3(1,.76,.55),b=vec3(.8,.47,.36),c=vec3(.54,.42,.61),d=vec3(.38,.47,.74),e=vec3(.19,.32,.63);float t=r/19.;if(t<.18)return mix(a,b,t/.18);if(t<.4)return mix(b,c,(t-.18)/.22);if(t<.65)return mix(c,d,(t-.4)/.25);return mix(d,e,clamp((t-.65)/.35,0.,1.));}
void main(){vec2 q=uv*2.-1.;vec3 rd=normalize(forward+right*q.x*aspect/1.9+up*q.y/1.9);vec3 bounds=vec3(24,24,2.5);vec3 t0=(-bounds-eye)/rd,t1=(bounds-eye)/rd;vec3 nearv=min(t0,t1),farv=max(t0,t1);float lo=max(max(nearv.x,nearv.y),nearv.z),hi=min(min(farv.x,farv.y),farv.z);if(hi<=max(lo,0.)){outColor=vec4(0);return;}lo=max(lo,0.);int steps=length(eye)<40.?320:160;float stepSize=(hi-lo)/float(steps);vec3 light=vec3(0);float trans=1.;for(int i=0;i<320;i++){if(i>=steps)break;vec3 p=eye+rd*(lo+(float(i)+.5)*stepSize);vec3 v=texture(field,p/(bounds*2.)+.5).rgb;
float footprint=max(length(p-eye)/(height*1.9),.0001);
float fineWeight=1.-smoothstep(.012,.05,footprint);
vec3 coord=p*vec3(1.,1.,1.4);
float coarse=grain(coord*4.);
float medium=grain(coord*12.+vec3(8.3,2.1,5.7));
float fine=grain(coord*30.+vec3(1.9,7.6,3.2));
float detail=.42*coarse+.34*medium+.24*mix(.5,fine,fineWeight);
// Local unsharp contrast restores cloud banks softened by texture interpolation.
vec3 tc=p/(bounds*2.)+.5;vec3 texel=1./vec3(textureSize(field,0));
float nearby=(texture(field,tc+vec3(texel.x*1.5,0,0)).r+texture(field,tc-vec3(texel.x*1.5,0,0)).r+texture(field,tc+vec3(0,texel.y*1.5,0)).r+texture(field,tc-vec3(0,texel.y*1.5,0)).r)*.25;
float sharpened=max(0.,v.r+(v.r-nearby)*1.1);
float em=exp(sharpened*log(17.))-1.;
float ridge=smoothstep(.33,.68,detail);
float breakup=mix(1.,.12+2.1*ridge*ridge,smoothstep(1.,4.,length(p.xy)));
em*=breakup;
float den=v.g*4.*(.35+2.6*smoothstep(.38,.68,1.-detail));
light+=trans*mix(colorAt(length(p.xy)),vec3(.95,.18,.36),v.b*.65)*em*stepSize*brightness;trans*=exp(-den*stepSize);if(trans<.015)break;}light=vec3(1)-exp(-light*1.15);light=pow(light,vec3(.8));outColor=vec4(light,min(1.-trans,.68));}`);
 const vao=gl.createVertexArray();gl.bindVertexArray(vao);const buf=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buf);gl.bufferData(gl.ARRAY_BUFFER,verts,gl.STATIC_DRAW);for(const [i,num,offset]of[[0,3,0],[1,3,12],[2,1,24]]){gl.enableVertexAttribArray(i);gl.vertexAttribPointer(i,num,gl.FLOAT,false,28,offset)}gl.bindVertexArray(null);
 const tex=gl.createTexture();gl.bindTexture(gl.TEXTURE_3D,tex);gl.pixelStorei(gl.UNPACK_ALIGNMENT,1);gl.texImage3D(gl.TEXTURE_3D,0,gl.RGB8,...GALAXY.dims,0,gl.RGB,gl.UNSIGNED_BYTE,decode(GALAXY.volume));for(const name of[gl.TEXTURE_MIN_FILTER,gl.TEXTURE_MAG_FILTER])gl.texParameteri(gl.TEXTURE_3D,name,gl.LINEAR);for(const name of[gl.TEXTURE_WRAP_S,gl.TEXTURE_WRAP_T,gl.TEXTURE_WRAP_R])gl.texParameteri(gl.TEXTURE_3D,name,gl.CLAMP_TO_EDGE);
 let az=-1.08,el=.7,dist=61,dirty=true,last=0;const pointers=new Map();let pinch=0;
 const setView=kind=>{az=-1.08;el=kind==='top'?1.56:kind==='side'?.05:.7;dist=kind==='close'?27:61;dirty=true};document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>setView(b.dataset.view));document.getElementById('reset').onclick=()=>{setView('oblique');document.getElementById('cloud').value=1;document.getElementById('star').value=1;document.getElementById('cv').value='1.0';document.getElementById('sv').value='1.0'};
 for(const [id,out]of[['cloud','cv'],['star','sv']])document.getElementById(id).oninput=e=>{document.getElementById(out).value=(+e.target.value).toFixed(1);dirty=true};document.getElementById('spin').onchange=()=>dirty=true;
 canvas.onpointerdown=e=>{canvas.setPointerCapture(e.pointerId);pointers.set(e.pointerId,[e.clientX,e.clientY]);pinch=0};canvas.onpointermove=e=>{if(!pointers.has(e.pointerId))return;const old=pointers.get(e.pointerId);pointers.set(e.pointerId,[e.clientX,e.clientY]);if(pointers.size===1){az-=(e.clientX-old[0])*.006;el=Math.max(-1.56,Math.min(1.56,el+(e.clientY-old[1])*.006))}else{const p=[...pointers.values()];const dd=Math.hypot(p[0][0]-p[1][0],p[0][1]-p[1][1]);if(pinch)dist=Math.max(7,Math.min(150,dist*pinch/dd));pinch=dd}dirty=true};canvas.onpointerup=canvas.onpointercancel=e=>{pointers.delete(e.pointerId);pinch=0};canvas.addEventListener('wheel',e=>{e.preventDefault();dist=Math.max(7,Math.min(150,dist*Math.exp(e.deltaY*.001)));dirty=true},{passive:false});canvas.onkeydown=e=>{if(e.key==='ArrowLeft')az-=.1;if(e.key==='ArrowRight')az+=.1;if(e.key==='ArrowUp')el=Math.min(1.56,el+.1);if(e.key==='ArrowDown')el=Math.max(-1.56,el-.1);dirty=true};
 new ResizeObserver(()=>{const ratio=Math.min(devicePixelRatio,1.75);canvas.width=Math.round(canvas.clientWidth*ratio);canvas.height=Math.round(canvas.clientHeight*ratio);dirty=true}).observe(canvas);
 function cameraUniform(p,eye,right,up,forward){gl.useProgram(p);for(const [name,val]of Object.entries({eye,right,up,forward}))gl.uniform3fv(gl.getUniformLocation(p,name),val);gl.uniform1f(gl.getUniformLocation(p,'aspect'),canvas.width/canvas.height)}
 function draw(t){requestAnimationFrame(draw);if(document.getElementById('spin').checked&&!pointers.size){az+=Math.min(t-last,50)*.00006;dirty=true}last=t;if(!dirty||gallery.classList.contains('open'))return;dirty=false;const ce=Math.cos(el),se=Math.sin(el),ca=Math.cos(az),sa=Math.sin(az);const eye=[dist*ce*ca,dist*ce*sa,dist*se],forward=[-ce*ca,-ce*sa,-se],right=[-sa,ca,0],up=[-se*ca,-se*sa,ce];gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(.002,.003,.006,1);gl.clear(gl.COLOR_BUFFER_BIT);gl.enable(gl.BLEND);gl.blendFunc(gl.ONE,gl.ONE);cameraUniform(star,eye,right,up,forward);gl.uniform1f(gl.getUniformLocation(star,'height'),canvas.height);gl.uniform1f(gl.getUniformLocation(star,'brightness'),+document.getElementById('star').value);gl.bindVertexArray(vao);gl.drawArrays(gl.POINTS,0,verts.length/7);gl.bindVertexArray(null);gl.blendFunc(gl.ONE,gl.ONE_MINUS_SRC_ALPHA);cameraUniform(volume,eye,right,up,forward);gl.uniform1f(gl.getUniformLocation(volume,'height'),canvas.height);gl.uniform1f(gl.getUniformLocation(volume,'brightness'),+document.getElementById('cloud').value);gl.drawArrays(gl.TRIANGLES,0,3);gl.disable(gl.BLEND);status.textContent='三维星图已就绪 · 可自由旋转';canvas.dataset.azimuth=az.toFixed(3);canvas.dataset.elevation=el.toFixed(3);canvas.dataset.distance=dist.toFixed(2);}
 requestAnimationFrame(draw);
}
