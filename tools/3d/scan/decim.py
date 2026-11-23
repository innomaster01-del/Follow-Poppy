import numpy as np
def normalize(P, height=1.35):
    """feet on y = 0, centred in x / z, [height] tall"""
    lo = P.min(0); hi = P.max(0); s = height / (hi[1] - lo[1])
    Q = (P - np.array([(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2])) * s
    return Q
def cluster(P, F, cell):
    """vertex clustering with a per-cluster quadric (the point closest to the planes of its faces)"""
    key = np.floor(P / cell).astype(np.int64)
    _, cid, counts = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    cid = cid.ravel(); nc = cid.max() + 1
    # face planes
    a = P[F[:, 0]]; b = P[F[:, 1]]; c = P[F[:, 2]]
    n = np.cross(b - a, c - a); area = np.linalg.norm(n, axis=1); n = n / (area[:, None] + 1e-20)
    d = -(n * a).sum(1)
    pl = np.concatenate([n, d[:, None]], 1)
    Kf = pl[:, :, None] * pl[:, None, :] * area[:, None, None]
    Q = np.zeros((nc, 4, 4))
    for k in range(3): np.add.at(Q, cid[F[:, k]], Kf)
    mean = np.zeros((nc, 3)); np.add.at(mean, cid, P); mean /= np.bincount(cid, minlength=nc)[:, None]
    A = Q[:, :3, :3] + np.eye(3)[None] * 1e-6 * (Q[:, :3, :3].trace(axis1=1, axis2=2)[:, None, None] + 1e-12)
    bvec = -Q[:, :3, 3]
    try: opt = np.linalg.solve(A, bvec[..., None])[..., 0]
    except np.linalg.LinAlgError: opt = mean
    # keep the optimum only when it stays inside (near) its cell, else the mean
    far = np.linalg.norm(opt - mean, axis=1) > cell * 0.9
    opt[far] = mean[far]
    NF = cid[F]
    ok = (NF[:, 0] != NF[:, 1]) & (NF[:, 1] != NF[:, 2]) & (NF[:, 0] != NF[:, 2])
    NF = NF[ok]
    s = np.sort(NF, 1); _, u = np.unique(s, axis=0, return_index=True); NF = NF[np.sort(u)]
    return opt, NF, cid
