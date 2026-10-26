"""将 Blender 实渲图排版为前后对照与四视角审阅图，不改动渲染内容。"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT=Path(__file__).resolve().parent/'reference_refined_v2'
FONT=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',27)


def sheet(filename,items,columns):
    w,h,bar=1280,720,58
    rows=(len(items)+columns-1)//columns
    canvas=Image.new('RGB',(columns*w,rows*(h+bar)),(18,23,29))
    draw=ImageDraw.Draw(canvas)
    for i,(image,title) in enumerate(items):
        x,y=(i%columns)*w,(i//columns)*(h+bar)
        im=Image.open(OUT/image).convert('RGB').resize((w,h),Image.Resampling.LANCZOS)
        canvas.paste(im,(x,y+bar))
        draw.text((x+26,y+11),title,font=FONT,fill=(218,227,235))
    canvas.save(OUT/filename)


sheet('comparison_before_after.png',[
    ('00_before_same_view.png','细化前 · 同机位 / 同灯光'),
    ('01_hero.png','细化后 · 曲率环和支撑保持原样')],2)
sheet('review_four_views.png',[
    ('01_hero.png','整体 · 舰艏装甲与机械层'),
    ('02_aft.png','舰尾 · 六台错位推进器'),
    ('04_prow_detail.png','近景 · 分层装甲与中央加速器'),
    ('05_engine_detail.png','近景 · 冷却管束与多层喷口')],2)
print('REVIEW_SHEETS_READY')
