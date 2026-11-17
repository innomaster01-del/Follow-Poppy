"""Renders Poppy for the app's opening screens from her GLB (transparent PNGs, two passes: black and white background).
usage: python3 splash_render.py <this dir> <models dir> <out dir>
  splash_<g>_walk<k>.png  8 frames of her walk loop, three-quarter view (all frames cropped the same)
  splash_poppy_<g>.png     a still, nearly front-on (the boy / girl choice)"""
import sys, os, numpy as np
from PIL import Image
sys.path.insert(0, sys.argv[1]); import render_glb as R
models, out = sys.argv[2], sys.argv[3]

def shot(glb, t, yaw, size, clip=0):
    imgs = []
    for bg in [(0, 0, 0), (1, 1, 1)]:
        tmp = os.path.join(out, '_tmp.png'); R.render(glb, tmp, t, yaw, size=size, bg=bg, clip=clip)
        imgs.append(np.asarray(Image.open(tmp)).astype(float) / 255); os.remove(tmp)
    b, w = imgs; a = np.clip(1 - (w - b).mean(axis=2), 0, 1)
    rgb = np.where(a[..., None] > 1e-3, b / np.maximum(a[..., None], 1e-3), 0).clip(0, 1)
    return Image.fromarray((np.dstack([rgb, a]) * 255).astype(np.uint8), 'RGBA')

for g in ['girl', 'boy']:
    glb = os.path.join(models, f'poppy_{g}.glb')
    frames = [shot(glb, k * 0.56 / 8, 0.5 if g == 'girl' else -0.5, 640) for k in range(8)]
    box = frames[0].getbbox()
    for f in frames[1:]:
        bb = f.getbbox(); box = (min(box[0], bb[0]), min(box[1], bb[1]), max(box[2], bb[2]), max(box[3], bb[3]))
    for k, f in enumerate(frames):
        c = f.crop(box); c = c.resize((c.width // 2, c.height // 2), Image.LANCZOS); c.save(os.path.join(out, f'splash_{g}_walk{k}.png'), optimize=True)
    s = shot(glb, 0.0, 0.25 if g == 'girl' else -0.25, 1000, clip=1)
    s = s.crop(s.getbbox()); s.resize((s.width * 3 // 5, s.height * 3 // 5), Image.LANCZOS).save(os.path.join(out, f'splash_poppy_{g}.png'), optimize=True)
