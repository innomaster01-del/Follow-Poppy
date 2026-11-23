"""A real texture for the model, baked texel by texel (instead of each triangle taking one picture): the surface is cut
into charts (pieces facing mostly one way), laid out flat in a square texture, and every texel takes a smooth blend
of the pictures that see that point squarely (front, right side, left = right mirrored), plain fur where none does.
No jagged edges where one picture hands over to another, and the texture's sharpness no longer depends on the size
of the triangles.

bake(V, G, ref, pics, size, rules) → (V2, G2, UV, texture image, vid)   (vertices are split along chart edges)
"""
import numpy as np
from PIL import Image
from scipy import ndimage
from mesh import normals
from raster import raster_xy

AXES = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float)
VIEWS = [('front', np.array([0, 0, 1.]), np.array([1, 0, 0.])), ('right', np.array([-1, 0, 0.]), np.array([0, 0, 1.])),
         ('left', np.array([1, 0, 0.]), np.array([0, 0, -1.]))]
FUR = np.array([0.95, 0.945, 0.94])


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)


def mask_box(a):
    m = (np.abs(a.astype(int) - 255).sum(2) > 45)
    rows = np.where(m.sum(1) > 2)[0]; cols = np.where(m.sum(0) > 2)[0]
    return cols[0], cols[-1], rows[0], rows[-1]


def charts(V, G):
    FN = np.cross(V[G[:, 1]] - V[G[:, 0]], V[G[:, 2]] - V[G[:, 0]]); FN /= np.linalg.norm(FN, axis=1, keepdims=True) + 1e-12
    lab = np.argmax(FN @ AXES.T, 1)
    # face adjacency through shared edges
    E = np.concatenate([G[:, [0, 1]], G[:, [1, 2]], G[:, [2, 0]]]); fid = np.tile(np.arange(len(G)), 3)
    key = np.minimum(E[:, 0], E[:, 1]).astype(np.int64) * len(V) + np.maximum(E[:, 0], E[:, 1])
    order = np.argsort(key); k = key[order]; f = fid[order]
    same = k[1:] == k[:-1]
    adj = np.stack([f[1:][same], f[:-1][same]], 1)
    # small islands of one direction join their neighbours (fewer, bigger charts)
    for _ in range(3):
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        ok = lab[adj[:, 0]] == lab[adj[:, 1]]
        a = adj[ok]
        n, comp = connected_components(coo_matrix((np.ones(len(a)), (a[:, 0], a[:, 1])), shape=(len(G), len(G))), directed=False)
        size = np.bincount(comp)
        small = size[comp] < 12
        if not small.any(): break
        for pair in (adj, adj[:, ::-1]):
            x, y = pair[:, 0], pair[:, 1]
            m = small[x] & ~small[y]
            lab[x[m]] = lab[y[m]]
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    ok = lab[adj[:, 0]] == lab[adj[:, 1]]; a = adj[ok]
    n, comp = connected_components(coo_matrix((np.ones(len(a)), (a[:, 0], a[:, 1])), shape=(len(G), len(G))), directed=False)
    return lab, comp, n


