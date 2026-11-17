"""Follow Poppy brand logo ideas (the app's own logo, not the home-screen icon): transparent PNGs and a preview sheet.
The lettering is Poppins Bold / Medium (SIL Open Font License).
usage: python3 brand_logo.py <out dir> <fonts dir>"""
import sys, math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

out, fonts = sys.argv[1], sys.argv[2]
BOLD = os.path.join(fonts, 'Poppins-Bold.ttf'); MED = os.path.join(fonts, 'Poppins-Medium.ttf')
PINK, BLUE, WHITE = (255, 127, 191), (95, 179, 255), (255, 255, 255)
K = 4                                                    # drawn 4x, scaled down at the end

def canvas(w, h): return Image.new('RGBA', (w * K, h * K), (0, 0, 0, 0))

def paw(d, cx, cy, s, fill, ang=0.0):
    c, sn = math.cos(ang), math.sin(ang)
    def ell(x, y, rx, ry):
        d.polygon([(cx + (x + rx * math.cos(t)) * c - (y + ry * math.sin(t)) * sn, cy + (x + rx * math.cos(t)) * sn + (y + ry * math.sin(t)) * c) for t in np.linspace(0, 2 * math.pi, 36)], fill=fill)
    ell(0, s * 0.25, s * 0.55, s * 0.45)
    for x, y in [(-0.62, -0.38), (-0.22, -0.7), (0.22, -0.7), (0.62, -0.38)]: ell(x * s, y * s, s * 0.2, s * 0.24)

def emblem(im, px, py, pr, body=WHITE, inner=PINK, ear_in=True):
    """The pin with bunny ears and a paw inside (as in the icon)."""
    W, H = im.size; lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for s in (-1, 1):
        e = Image.new('RGBA', (W, H), (0, 0, 0, 0)); de = ImageDraw.Draw(e)
        de.ellipse((px - pr * 0.22, py - pr * 1.9, px + pr * 0.22, py - pr * 0.5), fill=body)
        if ear_in: de.ellipse((px - pr * 0.09, py - pr * 1.72, px + pr * 0.09, py - pr * 0.85), fill=(PINK if s < 0 else BLUE) + (150,))
        e = e.rotate(-s * 16, center=(px, py - pr * 0.6), resample=Image.BICUBIC).transform((W, H), Image.AFFINE, (1, 0, -s * pr * 0.42, 0, 1, 0), resample=Image.BICUBIC)
        lay.alpha_composite(e)
    d = ImageDraw.Draw(lay)
    d.ellipse((px - pr, py - pr, px + pr, py + pr), fill=body)
    a = math.radians(42); d.polygon([(px - pr * math.cos(a), py + pr * math.sin(a)), (px + pr * math.cos(a), py + pr * math.sin(a)), (px, py + pr * 1.7)], fill=body)
    paw(d, px, py + pr * 0.08, pr * 0.5, inner)
    im.alpha_composite(lay)

def gradient_text(im, xy, text, font, c0, c1):
    W, H = im.size; m = Image.new('L', (W, H), 0); ImageDraw.Draw(m).text(xy, text, font=font, fill=255)
    bb = m.getbbox(); g = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    if bb:
        x0, x1 = bb[0], bb[2]; arr = np.zeros((H, W, 4), np.uint8)
        t = np.clip((np.arange(W) - x0) / max(1, x1 - x0), 0, 1)[None, :, None]
        arr[..., :3] = (np.array(c0) + (np.array(c1) - np.array(c0)) * t).astype(np.uint8); arr[..., 3] = 255
        g = Image.fromarray(arr, 'RGBA')
    im.paste(g, (0, 0), m)

def text_w(text, font): return ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), text, font=font)

