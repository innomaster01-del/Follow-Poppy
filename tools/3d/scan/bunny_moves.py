"""The new bunny's skeleton, props and moves (the ten things on the character sheet, plus walking and standing).

Joints (positions in metres, the model 1.35 m tall, facing +z): Body (rest = identity), Face (the head) with EarL / EarR,
ArmL (−x) / ArmR (+x) at the shoulders with ElbowL / ElbowR, FootL / FootR, Tail.

Props, hidden until a move shows them (scale ~0 / 1, switched by the app like the faces): PropPin (a map pin she hugs),
PropPhone (in her −x hand), PropArrowL / PropArrowR (a glowing navigation arrow in the hand that does not point),
PropRing (a glowing ring on the ground, for meditating).

Clips (index = what the app plays):
  0 walk (0.56 s, a bouncy run)  1 idle (2.4 s)
  2 thumbs (thumbs up, wink)     3 point_l / 4 point_r (points the way, arrow in the other hand)
  5 pin (hugs the pin)           6 peek (leans out to the side, wink)
  7 cheer (jumps, arms up)       8 phone (looks at the phone, points at it)
  9 think (hand to the chin)    10 ok (hand up by the face, wink)
 11 meditate (sits, hands on knees, breathing)
"""
import math
import numpy as np

JOINTS = [('Body', None, (0, 0, 0)), ('Face', 'Body', (0, 0.58, 0.02)), ('EarL', 'Face', (-0.12, 1.06, -0.08)), ('EarR', 'Face', (0.12, 1.06, -0.08)),
          ('ArmL', 'Body', (-0.19, 0.5, 0.05)), ('ArmR', 'Body', (0.19, 0.5, 0.05)),
          ('ElbowL', 'ArmL', (-0.285, 0.5, 0.05)), ('ElbowR', 'ArmR', (0.285, 0.5, 0.05)),
          ('FootL', 'Body', (-0.12, 0.05, 0.04)), ('FootR', 'Body', (0.12, 0.05, 0.04)), ('Tail', 'Body', (0, 0.22, -0.26))]
JI = {j[0]: i for i, j in enumerate(JOINTS)}
HAND_X = 0.37            # where the hand is along the arm (|x|)
CLIP_NAMES = ['walk', 'idle', 'thumbs', 'point_l', 'point_r', 'pin', 'peek', 'cheer', 'phone', 'think', 'ok', 'meditate']


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)


def weights(V):
    x, y, z = V[:, 0], V[:, 1], V[:, 2]; ax = np.abs(x)
    W = np.zeros((len(V), len(JOINTS)))
    lo = np.interp(y, [0.5, 0.6], [0.18, 0.295])
    arm = ss(lo, lo + 0.035, ax) * ss(0.36, 0.4, y) * (1 - ss(0.74, 0.78, y))
    fore = arm * ss(0.255, 0.3, ax)                       # past the elbow: the forearm and the hand (the thumb too)
    head = ss(0.54, 0.62, y) * (1 - arm)
    ear = ss(1.03, 1.1, y) * head
    foot = (1 - ss(0.07, 0.13, y)) * (1 - arm)
    tail = ss(-0.22, -0.27, z) * ss(0.05, 0.09, y) * (1 - ss(0.36, 0.4, y)) * (1 - foot)
    left = x < 0
    W[:, JI['EarL']] = ear * left; W[:, JI['EarR']] = ear * ~left
    W[:, JI['Face']] = head - ear
    W[:, JI['ArmL']] = (arm - fore) * left; W[:, JI['ArmR']] = (arm - fore) * ~left
    W[:, JI['ElbowL']] = fore * left; W[:, JI['ElbowR']] = fore * ~left
    W[:, JI['FootL']] = foot * left; W[:, JI['FootR']] = foot * ~left
    W[:, JI['Tail']] = tail
    W[:, JI['Body']] = np.clip(1 - W.sum(1), 0, 1)
    W /= W.sum(1, keepdims=True)
    idx = np.argsort(-W, 1)[:, :4]; w = np.take_along_axis(W, idx, 1); w /= w.sum(1, keepdims=True)
    return idx.astype(np.uint8), w.astype(np.float32)


# ------------------------------------------------------------------ rotations

def quat(axis, ang):
    s = math.sin(ang / 2); return [axis[0] * s, axis[1] * s, axis[2] * s, math.cos(ang / 2)]


def qmul(*qs):
    out = [0, 0, 0, 1]
    for b in qs:
        ax, ay, az, aw = out; bx, by, bz, bw = b
        out = [aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz]
    return out


