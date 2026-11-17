// Builds Poppy with the original makePet() code (three.js r128 from the desktop pet) and writes a GLB with:
//  - named parts the app moves: Body, Torso, Face, ArmL/ArmR, FootL/FootR, EarL/EarR
//  - faces the app switches by scale: EyeOpenL/R, EyeHappyL/R, EyeClosedL/R, MouthSmile, MouthGrin, MouthO
//  - clips: 0 "walk" (0.56 s loop: feet step, arms swing, ears bounce, body bobs), 1 "idle" (2.4 s: breathing, ears sway)
// usage: node export_poppy.js <three.min.js> <poppy_build.js> <girl|boy> <out.glb>
const fs = require('fs'), vm = require('vm');
const { writeGLB, loadThree } = require('./gltf_writer');
const [threePath, buildPath, gender, outPath] = process.argv.slice(2);

const sb = loadThree(threePath);
const prelude = `const mk=(w,h)=>{const c=document.createElement('canvas');c.width=w;c.height=h;return c;};
const V=(x=0,y=0,z=0)=>new THREE.Vector3(x,y,z); const rnd=(a,b)=>a+Math.random()*(b-a); const pick=a=>a[0];
const scene=new THREE.Scene();`;
vm.runInContext(prelude + fs.readFileSync(buildPath, 'utf8') + `\n;globalThis.PET=makePet(${JSON.stringify(gender)});globalThis.NOISE_IMG=NOISE.image;`, sb);
const THREE = sb.THREE, P = sb.PET;

// fur: the shell look with enough shells to read as soft, dense fur (still light for a phone GPU); the strands are the
// alpha of one shared texture
const KEEP = 9;
(function thin(o) {
  const shells = o.children.filter(c => c.isMesh && P.fur.includes(c.material));
  if (shells.length > KEEP) { const keep = new Set([...Array(KEEP)].map((_, k) => Math.round(k * (shells.length - 1) / (KEEP - 1)))); shells.forEach((m, i) => { if (!keep.has(i)) m.visible = false; }); }
  o.children.forEach(thin);
})(P.root);
// finer strands than the desktop pet (one texel each, twice the resolution) gathered in soft tufts, so the fur looks
// like fur up close instead of square pixels; the face keeps its short fur so the eyes and mouth stay clear
const noise = (() => {
  const W = 1024, H = 512, d = new Uint8Array(W * H * 4);
  let seed = 7; const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
  const G = 32, grid = [...Array((W / G + 1) * (H / G + 1))].map(rnd);                 // tufts: smooth low-frequency noise
  const tuft = (x, y) => { const gx = x / G, gy = y / G, ix = Math.floor(gx), iy = Math.floor(gy), fx = gx - ix, fy = gy - iy, n = W / G + 1;
    const v = (i, j) => grid[(j % (H / G + 1)) * n + (i % n)]; const sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy);
    return (v(ix, iy) * (1 - sx) + v(ix + 1, iy) * sx) * (1 - sy) + (v(ix, iy + 1) * (1 - sx) + v(ix + 1, iy + 1) * sx) * sy; };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const fx = (x - 256) / 124, fy = (y - 268) / 92, r = Math.hypot(fx, fy), q = r < 1 ? Math.pow(r, 3) : 1;
    const strand = Math.pow(rnd(), 0.8) * (0.55 + 0.45 * tuft(x, y));
    const v = r < 1 ? 0.2 * (1 - q) + strand * q : strand;
    const i = (y * W + x) * 4; d[i] = d[i + 1] = d[i + 2] = 255; d[i + 3] = Math.round(Math.min(1, v) * 255);
  }
  return { width: W, height: H, data: d, nearest: true };
})();
const baseFur = new THREE.Color(P.baseColor).convertSRGBToLinear();
P.fur.forEach((m, i) => {
  if (m.alphaMap) m.userData.rgba = noise;
  // darker at the roots, lighter at the tips: the fur gets depth
  const f = i / (P.fur.length - 1); m.color.copy(baseFur).multiplyScalar(0.48 + 0.62 * Math.pow(f, 1.25));
  // velvet: a light sheen of her own colour at grazing angles, stronger on the outer tips
  const c = m.color; m.userData.sheen = { color: [Math.min(1, c.r * 0.5 + 0.35), Math.min(1, c.g * 0.5 + 0.35), Math.min(1, c.b * 0.5 + 0.35)], roughness: 0.45 };
});

// names for the parts the app and the clips move
P.root.name = 'Poppy'; P.body.name = 'Body'; P.bodyG.name = 'Torso'; P.face.name = 'Face';
P.feet.forEach((f, i) => f.name = i ? 'FootR' : 'FootL'); P.arms.forEach((a, i) => a.name = i ? 'ArmR' : 'ArmL'); P.ears.forEach((e, i) => e.g.name = i ? 'EarR' : 'EarL');