def finish(im):
    bb = im.getbbox(); im = im.crop((bb[0] - 8 * K, bb[1] - 8 * K, bb[2] + 8 * K, bb[3] + 8 * K))
    return im.resize((im.width // K, im.height // K), Image.LANCZOS)

opts = []
# 1 — the pin beside the name: "Follow" light over a big "Poppy" in pink → blue
im = canvas(900, 300)
emblem(im, 120 * K, 160 * K, 62 * K)
gradient_text(im, (230 * K, 40 * K), 'Follow', ImageFont.truetype(MED, 64 * K), (225, 230, 245), (225, 230, 245))
gradient_text(im, (226 * K, 92 * K), 'Poppy', ImageFont.truetype(BOLD, 132 * K), PINK, BLUE)
opts.append(('1', 'סיכה ליד השם', finish(im)))

# 2 — the name in one line, the "o" of Poppy is the pin with ears, little paws walking under the words
im = canvas(1200, 340); d = ImageDraw.Draw(im); f = ImageFont.truetype(BOLD, 120 * K)
x = 30 * K; y = 90 * K
d.text((x, y), 'Follow P', font=f, fill=WHITE)
bx = d.textbbox((x, y), 'Follow P', font=f)[2]
oc = bx + 46 * K; emblem(im, oc, y + 92 * K, 40 * K, body=PINK, inner=WHITE, ear_in=False)
d = ImageDraw.Draw(im); gradient_text(im, (oc + 44 * K, y), 'ppy', f, PINK, BLUE)
for k in range(7):
    t = k / 6; px = 80 * K + t * 760 * K; py = 262 * K + math.sin(t * math.pi * 2) * 6 * K
    paw(d, px, py + (8 * K if k % 2 else -8 * K), 13 * K, (PINK if k % 2 else BLUE) + (int(90 + 160 * t),), math.pi / 2)
opts.append(('2', 'ה-o היא הסיכה', finish(im)))

# 3 — stacked: the pin, a short trail of paws to it, the name centred under
im = canvas(700, 620); d = ImageDraw.Draw(im)
emblem(im, 350 * K, 190 * K, 78 * K)
d = ImageDraw.Draw(im)
for k, (px, py) in enumerate([(250, 400), (290, 365), (225, 330), (265, 300)]):
    pass
f1 = ImageFont.truetype(BOLD, 96 * K); tw = text_w('Follow Poppy', f1)
x0 = 350 * K - (tw[2] - tw[0]) // 2
d.text((x0, 380 * K), 'Follow ', font=f1, fill=WHITE)
fw = d.textbbox((x0, 380 * K), 'Follow ', font=f1)[2]
gradient_text(im, (fw, 380 * K), 'Poppy', f1, PINK, BLUE)
d = ImageDraw.Draw(im)
for k in range(5):
    paw(d, (290 + k * 30) * K, (530 + (8 if k % 2 else -8)) * K, 11 * K, (PINK if k % 2 else BLUE) + (220,), math.pi / 2)
opts.append(('3', 'סמל מעל השם', finish(im)))

# 4 — a glass capsule: Follow · paws · Poppy, the pin at the end (like a small route)
im = canvas(1150, 260); d = ImageDraw.Draw(im)
d.rounded_rectangle((10 * K, 40 * K, 1060 * K, 220 * K), radius=90 * K, fill=(255, 255, 255, 34), outline=(255, 255, 255, 110), width=3 * K)
f = ImageFont.truetype(BOLD, 90 * K)
d.text((70 * K, 70 * K), 'Follow', font=f, fill=WHITE)
fx = d.textbbox((70 * K, 70 * K), 'Follow', font=f)[2]
for k in range(3): paw(d, fx + (40 + k * 34) * K, (132 + (10 if k % 2 else -10)) * K, 12 * K, PINK if k % 2 else BLUE, math.pi / 2)
gradient_text(im, (fx + 150 * K, 70 * K), 'Poppy', f, PINK, BLUE)
emblem(im, 975 * K, 136 * K, 34 * K)
opts.append(('4', 'קפסולת זכוכית', finish(im)))

for k, he, im in opts: im.save(os.path.join(out, f'brand_{k}.png'))
# preview on the app's night background
H = 1100; prev = Image.new('RGBA', (1000, H), (7, 11, 20, 255)); dp = ImageDraw.Draw(prev)
lab = ImageFont.truetype(BOLD, 40); y = 30
for k, he, im in opts:
    s = min(820 / im.width, 210 / im.height); sm = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    dp.text((30, y + sm.height // 2 - 24), k, font=lab, fill=(150, 160, 180)); prev.alpha_composite(sm, (110, y)); y += sm.height + 60
prev.crop((0, 0, 1000, y)).convert('RGB').save(os.path.join(out, 'brand_options.png'))


# ---------------- more styles ----------------
def more(out, fonts, still):
    LORA_I = os.path.join(fonts, 'Lora-Italic-Variable.ttf'); LIGHT = os.path.join(fonts, 'Poppins-Light.ttf')
    res = []
    # 5 — mascot: Poppy herself (3D) peeking from behind the name, sticker letters with a white outline
    im = canvas(1000, 420); d = ImageDraw.Draw(im)
    p = Image.open(still).convert('RGBA'); k = 330 * K / p.height; p = p.resize((int(p.width * k), int(p.height * k)), Image.LANCZOS)
    im.alpha_composite(p, (int(560 * K), int(60 * K)))
    f = ImageFont.truetype(BOLD, 128 * K)
    for txt, (x, y), cols in [('Follow', (40, 60), (WHITE, WHITE)), ('Poppy', (40, 200), (PINK, BLUE))]:
        m = Image.new('L', im.size, 0); ImageDraw.Draw(m).text((x * K, y * K), txt, font=f, fill=255)
        sh = m.filter(ImageFilter.MaxFilter(1 + 2 * 7 * K // 2 * 2 - 1 if False else 29))
        im.paste((40, 30, 80, 200), (6 * K, 10 * K), sh.filter(ImageFilter.GaussianBlur(6 * K)))
        im.paste((255, 255, 255, 255) if cols[0] != WHITE else (60, 44, 110, 255), (0, 0), sh)
        if cols[0] == WHITE: im.paste((255, 255, 255, 255), (0, 0), m)
        else: gradient_text(im, (x * K, y * K), txt, f, *cols)
    res.append(('5', finish(im)))
    # 6 — elegant: "Follow" in italic serif, "Poppy" bold, a thin route line with a pin at the end under them
    im = canvas(1000, 380); d = ImageDraw.Draw(im)
    d.text((60 * K, 40 * K), 'Follow', font=ImageFont.truetype(LORA_I, 100 * K), fill=(235, 236, 245))
    gradient_text(im, (395 * K, 30 * K), 'Poppy', ImageFont.truetype(BOLD, 120 * K), PINK, BLUE)
    d = ImageDraw.Draw(im)
    pts = [(70 * K + t * 760 * K, 270 * K + math.sin(t * math.pi * 1.5) * 18 * K) for t in np.linspace(0, 1, 60)]
    for i in range(0, len(pts) - 1, 2): d.line([pts[i], pts[i + 1]], fill=(255, 255, 255, 170), width=6 * K)
    emblem(im, 860 * K, 228 * K, 34 * K)
    res.append(('6', finish(im)))
    # 7 — minimal, lowercase and light, the dot of a paw for the "o" in follow and the pin for the last letter
    im = canvas(1100, 260); d = ImageDraw.Draw(im); f = ImageFont.truetype(LIGHT, 120 * K)
    d.text((30 * K, 40 * K), 'follow', font=f, fill=WHITE)
    x = d.textbbox((30 * K, 40 * K), 'follow ', font=f)[2]
    gradient_text(im, (x, 40 * K), 'poppy', f, PINK, BLUE)
    x2 = d.textbbox((x, 40 * K), 'poppy', font=f)[2]
    emblem(im, x2 + 50 * K, 122 * K, 32 * K)
    res.append(('7', finish(im)))
    # 8 — round badge: the 3D Poppy in a glowing circle, the name around it
    S8 = 700; im = canvas(S8, S8); c = S8 * K / 2; d = ImageDraw.Draw(im)
    g = Image.new('L', im.size, 0); ImageDraw.Draw(g).ellipse((c - 250 * K, c - 250 * K, c + 250 * K, c + 250 * K), fill=255)
    arr = np.zeros((S8 * K, S8 * K, 4), np.uint8); yy, xx = np.mgrid[0:S8 * K, 0:S8 * K]; t = np.clip((xx + yy) / (2 * S8 * K), 0, 1)[..., None]
    arr[..., :3] = (np.array((255, 160, 210)) + (np.array((120, 180, 255)) - np.array((255, 160, 210))) * t).astype(np.uint8); arr[..., 3] = 255
    im.paste(Image.fromarray(arr, 'RGBA'), (0, 0), g)
    d.ellipse((c - 250 * K, c - 250 * K, c + 250 * K, c + 250 * K), outline=(255, 255, 255, 230), width=8 * K)
    p = Image.open(still).convert('RGBA'); k = 400 * K / p.height; p = p.resize((int(p.width * k), int(p.height * k)), Image.LANCZOS)
    im.alpha_composite(p, (int(c - p.width / 2), int(c - p.height / 2 + 10 * K)))
    f = ImageFont.truetype(BOLD, 52 * K)
    for word, a0, a1 in [('FOLLOW', 232, 308), ('POPPY', 125, 55)]:
        n = len(word)
        for i, ch in enumerate(word):
            a = math.radians(a0 + (a1 - a0) * (i + 0.5) / n); r = 292 * K
            cx, cy = c + r * math.cos(a), c + r * math.sin(a)
            L = Image.new('RGBA', (90 * K, 90 * K), (0, 0, 0, 0)); ImageDraw.Draw(L).text((45 * K, 45 * K), ch, font=f, fill=WHITE, anchor='mm')
            rot = -math.degrees(a) - 90 if a1 > a0 else -math.degrees(a) + 90
            L = L.rotate(rot, resample=Image.BICUBIC); im.alpha_composite(L, (int(cx - 45 * K), int(cy - 45 * K)))
    for s in (-1, 1): paw(d, c + s * 300 * K, c, 18 * K, PINK if s < 0 else BLUE, math.pi / 2)
    res.append(('8', finish(im)))
    for k, im in res: im.save(os.path.join(out, f'brand_{k}.png'))
    H = 1600; prev = Image.new('RGBA', (1000, H), (7, 11, 20, 255)); dp = ImageDraw.Draw(prev); lab = ImageFont.truetype(BOLD, 40); y = 30
    for k, im in res:
        s = min(820 / im.width, 300 / im.height); sm = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
        dp.text((30, y + sm.height // 2 - 24), k, font=lab, fill=(150, 160, 180)); prev.alpha_composite(sm, (110, y)); y += sm.height + 60
    prev.crop((0, 0, 1000, y)).convert('RGB').save(os.path.join(out, 'brand_options2.png'))

if len(sys.argv) > 3: more(out, fonts, sys.argv[3])


# ---------------- just "Poppy" ----------------
def only_poppy(out, fonts, still):
    res = []
    # a — the pin and the name
    im = canvas(800, 300); emblem(im, 110 * K, 160 * K, 62 * K)
    gradient_text(im, (215 * K, 60 * K), 'Poppy', ImageFont.truetype(BOLD, 150 * K), PINK, BLUE); res.append(('a', finish(im)))
    # b — the "o" is the pin with ears
    im = canvas(900, 320); d = ImageDraw.Draw(im); f = ImageFont.truetype(BOLD, 150 * K)
    d.text((30 * K, 70 * K), 'P', font=f, fill=WHITE); bx = d.textbbox((30 * K, 70 * K), 'P', font=f)[2]
    oc = bx + 56 * K; emblem(im, oc, 70 * K + 118 * K, 50 * K, body=PINK, inner=WHITE, ear_in=False)
    gradient_text(im, (oc + 54 * K, 70 * K), 'ppy', f, PINK, BLUE); res.append(('b', finish(im)))
    # c — Poppy herself with sticker letters
    im = canvas(900, 400)
    p = Image.open(still).convert('RGBA'); k = 330 * K / p.height; p = p.resize((int(p.width * k), int(p.height * k)), Image.LANCZOS)
    im.alpha_composite(p, (int(560 * K), int(40 * K)))
    f = ImageFont.truetype(BOLD, 150 * K); m = Image.new('L', im.size, 0); ImageDraw.Draw(m).text((30 * K, 100 * K), 'Poppy', font=f, fill=255)
    sh = m.filter(ImageFilter.MaxFilter(29))
    im.paste((40, 30, 80, 200), (6 * K, 10 * K), sh.filter(ImageFilter.GaussianBlur(6 * K))); im.paste((255, 255, 255, 255), (0, 0), sh)
    gradient_text(im, (30 * K, 100 * K), 'Poppy', f, PINK, BLUE); res.append(('c', finish(im)))
    # d — round badge with POPPY around the top
    S8 = 640; im = canvas(S8, S8); c = S8 * K / 2; d = ImageDraw.Draw(im)
    g = Image.new('L', im.size, 0); ImageDraw.Draw(g).ellipse((c - 240 * K, c - 240 * K, c + 240 * K, c + 240 * K), fill=255)
    yy, xx = np.mgrid[0:S8 * K, 0:S8 * K]; t = np.clip((xx + yy) / (2 * S8 * K), 0, 1)[..., None]
    arr = np.zeros((S8 * K, S8 * K, 4), np.uint8); arr[..., :3] = (np.array((255, 160, 210)) + (np.array((120, 180, 255)) - np.array((255, 160, 210))) * t).astype(np.uint8); arr[..., 3] = 255
    im.paste(Image.fromarray(arr, 'RGBA'), (0, 0), g); d.ellipse((c - 240 * K, c - 240 * K, c + 240 * K, c + 240 * K), outline=(255, 255, 255, 230), width=8 * K)
    p = Image.open(still).convert('RGBA'); k = 380 * K / p.height; p = p.resize((int(p.width * k), int(p.height * k)), Image.LANCZOS)
    im.alpha_composite(p, (int(c - p.width / 2), int(c - p.height / 2 + 10 * K)))
    f = ImageFont.truetype(BOLD, 58 * K)
    for i, ch in enumerate('POPPY'):
        a = math.radians(236 + 68 * (i + 0.5) / 5); r = 282 * K; cx, cy = c + r * math.cos(a), c + r * math.sin(a)
        L = Image.new('RGBA', (90 * K, 90 * K), (0, 0, 0, 0)); ImageDraw.Draw(L).text((45 * K, 45 * K), ch, font=f, fill=WHITE, anchor='mm')
        im.alpha_composite(L.rotate(-math.degrees(a) - 90, resample=Image.BICUBIC), (int(cx - 45 * K), int(cy - 45 * K)))
    res.append(('d', finish(im)))
    for k, im in res: im.save(os.path.join(out, f'brand_{k}.png'))
    prev = Image.new('RGBA', (1000, 1500), (7, 11, 20, 255)); dp = ImageDraw.Draw(prev); lab = ImageFont.truetype(BOLD, 40); y = 30
    for k, im in res:
        s = min(700 / im.width, 280 / im.height); sm = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
        dp.text((30, y + sm.height // 2 - 24), k.upper(), font=lab, fill=(150, 160, 180)); prev.alpha_composite(sm, (110, y)); y += sm.height + 60
    prev.crop((0, 0, 1000, y)).convert('RGB').save(os.path.join(out, 'brand_poppy.png'))

if len(sys.argv) > 4: only_poppy(out, fonts, sys.argv[3])