X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)


def arm(side, raise_=0.0, fwd=0.0, twist=0.0):
    """shoulder: [side] +1 for the +x arm. raise > 0 lifts it (from sideways), fwd > 0 swings it forwards."""
    return qmul(quat(Y, -fwd * side), quat(Z, raise_ * side), quat(X, twist * side))


SHOULDER = {1: np.array([0.19, 0.5, 0.05]), -1: np.array([-0.19, 0.5, 0.05])}


def reach(side, target, body_y=0.0, wiggle=(0.0, 0.0)):
    """the shoulder turned so the arm points at [target] (where the hand should be, in the body's rest space; the arms
    are short, so this decides a gesture): direction (cos r cos f, sin r, cos r sin f) for the +x arm, mirrored for −x"""
    d = np.array(target, float) - SHOULDER[side] - np.array([0, body_y, 0]); d /= np.linalg.norm(d)
    r = math.asin(max(-1.0, min(1.0, d[1]))) + wiggle[0]
    f = math.atan2(d[2], d[0] * side) + wiggle[1]
    return arm(side, r, f)


def elbow(side, fwd=0.0, up=0.0):
    """elbow: fwd > 0 bends the forearm forwards, up > 0 bends it upwards."""
    return qmul(quat(Y, -fwd * side), quat(Z, up * side))


def body(lean=0.0, roll=0.0, turn=0.0):
    return qmul(quat(Y, turn), quat(Z, roll), quat(X, lean))


REST = {'FootL': (-0.12, 0.05, 0.04), 'FootR': (0.12, 0.05, 0.04)}


