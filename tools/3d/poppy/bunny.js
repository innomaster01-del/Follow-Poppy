// Poppy, the new look: a chibi bunny in a hoodie (three.js r128 in Node → GLB). Two of them:
//   girl: pink hoodie, pink inside the ears, dark warm eyes with lashes
//   boy:  blue hoodie, blue inside the ears, blue eyes
// The ears' outside and rim are white like the body; only the inside of the ear is coloured.
// Same parts and clips as before, so the app drives it unchanged:
//   nodes Body, Torso, Face (the head, turns), ArmL (−x) / ArmR (+x) at the shoulders, FootL / FootR, EarL / EarR,
//   faces switched by scale: EyeOpenL/R, EyeHappyL/R, EyeClosedL/R, MouthSmile, MouthGrin, MouthO
//   clips: 0 "walk" (0.56 s loop), 1 "idle" (2.4 s). Faces +z, feet on y = 0, about 1.4 units tall with the ears.
// usage: node bunny.js <three.min.js> <girl|boy> <out.glb>
const fs = require('fs');
const { writeGLB, loadThree } = require('./gltf_writer');
const [threePath, gender, outPath] = process.argv.slice(2);
const THREE = loadThree(threePath).THREE;
const girl = gender !== 'boy';
const C = hex => new THREE.Color(hex).convertSRGBToLinear();

// ---------------- colours and materials ----------------
// girl: pink hoodie; boy: black hoodie, sunglasses and sneakers (as in the reference pictures). Both: blue eyes, the
// split pink-blue heart on the hoodie; the inside of the ears pink (girl) or blue (boy)
const FUR = 0xf6f4f8, HOODIE = girl ? 0xff5aa8 : 0x26262d, HOODIE_DARK = girl ? 0xe8418f : 0x1a1a20;
const EAR_IN = girl ? 0xff8cc2 : 0x6eb4ff, PAD = 0xff9cc6, IRIS = 0x2f6fd6, IRIS_LOW = 0x7cc0ff;
const std = (hex, rough = 0.85, extra = {}) => Object.assign(new THREE.MeshStandardMaterial({ color: C(hex), roughness: rough, metalness: 0 }), extra);
const M = {
  skin: std(FUR, 0.95), hoodie: std(HOODIE, 0.9), hoodieDark: std(HOODIE_DARK, 0.92), white: std(0xffffff, 0.7),
  earIn: std(EAR_IN, 0.9), pad: std(PAD, 0.8), nose: std(0xff8fb4, 0.45), ink: std(0x2a1824, 0.6), brow: std(0x8a6a6a, 0.8),
  eye: std(0x101528, 0.15), iris: std(IRIS, 0.25), irisLow: std(IRIS_LOW, 0.3), pupil: std(0x05060c, 0.15),
  shine: new THREE.MeshBasicMaterial({ color: C(0xffffff) }), mouth: std(0x7a1f3a, 0.6), tongue: std(0xff7a9a, 0.6),
  teeth: std(0xffffff, 0.4), blush: Object.assign(new THREE.MeshBasicMaterial({ color: C(0xff8fb8), transparent: true, opacity: 0.5 }), {}),
};

