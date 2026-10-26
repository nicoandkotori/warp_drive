"""python verify_galaxy_refine.py：检查所有关键帧及推进段的有限性、乱序重渲染一致性。"""
import json
from pathlib import Path

import config
import numpy as np
from opusvid.gl import Engine
from opusvid.settings import W, H
from galaxynav import GalaxyNav
from preview_galaxy import VIEWS


def main():
    eng = Engine()
    nav = GalaxyNav(eng)
    _, target = eng.targets[0]

    def render(t):
        eng.time, eng.frame = t, round(t*60)
        target.use()
        eng.ctx.viewport = (0, 0, W, H)
        target.clear(0, 0, 0, 1)
        cam, kwargs = nav.galaxy_args(t)
        nav.g.draw(cam, **kwargs)
        return target.read(components=4, dtype='f4')

    times = sorted(set([t for _, t in VIEWS] + [round(6+i/10, 2) for i in range(61)]))
    finite = {}
    fingerprints = {}
    import hashlib
    for t in times:
        data = render(t)
        finite[str(t)] = bool(np.isfinite(np.frombuffer(data, np.float32)).all())
        fingerprints[t] = hashlib.sha256(data).hexdigest()
    deterministic = {}
    for name, t in reversed(VIEWS):
        deterministic[name] = hashlib.sha256(render(t)).hexdigest() == fingerprints[t]
    result = dict(hdr_finite=all(finite.values()), sampled_times=len(times),
                  deterministic=deterministic, all_deterministic=all(deterministic.values()))
    dest = Path(config.BUILD)/'galaxy'/'final'/'extended_checks.json'
    dest.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    assert result['hdr_finite'] and result['all_deterministic']


if __name__ == '__main__':
    main()
