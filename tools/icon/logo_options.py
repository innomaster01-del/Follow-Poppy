"""Four launcher-icon ideas for Follow Poppy (1024 px each) and a preview sheet with them at home-screen sizes.
usage: python3 logo_options.py <out dir> [poppy still png]"""
import sys, math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 1024
out = sys.argv[1]
still = sys.argv[2] if len(sys.argv) > 2 else None

def grad(c0, c1, angle=0.35):
    y, x = np.mgrid[0:S, 0:S] / S
    t = np.clip(x * math.sin(angle) + y * math.cos(angle), 0, 1)[..., None]
    a = np.array(c0, float); b = np.array(c1, float)
    return Image.fromarray((a + (b - a) * t).astype(np.uint8), 'RGB').convert('RGBA')

def glow(im, xy, r, color, alpha):
    g = Image.new('L', (S, S), 0); ImageDraw.Draw(g).ellipse((xy[0] - r, xy[1] - r, xy[0] + r, xy[1] + r), fill=int(255 * alpha))
    g = g.filter(ImageFilter.GaussianBlur(r * 0.45)); im.paste(Image.new('RGBA', (S, S), color + (255,)), (0, 0), g)

def paw(d, cx, cy, s, fill, ang=0):
    def rot(x, y):
        c, sn = math.cos(ang), math.sin(ang); return cx + x * c - y * sn, cy + x * sn + y * c
    def ell(x, y, rx, ry):
        pts = [rot(x + rx * math.cos(t), y + ry * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 40)]; d.polygon(pts, fill=fill)
    ell(0, s * 0.25, s * 0.55, s * 0.45)
    for x, y in [(-0.62, -0.38), (-0.22, -0.7), (0.22, -0.7), (0.62, -0.38)]: ell(x * s, y * s, s * 0.2, s * 0.24)

def fluffy_disc(cx, cy, r, bumps=22, amp=0.045):
    pts = []
    for i in range(720):
        t = i / 720 * 2 * math.pi; rr = r * (1 + amp * (0.5 + 0.5 * math.cos(t * bumps)) + amp * 0.4 * math.sin(t * bumps * 2.3))
        pts.append((cx + rr * math.cos(t), cy + rr * math.sin(t)))
    return pts

def face(d, cx, cy, r, eye_col, iris_col):
    for s in (-1, 1):
        ex, ey = cx + s * r * 0.36, cy + r * 0.02
        d.ellipse((ex - r * 0.2, ey - r * 0.25, ex + r * 0.2, ey + r * 0.25), fill=eye_col)
        d.ellipse((ex - r * 0.14, ey - r * 0.12, ex + r * 0.14, ey + r * 0.22), fill=iris_col)
        d.ellipse((ex - r * 0.09, ey - r * 0.04, ex + r * 0.09, ey + r * 0.16), fill=(14, 8, 18))
        d.ellipse((ex + r * 0.02, ey - r * 0.17, ex + r * 0.13, ey - r * 0.06), fill='white')
        d.ellipse((ex - r * 0.1, ey + r * 0.08, ex - r * 0.04, ey + r * 0.14), fill='white')
        d.ellipse((cx + s * r * 0.62 - r * 0.12, cy + r * 0.3 - r * 0.07, cx + s * r * 0.62 + r * 0.12, cy + r * 0.3 + r * 0.07), fill=(255, 150, 190))
    d.ellipse((cx - r * 0.05, cy + r * 0.24, cx + r * 0.05, cy + r * 0.31), fill=(220, 80, 128))
    d.arc((cx - r * 0.13, cy + r * 0.26, cx + r * 0.13, cy + r * 0.46), 20, 160, fill=(70, 30, 50), width=int(r * 0.035))

def rounded(im):
    m = Image.new('L', (S, S), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * 0.225), fill=255)
    o = im.copy(); o.putalpha(m); return o

opts = []
# A — Poppy's face, flat and soft (a sticker you'd put on a phone)
im = grad((255, 214, 232), (255, 168, 210)); d = ImageDraw.Draw(im)
glow(im, (S * 0.5, S * 0.58), S * 0.42, (255, 255, 255), 0.55)
cx, cy, r = S * 0.5, S * 0.6, S * 0.3
for s in (-1, 1):                                     # ears
    e = Image.new('RGBA', (S, S), (0, 0, 0, 0)); de = ImageDraw.Draw(e)
    de.ellipse((cx - r * 0.2, cy - r * 1.95, cx + r * 0.2, cy - r * 0.55), fill=(244, 120, 182)); de.ellipse((cx - r * 0.08, cy - r * 1.72, cx + r * 0.08, cy - r * 0.95), fill=(255, 205, 228))
    e = e.rotate(-s * 14, center=(cx, cy - r * 0.6), resample=Image.BICUBIC); e = e.transform(e.size, Image.AFFINE, (1, 0, -s * r * 0.45, 0, 1, 0), resample=Image.BICUBIC)
    im.alpha_composite(e)
d = ImageDraw.Draw(im); d.polygon(fluffy_disc(cx, cy, r), fill=(244, 120, 182)); d.polygon(fluffy_disc(cx, cy - r * 0.04, r * 0.9, 18, 0.03), fill=(250, 140, 194))
face(d, cx, cy, r, (40, 22, 40), (150, 60, 110))
opts.append(('A', 'הפנים של פופי', 'Poppy\'s face', im))