def clips():
    """[(name, times, {joint: (translations or None, rotations or None)}, props shown)]"""
    out = []

    def make(name, T, n, f, props=()):
        t = np.linspace(0, T, n); ch = {}
        for i, ti in enumerate(t):
            for j, (tr, rot) in f(2 * math.pi * ti / T, ti).items():
                c = ch.setdefault(j, ([], []))
                c[0].append(tr); c[1].append(rot)
        chans = {j: (None if any(v is None for v in trs) else trs, None if any(v is None for v in rots) else rots) for j, (trs, rots) in ch.items()}
        out.append((name, t, chans, props))

    def still(**extra):
        d = {'FootL': (REST['FootL'], None), 'FootR': (REST['FootR'], None)}
        d.update(extra); return d

    # 0 walk: a bouncy run, leaning in, arms bent and swinging, a little hop every step, ears and tail bobbing
    def walk(p, t):
        s = math.sin(p); c = math.cos(p)
        return {
            'Body': ((0, 0.04 * abs(s), 0.0), body(lean=0.14, roll=0.05 * s, turn=0.08 * c)),
            'Face': (None, qmul(quat(X, -0.1), quat(Z, -0.04 * s))),
            'FootL': ((-0.11, 0.05 + 0.06 * max(0, s), 0.04 + 0.09 * c), quat(X, -0.4 * max(0, s))),
            'FootR': ((0.11, 0.05 + 0.06 * max(0, -s), 0.04 - 0.09 * c), quat(X, -0.4 * max(0, -s))),
            'ArmL': (None, arm(-1, -0.95, 0.75 * c)), 'ArmR': (None, arm(1, -0.95, -0.75 * c)),
            'ElbowL': (None, elbow(-1, 1.25)), 'ElbowR': (None, elbow(1, 1.25)),
            'EarL': (None, qmul(quat(X, -0.25 - 0.15 * abs(s)), quat(Z, 0.08 * math.sin(2 * p)))),
            'EarR': (None, qmul(quat(X, -0.25 - 0.15 * abs(s)), quat(Z, -0.08 * math.sin(2 * p)))),
            'Tail': (None, quat(Y, 0.4 * math.sin(2 * p))),
        }
    make('walk', 0.56, 17, walk)

    # 1 idle: arms relaxed, breathing, an ear twitch, a tail wiggle
    def idle(p, t):
        return still(Body=((0, 0.006 * (1 - math.cos(p)), 0), body()),
                     ArmL=(None, arm(-1, -1.05 - 0.04 * math.sin(p), 0.15)), ArmR=(None, arm(1, -1.05 - 0.04 * math.sin(p), 0.15)),
                     ElbowL=(None, elbow(-1, 0.35)), ElbowR=(None, elbow(1, 0.35)),
                     EarL=(None, quat(Z, 0.05 * math.sin(p) + 0.04 * math.sin(3 * p))), EarR=(None, quat(Z, -0.05 * math.sin(p + 0.6))),
                     Tail=(None, quat(Y, 0.2 * math.sin(2 * p))), Face=(None, quat(Z, 0.03 * math.sin(p))))
    make('idle', 2.4, 25, idle)

    # 2 thumbs: her −x hand forward with the thumb up, the other on her hip, head tilted (wink: the app)
    def thumbs(p, t):
        b = 0.04 * math.sin(2 * p)
        return still(Body=((0, 0.005, 0), body(roll=-0.05, turn=0.12)), Face=(None, qmul(quat(Z, 0.14), quat(Y, -0.1))),
                     ArmL=(None, reach(-1, (-0.2, 0.64 + b, 0.36))), ElbowL=(None, elbow(-1, 0.1, 0.5)),
                     ArmR=(None, reach(1, (0.26, 0.34, 0.02))), ElbowR=(None, elbow(1, 1.0)),
                     EarL=(None, quat(Z, 0.06)), EarR=(None, quat(Z, -0.1)), Tail=(None, quat(Y, 0.3 * math.sin(2 * p))))
    make('thumbs', 1.6, 17, thumbs)

    # 3 / 4 point: one arm points the way (to her left or right), the other holds the glowing arrow up in front
    def pointer(side):
        def f(p, t):
            w = 0.06 * math.sin(2 * p)
            pa = 'ArmR' if side > 0 else 'ArmL'; pe = 'ElbowR' if side > 0 else 'ElbowL'
            ha = 'ArmL' if side > 0 else 'ArmR'; he = 'ElbowL' if side > 0 else 'ElbowR'
            return still(Body=((0, 0, 0), body(turn=0.25 * side, roll=0.05 * side)), Face=(None, qmul(quat(Y, 0.45 * side), quat(Z, -0.06 * side))),
                         **{pa: (None, reach(side, (0.19 * side + 0.8 * side, 0.5 + 0.5 + w, 0.05 + 0.35))), pe: (None, elbow(side, 0.0)),
                            ha: (None, reach(-side, (-0.13 * side, 0.58, 0.38))), he: (None, elbow(-side, 0.2, 0.6))},
                         EarL=(None, quat(Z, 0.05)), EarR=(None, quat(Z, -0.05)), Tail=(None, quat(Y, 0.25 * math.sin(2 * p))))
        return f
    make('point_l', 1.2, 13, pointer(-1), ('PropArrowR',))
    make('point_r', 1.2, 13, pointer(1), ('PropArrowL',))

    # 5 pin: hugs the map pin in front of her chest, swaying
    def pin(p, t):
        s = math.sin(p)
        return still(Body=((0, 0.008 * (1 - math.cos(2 * p)), 0), body(roll=0.06 * s, lean=0.04)), Face=(None, qmul(quat(Z, -0.14 * s), quat(X, 0.06))),
                     ArmL=(None, reach(-1, (-0.1, 0.47, 0.36))), ArmR=(None, reach(1, (0.1, 0.47, 0.36))),
                     ElbowL=(None, elbow(-1, 0.6, 0.2)), ElbowR=(None, elbow(1, 0.6, 0.2)),
                     EarL=(None, quat(Z, 0.1 * s)), EarR=(None, quat(Z, 0.1 * s)), Tail=(None, quat(Y, 0.35 * math.sin(2 * p))))
    make('pin', 1.6, 17, pin, ('PropPin',))

    # 6 peek: leans out to the side with a wink, hands together in front
    def peek(p, t):
        k = 0.5 - 0.5 * math.cos(p)                  # out and back
        return still(Body=((0.06 * k, -0.04 * k, 0), body(roll=0.4 * k, lean=0.1 * k)), Face=(None, quat(Z, -0.3 * k)),
                     ArmL=(None, reach(-1, (-0.1, 0.4, 0.33))), ArmR=(None, reach(1, (0.1, 0.4, 0.33))),
                     ElbowL=(None, elbow(-1, 0.6)), ElbowR=(None, elbow(1, 0.6)),
                     EarL=(None, quat(Z, 0.15 * k)), EarR=(None, quat(Z, 0.25 * k)), Tail=(None, quat(Y, 0.3 * math.sin(2 * p))))
    make('peek', 1.8, 19, peek)

    # 7 cheer: jumps with both arms up, feet tucked
    def cheer(p, t):
        j = max(0.0, math.sin(p))
        return {
            'Body': ((0, 0.16 * j, 0), body(lean=-0.06 * j)), 'Face': (None, quat(X, -0.15)),
            'FootL': ((-0.12, 0.05 + 0.05 * j, 0.04 - 0.04 * j), quat(X, 0.5 * j)), 'FootR': ((0.12, 0.05 + 0.05 * j, 0.04 - 0.04 * j), quat(X, 0.5 * j)),
            'ArmL': (None, reach(-1, (-0.19 - 0.45, 0.5 + 0.9 + 0.2 * j, 0.15))), 'ArmR': (None, reach(1, (0.19 + 0.45, 0.5 + 0.9 + 0.2 * j, 0.15))),
            'ElbowL': (None, elbow(-1, 0.0, 0.3)), 'ElbowR': (None, elbow(1, 0.0, 0.3)),
            'EarL': (None, quat(X, -0.3 * j)), 'EarR': (None, quat(X, -0.3 * j)), 'Tail': (None, quat(Y, 0.5 * math.sin(2 * p))),
        }
    make('cheer', 0.8, 13, cheer)

    # 8 phone: the phone in her −x hand in front, the other hand points at it, she looks at it
    def phone(p, t):
        w = 0.08 * math.sin(2 * p)
        return still(Body=((0, 0, 0), body(turn=-0.1)), Face=(None, qmul(quat(X, 0.2), quat(Y, -0.25), quat(Z, 0.08))),
                     ArmL=(None, reach(-1, (-0.13, 0.6, 0.38))), ElbowL=(None, elbow(-1, 0.2, 0.6)),
                     ArmR=(None, reach(1, (0.04, 0.5 + w, 0.38))), ElbowR=(None, elbow(1, 0.5)),
                     EarL=(None, quat(Z, 0.08)), EarR=(None, quat(Z, -0.08)), Tail=(None, quat(Y, 0.25 * math.sin(2 * p))))
    make('phone', 1.6, 17, phone, ('PropPhone',))

    # 9 think: her +x hand to the chin, the other arm across under it, head tilted, looking up
    def think(p, t):
        s = math.sin(p)
        return still(Body=((0, 0, 0), body(roll=-0.04)), Face=(None, qmul(quat(Z, 0.18 + 0.04 * s), quat(X, -0.18))),
                     ArmR=(None, reach(1, (0.07, 0.62, 0.34))), ElbowR=(None, elbow(1, 0.3, 0.9)),
                     ArmL=(None, reach(-1, (0.0, 0.44, 0.32))), ElbowL=(None, elbow(-1, 0.8)),
                     EarL=(None, quat(Z, 0.12)), EarR=(None, quat(Z, -0.02)), Tail=(None, quat(Y, 0.15 * s)))
    make('think', 2.4, 25, think)

    # 10 ok: her +x hand up beside the face (wink: the app), the other relaxed
    def ok(p, t):
        w = 0.05 * math.sin(2 * p)
        return still(Body=((0, 0, 0), body(roll=0.06, turn=-0.1)), Face=(None, quat(Z, -0.12)),
                     ArmR=(None, reach(1, (0.3, 0.76 + w, 0.22))), ElbowR=(None, elbow(1, 0.2, 0.9)),
                     ArmL=(None, reach(-1, (-0.26, 0.32, 0.08))), ElbowL=(None, elbow(-1, 0.5)),
                     EarL=(None, quat(Z, 0.04)), EarR=(None, quat(Z, -0.12)), Tail=(None, quat(Y, 0.3 * math.sin(2 * p))))
    make('ok', 1.6, 17, ok)

    # 11 meditate: sits low, feet in and forward (cross-legged), hands on the knees, slow breathing, ears at rest
    def meditate(p, t):
        br = 0.008 * (1 - math.cos(p))
        return {
            'Body': ((0, -0.2 + br, 0.02), body(lean=0.05)), 'Face': (None, quat(X, 0.05)),
            'FootL': ((0.0, 0.2, 0.2), qmul(quat(Y, 0.9), quat(Z, -0.4))), 'FootR': ((0.0, 0.17, 0.22), qmul(quat(Y, -0.9), quat(Z, 0.4))),
            'ArmL': (None, reach(-1, (-0.2, 0.12, 0.3), body_y=-0.2)), 'ArmR': (None, reach(1, (0.2, 0.12, 0.3), body_y=-0.2)),
            'ElbowL': (None, elbow(-1, 0.3, -0.2)), 'ElbowR': (None, elbow(1, 0.3, -0.2)),
            'EarL': (None, quat(Z, 0.05 + 0.03 * math.sin(p))), 'EarR': (None, quat(Z, -0.05 - 0.03 * math.sin(p))), 'Tail': (None, quat(Y, 0.0)),
        }
    make('meditate', 4.0, 25, meditate, ('PropRing',))
    return out


