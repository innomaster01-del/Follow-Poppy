"""Paint a shape from pictures of the character seen from the front, the right side and the back (the left is the right
mirrored): each point takes the colour of the pictures that see it, weighted by how squarely they see it."""
import sys, numpy as np
from PIL import Image
from mesh import load, normals

def mask_box(a):
    m = (np.abs(a.astype(int) - 255).sum(2) > 45)
    rows = np.where(m.sum(1) > 2)[0]; cols = np.where(m.sum(0) > 2)[0]
    return cols[0], cols[-1], rows[0], rows[-1]

EAR_Y = 0.5
def paint(P, F, pics):
    N = normals(P, F)
    # views: (picture, view direction towards camera, image-right axis)
    views = [(pics['front'], np.array([0,0,1.]), np.array([1,0,0.]))] + ([(pics['back'], np.array([0,0,-1.]), np.array([-1,0,0.]))] if pics.get('back') is not None else []) + [
             (pics['right'], np.array([-1,0,0.]), np.array([0,0,1.])), (np.asarray(pics['right'])[:, ::-1], np.array([1,0,0.]), np.array([0,0,-1.]))]
    acc = np.zeros((len(P), 3)); wsum = np.zeros(len(P))
    for img, d, r in views:
        a = np.asarray(img).astype(np.float64)
        x0, x1, y0, y1 = mask_box(np.asarray(img))
        u = P @ r; v = P[:, 1]; z = P @ d
        # fit the shape's outline to the picture's
        X = x0 + (u - u.min()) / (u.max() - u.min()) * (x1 - x0)
        Y = y1 - (v - v.min()) / (v.max() - v.min()) * (y1 - y0)
        H, W = a.shape[:2]
        xi = np.clip(X.round().astype(int), 0, W - 1); yi = np.clip(Y.round().astype(int), 0, H - 1)
        # what this picture can see: the nearest surface at each pixel (a coarse depth map)
        k = 4; zb = np.full((H // k + 2, W // k + 2), -1e9)
        np.maximum.at(zb, (yi // k, xi // k), z)
        zmax = np.maximum.reduce([np.roll(np.roll(zb, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
        vis = z > zmax[yi // k, xi // k] - 0.03
        w = np.clip(N @ d, 0, 1) ** 3 * vis
        x0f = np.floor(X).astype(int).clip(0, W - 2); y0f = np.floor(Y).astype(int).clip(0, H - 2); fx = (X - x0f).clip(0, 1)[:, None]; fy = (Y - y0f).clip(0, 1)[:, None]
        col = (a[y0f, x0f] * (1 - fx) * (1 - fy) + a[y0f, x0f + 1] * fx * (1 - fy) + a[y0f + 1, x0f] * (1 - fx) * fy + a[y0f + 1, x0f + 1] * fx * fy) / 255
        # the white background is not a colour of the character: points that land on it get no say from this picture
        bg = (col.min(1) > 0.97) & (N @ d < 0.5)
        w = w * ~bg
        # the backs of the ears are fur colour (only the inside of the ear is coloured): there only the back picture counts
        earBack = (P[:, 1] > EAR_Y) & (N[:, 2] < 0.05)
        if d[2] > -0.5: w = w * ~earBack
        acc += col * w[:, None]; wsum += w
    C = np.where(wsum[:, None] > 1e-6, acc / np.maximum(wsum, 1e-9)[:, None], np.nan)
    # points no picture sees: their neighbours' colour
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]); E = np.concatenate([E, E[:, ::-1]])
    for _ in range(60):
        miss = np.isnan(C[:, 0])
        if not miss.any(): break
        s = np.zeros_like(C); c = np.zeros(len(C)); ok = ~np.isnan(C[E[:, 1], 0])
        np.add.at(s, E[ok, 0], C[E[ok, 1]]); np.add.at(c, E[ok, 0], 1)
        fill = miss & (c > 0); C[fill] = s[fill] / c[fill][:, None]
    C[np.isnan(C)] = 0.95
    return C