# B — the trail: paw prints walking up a glowing path to a pin, on a night sky
im = grad((22, 28, 66), (10, 70, 96), 0.2); d = ImageDraw.Draw(im)
glow(im, (S * 0.5, S * 0.32), S * 0.3, (255, 127, 191), 0.5); glow(im, (S * 0.5, S * 0.82), S * 0.35, (95, 179, 255), 0.4)
path = [(S * (0.5 + 0.16 * math.sin(t * 2.6)), S * (0.9 - 0.62 * t)) for t in np.linspace(0, 1, 60)]
lay = Image.new('RGBA', (S, S), (0, 0, 0, 0)); ImageDraw.Draw(lay).line(path, fill=(255, 255, 255, 46), width=int(S * 0.09), joint='curve'); im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(6))); d = ImageDraw.Draw(im)
for k, t in enumerate(np.linspace(0.08, 0.7, 5)):
    x, y = S * (0.5 + 0.16 * math.sin(t * 2.6)), S * (0.9 - 0.62 * t); side = 1 if k % 2 else -1
    paw(d, x + side * S * 0.035, y, S * (0.034 + 0.008 * t), (255, 127, 191) if k % 2 else (95, 179, 255), ang=-0.4 * math.cos(t * 2.6))
px, py, pr = S * 0.5 + S * 0.16 * math.sin(0.9 * 2.6), S * 0.22, S * 0.1
d.ellipse((px - pr, py - pr, px + pr, py + pr), fill='white'); d.polygon([(px - pr * 0.75, py + pr * 0.65), (px + pr * 0.75, py + pr * 0.65), (px, py + pr * 1.75)], fill='white')
d.ellipse((px - pr * 0.42, py - pr * 0.42, px + pr * 0.42, py + pr * 0.42), fill=(255, 127, 191))
opts.append(('B', 'שביל טביעות', 'Paw trail', im))

# C — Poppy herself (her 3D look), peeking up on a soft gradient
im = grad((255, 190, 222), (130, 190, 255), 0.6)
glow(im, (S * 0.5, S * 0.55), S * 0.45, (255, 255, 255), 0.5)
if still:
    p = Image.open(still).convert('RGBA'); k = S * 0.92 / p.height; p = p.resize((int(p.width * k), int(p.height * k)), Image.LANCZOS)
    sh = Image.new('L', (S, S), 0); ImageDraw.Draw(sh).ellipse((S * 0.25, S * 0.86, S * 0.75, S * 0.98), fill=90); sh = sh.filter(ImageFilter.GaussianBlur(30))
    im.paste((60, 40, 90, 255), (0, 0), sh); im.alpha_composite(p, (int(S / 2 - p.width / 2), int(S * 0.1)))
opts.append(('C', 'פופי בתלת־ממד', 'Poppy in 3D', im))

# D — minimal: a white "P" made of a path with a paw for the dot, on deep teal (very clean, Apple style)
im = grad((16, 32, 52), (18, 120, 132), 0.5); d = ImageDraw.Draw(im)
glow(im, (S * 0.62, S * 0.36), S * 0.28, (255, 127, 191), 0.35)
w = int(S * 0.085)
d.line([(S * 0.36, S * 0.8), (S * 0.36, S * 0.26)], fill='white', width=w)
d.arc((S * 0.36 - S * 0.02, S * 0.22, S * 0.72, S * 0.58), -90, 90, fill='white', width=w)
d.line([(S * 0.36, S * 0.22 + w / 2), (S * 0.54, S * 0.22 + w / 2)], fill='white', width=w); d.line([(S * 0.36, S * 0.58 - w / 2), (S * 0.54, S * 0.58 - w / 2)], fill='white', width=w)
d.ellipse((S * 0.36 - w / 2, S * 0.8 - w / 2, S * 0.36 + w / 2, S * 0.8 + w / 2), fill='white'); d.ellipse((S * 0.36 - w / 2, S * 0.26 - w / 2, S * 0.36 + w / 2, S * 0.26 + w / 2), fill='white')
paw(d, S * 0.6, S * 0.76, S * 0.07, (255, 127, 191))
opts.append(('D', 'P עם טביעה', 'P with a paw', im))

for k, he, en, im in opts: rounded(im).save(os.path.join(out, f'logo_{k}.png'))
# preview: each at a big and a home-screen size, with its letter
W = 4 * 300 + 50; prev = Image.new('RGB', (W, 420), (242, 242, 247)); dp = ImageDraw.Draw(prev)
try: font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 44)
except Exception: font = None
for i, (k, he, en, im) in enumerate(opts):
    x = 30 + i * 300
    prev.paste(rounded(im).resize((240, 240), Image.LANCZOS), (x, 30), rounded(im).resize((240, 240), Image.LANCZOS))
    sm = rounded(im).resize((96, 96), Image.LANCZOS); prev.paste(sm, (x + 72, 290), sm)
    dp.text((x, 290), k, fill=(30, 30, 40), font=font)
prev.save(os.path.join(out, 'logo_options.png'))
