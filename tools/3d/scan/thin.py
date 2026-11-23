"""Removes thin strands from a scanned shape (whiskers, threads between the face and the hands): a point is thin when
the surface's other side is within a few millimetres (a neighbour facing the opposite way). Below the ears only (the
ears' rims are thin on purpose). The whiskers are drawn in the texture anyway."""
import numpy as np
from scipy.spatial import cKDTree
from mesh import normals

def drop_thin(P, F, gap=0.006, below=1.0, grow=2):
    N = normals(P, F)
    tree = cKDTree(P)
    pairs = tree.query_pairs(gap, output_type='ndarray')
    opp = (N[pairs[:, 0]] * N[pairs[:, 1]]).sum(1) < -0.3
    thin = np.zeros(len(P), bool); thin[pairs[opp].ravel()] = True
    thin &= P[:, 1] < below
    # and their immediate neighbours (the strand's roots)
    for _ in range(grow):
        t2 = thin.copy()
        for k in range(3):
            m = thin[F[:, k]]
            t2[F[m].ravel()] = True
        thin = t2 & (P[:, 1] < below)
    keepF = ~thin[F].any(1)
    # keep the biggest connected piece (drops whisker stubs left floating)
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    G = F[keepF]; n = len(P)
    E = np.concatenate([G[:, [0, 1]], G[:, [1, 2]], G[:, [2, 0]]])
    k, lab = connected_components(coo_matrix((np.ones(len(E)), (E[:, 0], E[:, 1])), shape=(n, n)), directed=False)
    big = np.argmax(np.bincount(lab[G[:, 0]]))
    G = G[lab[G[:, 0]] == big]
    used = np.unique(G); remap = -np.ones(n, int); remap[used] = np.arange(len(used))
    return P[used], remap[G]
