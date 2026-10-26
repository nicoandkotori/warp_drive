"""python export_galaxy_web.py：导出当前 galaxy.py 的着色器和确定性数据供 WebGL2 预览。"""
import json
from pathlib import Path

import config
import numpy as np
import galaxy


def main():
    out = Path(config.BUILD) / 'galaxy' / 'web'
    out.mkdir(parents=True, exist_ok=True)
    stars, volume = galaxy.load()
    stars.astype('<f4').tofile(out / 'stars.bin')
    volume.tofile(out / 'volume.bin')
    galaxy.detail_volume().astype('<f2').tofile(out / 'noise.bin')
    galaxy.unresolved_stars(volume).astype('<f4').tofile(out / 'mist.bin')
    # 与 Galaxy.__init__ 相同的种子和秩变换，网页与影片使用相同采样偏移。
    rng = np.random.default_rng(1931)
    white = rng.normal(size=(128, 128))
    fy, fx = np.meshgrid(np.fft.fftfreq(128), np.fft.fftfreq(128), indexing='ij')
    blue = np.fft.ifft2(np.fft.fft2(white)*np.sqrt(fx*fx+fy*fy)).real
    ranks = np.argsort(np.argsort(blue.ravel())).reshape(128, 128)
    ((ranks+.5)/16384).astype('<f4').tofile(out / 'dither.bin')

    def webgl(source):
        return '#version 300 es\nprecision highp float;\nprecision highp int;\nprecision highp sampler3D;\n' + source.replace('#version 430', '')

    shaders = {name: webgl(getattr(galaxy, name)) for name in
               ('STAR_VS', 'STAR_FS', 'CLOUD_FS', 'MIST_STAR_VS', 'MIST_STAR_FS')}
    shaders['dims'] = galaxy.DIMS
    shaders['stars'] = len(stars)
    shaders['mist'] = 650000
    (out / 'shaders.json').write_text(json.dumps(shaders, ensure_ascii=False), encoding='utf-8')
    print('Exported current galaxy shaders and data:', out)


if __name__ == '__main__':
    main()
