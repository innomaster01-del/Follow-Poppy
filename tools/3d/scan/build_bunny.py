"""Builds the app's Poppy from the new character (the white bunny with the paw-pin emblem, 2026-11):

    python3 build_bunny.py <shape.glb> <girl|boy> <out.glb> [preview.png]

One shape (Hunyuan3D-2mv from tools/3d/source/poppy_bunny_front/right.png, the standing views made with FLUX Kontext);
the two versions differ only in colour (recolor.py: the girl's inner ears and emblem pink, the boy's blue). Same app
contract as build_poppy.py (joints Body, Face, EarL/R, ArmL/R, FootL/R, plus Tail; face patches; walk / idle clips).
"""
import math, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_poppy as bp
from build_poppy import Glb, quat, qmul, ss
from mesh import load, normals
from decim import normalize, cluster
from thin import drop_thin
from smooth import taubin, face_weight, drop_whiskers, fill_holes, tuck_thumbs, close_mouth
import paint as pm
import atlas as at
from recolor import recolor, green_eyes
from bake import bake
TEX = 2048

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'source')
EAR_Y = 1.06

from bunny_moves import JOINTS, JI, weights, clips as move_clips, CLIP_NAMES
import bunny_moves as mv


def soften(im, strong=False):
    """Takes the faint coloured light off the white fur (the pictures' rim light is blue or pink, which turns into
    streaks on the model's sides); the ears, eyes, nose, mouth and emblem are strongly coloured and stay."""
    a = np.asarray(im.convert('RGB')).astype(float) / 255
    mx = a.max(2); mn = a.min(2); sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0)
    # hue: the light blue shadows on the fur (cheeks, rim) are pale even when fairly saturated; the irises are deep
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    bluish = (b >= r) & (b >= g * 0.98)
    faint = ((sat < 0.3) | (bluish & (sat < 0.5) & (mx > 0.8) & (mn > 0.45))) & (mx > 0.55)
    if strong:   # the side picture paints only the body's sides (white fur): any pale colour there is light, not paint
        faint |= (sat < 0.55) & (mx > 0.7) & (mn > 0.35)
    else:        # the front: the blue shadows under the chin and along the arms too, but never in the eyes
        keep = np.zeros(mx.shape, bool)
        yy, xx = np.mgrid[0:mx.shape[0], 0:mx.shape[1]]
        for cx, cy, rx, ry in bp.find_eyes(im):
            keep |= ((xx - cx) / (rx * 1.6)) ** 2 + ((yy - cy) / (ry * 1.6)) ** 2 < 1
        faint |= bluish & (sat < 0.55) & (mx > 0.72) & (mn > 0.3) & ~keep
    # never the ears (their pale inner colour is paint, not light): the top quarter of the character
    m = (np.abs(a - 1).sum(2) > 0.18); rows = np.where(m.sum(1) > 2)[0]
    if len(rows): faint &= np.arange(mx.shape[0])[:, None] > rows[0] + (rows[-1] - rows[0]) * 0.25
    k = np.where((bluish | strong) & (sat >= 0.3), 1.0, np.clip((0.3 - sat) / 0.15, 0, 1))[..., None] * faint[..., None]
    grey = (a.mean(2, keepdims=True) * 0.6 + mx[..., None] * 0.4)
    warm = grey * np.array([1.0, 0.985, 0.975])
    out = a * (1 - k) + warm * k
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


