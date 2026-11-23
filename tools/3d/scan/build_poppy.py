"""Builds the app's Poppy (assets/models/poppy_<girl|boy>.glb) from the 3D shape made from the character pictures
(Hunyuan3D-2mv, tools/3d/source/poppy_<n>_front/right/back.png):

    python3 build_poppy.py <shape.glb> <girl|boy> <out.glb> [preview.png]

1. the shape stood on its feet, 1.35 m tall, facing +z, reduced to ~45k triangles;
2. textured from the pictures (each triangle from the picture that sees it best; hidden ones painted);
3. skinned to the joints the app moves: Body (rest = identity), Face (the head; EarL / EarR under it), ArmL (−x) /
   ArmR (+x), FootL / FootR;
4. the faces the app switches (scale 1 = shown, ~0 = hidden), under Face: EyeOpenL/R and MouthSmile are the picture's
   own (empty nodes), EyeHappyL/R, EyeClosedL/R, MouthGrin and MouthO are patches of the face with those drawn on;
5. clips: 0 walk (0.56 s), 1 idle (2.4 s).
"""
import io, json, math, struct, sys, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mesh import load, normals
from decim import normalize, cluster
import paint as pm
import atlas as at

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'source')
HEIGHT = 1.35
CELL = 0.012

# joints: name, parent, rest position (world)
JOINTS = [('Body', None, (0, 0, 0)), ('Face', 'Body', (0, 0.57, 0)), ('EarL', 'Face', (-0.12, 1.03, -0.06)), ('EarR', 'Face', (0.12, 1.03, -0.06)),
          ('ArmL', 'Body', (-0.19, 0.5, -0.02)), ('ArmR', 'Body', (0.19, 0.5, -0.02)), ('FootL', 'Body', (-0.12, 0.06, 0.02)), ('FootR', 'Body', (0.12, 0.06, 0.02))]
JI = {j[0]: i for i, j in enumerate(JOINTS)}


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)


def weights(V):
    x, y = V[:, 0], V[:, 1]
    W = np.zeros((len(V), len(JOINTS)))
    head = ss(0.53, 0.61, y)
    ear = ss(1.01, 1.08, y) * head
    arm = ss(0.20, 0.235, np.abs(x)) * (1 - ss(0.53, 0.6, y)) * ss(0.2, 0.24, y)
    foot = 1 - ss(0.07, 0.14, y)
    left = x < 0
    W[:, JI['EarL']] = ear * left; W[:, JI['EarR']] = ear * ~left
    W[:, JI['Face']] = head - ear
    rest = 1 - head
    a = arm * rest; f = foot * rest * (1 - arm)
    W[:, JI['ArmL']] = a * left; W[:, JI['ArmR']] = a * ~left
    W[:, JI['FootL']] = f * left; W[:, JI['FootR']] = f * ~left
    W[:, JI['Body']] = np.clip(1 - W.sum(1), 0, 1)
    W /= W.sum(1, keepdims=True)
    # at most 4 per vertex
    idx = np.argsort(-W, 1)[:, :4]; w = np.take_along_axis(W, idx, 1); w /= w.sum(1, keepdims=True)
    return idx.astype(np.uint8), w.astype(np.float32)


# ------------------------------------------------------------------ the faces the app switches

def find_eyes(front):
    from scipy import ndimage
    a = np.asarray(front).astype(int); dark = a.sum(2) < 200
    lab, k = ndimage.label(dark); sizes = ndimage.sum(dark, lab, range(1, k + 1)); objs = ndimage.find_objects(lab)
    big = sorted([(s, o) for s, o in zip(sizes, objs) if s > 2000], key=lambda t: -t[0])[:2]
    eyes = sorted([((o[1].start + o[1].stop) / 2, (o[0].start + o[0].stop) / 2, (o[1].stop - o[1].start) / 2, (o[0].stop - o[0].start) / 2) for _, o in big])
    return eyes   # [(cx, cy, rx, ry)] image-left (−x) first