// ---------------- fur: shells of a strand texture over the white parts ----------------
const SHELLS = 10;
const strands = (() => {
  const W = 512, H = 256, d = new Uint8Array(W * H * 4);
  let seed = 11; const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
  const G = 16, n = W / G + 1, grid = [...Array(n * (H / G + 1))].map(rnd);
  const tuft = (x, y) => { const gx = x / G, gy = y / G, ix = Math.floor(gx), iy = Math.floor(gy), fx = gx - ix, fy = gy - iy;
    const v = (i, j) => grid[(j % (H / G + 1)) * n + (i % n)]; const sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy);
    return (v(ix, iy) * (1 - sx) + v(ix + 1, iy) * sx) * (1 - sy) + (v(ix, iy + 1) * (1 - sx) + v(ix + 1, iy + 1) * sx) * sy; };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const v = Math.pow(rnd(), 0.75) * (0.5 + 0.5 * tuft(x, y)); const i = (y * W + x) * 4;
    d[i] = d[i + 1] = d[i + 2] = 255; d[i + 3] = Math.round(Math.min(1, v) * 255);
  }
  return { width: W, height: H, data: d, nearest: true };
})();
const shellMats = new Map();
function shellMat(hex, k) {                                     // k: 0 root … 1 tip; darker roots give the fur depth
  const key = hex + ':' + k; if (shellMats.has(key)) return shellMats.get(key);
  const m = new THREE.MeshStandardMaterial({ color: C(hex).multiplyScalar(0.86 + 0.16 * k), roughness: 1, metalness: 0, side: THREE.FrontSide });
  m.alphaTest = 0.14 + 0.62 * k; m.userData.rgba = strands; shellMats.set(key, m); return m;
}
const geoCache = new Map();
function sphereGeo(seg = 32) { const k = 's' + seg; if (!geoCache.has(k)) geoCache.set(k, new THREE.SphereGeometry(1, seg, Math.round(seg * 0.7))); return geoCache.get(k); }
const shellCache = new Map();
function shellGeo(base, grow, uvScale) {                       // the base pushed out along its normals, uv tiled for fine strands
  const key = base.uuid + ':' + grow.toFixed(4) + ':' + uvScale.join('x');
  if (shellCache.has(key)) return shellCache.get(key);
  const g = base.clone(); shellCache.set(key, g), p = g.attributes.position, nrm = g.attributes.normal, uv = g.attributes.uv;
  for (let i = 0; i < p.count; i++) p.setXYZ(i, p.getX(i) + nrm.getX(i) * grow, p.getY(i) + nrm.getY(i) * grow, p.getZ(i) + nrm.getZ(i) * grow);
  if (uv) for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * uvScale[0], uv.getY(i) * uvScale[1]);
  return g;
}
/** A furry ellipsoid: a solid core plus shells (length = fur length relative to the unit sphere). */
const coreMats = new Map();
function furBall(parent, hex, [rx, ry, rz], pos, { length = 0.09, uv = [6, 3], rot, shells = SHELLS, coreMat, seg = 32 } = {}) {
  const g = new THREE.Group(); g.position.set(...pos); if (rot) g.rotation.set(...rot); g.scale.set(rx, ry, rz); parent.add(g);
  if (!coreMat) { if (!coreMats.has(hex)) coreMats.set(hex, std(hex, 0.95)); coreMat = coreMats.get(hex); }
  g.add(new THREE.Mesh(sphereGeo(seg), coreMat));
  const uvf = [uv[0] * 1.7, uv[1] * 1.7];                       // finer strands: plush, not shaggy
  for (let i = 1; i <= shells; i++) g.add(new THREE.Mesh(shellGeo(sphereGeo(seg), length * i / shells, uvf), shellMat(hex, i / shells)));
  return g;
}
function ball(parent, mat, [rx, ry, rz], pos, rot, seg = 32) {
  const m = new THREE.Mesh(sphereGeo(seg), mat); m.scale.set(rx, ry, rz); m.position.set(...pos); if (rot) m.rotation.set(...rot); parent.add(m); return m;
}
function tube(parent, mat, pts, r, seg = 24) {
  const curve = new THREE.CatmullRomCurve3(pts.map(p => new THREE.Vector3(...p)));
  const m = new THREE.Mesh(new THREE.TubeGeometry(curve, seg, r, 10, false), mat); parent.add(m);
  for (const e of [pts[0], pts[pts.length - 1]]) { const cap = new THREE.Mesh(sphereGeo(12), mat); cap.scale.setScalar(r); cap.position.set(...e); parent.add(cap); }
  return m;
}
const group = (parent, name, pos = [0, 0, 0], rot) => { const g = new THREE.Group(); if (name) g.name = name; g.position.set(...pos); if (rot) g.rotation.set(...rot); parent.add(g); return g; };

// ---------------- the bunny ----------------
const root = new THREE.Group(); root.name = 'Poppy';
const body = group(root, 'Body');                                  // identity at rest: the app sets it for sitting
const torso = group(body, 'Torso');

// hoodie: a soft rounded body (lathe), a ribbed hem, the hood lying behind the neck, drawstrings, a white heart
const prof = [[0.0, 0.12], [0.1, 0.125], [0.17, 0.15], [0.205, 0.2], [0.218, 0.28], [0.212, 0.36], [0.19, 0.43], [0.15, 0.49], [0.1, 0.525], [0.0, 0.535]]
  .map(([r, y]) => new THREE.Vector2(r, y));