class EarPaint:
    """The ears are painted by rule, not from the picture (the picture's ear never sits exactly on the model's ear, and
    its colours are patchy after recolouring): white fur on the back and round the rim, and inside, on the part that
    faces forward and lies more than RIM inside the ear's outline, a smooth gradient: deep in the middle and at the
    base, lighter towards the edge. Pink for her, blue for him; only the colour differs."""
    RIM = 0.022; RIM_SHARE = 0.38; FEATHER = 0.005; CELL = 0.002
    COLOURS = {True: (np.array([1.0, 0.62, 0.78]), np.array([0.92, 0.2, 0.5])),      # light, deep (pink)
               False: (np.array([0.62, 0.8, 1.0]), np.array([0.17, 0.47, 0.95]))}    # (blue)

    def __init__(self, V, girl):
        self.light, self.deep = self.COLOURS[girl]
        self.maps = []
        for side in (-1, 1):
            m = (V[:, 1] > EAR_Y - 0.03) & (V[:, 0] * side > 0.03)
            pts = V[m][:, :2]
            lo = pts.min(0) - 0.02; shape = np.ceil((pts.max(0) + 0.02 - lo) / self.CELL).astype(int) + 1
            g = np.zeros(shape, bool); ij = ((pts - lo) / self.CELL).astype(int); g[ij[:, 0], ij[:, 1]] = True
            from scipy import ndimage
            g = ndimage.binary_closing(ndimage.binary_dilation(g, iterations=2), iterations=3); g = ndimage.binary_fill_holes(g)
            g = ndimage.binary_erosion(g, iterations=2)
            # the ear's bottom is where it grows out of the head, not an edge: carry the mask on below it
            pad = int(0.08 / self.CELL)
            gp = np.concatenate([np.repeat(g[:, :1], pad, 1), g], 1)
            base = np.where(g.any(0))[0]
            if len(base): gp[:, :pad + base[0] + int(0.04 / self.CELL)] |= g[:, base[0]:base[0] + int(0.04 / self.CELL)].any(1)[:, None]
            d = ndimage.distance_transform_edt(gp)[:, pad:] * self.CELL
            # the white rim is a fixed share of the ear's half-width at each height (like the drawing), never thin
            half = ndimage.maximum_filter1d(d.max(0), 9)
            rim = np.maximum(half * self.RIM_SHARE, self.RIM)
            self.maps.append((side, lo, d, d.max(), rim))

    def __call__(self, P, N, col):
        out = col.copy()
        for side, lo, d, dmax, rimrow in self.maps:
            sel = (P[:, 0] * side > 0.02) & (P[:, 1] > EAR_Y - 0.06)
            if not sel.any(): continue
            ij = ((P[sel, :2] - lo) / self.CELL).astype(int)
            ok = (ij[:, 0] >= 0) & (ij[:, 0] < d.shape[0]) & (ij[:, 1] >= 0) & (ij[:, 1] < d.shape[1])
            dist = np.zeros(sel.sum()); dist[ok] = d[ij[ok, 0], ij[ok, 1]]
            rimv = np.full(sel.sum(), 1.0); jj = np.clip(ij[:, 1], 0, len(rimrow) - 1); rimv = rimrow[jj]
            y = P[sel, 1]; nz = N[sel, 2]
            inner = ss(rimv, rimv + self.FEATHER, dist) * ss(0.3, 0.5, nz)
            t = np.clip(dist / max(dmax, 1e-6), 0, 1)
            deep = np.clip(0.8 * ss(0.15, 0.7, t) + 0.5 * (1 - ss(EAR_Y, EAR_Y + 0.12, y)), 0, 1)
            inside = self.light[None] * (1 - deep[:, None]) + self.deep[None] * deep[:, None]
            # where the ear grows out of the head the rule fades out (the head keeps its own colour below)
            grow = ss(EAR_Y - 0.05, EAR_Y + 0.01, y)
            fur = bp_fur()
            painted = fur[None] * (1 - inner[:, None]) + inside * inner[:, None]
            out[sel] = col[sel] * (1 - grow[:, None]) + painted * grow[:, None]
        # the top of the head round the ears' roots: the picture's ear colour runs onto it there; only fur (the grey
        # brows are not coloured, they stay)
        top = P[:, 1] > 0.9
        sat = out.max(1) - out.min(1)
        smear = top & (sat > 0.1) & ~self._inner(P, N)
        out[smear] = bp_fur()
        # the hands: white fur (the picture's blue / pink rim light and nails would show as coloured fingertips)
        hands = (np.abs(P[:, 0]) > 0.26) & (P[:, 1] > 0.36) & (P[:, 1] < 0.64)
        sat2 = out.max(1) - out.min(1)
        k = (np.clip((sat2 - 0.03) / 0.08, 0, 1) * hands)[:, None]
        return out * (1 - k) + bp_fur()[None] * k

    def _inner(self, P, N):
        res = np.zeros(len(P), bool)
        for side, lo, d, dmax, rimrow in self.maps:
            sel = (P[:, 0] * side > 0.02) & (P[:, 1] > EAR_Y - 0.06)
            if not sel.any(): continue
            ij = ((P[sel, :2] - lo) / self.CELL).astype(int)
            ok = (ij[:, 0] >= 0) & (ij[:, 0] < d.shape[0]) & (ij[:, 1] >= 0) & (ij[:, 1] < d.shape[1])
            dist = np.zeros(sel.sum()); dist[ok] = d[ij[ok, 0], ij[ok, 1]]
            idx = np.where(sel)[0]
            res[idx] = (dist > rimrow[np.clip(ij[:, 1], 0, len(rimrow) - 1)] * 0.8) & (N[sel, 2] > 0.2)
        return res


