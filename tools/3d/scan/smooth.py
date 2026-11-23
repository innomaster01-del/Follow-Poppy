"""Cartoon faces are painted, not carved: the scanned shape has the eyes, brows and mouth carved in, never quite where
the picture paints them, which shows as a second pair of eyes / brows. This smooths the front of the face (Taubin
smoothing: no shrinking) so only the painted face shows, and cuts off the whiskers (they are painted too)."""
import numpy as np
from scipy.sparse import coo_matrix, diags

def neighbours(n, F):
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]); E = np.concatenate([E, E[:, ::-1]])
    A = coo_matrix((np.ones(len(E)), (E[:, 0], E[:, 1])), shape=(n, n)).tocsr(); A.data[:] = 1
    deg = np.asarray(A.sum(1)).ravel(); return A, deg

def taubin(P, F, weight, iters=40, lam=0.5, mu=-0.53):
    A, deg = neighbours(len(P), F)
    Dinv = diags(1 / np.maximum(deg, 1))
    W = weight[:, None]
    Q = P.copy()
    for _ in range(iters):
        for f in (lam, mu):
            avg = Dinv @ (A @ Q)
            Q = Q + f * W * (avg - Q)
    return Q

def face_weight(P, y0, y1, cx=0.0, half=0.26, zmin=0.0, soft=0.04):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    def ss(a, b, v):
        t = np.clip((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)
    return ss(y0, y0 + soft, y) * (1 - ss(y1 - soft, y1, y)) * (1 - ss(half - soft, half, np.abs(x - cx))) * ss(zmin, zmin + soft, z)

def drop_whiskers(P, F, y0, y1, zmin=0.0, gap=0.016):
    """faces of the whiskers: thin strands (the surface's other side within [gap]) in the cheeks' height band, in front"""
    from scipy.spatial import cKDTree
    from scipy.sparse.csgraph import connected_components
    from mesh import normals
    N = normals(P, F)
    zone = (P[:, 1] > y0) & (P[:, 1] < y1) & (P[:, 2] > zmin)
    idx = np.where(zone)[0]
    tree = cKDTree(P[idx])
    pairs = tree.query_pairs(gap, output_type='ndarray')
    a, b = idx[pairs[:, 0]], idx[pairs[:, 1]]
    opp = (N[a] * N[b]).sum(1) < -0.2
    thin = np.zeros(len(P), bool); thin[a[opp]] = True; thin[b[opp]] = True
    keep = ~thin[F].any(1)
    G = F[keep]; n = len(P)
    E = np.concatenate([G[:, [0, 1]], G[:, [1, 2]], G[:, [2, 0]]])
    k, lab = connected_components(coo_matrix((np.ones(len(E)), (E[:, 0], E[:, 1])), shape=(n, n)), directed=False)
    big = np.argmax(np.bincount(lab[G[:, 0]])); G = G[lab[G[:, 0]] == big]
    used = np.unique(G); remap = -np.ones(n, int); remap[used] = np.arange(len(used))
    return P[used], remap[G]


def fill_holes(P, F, max_loop=400):
    """closes the holes left where something was cut off: each boundary loop gets a fan around its centre"""
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    key = E[:, 0].astype(np.int64) * len(P) + E[:, 1]
    rev = E[:, 1].astype(np.int64) * len(P) + E[:, 0]
    s = set(key.tolist())
    bnd = [(int(a), int(b)) for (a, b), r in zip(E, rev) if r not in s]       # edges with no twin
    nxt = {}
    for a, b in bnd: nxt.setdefault(a, b)
    seen = set(); newP = [P]; newF = [F]; n = len(P)
    for a0, _ in bnd:
        if a0 in seen: continue
        loop = [a0]; seen.add(a0); cur = nxt.get(a0)
        while cur is not None and cur != a0 and cur not in seen and len(loop) <= max_loop:
            loop.append(cur); seen.add(cur); cur = nxt.get(cur)
        if cur != a0 or len(loop) < 3: continue
        c = P[loop].mean(0); ci = n; n += 1; newP.append(c[None])
        tris = [(loop[(i + 1) % len(loop)], loop[i], ci) for i in range(len(loop))]
        newF.append(np.array(tris))
    return np.concatenate(newP), np.concatenate(newF)
