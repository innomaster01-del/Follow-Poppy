"""Follow Poppy launcher icon: a soft pink-to-blue sky (her two colours), a white map pin with two bunny ears, and a
paw print in the pin. Drawn at 4x and scaled down (smooth edges). Writes the adaptive icon layers and the legacy icon.
usage: python3 make_icon.py <res dir> [preview.png]"""
import sys, math
from PIL import Image, ImageDraw, ImageFilter

S = 1728                                              # 4 x 432 (adaptive layer size at xxxhdpi)

def lerp(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))

def background():
    im = Image.new('RGB', (S, S)); px = im.load()
    top, bot = (255, 138, 196), (96, 170, 255)        # pink → blue, diagonal
    for y in range(S):
        for x in range(0, S):
            t = min(1, max(0, (x * 0.35 + y * 0.9) / (S * 1.25)))
            px[x, y] = lerp(top, bot, t)
    # a soft light from the top-left
    glow = Image.new('L', (S, S), 0); ImageDraw.Draw(glow).ellipse((-S * 0.3, -S * 0.45, S * 0.8, S * 0.55), fill=120)
    glow = glow.filter(ImageFilter.GaussianBlur(S * 0.12))
    return Image.composite(Image.new('RGB', (S, S), (255, 255, 255)), im, glow.point(lambda v: int(v * 0.45)))

def pin_mask(cx, cy, r):
    """A map pin (round head, point below) with two rounded bunny ears on top."""
    m = Image.new('L', (S, S), 0); d = ImageDraw.Draw(m)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    tip = cy + r * 1.72
    a = math.radians(40)                                # where the point's sides leave the circle
    d.polygon([(cx - r * math.cos(a), cy + r * math.sin(a)), (cx + r * math.cos(a), cy + r * math.sin(a)), (cx, tip)], fill=255)
    for s in (-1, 1):                                   # ears, tilted outwards
        ear = Image.new('L', (S, S), 0); ImageDraw.Draw(ear).ellipse((cx - r * 0.24, cy - r * 2.0, cx + r * 0.24, cy - r * 0.55), fill=255)
        ear = ear.rotate(-s * 16, center=(cx, cy - r * 0.6), resample=Image.BICUBIC)
        ear = ear.transform(ear.size, Image.AFFINE, (1, 0, -s * r * 0.42, 0, 1, 0), resample=Image.BICUBIC)
        m = Image.fromarray(__import__('numpy').maximum(__import__('numpy').asarray(m), __import__('numpy').asarray(ear)))
    # round the point a little
    return m.filter(ImageFilter.GaussianBlur(S * 0.002)).point(lambda v: 255 if v > 127 else 0)

def foreground():
    fg = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    cx, cy, r = S / 2, S * 0.53, S * 0.135             # inside the adaptive safe zone (middle 66%)
    m = pin_mask(cx, cy, r)
    # shadow
    sh = m.filter(ImageFilter.GaussianBlur(S * 0.018)).point(lambda v: int(v * 0.32))
    fg.paste((40, 30, 90, 255), (0, int(S * 0.012)), sh)
    fg.paste((255, 255, 255, 255), (0, 0), m)
    d = ImageDraw.Draw(fg)
    # ear insides
    for s in (-1, 1):
        inner = Image.new('L', (S, S), 0); ImageDraw.Draw(inner).ellipse((cx - r * 0.11, cy - r * 1.82, cx + r * 0.11, cy - r * 0.95), fill=255)
        inner = inner.rotate(-s * 16, center=(cx, cy - r * 0.6), resample=Image.BICUBIC)
        inner = inner.transform(inner.size, Image.AFFINE, (1, 0, -s * r * 0.42, 0, 1, 0), resample=Image.BICUBIC)
        fg.paste((255, 196, 224, 255) if s < 0 else (196, 224, 255, 255), (0, 0), inner)
    # a paw print in the pin: pink pad, blue toes (both Poppys)
    pr = r * 0.62
    d.ellipse((cx - pr * 0.55, cy - pr * 0.05, cx + pr * 0.55, cy + pr * 0.62), fill=(255, 112, 178, 255))
    for k, (dx, dy) in enumerate([(-0.62, -0.42), (-0.22, -0.72), (0.22, -0.72), (0.62, -0.42)]):
        tr = pr * 0.2
        d.ellipse((cx + dx * pr - tr, cy + dy * pr - tr * 1.1, cx + dx * pr + tr, cy + dy * pr + tr * 1.1), fill=(255, 112, 178, 255) if k < 2 else (82, 156, 255, 255))
    return fg

bg = background(); fg = foreground()
res = sys.argv[1]
for name, size in [('mdpi', 108), ('hdpi', 162), ('xhdpi', 216), ('xxhdpi', 324), ('xxxhdpi', 432)]:
    bg.resize((size, size), Image.LANCZOS).save(f'{res}/mipmap-{name}/ic_launcher_background.png', optimize=True)
    fg.resize((size, size), Image.LANCZOS).save(f'{res}/mipmap-{name}/ic_launcher_foreground.png', optimize=True)
# legacy icon (old launchers): the two layers in a rounded square, the middle 72/108 of the adaptive canvas
full = bg.convert('RGBA'); full.alpha_composite(fg)
crop = full.crop((S * 18 // 108, S * 18 // 108, S * 90 // 108, S * 90 // 108))
mask = Image.new('L', crop.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, crop.width - 1, crop.height - 1), radius=crop.width * 0.22, fill=255)
crop.putalpha(mask)
for name, size in [('mdpi', 48), ('hdpi', 72), ('xhdpi', 96), ('xxhdpi', 144), ('xxxhdpi', 192)]:
    crop.resize((size, size), Image.LANCZOS).save(f'{res}/mipmap-{name}/ic_launcher.png', optimize=True)
if len(sys.argv) > 2:
    prev = Image.new('RGBA', (600, 220), (240, 240, 245, 255))
    for i, s in enumerate([192, 144, 96]):
        prev.alpha_composite(crop.resize((s, s), Image.LANCZOS), (10 + [0, 210, 370][i], 10))
    prev.save(sys.argv[2])
