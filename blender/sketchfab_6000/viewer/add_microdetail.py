from pathlib import Path
p=Path(__file__).with_name('viewer.js');s=p.read_text(encoding='utf-8')
marker='vec3 colorAt(float r)'
code='''float hash21(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float grain(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash21(i),hash21(i+vec2(1,0)),f.x),mix(hash21(i+vec2(0,1)),hash21(i+vec2(1,1)),f.x),f.y);}
'''
if 'float hash21' not in s:s=s.replace(marker,code+marker)
s=s.replace('float den=v.g*4.;','float detail=.65*grain(p.xy*5.)+.35*grain(p.xy*13.);em*=.22+2.4*smoothstep(.28,.72,detail);float den=v.g*4.*(.6+1.5*(1.-detail));')
p.write_text(s,encoding='utf-8')
