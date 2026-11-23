"""Texture from the pictures: each triangle takes the picture that sees it best (front, right, back, left = right
mirrored), with UVs into a 2x2 atlas of those pictures; triangles no picture sees get the painted colour instead."""
import numpy as np
from PIL import Image
from mesh import normals
from paint import mask_box, paint

VIEWS = [('front', np.array([0, 0, 1.]), np.array([1, 0, 0.])), ('right', np.array([-1, 0, 0.]), np.array([0, 0, 1.])),
         ('back', np.array([0, 0, -1.]), np.array([-1, 0, 0.])), ('left', np.array([1, 0, 0.]), np.array([0, 0, -1.]))]
TILE = 1024
EAR_Y = 1.0                 # m: above this, the ears (the model is 1.35 m tall here)
FUR = np.array([0.94, 0.93, 0.93])
MOUTH = None               # ((y0, y1), half width, z min): where the mouth is
SLANT = 0.3                # the front picture paints the head only where it faces the camera at least this much
FACE_Y = None              # (low, high) m: the head's height; its front half is painted from the front picture only

def project(P, ref, img, d, r):
    """pixel coords of points P in picture img (fitting the reference shape ref's outline to the picture's)"""
    x0, x1, y0, y1 = mask_box(np.asarray(img))
    u = ref @ r; v = ref[:, 1]
    pu = P @ r; pv = P[:, 1]
    X = x0 + (pu - u.min()) / (u.max() - u.min()) * (x1 - x0)
    Y = y1 - (pv - v.min()) / (v.max() - v.min()) * (y1 - y0)
    return X, Y

def build(V, G, dense, denseF, pics, colors):
    """V, G: the reduced mesh; dense: the full one (for what each picture can see); colors: painted colour per V."""
    imgs = {'front': pics['front'], 'right': pics['right'], 'back': pics.get('back'), 'left': Image.fromarray(np.asarray(pics['right'])[:, ::-1])}
    atlas = Image.new('RGB', (2 * TILE, 2 * TILE), (255, 255, 255))
    FN = np.cross(V[G[:, 1]] - V[G[:, 0]], V[G[:, 2]] - V[G[:, 0]]); FN /= np.linalg.norm(FN, axis=1, keepdims=True) + 1e-12
    cen = V[G].mean(1)
    score = np.full((len(G), 4), -1.0); uvs = []
    for k, (name, d, r) in enumerate(VIEWS):
        if imgs[name] is None:                     # no picture from there (the back): those triangles get painted colours
            uvs.append(np.zeros((len(V), 2))); continue
        img = imgs[name].resize((TILE, TILE), Image.LANCZOS); atlas.paste(img, ((k % 2) * TILE, (k // 2) * TILE))
        X, Y = project(V, dense, img, d, r)
        # visibility from the dense shape: nearest surface per 6 px cell
        DX, DY = project(dense, dense, img, d, r); dz = dense @ d
        kk = 4; zb = np.full((TILE // kk + 3, TILE // kk + 3), -1e9)
        np.maximum.at(zb, (np.clip(DY // kk, 0, TILE // kk + 2).astype(int), np.clip(DX // kk, 0, TILE // kk + 2).astype(int)), dz)
        zmax = np.maximum.reduce([np.roll(np.roll(zb, a, 0), b, 1) for a in (-1, 0, 1) for b in (-1, 0, 1)])
        CX, CY = project(cen, dense, img, d, r)
        vis = (cen @ d) > zmax[np.clip(CY // kk, 0, TILE // kk + 2).astype(int), np.clip(CX // kk, 0, TILE // kk + 2).astype(int)] - 0.03
        sc = FN @ d
        # the front picture is the best one (the side pictures have coloured rim light): it wins near the edge, and a
        # side picture is only used where it looks at the surface squarely
        lim = 0.2 if name in ('front', 'back') else 0.6
        bonus = 1.25 if name == 'front' else 1.0
        score[:, k] = np.where(vis & (sc > lim), sc * bonus, -1)
        if k == 0: front_vis = vis
        uvs.append(np.stack([((k % 2) * TILE + X) / (2 * TILE), ((k // 2) * TILE + Y) / (2 * TILE)], 1))
    # the face: only the front picture paints it. The side picture shows an eye in profile, which would land on the
    # cheek's side as a second pair of eyes; the front half of the head takes no side picture
    if FACE_Y is not None:
        face = (cen[:, 1] > FACE_Y[0]) & (cen[:, 1] < FACE_Y[1])          # the whole head (white fur round the back)
        score[face, 1] = -1; score[face, 3] = -1
        # and the front picture only where it looks at the face squarely enough (at a slant it smears the brows and
        # eyes into streaks round the head), nor on the top of the head (the ears' colour would run down onto it)
        slant = face & (FN[:, 2] < SLANT)
        if MOUTH is not None:          # the mouth's inside: the picture's mouth, seen from the front, whatever its slant
            (my0, my1), mx_, mz = MOUTH
            slant &= ~((cen[:, 1] > my0) & (cen[:, 1] < my1) & (np.abs(cen[:, 0]) < mx_) & (cen[:, 2] > mz))
        top = (cen[:, 1] > FACE_Y[0]) & (cen[:, 1] < FACE_Y[1] + 0.05) & (FN[:, 1] > 0.55) & (cen[:, 1] > FACE_Y[1] - 0.15)
        score[slant | top, 0] = -1
        face = face | top
    # the ears: only their inside is coloured; their back and outer rim take only the back picture (white fur)
    ear = (cen[:, 1] > EAR_Y) & (FN[:, 2] < 0.25)
    score[ear, 0] = -1; score[ear, 1] = -1; score[ear, 3] = -1
    best = score.argmax(1); hidden = score.max(1) < 0
    # split vertices per (vertex, view): view 4 = painted colour, UV on a white corner
    key = np.where(hidden[:, None], 4, best[:, None]) * len(V) + G
    uk, inv = np.unique(key.ravel(), return_inverse=True)
    vid = uk % len(V); view = uk // len(V)
    NV = V[vid]; NG = inv.reshape(-1, 3)
    UV = np.zeros((len(uk), 2)); COL = np.ones((len(uk), 3))
    for k in range(4): m = view == k; UV[m] = uvs[k][vid[m]]
    m = view == 4; UV[m] = [0.5 / (2 * TILE), 0.5 / (2 * TILE)]; COL[m] = colors[vid[m]]
    earV = np.zeros(len(V), bool); earV[G[ear].ravel()] = True
    m2 = m & earV[vid]; COL[m2] = FUR
    # the face's sides that no picture paints: plain fur (a painted guess would carry the side picture's eye)
    if FACE_Y is not None:
        faceV = np.zeros(len(V), bool); faceV[G[hidden & face].ravel()] = True
        COL[m & faceV[vid]] = FUR
    # no back picture: what faces backwards and no picture sees is plain fur (the painted guess is streaky there)
    if imgs['back'] is None:
        backV = np.zeros(len(V), bool); backV[G[hidden & (FN[:, 2] < -0.15)].ravel()] = True
        m3 = m & backV[vid]; COL[m3] = FUR
    return NV, NG, UV, COL, atlas, vid
