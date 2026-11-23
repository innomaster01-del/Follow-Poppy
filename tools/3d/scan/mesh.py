import json, struct, numpy as np
from PIL import Image
def load(path):
    d = open(path, 'rb').read(); jl = struct.unpack_from('<I', d, 12)[0]; g = json.loads(d[20:20+jl]); bo = 20 + jl + 8
    def acc(i):
        a = g['accessors'][i]; v = g['bufferViews'][a['bufferView']]
        n = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']]; dt = {5126:np.float32,5123:np.uint16,5125:np.uint32}[a['componentType']]
        return np.frombuffer(d, dt, a['count']*n, bo + v.get('byteOffset',0) + a.get('byteOffset',0)).reshape(a['count'], n) if n>1 else np.frombuffer(d, dt, a['count'], bo + v.get('byteOffset',0) + a.get('byteOffset',0))
    p = g['meshes'][0]['primitives'][0]
    return acc(p['attributes']['POSITION']).astype(np.float64), acc(p['indices']).reshape(-1,3).astype(np.int64)
def normals(P, F):
    fn = np.cross(P[F[:,1]]-P[F[:,0]], P[F[:,2]]-P[F[:,0]])
    vn = np.zeros_like(P)
    for k in range(3): np.add.at(vn, F[:,k], fn)
    return vn / (np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12)
def render(P, F, C, yaw, size=512, bg=(240,240,245), ss=2):
    if ss > 1: return render(P, F, C, yaw, size * ss, bg, 1).resize((size, size), Image.LANCZOS)
    """orthographic, camera looking at the model from direction yaw (0 = from +z), y up. C: per-vertex colour 0..1"""
    c, s = np.cos(yaw), np.sin(yaw)
    R = np.array([[c,0,-s],[0,1,0],[s,0,c]])        # rotate model so the camera is on +z
    Q = P @ R.T
    N = normals(P, F) @ R.T
    lo = Q.min(0); hi = Q.max(0); sc = 0.9*size/max(hi[0]-lo[0], hi[1]-lo[1]); cx = (lo[0]+hi[0])/2; cy = (lo[1]+hi[1])/2
    X = (Q[:,0]-cx)*sc + size/2; Y = size/2 - (Q[:,1]-cy)*sc; Z = Q[:,2]
    img = np.zeros((size,size,3)) + np.array(bg)/255; zb = np.full((size,size), -1e9)
    L = np.array([0.4,0.6,0.7]); L /= np.linalg.norm(L)
    shade = (0.45 + 0.55*np.clip(N@L,0,1))[:,None]
    col = C*shade
    tri = F[(N[F].mean(1)[:,2] > -0.2)]
    # splat triangles by barycentric rasterisation (vectorised per triangle bbox is slow; use dense vertex splats instead)
    keep = N[:, 2] > -0.05
    order = np.argsort(Z[keep]); Xk = X[keep][order]; Yk = Y[keep][order]; ck = col[keep][order]; Zk = Z[keep][order]
    zb2 = np.full((size, size), -1e9)
    for dx in (-1, 0, 1, 2):
        for dy in (-1, 0, 1, 2):
            xx = np.clip(Xk.astype(int) + dx, 0, size - 1); yy = np.clip(Yk.astype(int) + dy, 0, size - 1)
            np.maximum.at(zb2, (yy, xx), Zk)
    for dx in (-1, 0, 1, 2):
        for dy in (-1, 0, 1, 2):
            xx = np.clip(Xk.astype(int) + dx, 0, size - 1); yy = np.clip(Yk.astype(int) + dy, 0, size - 1)
            ok = Zk >= zb2[yy, xx] - 0.02
            img[yy[ok], xx[ok]] = ck[ok]
    return Image.fromarray((np.clip(img,0,1)*255).astype(np.uint8))