def bake(V, G, ref, pics, size=2048, face_y=None, ear_y=None, slant=0.55, mouth=None, pad=4):
    lab, comp, n = charts(V, G)
    # per chart: flat coordinates along its direction's two other axes
    axes2 = {0: (2, 1, -1), 1: (2, 1, 1), 2: (0, 2, 1), 3: (0, 2, -1), 4: (0, 1, 1), 5: (0, 1, -1)}
    # split vertices per chart
    key = comp[:, None] * len(V) + G
    uk, inv = np.unique(key.ravel(), return_inverse=True)
    vid = uk % len(V); vchart = uk // len(V)
    G2 = inv.reshape(-1, 3); V2 = V[vid]
    clab = np.zeros(n, int); clab[comp] = lab
    uvm = np.zeros((len(V2), 2))
    for c_lab, (i, j, sgn) in axes2.items():
        m = clab[vchart] == c_lab
        uvm[m, 0] = V2[m, i] * sgn; uvm[m, 1] = -V2[m, j]
    # pack the charts (shelves) at a scale that fills the square
    lo = np.full((n, 2), np.inf); hi = np.full((n, 2), -np.inf)
    np.minimum.at(lo, vchart, uvm); np.maximum.at(hi, vchart, uvm)
    dims = hi - lo
    area = (dims[:, 0] * dims[:, 1]).sum()
    scale = np.sqrt(0.62 * size * size / max(area, 1e-9))
    for _ in range(20):
        w = dims * scale + 2 * pad
        order = np.argsort(-w[:, 1]); x = y = shelf = 0; pos = np.zeros((n, 2)); ok = True
        for c in order:
            if x + w[c, 0] > size: x = 0; y += shelf; shelf = 0
            pos[c] = (x + pad, y + pad); x += w[c, 0]; shelf = max(shelf, w[c, 1])
        if y + shelf <= size: break
        scale *= 0.95
    UVpx = (uvm - lo[vchart]) * scale + pos[vchart]
    UV = UVpx / size

    # the pictures: where each surface point falls in them, and what each can see (depth from the full shape)
    imgs = {'front': pics['front'], 'right': pics['right'], 'left': Image.fromarray(np.asarray(pics['right'])[:, ::-1].copy())}
    views = []
    for name, d, r in VIEWS:
        im = imgs[name]; a = np.asarray(im.convert('RGB')).astype(np.float32) / 255
        H, W = a.shape[:2]
        x0, x1, y0, y1 = mask_box(np.asarray(im.convert('RGB')))
        u = ref @ r; v = ref[:, 1]
        fit = (u.min(), u.max(), v.min(), v.max(), x0, x1, y0, y1)
        views.append((name, d, r, a, fit))

    def to_pic(p, r, fit):
        umin, umax, vmin, vmax, x0, x1, y0, y1 = fit
        return x0 + (p @ r - umin) / (umax - umin) * (x1 - x0), y1 - (p[:, 1] - vmin) / (vmax - vmin) * (y1 - y0)

    depth = []
    for name, d, r, a, fit in views:
        H, W = a.shape[:2]
        X, Y = to_pic(V, r, fit)
        zimg, mask = raster_xy(X, Y, V @ d, G, (V @ d)[:, None], W)
        depth.append(np.where(mask, zimg[..., 0], -1e9))

    tex = np.zeros((size, size, 3), np.float32); have = np.zeros((size, size), bool)
    VN = normals(V, G)[vid]
    E = np.maximum.reduce([np.hypot(*(UVpx[G2[:, i]] - UVpx[G2[:, (i + 1) % 3]]).T) for i in range(3)])
    from raster import bary
    for lo_, hi_, nn in ((0, 2, 3), (2, 4, 6), (4, 8, 11), (8, 16, 22), (16, 32, 44), (32, 1e9, 90)):
        sel = np.where((E > lo_) & (E <= hi_))[0]
        if len(sel) == 0: continue
        B = bary(nn).astype(np.float32)
        for chunk in np.array_split(sel, max(1, len(sel) * len(B) // 2_000_000 + 1)):
            T = G2[chunk]
            px = np.einsum('sk,tkd->tsd', B, UVpx[T]).reshape(-1, 2)
            P3 = np.einsum('sk,tkd->tsd', B, V2[T]).reshape(-1, 3)
            N3 = np.einsum('sk,tkd->tsd', B, VN[T]).reshape(-1, 3); N3 /= np.linalg.norm(N3, axis=1, keepdims=True) + 1e-9
            col, wsum = shade(P3, N3, views, depth, to_pic, face_y, ear_y, slant, mouth)
            xi = np.clip(px[:, 0].astype(int), 0, size - 1); yi = np.clip(px[:, 1].astype(int), 0, size - 1)
            tex[yi, xi] = col; have[yi, xi] = True
    # grow the charts' colours a few texels outwards (no seams when the texture is filtered)
    for _ in range(pad + 2):
        grown = ndimage.binary_dilation(have)
        edge = grown & ~have
        if not edge.any(): break
        acc = np.zeros_like(tex); cnt = np.zeros(have.shape, np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                sh = np.roll(np.roll(have, dy, 0), dx, 1); st = np.roll(np.roll(tex, dy, 0), dx, 1)
                acc += st * sh[..., None]; cnt += sh
        tex[edge] = acc[edge] / np.maximum(cnt[edge], 1)[:, None]; have = grown
    tex[~have] = FUR
    img = Image.fromarray((np.clip(tex, 0, 1) * 255).astype(np.uint8))
    return V2, G2, UV, img, vid


def shade(P, N, views, depth, to_pic, face_y, ear_y, slant, mouth):
    acc = np.zeros((len(P), 3), np.float32); wsum = np.zeros(len(P), np.float32)
    head = (P[:, 1] > face_y[0]) & (P[:, 1] < face_y[1]) if face_y else np.zeros(len(P), bool)
    ear = (P[:, 1] > ear_y) if ear_y else np.zeros(len(P), bool)
    in_mouth = np.zeros(len(P), bool)
    if mouth is not None:
        (my0, my1), mxh, mz = mouth
        in_mouth = (P[:, 1] > my0) & (P[:, 1] < my1) & (np.abs(P[:, 0]) < mxh) & (P[:, 2] > mz)
    for k, (name, d, r, a, fit) in enumerate(views):
        H, W = a.shape[:2]
        X, Y = to_pic(P, r, fit)
        xi = np.clip(X.astype(int), 0, W - 1); yi = np.clip(Y.astype(int), 0, H - 1)
        z = P @ d
        # visible: nearly as near as the nearest surface there (look in a small neighbourhood: edges)
        dz = depth[k]
        near = np.maximum.reduce([dz[np.clip(yi + oy, 0, H - 1), np.clip(xi + ox, 0, W - 1)] for oy in (-2, 0, 2) for ox in (-2, 0, 2)])
        vis = z > near - 0.012
        c = np.clip(N @ d, 0, 1)
        if name == 'front':
            w = ss(0.15, 0.55, c) ** 2
            # the head: only where it faces the camera (whiskers / brows would smear round it); the mouth's inside always
            hw = ss(slant - 0.12, slant + 0.08, c)
            w = np.where(head & ~in_mouth, w * hw, w)
        else:
            w = ss(0.55, 0.9, c) ** 2
            w = np.where(head, 0, w)                     # the side picture's eye must not land on the cheek
        w = np.where(ear, w * ss(0.1, 0.4, N[:, 2]), w)   # the ears' backs and outer rims are fur (a soft edge)
        # the top of the head, where the ears grow: the picture's ear colour must not run onto it
        w = w * (1 - ss(0.95, 1.03, P[:, 1]) * (1 - ss(0.65, 0.9, N[:, 2])) * (~ear))
        w = w * vis
        # bilinear sample
        x0 = np.floor(X).astype(int).clip(0, W - 2); y0 = np.floor(Y).astype(int).clip(0, H - 2)
        fx = (X - x0).clip(0, 1)[:, None]; fy = (Y - y0).clip(0, 1)[:, None]
        col = a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x0 + 1] * fx * (1 - fy) + a[y0 + 1, x0] * (1 - fx) * fy + a[y0 + 1, x0 + 1] * fx * fy
        # the white background is no colour of hers
        w = np.where(col.min(1) > 0.985, w * 0.05, w)
        acc += col * w[:, None]; wsum += w
    fur_w = 0.04
    col = (acc + FUR * fur_w) / (wsum + fur_w)[:, None]
    return col, wsum
