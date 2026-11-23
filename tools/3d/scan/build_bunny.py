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
import paint as pm
import atlas as at
from recolor import recolor

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'source')
EAR_Y = 1.06

JOINTS = [('Body', None, (0, 0, 0)), ('Face', 'Body', (0, 0.58, 0.02)), ('EarL', 'Face', (-0.12, 1.06, -0.08)), ('EarR', 'Face', (0.12, 1.06, -0.08)),
          ('ArmL', 'Body', (-0.19, 0.5, 0.05)), ('ArmR', 'Body', (0.19, 0.5, 0.05)), ('FootL', 'Body', (-0.12, 0.05, 0.04)), ('FootR', 'Body', (0.12, 0.05, 0.04)),
          ('Tail', 'Body', (0, 0.22, -0.26))]
JI = {j[0]: i for i, j in enumerate(JOINTS)}


def weights(V):
    x, y, z = V[:, 0], V[:, 1], V[:, 2]; ax = np.abs(x)
    W = np.zeros((len(V), len(JOINTS)))
    # the arms reach out sideways; the thumbs stand up beside the cheeks, so above the shoulders an arm is further out
    lo = np.interp(y, [0.5, 0.6], [0.18, 0.295])
    arm = ss(lo, lo + 0.035, ax) * ss(0.36, 0.4, y) * (1 - ss(0.74, 0.78, y))
    head = ss(0.54, 0.62, y) * (1 - arm)
    ear = ss(1.03, 1.1, y) * head
    foot = (1 - ss(0.07, 0.13, y)) * (1 - arm)
    tail = ss(-0.22, -0.27, z) * ss(0.05, 0.09, y) * (1 - ss(0.36, 0.4, y)) * (1 - foot)
    left = x < 0
    W[:, JI['EarL']] = ear * left; W[:, JI['EarR']] = ear * ~left
    W[:, JI['Face']] = head - ear
    W[:, JI['ArmL']] = arm * left; W[:, JI['ArmR']] = arm * ~left
    W[:, JI['FootL']] = foot * left; W[:, JI['FootR']] = foot * ~left
    W[:, JI['Tail']] = tail
    W[:, JI['Body']] = np.clip(1 - W.sum(1), 0, 1)
    W /= W.sum(1, keepdims=True)
    idx = np.argsort(-W, 1)[:, :4]; w = np.take_along_axis(W, idx, 1); w /= w.sum(1, keepdims=True)
    return idx.astype(np.uint8), w.astype(np.float32)


def soften(im):
    """Takes the faint coloured light off the white fur (the pictures' rim light is blue or pink, which turns into
    streaks on the model's sides); the ears, eyes, nose, mouth and emblem are strongly coloured and stay."""
    a = np.asarray(im.convert('RGB')).astype(float) / 255
    mx = a.max(2); mn = a.min(2); sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0)
    faint = (sat < 0.3) & (mx > 0.55)
    k = np.clip((0.3 - sat) / 0.15, 0, 1)[..., None] * faint[..., None]
    grey = (a.mean(2, keepdims=True) * 0.6 + mx[..., None] * 0.4)
    warm = grey * np.array([1.0, 0.985, 0.975])
    out = a * (1 - k) + warm * k
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def clips():
    out = []
    T = 0.56; t = np.linspace(0, T, 17); ph = 2 * np.pi * t / T
    walk = {   # a bouncy bunny walk: a little hop each step, ears and tail bobbing
        'Body': ([[0, 0.035 * abs(math.sin(p)), 0] for p in ph], [qmul(quat((0, 0, 1), 0.06 * math.sin(p)), quat((1, 0, 0), 0.06)) for p in ph]),
        'FootL': ([[-0.12, 0.05 + 0.04 * max(0, math.sin(p)), 0.04 + 0.06 * math.cos(p)] for p in ph], None),
        'FootR': ([[0.12, 0.05 + 0.04 * max(0, -math.sin(p)), 0.04 - 0.06 * math.cos(p)] for p in ph], None),
        'ArmL': (None, [qmul(quat((0, 0, 1), -0.75), quat((1, 0, 0), -0.4 * math.cos(p))) for p in ph]),
        'ArmR': (None, [qmul(quat((0, 0, 1), 0.75), quat((1, 0, 0), 0.4 * math.cos(p))) for p in ph]),
        'EarL': (None, [qmul(quat((0, 0, 1), 0.07 * math.sin(2 * p)), quat((1, 0, 0), -0.12 * abs(math.sin(p)))) for p in ph]),
        'EarR': (None, [qmul(quat((0, 0, 1), -0.07 * math.sin(2 * p)), quat((1, 0, 0), -0.12 * abs(math.sin(p)))) for p in ph]),
        'Tail': (None, [quat((0, 1, 0), 0.35 * math.sin(2 * p)) for p in ph]),
    }
    out.append(('walk', t, walk))
    T = 2.4; t = np.linspace(0, T, 25); ph = 2 * np.pi * t / T
    idle = {   # arms relaxed down a little, breathing, an ear twitch, a tail wiggle
        'Body': ([[0, 0.006 * (1 - math.cos(p)), 0] for p in ph], [[0, 0, 0, 1] for p in ph]),
        'FootL': ([[-0.12, 0.05, 0.04] for p in ph], None), 'FootR': ([[0.12, 0.05, 0.04] for p in ph], None),
        'ArmL': (None, [quat((0, 0, 1), -0.7 - 0.05 * math.sin(p)) for p in ph]),
        'ArmR': (None, [quat((0, 0, 1), 0.7 + 0.05 * math.sin(p)) for p in ph]),
        'EarL': (None, [quat((0, 0, 1), 0.05 * math.sin(p) + 0.04 * math.sin(3 * p)) for p in ph]),
        'EarR': (None, [quat((0, 0, 1), -0.05 * math.sin(p + 0.6)) for p in ph]),
        'Tail': (None, [quat((0, 1, 0), 0.2 * math.sin(2 * p)) for p in ph]),
    }
    out.append(('idle', t, idle))
    return out


def build(shape, n, out, preview=None):
    girl = n == 'girl'
    P, F = load(shape); P = normalize(P, bp.HEIGHT)
    P, F = drop_thin(P, F)
    V, G, cid = cluster(P, F, bp.CELL)
    base = {v: Image.open(os.path.join(SRC, f'poppy_bunny_{v}.png')).convert('RGB') for v in ('front', 'right')}
    pics = {v: soften(recolor(im, girl)) for v, im in base.items()}
    pm.EAR_Y = EAR_Y; at.EAR_Y = EAR_Y; at.FACE_Y = (0.6, EAR_Y)
    C = pm.paint(V, G, pics)
    NV, NG, UV, COL, atlas_img, vid = at.build(V, G, P, F, pics, C)
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
    base_tex = gl.image(atlas_img, 88); face_tex = gl.image(sheet, 90)
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
    g['meshes'] = meshes

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
    g['nodes'] = nodes
    ibm = np.zeros((len(JOINTS), 16), np.float32)
    for i, (_, _, pos) in enumerate(JOINTS):
        m = np.eye(4); m[:3, 3] = -np.array(pos); ibm[i] = m.T.ravel()
    g['skins'] = [{'joints': [jnode[j[0]] for j in JOINTS], 'skeleton': jnode['Body'], 'inverseBindMatrices': gl.acc(ibm, 'MAT4')}]
    g['scenes'] = [{'nodes': [0]}]; g['scene'] = 0

    anims = []
    for cname, t, chans in clips():
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