const hood = new THREE.Mesh(new THREE.LatheGeometry(new THREE.SplineCurve(prof).getPoints(40), 48), M.hoodie); hood.scale.set(1.06, 1, 1.04); torso.add(hood);
const hem = new THREE.Mesh(new THREE.TorusGeometry(0.198, 0.023, 12, 48), M.hoodieDark); hem.rotation.x = Math.PI / 2; hem.position.y = 0.165; torso.add(hem);
const collar = new THREE.Mesh(new THREE.TorusGeometry(0.12, 0.038, 14, 40), M.hoodie); collar.rotation.x = Math.PI / 2 + 0.25; collar.position.set(0, 0.515, -0.01); torso.add(collar);
ball(torso, M.hoodie, [0.19, 0.12, 0.1], [0, 0.53, -0.14], [0.35, 0, 0]);            // the hood, down on the back
ball(torso, M.hoodieDark, [0.15, 0.085, 0.06], [0, 0.545, -0.17], [0.35, 0, 0]);       // its opening, a shade darker
for (const s of [-1, 1]) {
  tube(torso, M.white, [[s * 0.045, 0.49, 0.13], [s * 0.05, 0.43, 0.175], [s * 0.048, 0.37, 0.19]], 0.009, 16);
  ball(torso, M.white, [0.014, 0.022, 0.014], [s * 0.048, 0.355, 0.192]);
}
const heart = new THREE.Shape(); heart.moveTo(0, -0.035);
heart.bezierCurveTo(-0.05, -0.0, -0.045, 0.035, -0.022, 0.035); heart.bezierCurveTo(-0.008, 0.035, 0, 0.025, 0, 0.015);
heart.bezierCurveTo(0, 0.025, 0.008, 0.035, 0.022, 0.035); heart.bezierCurveTo(0.045, 0.035, 0.05, 0.0, 0, -0.035);
const half = sgn => { const h = new THREE.Shape(); h.moveTo(0, -0.035);
  h.bezierCurveTo(sgn * 0.05, 0.0, sgn * 0.045, 0.035, sgn * 0.022, 0.035); h.bezierCurveTo(sgn * 0.008, 0.035, 0, 0.025, 0, 0.015); h.lineTo(0, -0.035); return h; };
{                                                                  // a white edge, so the heart shows on any hoodie
  const edge = new THREE.Mesh(new THREE.ExtrudeGeometry(heart, { depth: 0.006, bevelEnabled: true, bevelThickness: 0.003, bevelSize: 0.003, bevelSegments: 2, curveSegments: 16 }), M.white);
  edge.scale.setScalar(1.45); edge.position.set(0.0, 0.322, 0.211); edge.rotation.x = -0.08; torso.add(edge);
}
for (const [sgn, hex] of [[-1, 0xff5fae], [1, 0x4f9dff]]) {
  const hm = new THREE.Mesh(new THREE.ExtrudeGeometry(half(sgn), { depth: 0.008, bevelEnabled: true, bevelThickness: 0.004, bevelSize: 0.003, bevelSegments: 2, curveSegments: 16 }), std(hex, 0.5));
  hm.scale.setScalar(1.25); hm.position.set(0.0, 0.32, 0.217); hm.rotation.x = -0.08; torso.add(hm);
}
// a pocket across the belly
const pocket = new THREE.Mesh(new THREE.CylinderGeometry(0.229, 0.235, 0.075, 40, 1, true, -0.85, 1.7), M.hoodieDark); pocket.position.y = 0.23; torso.add(pocket);
// short furry legs under the hoodie, and a round tail
for (const s of [-1, 1]) furBall(torso, FUR, [0.085, 0.07, 0.085], [s * 0.085, 0.12, 0.0], { uv: [4, 2] });
furBall(torso, FUR, [0.075, 0.075, 0.07], [0, 0.2, -0.205], { length: 0.16, uv: [4, 2] });