// faces: each look in its own wrapper; the hidden ones are written at scale 0.0001
const hidden = new Set();
function wrap(parent, name, kids, show) {
  const w = new THREE.Group(); w.name = name; parent.add(w);
  for (const k of kids) if (k) { parent.remove(k); k.visible = true; w.add(k); }
  if (!show) hidden.add(w); return w;
}
// eyes with depth: a coloured iris and a pupil under a glossy clear coat, the sparkles sitting on top
const irisMat = new THREE.MeshStandardMaterial({ color: new THREE.Color(gender === 'boy' ? 0x2f5d9e : 0x8a3a64).convertSRGBToLinear(), roughness: 0.3, metalness: 0 });
irisMat.clearcoat = 1; irisMat.clearcoatRoughness = 0.05;
const pupilMat = new THREE.MeshStandardMaterial({ color: 0x050307, roughness: 0.2, metalness: 0 }); pupilMat.clearcoat = 1; pupilMat.clearcoatRoughness = 0.05;
const SPH_E = new THREE.SphereGeometry(1, 28, 20);
P.eyes.forEach(e => {
  const iris = new THREE.Mesh(SPH_E, irisMat); iris.scale.set(0.078, 0.1, 0.04); iris.position.set(0.004, -0.008, 0.02); e.g.add(iris);
  const pupil = new THREE.Mesh(SPH_E, pupilMat); pupil.scale.set(0.046, 0.06, 0.03); pupil.position.set(0.006, -0.006, 0.035); e.g.add(pupil);
  e.iris = iris; e.pupil = pupil;
  e.h1.position.z = 0.072; e.h2.position.z = 0.07; e.h1.scale.setScalar(0.033);
  if (e.ball.material.clearcoat !== undefined) { e.ball.material.clearcoat = 1; e.ball.material.clearcoatRoughness = 0.08; }
});
P.eyes.forEach((e, i) => {
  const side = i ? 'R' : 'L';
  wrap(e.g, 'EyeOpen' + side, [e.ball, e.iris, e.pupil, e.h1, e.h2, e.lashes], true);
  wrap(e.g, 'EyeHappy' + side, [e.happy], false);
  wrap(e.g, 'EyeClosed' + side, [e.closed], false);
  e.spiral.visible = false;
});
wrap(P.mouthG, 'MouthSmile', [P.mouths.smile], true);
wrap(P.mouthG, 'MouthGrin', [P.mouths.grin], false);
wrap(P.mouthG, 'MouthO', [P.mouths.o], false);
const skip = o => !o.visible || o === P.shadow;

// clips
const q = (ex, ey, ez) => { const v = new THREE.Quaternion().setFromEuler(new THREE.Euler(ex, ey, ez)); return [v.x, v.y, v.z, v.w]; };
const walk = { name: 'walk', duration: 0.56, frames: 17, tracks: [] }, idle = { name: 'idle', duration: 2.4, frames: 25, tracks: [] };
walk.tracks.push({ object: P.body, path: 'translation', fn: a => [0, Math.abs(Math.sin(a)) * 0.06, 0] });
walk.tracks.push({ object: P.body, path: 'rotation', fn: a => q(0.06, 0, Math.sin(a) * 0.09) });
P.feet.forEach((f, s) => { const b = f.position.clone(), sg = s ? 1 : -1; walk.tracks.push({ object: f, path: 'translation', fn: a => [b.x, b.y + Math.max(0, Math.sin(a) * sg) * 0.07, b.z + Math.cos(a) * sg * 0.09] }); });
P.arms.forEach((g, s) => { const sg = s ? 1 : -1; walk.tracks.push({ object: g, path: 'rotation', fn: a => q(Math.cos(a) * sg * 0.55, 0, -sg * 0.15) }); });
P.ears.forEach((e, s) => { const sg = s ? 1 : -1; walk.tracks.push({ object: e.g, path: 'rotation', fn: a => q(-Math.abs(Math.sin(a)) * 0.12, 0, e.base + sg * Math.sin(2 * a) * 0.08) }); });
idle.tracks.push({ object: P.body, path: 'translation', fn: a => [0, (1 - Math.cos(a)) * 0.006, 0] });
idle.tracks.push({ object: P.body, path: 'rotation', fn: a => q(0, 0, 0) });
P.feet.forEach(f => { const b = f.position.clone(); idle.tracks.push({ object: f, path: 'translation', fn: () => [b.x, b.y, b.z] }); });
P.arms.forEach((g, s) => { const sg = s ? 1 : -1; idle.tracks.push({ object: g, path: 'rotation', fn: a => q(0, 0, -sg * (0.1 + 0.05 * Math.sin(a))) }); });
P.ears.forEach((e, s) => { const sg = s ? 1 : -1; idle.tracks.push({ object: e.g, path: 'rotation', fn: a => q(0, 0, e.base + sg * 0.06 * Math.sin(a + s)) }); });

const { glb, gltf } = writeGLB(THREE, P.root, { skip, hidden, animations: [walk, idle] });
fs.writeFileSync(outPath, glb);
console.log(outPath, (glb.length / 1024).toFixed(0) + ' KB,', gltf.nodes.length, 'nodes,', gltf.meshes.length, 'meshes,', gltf.materials.length, 'materials,', gltf.animations.map(a => a.name).join('+'));
