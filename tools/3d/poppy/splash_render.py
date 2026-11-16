import sys, numpy as np
from PIL import Image
sys.path.insert(0, sys.argv[1]); import render_glb as R
glb, out = sys.argv[2], sys.argv[3]
imgs = []
for bg in [(0,0,0),(1,1,1)]:
    R.render(glb, out + '.tmp.png', 0.0, 0.3, size=1200, bg=bg); imgs.append(np.asarray(Image.open(out + '.tmp.png')).astype(float) / 255)
b, w = imgs; a = np.clip(1 - (w - b).mean(axis=2), 0, 1)
rgb = np.where(a[..., None] > 1e-3, b / np.maximum(a[..., None], 1e-3), 0).clip(0, 1)
im = Image.fromarray((np.dstack([rgb, a]) * 255).astype(np.uint8), 'RGBA').resize((600, 600), Image.LANCZOS)
im.crop(im.getbbox()).save(out, optimize=True)
import os; os.remove(out + '.tmp.png')
