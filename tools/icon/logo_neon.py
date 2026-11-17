"""The app's logo, drawn cleanly (no haze): Poppy's emblem (the white pin with bunny ears and the paw pressed into it),
standing on a neon ring, a neon route curving away from it to a glowing pink pin. Transparent PNG.
usage: python3 logo_neon.py <out.png> [preview.png]"""
import sys, math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emblem import emblem

K = 3; W, H = 1100 * K, 860 * K
im = Image.new('RGBA', (W, H), (0, 0, 0, 0))

def glow_stroke(pts, layers):
    """Neon: several strokes, widest and softest first (blurred as masks, so the glow never darkens)."""
    for width, color, alpha, blur in layers:
        m = Image.new('L', (W, H), 0); d = ImageDraw.Draw(m)
        d.line(pts, fill=255, width=int(width), joint='curve')
        for p in (pts[0], pts[-1]):
            r = width / 2; d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=255)
        if blur: m = m.filter(ImageFilter.GaussianBlur(blur))
        im.paste(color + (255,), (0, 0), m.point(lambda v: int(v * alpha)))

NEON = [(70 * K, (60, 140, 255), 0.32, 30 * K), (44 * K, (35, 130, 255), 0.85, 14 * K), (18 * K, (60, 210, 255), 1.0, 3 * K), (6 * K, (225, 250, 255), 1.0, 0)]

# the route: from the ring under the pin, right and up in an S, to the pink pin
ring_c = (420 * K, 760 * K)
def route(t):
    # a smooth S built from two half-loops
    p0 = (ring_c[0] + 70 * K, ring_c[1] - 10 * K); p3 = (885 * K, 420 * K)
    x = p0[0] + (p3[0] - p0[0]) * t + 150 * K * math.sin(t * 2 * math.pi) * (1 - t * 0.3)
    y = p0[1] + (p3[1] - p0[1]) * t - 40 * K * math.sin(t * math.pi)
    return (x, y)
pts = [route(t) for t in np.linspace(0, 1, 160)]
glow_stroke(pts, NEON)
# the ring the pin stands on (an ellipse lying on the ground)
ring = [(ring_c[0] + 120 * K * math.cos(a), ring_c[1] + 30 * K * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 120)]
glow_stroke(ring, NEON)

# the pink destination pin, glossy, with a pink glow
px, py, pr = 885 * K, 300 * K, 62 * K
g = Image.new('L', (W, H), 0); ImageDraw.Draw(g).ellipse((px - pr * 2.2, py - pr * 2.2, px + pr * 2.2, py + pr * 2.2), fill=150)
im.paste((255, 40, 140, 255), (0, 0), g.filter(ImageFilter.GaussianBlur(pr * 0.9)))
pin = Image.new('L', (W, H), 0); d = ImageDraw.Draw(pin)
d.ellipse((px - pr, py - pr, px + pr, py + pr), fill=255)
a = math.radians(40); d.polygon([(px - pr * math.cos(a), py + pr * math.sin(a)), (px + pr * math.cos(a), py + pr * math.sin(a)), (px, py + pr * 1.8)], fill=255)
yy, xx = np.mgrid[0:H, 0:W]; t = np.clip((yy - (py - pr)) / (pr * 2.8), 0, 1)
grad = np.zeros((H, W, 4), np.uint8); grad[..., 0] = 255; grad[..., 1] = (110 - 80 * t).astype(np.uint8); grad[..., 2] = (190 - 60 * t).astype(np.uint8); grad[..., 3] = 255
im.paste(Image.fromarray(grad, 'RGBA'), (0, 0), pin)
d2 = ImageDraw.Draw(im)
d2.ellipse((px - pr * 0.42, py - pr * 0.42, px + pr * 0.42, py + pr * 0.42), fill=(200, 30, 110, 255))
d2.ellipse((px - pr * 0.3, py - pr * 0.3, px + pr * 0.3, py + pr * 0.3), fill=(245, 70, 150, 255))
hl = Image.new('L', (W, H), 0); ImageDraw.Draw(hl).ellipse((px - pr * 0.75, py - pr * 0.85, px + pr * 0.1, py - pr * 0.2), fill=110)
im.paste((255, 255, 255, 255), (0, 0), ImageChops_mult := hl.filter(ImageFilter.GaussianBlur(pr * 0.15)))

# Poppy's emblem standing on the ring (its point on the ring's centre)
em = emblem(1000, shadow=False)
eh = 720 * K; ew = int(em.width * eh / em.height); em = em.resize((ew, eh), Image.LANCZOS)
# a soft white aura only right around it (tight, not a haze)
aura = em.split()[3].filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(10 * K)).point(lambda v: int(v * 0.18))
ax, ay = ring_c[0] - ew // 2, ring_c[1] - eh + 8 * K
im.paste((235, 240, 255, 255), (ax, ay), aura)
im.alpha_composite(em, (ax, ay))

out = im.crop(im.getbbox()); out = out.resize((out.width // K, out.height // K), Image.LANCZOS)
out.save(sys.argv[1], optimize=True)
if len(sys.argv) > 2:
    c = Image.new('RGBA', (out.width * 2 + 120, out.height + 80), (7, 11, 20, 255)); c.paste((90, 90, 100, 255), (out.width + 80, 0, out.width * 2 + 120, out.height + 80))
    c.alpha_composite(out, (40, 40)); c.alpha_composite(out, (out.width + 80, 40)); c.convert('RGB').resize((c.width // 2, c.height // 2)).save(sys.argv[2])