def bp_fur():
    from bake import FUR
    return FUR


def build(shape, n, out, preview=None):
    girl = n == 'girl'
    P, F = load(shape); P = normalize(P, bp.HEIGHT)
    P, F = drop_thin(P, F)
    # the face is painted, not carved: whiskers cut off (painted), holes closed, the carved eyes / brows smoothed away
    P, F = drop_whiskers(P, F, 0.675, 0.81, 0.0)
    P = tuck_thumbs(P, F)                       # no thumbs sticking up (they look like spikes when she moves)
    V, G, cid = cluster(P, F, bp.CELL)
    V, G = fill_holes(V, G)
    V = taubin(V, G, face_weight(V, 0.62, 1.03, half=0.25, zmin=0.02), iters=180)
    V = close_mouth(V, (0.635, 0.75, 0.11, 0.1), (0.6, 0.82, 0.17, 0.12))                         # the carved mouth closed
    V = taubin(V, G, face_weight(V, 0.62, 0.77, half=0.13, zmin=0.1, soft=0.03), iters=60)
    base = {v: Image.open(os.path.join(SRC, f'poppy_bunny_{v}.png')).convert('RGB') for v in ('front', 'right')}
    pics = {v: soften(recolor(im, girl), strong=(v == 'right')) for v, im in base.items()}
    if girl: pics = {v: green_eyes(im) for v, im in pics.items()}          # her eyes green, his stay blue
    pm.EAR_Y = EAR_Y; at.EAR_Y = EAR_Y; at.FACE_Y = (0.6, EAR_Y); at.MOUTH = ((0.635, 0.75), 0.11, 0.1); at.SLANT = 0.55   # the whiskers in the picture would streak round the cheeks
    # an HD texture baked texel by texel from the pictures (smooth hand-over between them, plain fur where none sees)
    NV, NG, UV, atlas_img, vid = bake(V, G, P, pics, size=TEX, face_y=(0.6, EAR_Y), ear_y=EAR_Y, slant=0.62, mouth=((0.635, 0.75), 0.11, 0.1), pad=14,
                                      after=EarPaint(V, girl))
    COL = np.ones((len(NV), 3))
    VN = normals(V, G)[vid]
    J, W = weights(V); J = J[vid]; W = W[vid]

    # the face patches (closed / happy eyes, grin, 'o'), placed from the eyes in this picture
    eyes = bp.find_eyes(pics['front'])
    (lx, ly, lrx, lry), (rx_, ry_, rrx, rry) = eyes
    bp.FACE_BOX = (int(lx - 150), int(min(ly, ry_) - 150), int(rx_ + 150), int(max(ly, ry_) + 230))
    bp.cover_k = lambda g: 1.45
    bp.MOUTH_DY = 78
    sheet, regions = bp.face_variants(pics['front'], girl)

    gl = Glb(); g = gl.g
    base_tex = gl.image(atlas_img, 92); face_tex = gl.image(sheet, 90)
    g['materials'] = [
        {'name': 'Poppy', 'pbrMetallicRoughness': {'baseColorTexture': {'index': base_tex}, 'metallicFactor': 0.0, 'roughnessFactor': 0.85}},
        {'name': 'PoppyFace', 'pbrMetallicRoughness': {'baseColorTexture': {'index': face_tex}, 'metallicFactor': 0.0, 'roughnessFactor': 0.85}},
    ]
    meshes = []
    idx_t = np.uint16 if len(NV) < 65536 else np.uint32
    prim = {'attributes': {'POSITION': gl.acc(NV.astype(np.float32), 'VEC3', 34962, True), 'NORMAL': gl.acc(VN.astype(np.float32), 'VEC3', 34962),
                           'TEXCOORD_0': gl.acc(UV.astype(np.float32), 'VEC2', 34962), 'COLOR_0': gl.acc(COL.astype(np.float32), 'VEC3', 34962),
                           'JOINTS_0': gl.acc(J, 'VEC4', 34962), 'WEIGHTS_0': gl.acc(W, 'VEC4', 34962)},
            'indices': gl.acc(NG.astype(idx_t).ravel(), 'SCALAR', 34963), 'material': 0}
    meshes.append({'name': 'PoppyBody', 'primitives': [prim]})

    fx, fy = at.project(NV, P, pics['front'].resize((at.TILE, at.TILE)), np.array([0, 0, 1.]), np.array([1, 0, 0.]))
    sx = pics['front'].width / at.TILE; fx = fx * sx; fy = fy * sx
    FN = np.cross(NV[NG[:, 1]] - NV[NG[:, 0]], NV[NG[:, 2]] - NV[NG[:, 0]]); FN /= np.linalg.norm(FN, axis=1, keepdims=True) + 1e-12
    x0, y0, x1, y1 = bp.FACE_BOX; bw, bh = x1 - x0, y1 - y0
    face_rest = np.array(JOINTS[JI['Face']][2], float)
    mouth = [r for k_, r in regions if k_ == 'mouth'][0]

    def patch(region, tile, k):
        cx, cy, rx, ry = region
        inside = (((fx - cx) / (rx * k)) ** 2 + ((fy - cy) / (ry * k)) ** 2) < 1
        tri = inside[NG].all(1) & (FN[:, 2] > 0.15) & (NV[NG][:, :, 1].mean(1) > 0.62)
        T = NG[tri]; used = np.unique(T); remap = -np.ones(len(NV), int); remap[used] = np.arange(len(used))
        pos = NV[used] + VN[used] * 0.003 - face_rest
        u = ((tile % 2) * bw + (fx[used] - x0)) / (2 * bw); v = ((tile // 2) * bh + (fy[used] - y0)) / (2 * bh)
        pr = {'attributes': {'POSITION': gl.acc(pos.astype(np.float32), 'VEC3', 34962, True), 'NORMAL': gl.acc(VN[used].astype(np.float32), 'VEC3', 34962),
                             'TEXCOORD_0': gl.acc(np.stack([u, v], 1).astype(np.float32), 'VEC2', 34962)},
              'indices': gl.acc(remap[T].astype(np.uint16).ravel(), 'SCALAR', 34963), 'material': 1}
        meshes.append({'primitives': [pr]}); return len(meshes) - 1

    looks = []
    for s_, e in zip('LR', eyes):
        looks += [(f'EyeOpen{s_}', None, True), (f'EyeClosed{s_}', patch(e, 0, 1.8), False), (f'EyeHappy{s_}', patch(e, 1, 1.8), False)]
    looks += [('MouthSmile', None, True), ('MouthGrin', patch(mouth, 2, 1.5), False), ('MouthO', patch(mouth, 3, 1.5), False)]
    # the props: hidden until a move shows them (the app switches them like the faces)
    theme = np.array([0.95, 0.27, 0.56]) if girl else np.array([0.2, 0.52, 0.98])
    def mat(name, colour, emissive=(0, 0, 0), rough=0.5, tex=None):
        m = {'name': name, 'pbrMetallicRoughness': {'baseColorFactor': [float(c) for c in colour] + [1.0], 'metallicFactor': 0.0, 'roughnessFactor': rough},
             'emissiveFactor': [float(e) for e in emissive]}
        if tex is not None: m['pbrMetallicRoughness']['baseColorTexture'] = {'index': tex}; m['emissiveTexture'] = {'index': tex}
        g['materials'].append(m); return len(g['materials']) - 1
    def prop_mesh(parts):
        prims = []
        for (V_, F_), mi, smooth, uv in parts:
            if smooth: P_, G_, N_ = V_, F_, mv.smooth_normals(V_, F_)
            else: P_, G_, N_ = mv.flat_normals(V_, F_)
            attrs = {'POSITION': gl.acc(np.asarray(P_, np.float32), 'VEC3', 34962, True), 'NORMAL': gl.acc(np.asarray(N_, np.float32), 'VEC3', 34962)}
            if uv is not None: attrs['TEXCOORD_0'] = gl.acc(uv(P_).astype(np.float32), 'VEC2', 34962)
            prims.append({'attributes': attrs, 'indices': gl.acc(np.asarray(G_, np.uint16).ravel(), 'SCALAR', 34963), 'material': mi})
        meshes.append({'primitives': prims}); return len(meshes) - 1
    pin_body, pin_dot = mv.pin_mesh(1.25)
    m_theme = mat('PropTheme', theme, theme * 0.25, 0.35); m_white = mat('PropWhite', (1, 1, 1), (0.25, 0.25, 0.25), 0.4)
    pin_m = prop_mesh([(pin_body, m_theme, True, None), (pin_dot, m_white, True, None)])
    # the phone: dark body, a glowing screen with the paw-pin
    from PIL import ImageDraw
    scr = Image.new('RGB', (128, 224), (16, 32, 70)); d_ = ImageDraw.Draw(scr)
    d_.ellipse([34, 70, 94, 130], fill=tuple(int(c * 255) for c in theme)); d_.polygon([(40, 112), (88, 112), (64, 156)], fill=tuple(int(c * 255) for c in theme))
    for cx, cy, r in ((64, 104, 9), (50, 88, 5), (60, 82, 5), (70, 82, 5), (78, 88, 5)): d_.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255))
    scr_tex = gl.image(scr, 90)
    m_dark = mat('PropPhone', (0.06, 0.08, 0.14), (0, 0, 0), 0.3); m_screen = mat('PropScreen', (1, 1, 1), (0.9, 0.9, 0.9), 0.2, scr_tex)
    sw_, sh_ = 0.09, 0.165
    phone_m = prop_mesh([(mv.box_mesh(0.1, 0.18, 0.014), m_dark, False, None),
                         ((mv.box_mesh(sw_, sh_, 0.002)[0] + np.array([0, 0, 0.0065]), mv.box_mesh(sw_, sh_, 0.002)[1]), m_screen, False,
                          lambda P_: np.stack([(P_[:, 0] + sw_ / 2) / sw_, 1 - (P_[:, 1] + sh_ / 2) / sh_], 1))])
    m_glow = mat('PropGlow', (0.35, 0.7, 1.0), (0.3, 0.65, 1.0), 0.3)
    arrow_m = prop_mesh([(mv.arrow_mesh(), m_glow, False, None)])
    m_ring = mat('PropRing', (0.3, 0.9, 1.0), (0.25, 0.85, 1.0), 0.3)
    ring_m = prop_mesh([(mv.ring_mesh(R=0.34), m_ring, True, None)])
    m_cush = mat('PropCushion', theme * 0.55 + 0.45, theme * 0.12, 0.8)
    cush_m = prop_mesh([(mv.cushion_mesh(), m_cush, True, None)])
    g['meshes'] = meshes
    hand = mv.HAND_X - 0.285          # from the elbow to the hand, along the arm
    # a prop in a hand is turned so that, in the move that shows it, it faces you upright (screen / arrow towards you)
    from scipy.spatial.transform import Rotation as Rot
    cl = {c[0]: c for c in move_clips()}
    def facing(clip, arm_j, elbow_j, tilt=-0.25):
        _, t_, ch, _p = cl[clip]
        q = (Rot.from_quat(ch['Body'][1][0]) if 'Body' in ch and ch['Body'][1] else Rot.identity()) * Rot.from_quat(ch[arm_j][1][0]) * Rot.from_quat(ch[elbow_j][1][0])
        want = Rot.from_rotvec([tilt, 0, 0])
        return (q.inv() * want).as_quat().tolist()
    props = [('PropPin', 'Body', pin_m, (0, 0.33, 0.2), None),
             ('PropPhone', 'ElbowL', phone_m, (-hand - 0.06, 0.02, 0.0), facing('phone', 'ArmL', 'ElbowL')),
             ('PropArrowL', 'ElbowL', arrow_m, (-hand - 0.07, 0.03, 0.0), facing('point_r', 'ArmL', 'ElbowL', 0.0)),
             ('PropArrowR', 'ElbowR', arrow_m, (hand + 0.07, 0.03, 0.0), facing('point_l', 'ArmR', 'ElbowR', 0.0)),
             ('PropRing', None, ring_m, (0, 0.002, 0.03), None), ('PropCushion', None, cush_m, (0, 0.0, 0.03), None)]

    nodes = [{'name': 'Poppy', 'children': [1, 2]}, {'name': 'PoppyMesh', 'mesh': 0, 'skin': 0}]
    jnode = {}
    for name, parent, pos in JOINTS:
        jnode[name] = len(nodes)
        ppos = np.array(JOINTS[JI[parent]][2]) if parent else np.zeros(3)
        nd = {'name': name}; t = (np.array(pos) - ppos).tolist()
        if any(abs(x) > 1e-9 for x in t): nd['translation'] = t
        nodes.append(nd)
    for name, parent, _ in JOINTS:
        if parent: nodes[jnode[parent]].setdefault('children', []).append(jnode[name])
    for name, mesh, shown in looks:
        nd = {'name': name}
        if mesh is not None: nd['mesh'] = mesh
        if not shown: nd['scale'] = [1e-4, 1e-4, 1e-4]
        nodes.append(nd); nodes[jnode['Face']].setdefault('children', []).append(len(nodes) - 1)
    for name, parent, mesh, t_, _r in props:
        nd = {'name': name, 'mesh': mesh, 'translation': list(t_), 'scale': [1e-4, 1e-4, 1e-4]}
        if _r is not None: nd['rotation'] = _r
        nodes.append(nd)
        if parent: nodes[jnode[parent]].setdefault('children', []).append(len(nodes) - 1)
        else: nodes[0]['children'].append(len(nodes) - 1)
    g['nodes'] = nodes
    ibm = np.zeros((len(JOINTS), 16), np.float32)
    for i, (_, _, pos) in enumerate(JOINTS):
        m = np.eye(4); m[:3, 3] = -np.array(pos); ibm[i] = m.T.ravel()
    g['skins'] = [{'joints': [jnode[j[0]] for j in JOINTS], 'skeleton': jnode['Body'], 'inverseBindMatrices': gl.acc(ibm, 'MAT4')}]
    g['scenes'] = [{'nodes': [0]}]; g['scene'] = 0

    anims = []
    for cname, t, chans, _props in move_clips():
        samplers = []; channels = []
        ti = gl.acc(t.astype(np.float32), 'SCALAR', None, True)
        for jn, (tr, rot) in chans.items():
            if tr is not None:
                parent = JOINTS[JI[jn]][1]; ppos = np.array(JOINTS[JI[parent]][2]) if parent else np.zeros(3)
                vals = np.array(tr, np.float32) - ppos if jn.startswith('Foot') else np.array(tr, np.float32) + (np.array(JOINTS[JI[jn]][2]) - ppos)
                samplers.append({'input': ti, 'output': gl.acc(vals.astype(np.float32), 'VEC3'), 'interpolation': 'LINEAR'})
                channels.append({'sampler': len(samplers) - 1, 'target': {'node': jnode[jn], 'path': 'translation'}})
            if rot is not None:
                samplers.append({'input': ti, 'output': gl.acc(np.array(rot, np.float32), 'VEC4'), 'interpolation': 'LINEAR'})
                channels.append({'sampler': len(samplers) - 1, 'target': {'node': jnode[jn], 'path': 'rotation'}})
        anims.append({'name': cname, 'samplers': samplers, 'channels': channels})
    g['animations'] = anims
    gl.save(out)
    print(out, os.path.getsize(out) // 1024, 'KB', len(NV), 'vertices', len(NG), 'triangles')
    if preview:
        sheet.save(preview.replace('.png', '_faces.png'))


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
