"""Variations of the paw-trail launcher icon (idea B), 1024 px each, and a preview sheet.
usage: python3 logo_trail.py <out dir>"""
import sys, math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 1024; out = sys.argv[1]
PINK, BLUE = (255, 127, 191), (95, 179, 255)

def grad(stops, angle=0.2):
    y, x = np.mgrid[0:S, 0:S] / S; t = np.clip(x * math.sin(angle) + y * math.cos(angle), 0, 1)
    img = np.zeros((S, S, 3))
    for i in range(len(stops) - 1):
        (p0, c0), (p1, c1) = stops[i], stops[i + 1]
        m = (t >= p0) & (t <= p1); k = ((t - p0) / max(p1 - p0, 1e-6))[m][:, None]
        img[m] = np.array(c0) + (np.array(c1) - np.array(c0)) * k
    return Image.fromarray(img.astype(np.uint8), 'RGB').convert('RGBA')

def glow(im, xy, r, color, alpha):
    g = Image.new('L', (S, S), 0); ImageDraw.Draw(g).ellipse((xy[0] - r, xy[1] - r, xy[0] + r, xy[1] + r), fill=int(255 * alpha))
    im.paste(Image.new('RGBA', (S, S), color + (255,)), (0, 0), g.filter(ImageFilter.GaussianBlur(r * 0.45)))

def paw(d, cx, cy, s, fill, ang=0.0):
    c, sn = math.cos(ang), math.sin(ang)
    def ell(x, y, rx, ry):
        d.polygon([(cx + (x + rx * math.cos(t)) * c - (y + ry * math.sin(t)) * sn, cy + (x + rx * math.cos(t)) * sn + (y + ry * math.sin(t)) * c) for t in np.linspace(0, 2 * math.pi, 40)], fill=fill)
    ell(0, s * 0.25, s * 0.55, s * 0.45)
    for x, y in [(-0.62, -0.38), (-0.22, -0.7), (0.22, -0.7), (0.62, -0.38)]: ell(x * s, y * s, s * 0.2, s * 0.24)

def pin(im, px, py, pr, inner=PINK, ears=False, shadow=True):
    lay = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    if ears:
        for s in (-1, 1):
            e = Image.new('RGBA', (S, S), (0, 0, 0, 0)); ImageDraw.Draw(e).ellipse((px - pr * 0.22, py - pr * 1.9, px + pr * 0.22, py - pr * 0.5), fill='white')
            e = e.rotate(-s * 16, center=(px, py - pr * 0.6), resample=Image.BICUBIC).transform((S, S), Image.AFFINE, (1, 0, -s * pr * 0.42, 0, 1, 0), resample=Image.BICUBIC)
            lay.alpha_composite(e)
    d.ellipse((px - pr, py - pr, px + pr, py + pr), fill='white')
    a = math.radians(42); d.polygon([(px - pr * math.cos(a), py + pr * math.sin(a)), (px + pr * math.cos(a), py + pr * math.sin(a)), (px, py + pr * 1.7)], fill='white')
    if shadow:
        sh = lay.split()[3].filter(ImageFilter.GaussianBlur(pr * 0.18)).point(lambda v: int(v * 0.35))
        im.paste((20, 10, 50, 255), (0, int(pr * 0.12)), sh)
    im.alpha_composite(lay)
    d = ImageDraw.Draw(im)
    if inner == 'paw': paw(d, px, py + pr * 0.08, pr * 0.5, PINK)
    else: d.ellipse((px - pr * 0.42, py - pr * 0.42, px + pr * 0.42, py + pr * 0.42), fill=inner)

def curve(f, n=80): return [f(t) for t in np.linspace(0, 1, n)]

def soft_line(im, pts, width, color, alpha, blur):
    lay = Image.new('RGBA', (S, S), (0, 0, 0, 0)); ImageDraw.Draw(lay).line(pts, fill=color + (int(255 * alpha),), width=int(width), joint='curve')
    im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(blur)) if blur else lay)

