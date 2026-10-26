from pathlib import Path
import subprocess,sys
from PIL import Image,ImageChops,ImageStat
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
from opusvid.settings import FFMPEG
p=Path(__file__).resolve().parent
files=sorted((p/'video_frames').glob('*.png'))
assert len(files)==48,len(files)
a=Image.open(files[0]).convert('RGB');b=Image.open(files[-1]).convert('RGB')
d=ImageChops.difference(a,b)
assert d.getbbox() is not None
print('RGB mean difference:',ImageStat.Stat(d).mean)
subprocess.run([FFMPEG,'-y','-v','error','-framerate','12','-i',str(p/'video_frames/%03d.png'),'-c:v','libx264','-profile:v','baseline','-level','3.0','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart','-an',str(p/'animated_star_4s.mp4')],check=True)
subprocess.run([FFMPEG,'-y','-v','error','-i',str(p/'animated_star_4s.mp4'),'-filter_complex','split[a][b];[a]palettegen[p];[b][p]paletteuse=dither=sierra2_4a','-loop','0',str(p/'animated_star_4s.gif')],check=True)
subprocess.run([FFMPEG,'-v','error','-i',str(p/'animated_star_4s.mp4'),'-f','null','-'],check=True)
print('VIDEO_AND_GIF_VALIDATED')