// feet: chubby, with a pink paw pad underneath (shows when she lifts them)
const feet = [-1, 1].map(s => {
  const f = group(body, s < 0 ? 'FootL' : 'FootR', [s * 0.09, 0.05, 0.03]);
  if (girl) {
    furBall(f, FUR, [0.07, 0.055, 0.1], [0, 0, 0.02], { uv: [4, 2] });
    const pad = group(f, null, [0, -0.045, 0.0], [Math.PI / 2 + 0.25, 0, 0]);
    ball(pad, M.pad, [0.04, 0.05, 0.008], [0, -0.01, 0]);
    for (const [x, y] of [[-0.028, 0.045], [0, 0.058], [0.028, 0.045]]) ball(pad, M.pad, [0.013, 0.015, 0.006], [x, y, 0]);
  } else {
    // sneakers: white with a pink and a blue panel, a thick sole, grey laces, a padded collar
    const white = std(0xfbfbfd, 0.55), grey = std(0xc9ccd6, 0.6);
    ball(f, std(0xeef0f4, 0.7), [0.078, 0.022, 0.115], [0, -0.038, 0.025]);                 // sole
    ball(f, white, [0.072, 0.052, 0.108], [0, -0.005, 0.02]);                                // upper
    ball(f, std(0xff6fb1, 0.5), [0.074, 0.03, 0.06], [0, -0.012, -0.03]);                     // heel panel, pink
    ball(f, std(0x4f9dff, 0.5), [0.073, 0.024, 0.05], [0, -0.016, 0.075]);                    // toe panel, blue
    ball(f, white, [0.05, 0.03, 0.04], [0, 0.04, -0.015]);                                     // collar
    for (let k = 0; k < 3; k++) tube(f, grey, [[-0.022, 0.034 - k * 0.012, 0.045 + k * 0.022], [0.022, 0.034 - k * 0.012, 0.045 + k * 0.022]], 0.0045, 4);
  }
  return f;
});

// arms: hoodie sleeves with a ribbed cuff and a round white paw, hanging from the shoulder
const arms = [-1, 1].map(s => {
  const a = group(body, s < 0 ? 'ArmL' : 'ArmR', [s * 0.175, 0.45, 0.0]);
  const sleeve = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.055, 0.17, 20), M.hoodie);
  sleeve.position.set(s * 0.04, -0.09, 0.015); sleeve.rotation.z = s * 0.38; a.add(sleeve);
  ball(a, M.hoodie, [0.064, 0.064, 0.064], [s * 0.005, -0.005, 0.005]);                     // the shoulder, round
  ball(a, M.hoodie, [0.058, 0.058, 0.058], [s * 0.07, -0.165, 0.025]);                      // the elbow end of the sleeve
  const cuff = new THREE.Mesh(new THREE.TorusGeometry(0.048, 0.016, 10, 24), M.hoodieDark); cuff.position.set(s * 0.085, -0.2, 0.03); cuff.rotation.set(Math.PI / 2, 0, s * 0.38); a.add(cuff);
  furBall(a, FUR, [0.052, 0.05, 0.052], [s * 0.1, -0.24, 0.035], { uv: [3, 2] });
  return a;
});

// ---------------- the head ----------------
const face = group(body, 'Face', [0, 0.52, 0]);
furBall(face, FUR, [0.37, 0.31, 0.31], [0, 0.27, 0], { uv: [8, 4], length: 0.06, seg: 44 });
// puffy cheeks and the muzzle, chubby
for (const s of [-1, 1]) furBall(face, FUR, [0.12, 0.09, 0.085], [s * 0.075, 0.155, 0.23], { uv: [3, 2], length: 0.08, shells: 6 });
furBall(face, FUR, [0.085, 0.06, 0.07], [0, 0.11, 0.235], { uv: [3, 2], length: 0.08, shells: 6 });
ball(face, M.nose, [0.032, 0.022, 0.02], [0, 0.205, 0.322]);
ball(face, M.white, [0.009, 0.006, 0.004], [-0.01, 0.214, 0.34]);                        // a little shine on the nose
for (const s of [-1, 1]) ball(face, M.blush, [0.06, 0.035, 0.01], [s * 0.215, 0.18, 0.25], [0, s * 0.6, 0]);
// eyebrows
for (const s of [-1, 1]) tube(face, M.brow, [[s * 0.075, 0.435, 0.27], [s * 0.125, 0.452, 0.262], [s * 0.172, 0.44, 0.24]], 0.007, 12);