def skin_around(a, cx, cy, rx, ry):
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    r = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    ring = (r > 1.5) & (r < 2.4) & (a.sum(2) > 600)
    return tuple(int(v) for v in np.median(a[ring], 0))


FACE_BOX = (430, 220, 990, 600)
MOUTH_DY = 30   # px below the eyes to the smile line


def cover_k(girl):
    """how much bigger than the dark part of the eye its cover is (his eyes have more white and blue around the dark)"""
    return 1.25 if girl else 1.55   # the part of the front picture the patches use (x0, y0, x1, y1)


def face_variants(front, girl):
    """the front picture's face with closed eyes, happy eyes, a grin and an 'o' drawn on: 4 crops in one image"""
    a = np.asarray(front.convert('RGB')).astype(int)
    eyes = find_eyes(front)
    ink = (52, 34, 34)
    out = []
    S = 4   # draw big, then shrink (smooth lines)

    def cover(img, cx, cy, rx, ry, k=None):
        k = k or cover_k(girl)
        col = skin_around(a, cx, cy, rx, ry)
        m = Image.new('L', img.size, 0); ImageDraw.Draw(m).ellipse([(cx - rx * k) * S, (cy - ry * k) * S, (cx + rx * k) * S, (cy + ry * k) * S], 255)
        m = m.filter(ImageFilter.GaussianBlur(11 * S))
        img.paste(Image.new('RGB', img.size, col), (0, 0), m)

    def big():
        return front.convert('RGB').resize((front.width * S, front.height * S), Image.LANCZOS)

    for kind in ('closed', 'happy'):
        img = big(); d = ImageDraw.Draw(img)
        for i, (cx, cy, rx, ry) in enumerate(eyes):
            cover(img, cx, cy, rx, ry); d = ImageDraw.Draw(img)
            w = 9 * S
            if kind == 'closed':     # a lid line curving down, with lashes for her
                box = [(cx - rx * 0.95) * S, (cy - ry * 0.55) * S, (cx + rx * 0.95) * S, (cy + ry * 0.55) * S]
                d.arc(box, 15, 165, fill=ink, width=w)
                if girl:
                    out_ = -1 if i == 0 else 1          # towards the outside of the face
                    for t in (0.6, 0.8, 0.95):
                        ang = math.radians(90 - out_ * 75 * t)
                        px = cx + math.cos(ang) * rx * 0.95; py = cy + math.sin(ang) * ry * 0.55
                        d.line([px * S, py * S, (px + out_ * 16 * t) * S, (py + 10) * S], fill=ink, width=5 * S)
            else:                     # ^ ^
                box = [(cx - rx * 0.85) * S, (cy - ry * 0.35) * S, (cx + rx * 0.85) * S, (cy + ry * 0.75) * S]
                d.arc(box, 200, 340, fill=ink, width=w)
        out.append(img.resize(front.size, Image.LANCZOS))
    # the mouth: under the nose, between the eyes
    mx = (eyes[0][0] + eyes[1][0]) / 2; my = max(e[1] + e[3] for e in eyes) + MOUTH_DY    # the smile line
    for kind in ('grin', 'o'):
        img = big()
        col = skin_around(a, mx, my, 40, 18)
        m = Image.new('L', img.size, 0); ImageDraw.Draw(m).ellipse([(mx - 64) * S, (my - 14) * S, (mx + 64) * S, (my + 40) * S], 255)
        img.paste(Image.new('RGB', img.size, col), (0, 0), m.filter(ImageFilter.GaussianBlur(5 * S)))
        d = ImageDraw.Draw(img)
        if kind == 'grin':
            d.chord([(mx - 42) * S, (my - 30) * S, (mx + 42) * S, (my + 30) * S], 0, 180, fill=(120, 36, 48), outline=ink, width=4 * S)
            d.chord([(mx - 22) * S, (my + 6) * S, (mx + 22) * S, (my + 34) * S], 200, 340, fill=(236, 120, 140))
        else:
            d.ellipse([(mx - 17) * S, (my - 4) * S, (mx + 17) * S, (my + 32) * S], fill=(120, 36, 48), outline=ink, width=4 * S)
            d.chord([(mx - 11) * S, (my + 16) * S, (mx + 11) * S, (my + 32) * S], 180, 360, fill=(236, 120, 140))
        out.append(img.resize(front.size, Image.LANCZOS))
    x0, y0, x1, y1 = FACE_BOX; w, h = x1 - x0, y1 - y0
    sheet = Image.new('RGB', (2 * w, 2 * h), (255, 255, 255))
    for i, im in enumerate(out): sheet.paste(im.crop(FACE_BOX), ((i % 2) * w, (i // 2) * h))
    regions = [('eye', e) for e in eyes] + [('mouth', (mx, my + 12, 66, 40))]
    return sheet, regions


# ------------------------------------------------------------------ glb writer

class Glb:
    def __init__(self): self.bin = bytearray(); self.g = {'asset': {'version': '2.0', 'generator': 'follow-poppy build_poppy.py'}, 'bufferViews': [], 'accessors': []}

    def view(self, data: bytes, target=None):
        while len(self.bin) % 4: self.bin += b'\0'
        v = {'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': len(data)}
        if target: v['target'] = target
        self.bin += data; self.g['bufferViews'].append(v); return len(self.g['bufferViews']) - 1

    def acc(self, arr, kind, target=None, minmax=False):
        arr = np.ascontiguousarray(arr)
        ct = {np.dtype('float32'): 5126, np.dtype('uint16'): 5123, np.dtype('uint32'): 5125, np.dtype('uint8'): 5121}[arr.dtype]
        a = {'bufferView': self.view(arr.tobytes(), target), 'componentType': ct, 'count': int(arr.shape[0]), 'type': kind}
        if minmax: a['min'] = [float(x) for x in arr.reshape(arr.shape[0], -1).min(0)]; a['max'] = [float(x) for x in arr.reshape(arr.shape[0], -1).max(0)]
        self.g['accessors'].append(a); return len(self.g['accessors']) - 1

    def image(self, img, quality=88):
        b = io.BytesIO(); img.save(b, 'JPEG', quality=quality)
        self.g.setdefault('images', []).append({'bufferView': self.view(b.getvalue()), 'mimeType': 'image/jpeg'})
        self.g.setdefault('samplers', [{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 33071, 'wrapT': 33071}])
        self.g.setdefault('textures', []).append({'source': len(self.g['images']) - 1, 'sampler': 0})
        return len(self.g['textures']) - 1

    def save(self, path):
        while len(self.bin) % 4: self.bin += b'\0'
        self.g['buffers'] = [{'byteLength': len(self.bin)}]
        js = json.dumps(self.g, separators=(',', ':')).encode()
        while len(js) % 4: js += b' '
        total = 12 + 8 + len(js) + 8 + len(self.bin)
        with open(path, 'wb') as f:
            f.write(struct.pack('<III', 0x46546C67, 2, total)); f.write(struct.pack('<II', len(js), 0x4E4F534A)); f.write(js)
            f.write(struct.pack('<II', len(self.bin), 0x004E4942)); f.write(self.bin)


def quat(axis, ang):
    s = math.sin(ang / 2); return [axis[0] * s, axis[1] * s, axis[2] * s, math.cos(ang / 2)]


def qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz]


def clips():
    """walk (0.56 s) and idle (2.4 s): per joint, (times, translations or None, rotations)"""
    out = []
    T = 0.56; t = np.linspace(0, T, 17); ph = 2 * np.pi * t / T
    walk = {
        'Body': ([[0, 0.02 * (1 - math.cos(2 * p)), 0] for p in ph], [qmul(quat((0, 0, 1), 0.07 * math.sin(p)), quat((1, 0, 0), 0.05)) for p in ph]),
        'FootL': ([[-0.12, 0.06 + 0.035 * max(0, math.sin(p)), 0.02 + 0.055 * math.cos(p)] for p in ph], None),
        'FootR': ([[0.12, 0.06 + 0.035 * max(0, -math.sin(p)), 0.02 - 0.055 * math.cos(p)] for p in ph], None),
        'ArmL': (None, [quat((1, 0, 0), -0.45 * math.cos(p)) for p in ph]),
        'ArmR': (None, [quat((1, 0, 0), 0.45 * math.cos(p)) for p in ph]),
        'EarL': (None, [qmul(quat((0, 0, 1), 0.06 * math.sin(2 * p)), quat((1, 0, 0), -0.08 * (1 - math.cos(2 * p)) / 2)) for p in ph]),
        'EarR': (None, [qmul(quat((0, 0, 1), -0.06 * math.sin(2 * p)), quat((1, 0, 0), -0.08 * (1 - math.cos(2 * p)) / 2)) for p in ph]),
    }
    out.append(('walk', t, walk))
    T = 2.4; t = np.linspace(0, T, 25); ph = 2 * np.pi * t / T
    idle = {
        'Body': ([[0, 0.006 * (1 - math.cos(p)), 0] for p in ph], [[0, 0, 0, 1] for p in ph]),
        'FootL': ([[-0.12, 0.06, 0.02] for p in ph], None), 'FootR': ([[0.12, 0.06, 0.02] for p in ph], None),
        'ArmL': (None, [quat((0, 0, 1), -0.05 * math.sin(p)) for p in ph]),
        'ArmR': (None, [quat((0, 0, 1), 0.05 * math.sin(p)) for p in ph]),
        'EarL': (None, [quat((0, 0, 1), 0.05 * math.sin(p) + 0.03 * math.sin(3 * p)) for p in ph]),
        'EarR': (None, [quat((0, 0, 1), -0.05 * math.sin(p + 0.6)) for p in ph]),
    }
    out.append(('idle', t, idle))
    return out


def build(shape, n, out, preview=None):
    girl = n == 'girl'
    P, F = load(shape); P = normalize(P, HEIGHT)
    V, G, cid = cluster(P, F, CELL)
    pics = {v: Image.open(os.path.join(SRC, f'poppy_{n}_{v}.png')).convert('RGB') for v in ('front', 'right', 'back')}
    pm.EAR_Y = 1.0
    C = pm.paint(V, G, pics)
    NV, NG, UV, COL, atlas_img, vid = at.build(V, G, P, F, pics, C)
    VN = normals(V, G)[vid]
    J, W = weights(V); J = J[vid]; W = W[vid]

    gl = Glb(); g = gl.g
    base_tex = gl.image(atlas_img, 88)
    sheet, regions = face_variants(pics['front'], girl)
    face_tex = gl.image(sheet, 90)
    g['materials'] = [
        {'name': 'Poppy', 'pbrMetallicRoughness': {'baseColorTexture': {'index': base_tex}, 'metallicFactor': 0.0, 'roughnessFactor': 0.9}},
        {'name': 'PoppyFace', 'pbrMetallicRoughness': {'baseColorTexture': {'index': face_tex}, 'metallicFactor': 0.0, 'roughnessFactor': 0.9}},
    ]
    meshes = []
    idx_t = np.uint16 if len(NV) < 65536 else np.uint32
    prim = {'attributes': {'POSITION': gl.acc(NV.astype(np.float32), 'VEC3', 34962, True), 'NORMAL': gl.acc(VN.astype(np.float32), 'VEC3', 34962),
                           'TEXCOORD_0': gl.acc(UV.astype(np.float32), 'VEC2', 34962), 'COLOR_0': gl.acc(COL.astype(np.float32), 'VEC3', 34962),
                           'JOINTS_0': gl.acc(J, 'VEC4', 34962), 'WEIGHTS_0': gl.acc(W, 'VEC4', 34962)},
            'indices': gl.acc(NG.astype(idx_t).ravel(), 'SCALAR', 34963), 'material': 0}
    meshes.append({'name': 'PoppyBody', 'primitives': [prim]})

    # face patches: triangles of the face inside each region (front picture coordinates), lifted 3 mm, textured from the sheet
    fx, fy = at.project(NV, P, pics['front'].resize((at.TILE, at.TILE)), np.array([0, 0, 1.]), np.array([1, 0, 0.]))
    sx = pics['front'].width / at.TILE; fx = fx * sx; fy = fy * sx
    FN = np.cross(NV[NG[:, 1]] - NV[NG[:, 0]], NV[NG[:, 2]] - NV[NG[:, 0]]); FN /= np.linalg.norm(FN, axis=1, keepdims=True) + 1e-12
    x0, y0, x1, y1 = FACE_BOX; bw, bh = x1 - x0, y1 - y0
    face_rest = np.array(JOINTS[JI['Face']][2], float)

    def patch(region, tile):
        cx, cy, rx, ry = region
        k = cover_k(girl) + 0.35 if region is not mouth else 1.55
        inside = (((fx - cx) / (rx * k)) ** 2 + ((fy - cy) / (ry * k)) ** 2) < 1
        tri = inside[NG].all(1) & (FN[:, 2] > 0.15) & (NV[NG][:, :, 1].mean(1) > 0.6)
        T = NG[tri]; used = np.unique(T); remap = -np.ones(len(NV), int); remap[used] = np.arange(len(used))
        pos = NV[used] + VN[used] * 0.003 - face_rest
        u = ((tile % 2) * bw + (fx[used] - x0)) / (2 * bw); v = ((tile // 2) * bh + (fy[used] - y0)) / (2 * bh)
        pr = {'attributes': {'POSITION': gl.acc(pos.astype(np.float32), 'VEC3', 34962, True), 'NORMAL': gl.acc(VN[used].astype(np.float32), 'VEC3', 34962),
                             'TEXCOORD_0': gl.acc(np.stack([u, v], 1).astype(np.float32), 'VEC2', 34962)},
              'indices': gl.acc(remap[T].astype(np.uint16).ravel(), 'SCALAR', 34963), 'material': 1}
        meshes.append({'primitives': [pr]}); return len(meshes) - 1

    eyes = [r for k_, r in regions if k_ == 'eye']; mouth = [r for k_, r in regions if k_ == 'mouth'][0]
    looks = []   # (name, mesh or None, shown at rest)
    for s, e in zip('LR', eyes):
        looks += [(f'EyeOpen{s}', None, True), (f'EyeClosed{s}', patch(e, 0), False), (f'EyeHappy{s}', patch(e, 1), False)]
    looks += [('MouthSmile', None, True), ('MouthGrin', patch(mouth, 2), False), ('MouthO', patch(mouth, 3), False)]
    g['meshes'] = meshes

    # nodes: 0 Poppy, 1 mesh, joints, looks
    nodes = [{'name': 'Poppy', 'children': [1, 2]}, {'name': 'PoppyMesh', 'mesh': 0, 'skin': 0}]
    jnode = {}
    for name, parent, pos in JOINTS:
        jnode[name] = len(nodes)
        ppos = np.array(JOINTS[JI[parent]][2]) if parent else np.zeros(3)
        nd = {'name': name}
        t = (np.array(pos) - ppos).tolist()
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
                vals = np.array(tr, np.float32) - (ppos if jn.startswith('Foot') else 0)
                if not jn.startswith('Foot'): vals = vals + (np.array(JOINTS[JI[jn]][2]) - ppos)
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
        from raster import render2
        tex = np.asarray(atlas_img).astype(float)
        o = Image.new('RGB', (1600, 400), (240, 240, 245))
        for i, yaw in enumerate([0, -0.7, -np.pi / 2, np.pi]): o.paste(render2(NV, NG, yaw, 400, UV=UV, tex=tex, C=COL), (i * 400, 0))
        o.save(preview)
        sheet.save(preview.replace('.png', '_faces.png'))


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
