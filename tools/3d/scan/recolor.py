"""The two versions of the bunny from one picture: only the colours change. The girl: both inner ears and the chest
emblem pink; the boy: both blue. The eyes stay as they are (blue), and so do the nose and the mouth: only the ears
(above the eyes) and the emblem (below the chin) are recoloured.
    python3 recolor.py <picture> <girl.png> <boy.png>"""
import sys, numpy as np
from PIL import Image
from scipy import ndimage

PINK_HUE, BLUE_HUE = 0.93, 0.585   # (0..1)

def hsv(a):
    import colorsys
    return np.vectorize(colorsys.rgb_to_hsv)(a[..., 0], a[..., 1], a[..., 2])

def recolor(im, to_pink):
    a = np.asarray(im.convert('RGB')).astype(float) / 255
    mx = a.max(2); mn = a.min(2); d = mx - mn; s = np.where(mx > 0, d / np.maximum(mx, 1e-9), 0)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    h = np.zeros_like(mx)
    m = d > 1e-9
    rc = np.where(m, (mx - r) / np.maximum(d, 1e-9), 0); gc = np.where(m, (mx - g) / np.maximum(d, 1e-9), 0); bc = np.where(m, (mx - b) / np.maximum(d, 1e-9), 0)
    h = np.where(r == mx, bc - gc, np.where(g == mx, 2 + rc - bc, 4 + gc - rc)); h = (h / 6) % 1
    pinkish0 = (s > 0.09) & ((h > 0.78) | (h < 0.04)); bluish0 = (s > 0.09) & (h > 0.47) & (h < 0.75)
    pinkish = (s > 0.22) & ((h > 0.78) | (h < 0.04))
    bluish = (s > 0.22) & (h > 0.47) & (h < 0.75)
    # protect the eyes (blue, they stay) and the nose / mouth / tongue (pink, they stay): found from the dark pupils
    H, W = mx.shape
    dark = mx < 0.22
    lab, n = ndimage.label(dark); sizes = ndimage.sum(dark, lab, range(1, n + 1))
    objs = sorted([o for sz, o in zip(sizes, ndimage.find_objects(lab)) if sz > 120 and o[0].start < H * 0.6], key=lambda o: -(o[0].stop - o[0].start) * (o[1].stop - o[1].start))[:2]
    keep = np.zeros((H, W), bool)
    yy, xx = np.mgrid[0:H, 0:W]
    if objs:
        cs = [((o[1].start + o[1].stop) / 2, (o[0].start + o[0].stop) / 2, max(o[1].stop - o[1].start, o[0].stop - o[0].start)) for o in objs]
        for cx, cy, sz in cs: keep |= (xx - cx) ** 2 + (yy - cy) ** 2 < (sz * 1.1) ** 2          # the eye with its blue iris
        top = min(cy for _, cy, _ in cs); size = max(sz for *_, sz in cs)
        x0 = min(cx for cx, _, _ in cs) - size * 0.6; x1 = max(cx for cx, _, _ in cs) + size * 0.6
        if len(cs) == 1: x0, x1 = cs[0][0] - size * 2.5, cs[0][0] + size * 2.5
        keep |= (yy > top + size * 0.2) & (yy < top + size * 2.0) & (xx > x0) & (xx < x1)   # nose, mouth, tongue, cheeks
    src = (bluish if to_pink else pinkish) & ~keep
    # only the ears (above the eyes) and the emblem (the biggest coloured patch below the face); not the coloured rim
    # light along the body's edges
    if objs:
        ears = ((bluish0 if to_pink else pinkish0) & ~keep) & (yy < top - size * 0.3)       # the ears: even their pale parts
        below = src & (yy > top + size * 1.2)
        lab2, n2 = ndimage.label(ndimage.binary_closing(below, iterations=2))
        emblem = np.zeros_like(src)
        if n2:
            # the emblem: a solid, strongly coloured patch (the rim light is a faint thin strip)
            sz2 = ndimage.sum(below, lab2, range(1, n2 + 1)); sat2 = ndimage.mean(s, lab2, range(1, n2 + 1))
            score = np.where(sz2 > 150, sat2 ** 3 * np.sqrt(sz2), 0)
            emblem = (lab2 == (np.argmax(score) + 1)) & below
            emblem = ndimage.binary_dilation(emblem, iterations=2) & (bluish if to_pink else pinkish)
        src = ears | emblem
    nh = PINK_HUE if to_pink else BLUE_HUE
    # rebuild colour with the new hue, same saturation and value
    v = mx
    i = np.floor(nh * 6); f = nh * 6 - i; p = v * (1 - s); q = v * (1 - s * f); t = v * (1 - s * (1 - f)); i = int(i) % 6
    out = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]
    new = np.stack(out, -1)
    a2 = np.where(src[..., None], new, a)
    return Image.fromarray((np.clip(a2, 0, 1) * 255).astype(np.uint8))

if __name__ == '__main__':
    im = Image.open(sys.argv[1])
    recolor(im, True).save(sys.argv[2]); recolor(im, False).save(sys.argv[3])


GREEN_HUE = 0.37

def green_eyes(im):
    """Her eyes green (his stay blue): the blue of the irises, only inside the eyes (found from the dark pupils)."""
    a = np.asarray(im.convert('RGB')).astype(float) / 255
    mx = a.max(2); mn = a.min(2); d = mx - mn; s = np.where(mx > 0, d / np.maximum(mx, 1e-9), 0)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = d > 1e-9
    rc = np.where(m, (mx - r) / np.maximum(d, 1e-9), 0); gc = np.where(m, (mx - g) / np.maximum(d, 1e-9), 0); bc = np.where(m, (mx - b) / np.maximum(d, 1e-9), 0)
    h = np.where(r == mx, bc - gc, np.where(g == mx, 2 + rc - bc, 4 + gc - rc)); h = (h / 6) % 1
    H, W = mx.shape
    dark = mx < 0.22
    lab, n = ndimage.label(dark); sizes = ndimage.sum(dark, lab, range(1, n + 1))
    objs = sorted([o for sz, o in zip(sizes, ndimage.find_objects(lab)) if sz > 120 and o[0].start < H * 0.6], key=lambda o: -(o[0].stop - o[0].start) * (o[1].stop - o[1].start))[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    eye = np.zeros((H, W), bool)
    for o in objs:
        cx = (o[1].start + o[1].stop) / 2; cy = (o[0].start + o[0].stop) / 2; sz = max(o[1].stop - o[1].start, o[0].stop - o[0].start)
        eye |= (xx - cx) ** 2 + (yy - cy) ** 2 < (sz * 0.72) ** 2
    src = eye & (s > 0.3) & (h > 0.45) & (h < 0.75)
    v = mx; nh = GREEN_HUE
    i = int(np.floor(nh * 6)) % 6; f = nh * 6 - np.floor(nh * 6)
    p = v * (1 - s); q = v * (1 - s * f); t = v * (1 - s * (1 - f))
    new = np.stack([(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i], -1)
    out = np.where(src[..., None], new, a)
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))