// eyes: big and glossy, a coloured iris lighter below, a pupil, two sparkles; lashes for her
const eyeLooks = [];
for (const s of [-1, 1]) {
  const side = s < 0 ? 'L' : 'R';
  const e = group(face, null, [s * 0.122, 0.285, 0.272], [0, s * 0.32, 0]);
  const open = group(e, 'EyeOpen' + side);
  ball(open, M.eye, [0.088, 0.108, 0.045], [0, 0, 0]);
  ball(open, M.iris, [0.074, 0.092, 0.04], [0, -0.01, 0.01]);
  ball(open, M.irisLow, [0.055, 0.035, 0.03], [0, -0.055, 0.026]);
  ball(open, M.pupil, [0.04, 0.05, 0.03], [0, -0.006, 0.022]);
  ball(open, M.shine, [0.028, 0.032, 0.012], [s * -0.026, 0.036, 0.044]);
  ball(open, M.shine, [0.012, 0.012, 0.008], [s * 0.026, -0.046, 0.041]);
  if (girl) for (const [x, y, r] of [[0.06, 0.088, 0.5], [0.078, 0.07, 0.85], [0.088, 0.046, 1.15]])
    tube(open, M.ink, [[s * x * 0.7, y * 0.85, 0.036], [s * x, y, 0.034], [s * (x + 0.024 * Math.sin(r)), y + 0.024 * Math.cos(r), 0.026]], 0.005, 6);
  tube(open, M.ink, [[s * -0.075, 0.066, 0.032], [s * -0.01, 0.11, 0.036], [s * 0.062, 0.088, 0.034]], girl ? 0.007 : 0.005, 14);   // upper lid line
  const happy = group(e, 'EyeHappy' + side);                       // ^ ^
  tube(happy, M.ink, [[-0.065, -0.02, 0.036], [0, 0.04, 0.042], [0.065, -0.02, 0.036]], 0.012, 16);
  const closed = group(e, 'EyeClosed' + side);                     // u u (sleeping)
  tube(closed, M.ink, [[-0.065, 0.005, 0.036], [0, -0.035, 0.042], [0.065, 0.005, 0.036]], 0.011, 16);
  eyeLooks.push(happy, closed);
}

// his sunglasses: two rounded black lenses with a glint, a bridge and the arms back to the head (always on)
if (!girl) {
  const glasses = group(face, null, [0, 0.29, 0]);
  const lensShape = new THREE.Shape(); const lw = 0.092, lh = 0.07, r = 0.035;
  lensShape.moveTo(-lw + r, -lh); lensShape.lineTo(lw - r, -lh); lensShape.quadraticCurveTo(lw, -lh, lw, -lh + r); lensShape.lineTo(lw, lh - r);
  lensShape.quadraticCurveTo(lw, lh, lw - r, lh); lensShape.lineTo(-lw + r, lh); lensShape.quadraticCurveTo(-lw, lh, -lw, lh - r); lensShape.lineTo(-lw, -lh + r); lensShape.quadraticCurveTo(-lw, -lh, -lw + r, -lh);
  const lensGeo = new THREE.ExtrudeGeometry(lensShape, { depth: 0.012, bevelEnabled: true, bevelThickness: 0.005, bevelSize: 0.005, bevelSegments: 3, curveSegments: 12 });
  const lensMat = std(0x0b0b10, 0.08), frame = std(0x15151a, 0.3);
  for (const s of [-1, 1]) {
    // in front of the eyes (which stand out of the fur), following the face's curve
    const l = new THREE.Mesh(lensGeo, lensMat); l.position.set(s * 0.122, -0.005, 0.322); l.rotation.y = s * 0.3; glasses.add(l);
    ball(glasses, M.shine, [0.034, 0.007, 0.003], [s * 0.122 - 0.025, 0.025, 0.343 - s * 0.01], [0, s * 0.3, 0.6]);
    tube(glasses, frame, [[s * 0.205, 0.02, 0.29], [s * 0.32, 0.03, 0.15], [s * 0.36, 0.02, 0.0]], 0.009, 12);
  }
  tube(glasses, frame, [[-0.04, 0.02, 0.345], [0, 0.03, 0.352], [0.04, 0.02, 0.345]], 0.009, 10);
}

// mouths: a small smile, an open happy grin, a little "o"
const mouth = group(face, null, [0, 0.162, 0.318]);
const smile = group(mouth, 'MouthSmile');
tube(smile, M.ink, [[-0.05, 0.01, -0.004], [-0.025, -0.016, 0.005], [0, -0.002, 0.009], [0.025, -0.016, 0.005], [0.05, 0.01, -0.004]], 0.0065, 24);
const grin = group(mouth, 'MouthGrin');
ball(grin, M.mouth, [0.045, 0.03, 0.012], [0, -0.012, 0.0]);
ball(grin, M.tongue, [0.025, 0.014, 0.008], [0, -0.025, 0.007]);
ball(grin, M.teeth, [0.02, 0.009, 0.006], [0, 0.008, 0.008]);
const oh = group(mouth, 'MouthO');
ball(oh, M.mouth, [0.02, 0.024, 0.01], [0, -0.01, 0.004]);

