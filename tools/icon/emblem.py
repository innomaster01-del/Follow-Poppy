"""Poppy's emblem: the white map pin with bunny ears, the paw print pressed into it in soft grey (looks 3D), the pin
itself softly shaded. Writes transparent PNGs: the emblem alone and with the name, plus a preview on the app's night.
usage: python3 emblem.py <out dir> <fonts dir>"""
import sys, math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageFont

K = 4; PINK, BLUE = (255, 127, 191), (95, 179, 255)

def paw_mask(W, H, cx, cy, s):
    m = Image.new('L', (W, H), 0); d = ImageDraw.Draw(m)
    d.ellipse((cx - s * 0.55, cy + s * 0.25 - s * 0.45, cx + s * 0.55, cy + s * 0.25 + s * 0.45), fill=255)
    for x, y in [(-0.62, -0.38), (-0.22, -0.7), (0.22, -0.7), (0.62, -0.38)]:
        d.ellipse((cx + x * s - s * 0.2, cy + y * s - s * 0.24, cx + x * s + s * 0.2, cy + y * s + s * 0.24), fill=255)
    return m

def shift(m, dx, dy): return ImageChops.offset(m, int(dx), int(dy))

def emblem(size=600, shadow=True):
    W = H = size * K; px, py, pr = W / 2, H * 0.58, W * 0.25
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    # silhouette: ears + round head + point
    body = Image.new('L', (W, H), 0); d = ImageDraw.Draw(body)
    ears = []
    for s in (-1, 1):
        e = Image.new('L', (W, H), 0); ImageDraw.Draw(e).ellipse((px - pr * 0.22, py - pr * 1.9, px + pr * 0.22, py - pr * 0.5), fill=255)
        e = e.rotate(-s * 16, center=(px, py - pr * 0.6), resample=Image.BICUBIC).transform((W, H), Image.AFFINE, (1, 0, -s * pr * 0.42, 0, 1, 0), resample=Image.BICUBIC)
        ears.append(e); body = ImageChops.lighter(body, e)
    d = ImageDraw.Draw(body); d.ellipse((px - pr, py - pr, px + pr, py + pr), fill=255)
    a = math.radians(42); d.polygon([(px - pr * math.cos(a), py + pr * math.sin(a)), (px + pr * math.cos(a), py + pr * math.sin(a)), (px, py + pr * 1.7)], fill=255)
    # soft drop shadow
    if shadow:
        sh = body.filter(ImageFilter.GaussianBlur(pr * 0.12)).point(lambda v: int(v * 0.45))
        im.paste((10, 6, 30, 255), (0, int(pr * 0.08)), sh)
    # the pin: white, a touch of grey towards the lower right (light from the top left)
    yy, xx = np.mgrid[0:H, 0:W]; t = np.clip(((xx - (px - pr)) + (yy - (py - pr))) / (4 * pr), 0, 1)
    shade = np.zeros((H, W, 4), np.uint8); c = (255 - 30 * t ** 1.5); shade[..., 0] = c; shade[..., 1] = c; shade[..., 2] = (c + 4 * t).clip(0, 255); shade[..., 3] = 255
    im.paste(Image.fromarray(shade, 'RGBA'), (0, 0), body)
    # ear insides: pink and blue (the two Poppys)
    for e, col, s in zip(ears, (PINK, BLUE), (-1, 1)):
        inn = Image.new('L', (W, H), 0); ImageDraw.Draw(inn).ellipse((px - pr * 0.09, py - pr * 1.72, px + pr * 0.09, py - pr * 0.85), fill=255)
        inn = inn.rotate(-s * 16, center=(px, py - pr * 0.6), resample=Image.BICUBIC).transform((W, H), Image.AFFINE, (1, 0, -s * pr * 0.42, 0, 1, 0), resample=Image.BICUBIC)
        im.paste(col + (255,), (0, 0), inn.point(lambda v: int(v * 0.85)))
    # the paw, pressed in: soft grey, a shadow on its upper-left inner edge, light on the lower-right edge
    m = paw_mask(W, H, px, py + pr * 0.08, pr * 0.5); dd = pr * 0.035
    im.paste((206, 210, 220, 255), (0, 0), m)
    inner_sh = ImageChops.subtract(m, shift(m, dd, dd)).filter(ImageFilter.GaussianBlur(dd * 0.9))
    im.paste((120, 124, 140, 255), (0, 0), ImageChops.multiply(inner_sh, m).point(lambda v: min(255, int(v * 1.6))))
    rim_light = ImageChops.subtract(shift(m, dd * 0.8, dd * 0.8), m).filter(ImageFilter.GaussianBlur(dd * 0.6))
    im.paste((255, 255, 255, 255), (0, 0), rim_light)
    rim_dark = ImageChops.subtract(shift(m, -dd * 0.6, -dd * 0.6), m).filter(ImageFilter.GaussianBlur(dd * 0.6))
    im.paste((160, 164, 178, 255), (0, 0), rim_dark.point(lambda v: int(v * 0.7)))
    bb = im.getbbox(); im = im.crop(bb)
    return im.resize((im.width // K, im.height // K), Image.LANCZOS)

def gradient_text(text, font, c0, c1):
    d0 = ImageDraw.Draw(Image.new('L', (1, 1))); bb = d0.textbbox((0, 0), text, font=font)
    W, H = bb[2] - bb[0] + 8, bb[3] - bb[1] + 8
    m = Image.new('L', (W, H), 0); ImageDraw.Draw(m).text((-bb[0] + 4, -bb[1] + 4), text, font=font, fill=255)
    t = np.linspace(0, 1, W)[None, :, None]; arr = np.zeros((H, W, 4), np.uint8)
    arr[..., :3] = (np.array(c0) + (np.array(c1) - np.array(c0)) * t).astype(np.uint8); arr[..., 3] = np.asarray(m)
    return Image.fromarray(arr, 'RGBA')

if __name__ == '__main__':
    out, fonts = sys.argv[1], sys.argv[2]
    em = emblem(); em.save(os.path.join(out, 'emblem.png'))
    bold = ImageFont.truetype(os.path.join(fonts, 'Poppins-Bold.ttf'), 150)
    word = gradient_text('Poppy', bold, PINK, BLUE)
    # with the name beside it
    e2 = em.resize((int(em.width * 300 / em.height), 300), Image.LANCZOS)
    row = Image.new('RGBA', (e2.width + 40 + word.width, 300), (0, 0, 0, 0)); row.alpha_composite(e2, (0, 0)); row.alpha_composite(word, (e2.width + 40, 300 - word.height - 40))
    row.save(os.path.join(out, 'emblem_name.png'))
    # stacked: emblem over the name
    e3 = em.resize((int(em.width * 320 / em.height), 320), Image.LANCZOS); w3 = max(e3.width, word.width)
    col = Image.new('RGBA', (w3, 320 + 20 + word.height), (0, 0, 0, 0)); col.alpha_composite(e3, ((w3 - e3.width) // 2, 0)); col.alpha_composite(word, ((w3 - word.width) // 2, 340))
    col.save(os.path.join(out, 'emblem_stacked.png'))
    prev = Image.new('RGBA', (1400, 520), (7, 11, 20, 255))
    prev.alpha_composite(em.resize((int(em.width * 420 / em.height), 420), Image.LANCZOS), (40, 50))
    prev.alpha_composite(row.resize((int(row.width * 0.75), int(row.height * 0.75)), Image.LANCZOS), (380, 60))
    prev.alpha_composite(col.resize((int(col.width * 0.62), int(col.height * 0.62)), Image.LANCZOS), (1000, 120))
    prev.convert('RGB').save(os.path.join(out, 'emblem_preview.png'))
    big = Image.new('RGBA', (700, 760), (7, 11, 20, 255)); big.alpha_composite(em.resize((int(em.width * 700 / em.height), 700), Image.LANCZOS), (int(350 - em.width * 700 / em.height / 2), 30)); big.convert('RGB').save(os.path.join(out, 'emblem_big.png'))