def rounded(im):
    m = Image.new('L', (S, S), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * 0.225), fill=255)
    o = im.copy(); o.putalpha(m); return o

opts = []
# B1 — the original idea, cleaner: an S-shaped trail of pink/blue paws up to a pin with a paw inside
im = grad([(0, (28, 24, 72)), (0.6, (34, 52, 110)), (1, (14, 92, 120))], 0.25)
glow(im, (S * 0.6, S * 0.28), S * 0.32, PINK, 0.45); glow(im, (S * 0.4, S * 0.85), S * 0.35, BLUE, 0.35)
f = lambda t: (S * (0.42 + 0.17 * math.sin(t * 3.0 - 0.4)), S * (0.94 - 0.6 * t))
soft_line(im, curve(f), S * 0.1, (255, 255, 255), 0.12, 10)
d = ImageDraw.Draw(im)
for k, t in enumerate(np.linspace(0.06, 0.72, 6)):
    x, y = f(t); x2, y2 = f(t + 0.01); ang = math.atan2(y2 - y, x2 - x) + math.pi / 2; side = 1 if k % 2 else -1
    paw(d, x + side * S * 0.03 * math.cos(ang), y + side * S * 0.03 * math.sin(ang), S * (0.03 + 0.012 * t), PINK if k % 2 else BLUE, ang)
x, y = f(1.0); pin(im, x, S * 0.24, S * 0.11, 'paw')
opts.append(('1', im))

# B2 — big glossy pin with bunny ears (Poppy) in the middle, a short paw trail curling in from below, purple dusk
im = grad([(0, (74, 36, 120)), (0.55, (40, 40, 110)), (1, (18, 74, 128))], 0.1)
glow(im, (S * 0.5, S * 0.42), S * 0.36, PINK, 0.5)
f = lambda t: (S * (0.2 + 0.3 * t + 0.08 * math.sin(t * 5)), S * (0.92 - 0.12 * t))
d = ImageDraw.Draw(im)
for k, t in enumerate(np.linspace(0.0, 0.9, 4)):
    x, y = f(t); paw(d, x, y + (12 if k % 2 else -12), S * 0.032, (255, 255, 255, 200) if k % 2 else (255, 200, 228), 1.2)
pin(im, S * 0.52, S * 0.5, S * 0.17, 'paw', ears=True)
opts.append(('2', im))

# B3 — a glowing route line (pink → blue) on faint night streets, the paws walking along it, a pin at the end
im = grad([(0, (14, 20, 40)), (1, (20, 36, 66))], 0.3)
st = Image.new('RGBA', (S, S), (0, 0, 0, 0)); ds = ImageDraw.Draw(st)
for i in range(-2, 7):                                     # faint streets
    ds.line([(i * S * 0.17, 0), (i * S * 0.17 + S * 0.35, S)], fill=(255, 255, 255, 20), width=10)
    ds.line([(0, i * S * 0.19), (S, i * S * 0.19 - S * 0.25)], fill=(255, 255, 255, 14), width=8)
im.alpha_composite(st)
pts = curve(lambda t: (S * (0.2 + 0.56 * t), S * (0.84 - 0.46 * t + 0.12 * math.sin(t * math.pi))))
for w, a, b in [(S * 0.12, 0.25, 22), (S * 0.045, 1.0, 0)]:
    lay = Image.new('RGBA', (S, S), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    for i in range(len(pts) - 1):
        t = i / (len(pts) - 1); c = tuple(int(PINK[j] + (BLUE[j] - PINK[j]) * t) for j in range(3))
        dl.line([pts[i], pts[i + 1]], fill=c + (int(255 * a),), width=int(w))
        dl.ellipse((pts[i][0] - w / 2, pts[i][1] - w / 2, pts[i][0] + w / 2, pts[i][1] + w / 2), fill=c + (int(255 * a),))
    im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(b)) if b else lay)
d = ImageDraw.Draw(im)
for k, t in enumerate([0.12, 0.3, 0.48, 0.66]):
    x, y = pts[int(t * (len(pts) - 1))]; paw(d, x, y, S * 0.03, (255, 255, 255), 0.9)