// ears: long, white outside and on the rim, coloured only inside
const ears = [-1, 1].map(s => {
  const g = group(face, s < 0 ? 'EarL' : 'EarR', [s * 0.13, 0.5, -0.03], [-0.12, 0, -s * 0.2]);
  furBall(g, FUR, [0.09, 0.26, 0.06], [0, 0.23, 0], { uv: [3, 5], length: 0.07 });
  // the inside: a soft pad of colour set into the front of the ear, with short velvet fur; white all around it
  const inner = group(g, null, [0, 0.215, 0.056], [-0.04, 0, 0]);
  furBall(inner, EAR_IN, [0.058, 0.2, 0.016], [0, 0, 0], { uv: [3, 6], length: 0.12, shells: 3, coreMat: M.earIn });
  g.userData.base = -s * 0.2;
  return g;
});

// ---------------- clips ----------------
const hidden = new Set(eyeLooks.concat([grin, oh]));
const q = (ex, ey, ez) => { const v = new THREE.Quaternion().setFromEuler(new THREE.Euler(ex, ey, ez)); return [v.x, v.y, v.z, v.w]; };
const walk = { name: 'walk', duration: 0.56, frames: 17, tracks: [] }, idle = { name: 'idle', duration: 2.4, frames: 25, tracks: [] };
walk.tracks.push({ object: body, path: 'translation', fn: a => [0, Math.abs(Math.sin(a)) * 0.045, 0] });
walk.tracks.push({ object: body, path: 'rotation', fn: a => q(0.05, 0, Math.sin(a) * 0.08) });
feet.forEach((f, i) => { const b = f.position.clone(), sg = i ? 1 : -1; walk.tracks.push({ object: f, path: 'translation', fn: a => [b.x, b.y + Math.max(0, Math.sin(a) * sg) * 0.06, b.z + Math.cos(a) * sg * 0.08] }); });
feet.forEach((f, i) => { const sg = i ? 1 : -1; walk.tracks.push({ object: f, path: 'rotation', fn: a => q(-Math.max(0, Math.sin(a) * sg) * 0.5, 0, 0) }); });
arms.forEach((g, i) => { const sg = i ? 1 : -1; walk.tracks.push({ object: g, path: 'rotation', fn: a => q(-Math.cos(a) * sg * 0.6, 0, sg * 0.08) }); });
ears.forEach((e, i) => { const sg = i ? 1 : -1; walk.tracks.push({ object: e, path: 'rotation', fn: a => q(-0.12 - Math.abs(Math.sin(a)) * 0.14, 0, e.userData.base + sg * Math.sin(2 * a) * 0.07) }); });
idle.tracks.push({ object: body, path: 'translation', fn: a => [0, (1 - Math.cos(a)) * 0.005, 0] });
idle.tracks.push({ object: body, path: 'rotation', fn: () => q(0, 0, 0) });
feet.forEach(f => { const b = f.position.clone(); idle.tracks.push({ object: f, path: 'translation', fn: () => [b.x, b.y, b.z] }); idle.tracks.push({ object: f, path: 'rotation', fn: () => q(0, 0, 0) }); });
arms.forEach((g, i) => { const sg = i ? 1 : -1; idle.tracks.push({ object: g, path: 'rotation', fn: a => q(0.05 * Math.sin(a), 0, sg * (0.05 + 0.04 * Math.sin(a))) }); });
ears.forEach((e, i) => { const sg = i ? 1 : -1; idle.tracks.push({ object: e, path: 'rotation', fn: a => q(-0.12 + 0.04 * Math.sin(a + i), 0, e.userData.base + sg * 0.05 * Math.sin(a + i)) }); });

const { glb, gltf } = writeGLB(THREE, root, { hidden, animations: [walk, idle] });
fs.writeFileSync(outPath, glb);
const tris = gltf.meshes.length;
console.log(outPath, (glb.length / 1024).toFixed(0) + ' KB,', gltf.nodes.length, 'nodes,', tris, 'meshes,', gltf.materials.length, 'materials,', gltf.animations.map(a => a.name).join('+'));
