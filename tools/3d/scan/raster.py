import numpy as np
from PIL import Image
from mesh import normals
def bary(n):
    pts = [(i / n, j / n) for i in range(n + 1) for j in range(n + 1 - i)]
    a = np.array(pts); return np.stack([a[:, 0], a[:, 1], 1 - a[:, 0] - a[:, 1]], 1)
def render2(V, G, yaw, size=512, C=None, UV=None, tex=None, pitch=0.0, bg=(240, 240, 245), box=None, ss=2):
    S = size * ss
    c, s = np.cos(yaw), np.sin(yaw)
    R = np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])
    cp, sp = np.cos(pitch), np.sin(pitch); Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    R = Rx @ R
    Q = V @ R.T; N = normals(V, G) @ R.T
    lo, hi = (Q.min(0), Q.max(0)) if box is None else box
    sc = 0.92 * S / max(hi[0] - lo[0], hi[1] - lo[1]); cx = (lo[0] + hi[0]) / 2; cy = (lo[1] + hi[1]) / 2
    X = (Q[:, 0] - cx) * sc + S / 2; Y = S / 2 - (Q[:, 1] - cy) * sc; Z = Q[:, 2]
    # samples per triangle by its size on screen
    e = np.maximum.reduce([np.hypot(X[G[:, i]] - X[G[:, (i + 1) % 3]], Y[G[:, i]] - Y[G[:, (i + 1) % 3]]) for i in range(3)])
    img = np.zeros((S, S, 3)) + np.array(bg) / 255; zb = np.full((S, S), -1e9)
    L = np.array([0.35, 0.55, 0.75]); L /= np.linalg.norm(L)
    for n in (2, 4, 8, 16, 32):
        sel = np.where((e <= n) if n < 32 else (e > 16))[0] if n > 2 else np.where(e <= 2)[0]
        if n > 2 and n < 32: sel = np.where((e > n / 2) & (e <= n))[0]
        if len(sel) == 0: continue
        B = bary(max(n, 2) if n < 32 else int(min(e.max(), 120)))
        for chunk in np.array_split(sel, max(1, len(sel) * len(B) // 400_000 + 1)):
            _draw(chunk, B, G, X, Y, Z, N, C, UV, tex, img, zb, S, L)
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    return im.resize((size, size), Image.LANCZOS) if ss > 1 else im


def _draw(sel, B, G, X, Y, Z, N, C, UV, tex, img, zb, S, L):
    if True:
        T = G[sel]
        px = (B @ X[T].T).T; py = (B @ Y[T].T).T; pz = (B @ Z[T].T).T          # (tris, samples)
        nn = np.einsum('sk,tkd->tsd', B, N[T])
        if UV is not None:
            uv = np.einsum('sk,tkd->tsd', B, UV[T]); H, W = tex.shape[:2]
            tx = uv[..., 0] * W - 0.5; ty = uv[..., 1] * H - 0.5
            x0 = np.clip(np.floor(tx).astype(int), 0, W - 2); y0 = np.clip(np.floor(ty).astype(int), 0, H - 2)
            fx = np.clip(tx - x0, 0, 1)[..., None]; fy = np.clip(ty - y0, 0, 1)[..., None]
            col = (tex[y0, x0] * (1 - fx) * (1 - fy) + tex[y0, x0 + 1] * fx * (1 - fy) + tex[y0 + 1, x0] * (1 - fx) * fy + tex[y0 + 1, x0 + 1] * fx * fy) / 255
            if C is not None: col = col * np.einsum('sk,tkd->tsd', B, C[T])
        elif C is not None: col = np.einsum('sk,tkd->tsd', B, C[T])
        else: col = np.full(px.shape + (3,), 0.85)
        nl = nn / (np.linalg.norm(nn, axis=-1, keepdims=True) + 1e-9)
        sh = 0.55 + 0.45 * np.clip(nl @ L, 0, 1)
        col = col * sh[..., None]
        xi = np.clip(px.astype(int).ravel(), 0, S - 1); yi = np.clip(py.astype(int).ravel(), 0, S - 1); z = pz.ravel(); cc = col.reshape(-1, 3)
        front = nl[..., 2].ravel() > -0.3
        xi, yi, z, cc = xi[front], yi[front], z[front], cc[front]
        np.maximum.at(zb, (yi, xi), z)
        ok = z >= zb[yi, xi] - 1e-6
        img[yi[ok], xi[ok]] = cc[ok]


def raster_xy(X, Y, Z, G, col, S, bg=0.0):
    """Triangles already in pixel coordinates (X, Y; Z nearer = larger) with a value per vertex → (S x S x C) image and
    a coverage mask."""
    C = col.shape[1]
    img = np.full((S, S, C), bg, float); zb = np.full((S, S), -1e9)
    e = np.maximum.reduce([np.hypot(X[G[:, i]] - X[G[:, (i + 1) % 3]], Y[G[:, i]] - Y[G[:, (i + 1) % 3]]) for i in range(3)])
    for lo_, hi_, n in ((0, 1.5, 2), (1.5, 3, 4), (3, 6, 8), (6, 12, 16), (12, 1e9, 40)):
        sel = np.where((e > lo_) & (e <= hi_))[0]
        if len(sel) == 0: continue
        B = bary(n); T = G[sel]
        px = (B @ X[T].T).T; py = (B @ Y[T].T).T; pz = (B @ Z[T].T).T
        cc = np.einsum('sk,tkd->tsd', B, col[T])
        xi = np.clip(px.astype(int).ravel(), 0, S - 1); yi = np.clip(py.astype(int).ravel(), 0, S - 1); z = pz.ravel(); cc = cc.reshape(-1, C)
        np.maximum.at(zb, (yi, xi), z)
        ok = z >= zb[yi, xi] - 1e-6
        img[yi[ok], xi[ok]] = cc[ok]
    return img, zb > -1e8