x, y = pts[-1]; pin(im, x, y - S * 0.17, S * 0.1, BLUE)
opts.append(('3', im))

# B4 — light and friendly: soft sunrise, the trail in white, pin in pink with a paw (bright on a dark home screen)
im = grad([(0, (255, 196, 222)), (0.5, (214, 190, 255)), (1, (150, 200, 255))], 0.35)
glow(im, (S * 0.5, S * 0.3), S * 0.3, (255, 255, 255), 0.6)
f = lambda t: (S * (0.5 - 0.2 * math.sin(t * 2.6)), S * (0.92 - 0.58 * t))
soft_line(im, curve(f), S * 0.11, (255, 255, 255), 0.45, 12)
d = ImageDraw.Draw(im)
for k, t in enumerate(np.linspace(0.06, 0.7, 5)):
    x, y = f(t); x2, y2 = f(t + 0.01); ang = math.atan2(y2 - y, x2 - x) + math.pi / 2; side = 1 if k % 2 else -1
    paw(d, x + side * S * 0.028 * math.cos(ang), y + side * S * 0.028 * math.sin(ang), S * 0.034, (232, 92, 160) if k % 2 else (70, 140, 235), ang)
x, y = f(1.0)
lay = Image.new('RGBA', (S, S), (0, 0, 0, 0)); pin(lay, x, S * 0.24, S * 0.12, 'paw', shadow=False)
r, g, b, a = lay.split(); tint = Image.merge('RGBA', (r.point(lambda v: 255), g.point(lambda v: int(v * 0.5 + 40)), b.point(lambda v: int(v * 0.75 + 30)), a))
sh = a.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.3)); im.paste((120, 40, 110, 255), (0, 14), sh)
im.alpha_composite(lay)
opts.append(('4', im))

for k, im in opts: rounded(im).save(os.path.join(out, f'trail_{k}.png'))
W = 4 * 300 + 50; prev = Image.new('RGB', (W, 420), (242, 242, 247)); dp = ImageDraw.Draw(prev)
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 44)
for i, (k, im) in enumerate(opts):
    x = 30 + i * 300; big = rounded(im).resize((240, 240), Image.LANCZOS); prev.paste(big, (x, 30), big)
    sm = rounded(im).resize((96, 96), Image.LANCZOS); prev.paste(sm, (x + 72, 290), sm); dp.text((x, 290), k, fill=(30, 30, 40), font=font)
prev.save(os.path.join(out, 'trail_options.png'))

# ---- the chosen one: 1 + 2 — the trail of pink and blue paws (1) leading up to the pin with bunny ears (2) ----
def final():
    im = grad([(0, (52, 30, 104)), (0.55, (34, 48, 112)), (1, (14, 92, 122))], 0.22)
    glow(im, (S * 0.56, S * 0.34), S * 0.34, PINK, 0.5); glow(im, (S * 0.36, S * 0.88), S * 0.34, BLUE, 0.32)
    f = lambda t: (S * (0.36 + 0.16 * math.sin(t * 3.0 - 0.6) + 0.14 * t), S * (0.95 - 0.5 * t))
    soft_line(im, curve(f), S * 0.1, (255, 255, 255), 0.13, 10)
    d = ImageDraw.Draw(im)
    for k, t in enumerate(np.linspace(0.06, 0.82, 6)):
        x, y = f(t); x2, y2 = f(t + 0.01); ang = math.atan2(y2 - y, x2 - x) + math.pi / 2; side = 1 if k % 2 else -1
        paw(d, x + side * S * 0.03 * math.cos(ang), y + side * S * 0.03 * math.sin(ang), S * (0.028 + 0.012 * t), PINK if k % 2 else BLUE, ang)
    pin(im, S * 0.54, S * 0.36, S * 0.14, 'paw', ears=True)
    return im
if __name__ == '__main__':
    fin = final(); rounded(fin).save(os.path.join(out, 'final.png'))
    fin.convert('RGB').save(os.path.join(out, 'final_square.png'))