# ------------------------------------------------------------------ props (simple meshes)

def _sphere(c, r, n=16, m=10):
    vs = []; fs = []
    for i in range(m + 1):
        th = math.pi * i / m
        for j in range(n):
            ph = 2 * math.pi * j / n
            vs.append((c[0] + r * math.sin(th) * math.cos(ph), c[1] + r * math.cos(th), c[2] + r * math.sin(th) * math.sin(ph)))
    for i in range(m):
        for j in range(n):
            a = i * n + j; b = i * n + (j + 1) % n; c_ = (i + 1) * n + j; d = (i + 1) * n + (j + 1) % n
            fs += [(a, c_, b), (b, c_, d)]
    return np.array(vs), np.array(fs)


def _merge(parts):
    V = []; F = []; o = 0
    for v, f in parts: V.append(v); F.append(f + o); o += len(v)
    return np.concatenate(V), np.concatenate(F)


def pin_mesh(s=1.0):
    """a map pin: a round head tapering to a point, with a white dot in front (two parts: body, dot)"""
    vs = []; fs = []; n = 20
    prof = [(0.0, 0.17), (0.04, 0.165), (0.066, 0.145), (0.075, 0.12), (0.07, 0.095), (0.055, 0.07), (0.035, 0.045), (0.015, 0.02), (0.0, 0.0)]
    for (r, y) in prof:
        for j in range(n):
            ph = 2 * math.pi * j / n; vs.append((r * math.cos(ph), y, r * math.sin(ph)))
    for i in range(len(prof) - 1):
        for j in range(n):
            a = i * n + j; b = i * n + (j + 1) % n; c = (i + 1) * n + j; d = (i + 1) * n + (j + 1) % n
            fs += [(a, b, c), (b, d, c)]
    body_ = (np.array(vs) * s, np.array(fs))
    dot = _sphere((0, 0.12 * s, 0.062 * s), 0.028 * s)
    dot = (dot[0] * np.array([1, 1, 0.35]) + np.array([0, 0, 0.062 * s * 0.65]), dot[1])
    return body_, dot


