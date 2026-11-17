"""Makes the app's icon and logo from the two pictures in tools/icon/source:
  app_icon_card.png  - the icon as a card on a white page (cut out, white corners filled, made square)
  logo_on_black.png  - the logo drawn on black (black turned into transparency, glow faded at the edges)
usage: python3 from_pictures.py <res dir> <assets dir>   (needs opencv-python and Pillow)"""
import os, sys, subprocess
import numpy as np, cv2
from PIL import Image
here = os.path.dirname(os.path.abspath(__file__)); res, assets = sys.argv[1], sys.argv[2]

# icon: the card is at x 28..536, y 11..658 of the picture
src = cv2.cvtColor(np.asarray(Image.open(os.path.join(here, 'source/app_icon_card.png')).convert('RGB')), cv2.COLOR_RGB2BGR)
c = src[11:659, 28:537].copy(); h, w = c.shape[:2]
reg = (c.astype(int).sum(axis=2) > 420).astype(np.uint8); ff = np.zeros((h + 2, w + 2), np.uint8)
for (x, y) in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0)]:
    if reg[y, x]: cv2.floodFill(reg, ff, (x, y), 2)                    # the white page around the card's rounded corners
mask = cv2.dilate((reg == 2).astype(np.uint8) * 255, np.ones((9, 9), np.uint8))
fill = cv2.inpaint(c, mask, 30, cv2.INPAINT_TELEA)
S = int(h * 1.08); top = (S - h) // 2; left = (S - w) // 2
sq = cv2.copyMakeBorder(fill, top, S - h - top, left, S - w - left, cv2.BORDER_REPLICATE); bl = cv2.GaussianBlur(sq, (0, 0), 25)
m = np.zeros(sq.shape[:2], np.float32); m[top + 12:top + h - 12, left + 12:left + w - 12] = 1; m = cv2.GaussianBlur(m, (0, 0), 12)[..., None]
o = cv2.resize((sq * m + bl * (1 - m)).astype(np.uint8), (1024, 1024), interpolation=cv2.INTER_LANCZOS4)
Image.fromarray(cv2.cvtColor(o, cv2.COLOR_BGR2RGB)).save(os.path.join(here, 'source/app_icon.png'))
subprocess.run([sys.executable, os.path.join(here, 'install_icon.py'), os.path.join(here, 'source/app_icon.png'), res], check=True)

# logo: light on black → colour + alpha
im = np.asarray(Image.open(os.path.join(here, 'source/logo_on_black.png')).convert('RGB')).astype(np.float32) / 255
a = np.clip((im.max(axis=2) - 0.03) / 0.97, 0, 1)
rgb = np.where(a[..., None] > 1e-3, np.clip(im / np.maximum(a[..., None], 1e-3), 0, 1), 0)
H, W = a.shape; yy, xx = np.mgrid[0:H, 0:W]
a = a * np.clip(np.minimum.reduce([xx / W, (W - 1 - xx) / W, yy / H, (H - 1 - yy) / H]) / 0.14, 0, 1) ** 1.6
out = Image.fromarray((np.dstack([rgb, a]) * 255).astype(np.uint8), 'RGBA')
out = out.crop(Image.fromarray((a > 0.02).astype(np.uint8) * 255).getbbox())
k = 900 / max(out.size); out.resize((int(out.width * k), int(out.height * k)), Image.LANCZOS).save(os.path.join(assets, 'splash_logo.png'), optimize=True)
