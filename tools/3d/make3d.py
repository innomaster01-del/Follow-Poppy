"""Turns the character pictures in tools/3d/source (poppy_<girl|boy>_front.png) into textured 3D models with the
free Hunyuan3D-2 demo on Hugging Face (run on the build server, which has internet). Writes out/<name>.glb and
out/log.txt (what each demo offers and what happened), so a run that fails says why.
usage: python make3d.py <source dir> <out dir>"""
import os, sys, shutil, traceback, json
from gradio_client import Client, handle_file

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
log = open(os.path.join(out, 'log.txt'), 'w')
def say(*a):
    print(*a, flush=True); print(*a, file=log, flush=True)

SPACES = ['tencent/Hunyuan3D-2', 'tencent/Hunyuan3D-2.1', 'tencent/Hunyuan3D-2mini-Turbo']
names = [n for n in ('girl', 'boy') if os.path.exists(os.path.join(src, f'poppy_{n}_front.png'))]
token = os.environ.get('HF_TOKEN') or None

def save(res, name, tag):
    """Copy every .glb (or other 3D file) the demo returned."""
    files = []
    def walk(x):
        if isinstance(x, str) and os.path.exists(x): files.append(x)
        elif isinstance(x, dict):
            for v in x.values(): walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x: walk(v)
    walk(res)
    kept = []
    for i, f in enumerate(files):
        ext = os.path.splitext(f)[1].lower()
        if ext in ('.glb', '.obj', '.ply', '.gltf'):
            dst = os.path.join(out, f'{name}_{tag}_{i}{ext}'); shutil.copy(f, dst); kept.append(dst)
    say('  files:', files, '-> kept', kept)
    return kept

for space in SPACES:
    try:
        c = Client(space, token=token) if token else Client(space)
        api = c.view_api(return_format='dict', print_info=False)
        say('==', space, 'endpoints:', list(api['named_endpoints'].keys()))
        for k, v in api['named_endpoints'].items():
            say('  ', k, json.dumps([(p.get('parameter_name'), p.get('parameter_has_default'), p.get('parameter_default')) for p in v.get('parameters', [])])[:900])
        ep = next((k for k in api['named_endpoints'] if 'generation_all' in k), None) or next((k for k in api['named_endpoints'] if 'gen' in k.lower()), None)
        if not ep: continue
        params = api['named_endpoints'][ep]['parameters']
        done = 0
        for n in names:
            img = handle_file(os.path.join(src, f'poppy_{n}_front.png'))
            kw = {}
            for p in params:
                pn = p.get('parameter_name') or ''
                if pn in ('image', 'img', 'input_image'): kw[pn] = img
                elif pn == 'caption': kw[pn] = None
                elif pn.startswith('mv_image'): kw[pn] = None
                elif pn == 'steps': kw[pn] = 30                 # the demo's default (a free account's daily GPU time is short)
                elif pn == 'octree_resolution': kw[pn] = 256
                elif pn == 'check_box_rembg': kw[pn] = True
                elif pn == 'randomize_seed': kw[pn] = False
                elif pn == 'seed': kw[pn] = 1234
                elif not p.get('parameter_has_default'): kw[pn] = None
            say(' ', n, 'calling', ep, {k: ('<image>' if k in ('image', 'img', 'input_image') else v) for k, v in kw.items()})
            try:
                res = c.predict(api_name=ep, **kw)
                say('  result:', str(res)[:600])
                if save(res, n, space.split('/')[-1]): done += 1
            except Exception as e:
                say('  failed:', repr(e)[:800])
        if done == len(names): say('all done with', space); break
    except Exception as e:
        say('==', space, 'unavailable:', repr(e)[:600]); traceback.print_exc()
log.close()