def box_mesh(w, h, d):
    x, y, z = w / 2, h / 2, d / 2
    V = np.array([(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z), (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)])
    F = np.array([(4, 5, 6), (4, 6, 7), (1, 0, 3), (1, 3, 2), (0, 4, 7), (0, 7, 3), (5, 1, 2), (5, 2, 6), (3, 7, 6), (3, 6, 2), (0, 1, 5), (0, 5, 4)])
    return V, F


def arrow_mesh(s=0.17, t=0.016):
    """the navigation arrow (an arrowhead with a notch), flat, pointing up (+y)"""
    pts = [(0, 1.0), (0.62, -0.75), (0, -0.35), (-0.62, -0.75)]
    top = [(x * s, y * s, t / 2) for x, y in pts]; bot = [(x * s, y * s, -t / 2) for x, y in pts]
    V = np.array(top + bot)
    F = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6)]
    for i in range(4):
        j = (i + 1) % 4; F += [(i, i + 4, j), (j, i + 4, j + 4)]
    return V, np.array(F)


def ring_mesh(R=0.36, r=0.018, n=48, m=8):
    vs = []; fs = []
    for i in range(n):
        a = 2 * math.pi * i / n
        for j in range(m):
            b = 2 * math.pi * j / m
            vs.append(((R + r * math.cos(b)) * math.cos(a), r * math.sin(b) + r, (R + r * math.cos(b)) * math.sin(a)))
    for i in range(n):
        for j in range(m):
            a = i * m + j; b_ = i * m + (j + 1) % m; c = ((i + 1) % n) * m + j; d = ((i + 1) % n) * m + (j + 1) % m
            fs += [(a, b_, c), (b_, d, c)]
    return np.array(vs), np.array(fs)


def flat_normals(V, F):
    """per-face vertices with flat normals (crisp props)"""
    P = V[F].reshape(-1, 3); G = np.arange(len(P)).reshape(-1, 3)
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    return P, G, np.repeat(n, 3, 0)


def smooth_normals(V, F):
    n = np.zeros_like(V, dtype=float)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    for k in range(3): np.add.at(n, F[:, k], fn)
    return n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)
