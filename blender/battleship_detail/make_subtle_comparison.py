"""并排排版用户选定的 V2 与轻修订 V4 的同灯光实渲。"""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

root=Path(__file__).resolve().parent
out=root/'reference_refined_v4'
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',26)
canvas=Image.new('RGB',(2560,780),(22,26,32))
draw=ImageDraw.Draw(canvas)
for x,path,title in [(0,root/'reference_refined_v2/01_hero.png','你选定的原版 V2'),
                     (1280,out/'01_hero.png','回归原轮廓 · 仅薄层细节和轻微金属调整')]:
    im=Image.open(path).convert('RGB').resize((1280,720),Image.Resampling.LANCZOS)
    canvas.paste(im,(x,60)); draw.text((x+24,14),title,font=font,fill=(221,228,236))
canvas.save(out/'comparison_v2_subtle_v4.png')
print('COMPARISON_READY')
