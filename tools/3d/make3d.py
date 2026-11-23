"""Turns the character pictures in tools/3d/source (poppy_<girl|boy>_front.png, and _right / _back when there are
views from the side and the back) into 3D models with the
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

# (space, endpoint, textured?) in order. Hunyuan3D-2's demo has its texturing switched off ("texgen_worker is not
# defined"), so it is only used for the shape; 2.1 makes the textured model but needs ~270 s of GPU each.
# A free account gets only a few minutes a day, so the shape comes first for both (the colours are then painted on
# from the same picture by paint_from_picture.py); the textured 2.1 model is the fallback.
# With views from the side and the back, the multi-view model (Hunyuan3D-2mv) goes first: the shape then matches the
# character all round, not only from the front.
PLAN = [('tencent/Hunyuan3D-2mv', '/shape_generation', False), ('tencent/Hunyuan3D-2', '/shape_generation', False),
        ('tencent/Hunyuan3D-2.1', '/shape_generation', False), ('tencent/Hunyuan3D-2.1', '/generation_all', True)]
# which characters: the third argument (comma separated), else the girl and the boy
want = sys.argv[3].split(',') if len(sys.argv) > 3 else ['girl', 'boy']
names = [n for n in want if os.path.exists(os.path.join(src, f'poppy_{n}_front.png'))]
# 'textured' (fourth argument): only the textured model (Hunyuan3D-2.1 shape + HD texture painted by its multi-view model)
if len(sys.argv) > 4 and sys.argv[4] == 'textured': PLAN = [('tencent/Hunyuan3D-2.1', '/generation_all', True)]
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

clients = {}
def client(space):
    if space not in clients: clients[space] = Client(space, token=token) if token else Client(space)
    return clients[space]

for n in names:
    for space, ep, textured in PLAN:
        if any(f.startswith(n + '_') and not f.endswith('.png') for f in os.listdir(out)): break        # this one is done
        try:
            c = client(space)
            params = c.view_api(return_format='dict', print_info=False)['named_endpoints'][ep]['parameters']
            img = handle_file(os.path.join(src, f'poppy_{n}_front.png'))
            # the side picture shows the character's right side (it faces right); its left side is that mirrored
            views = {'front': os.path.join(src, f'poppy_{n}_front.png'), 'back': os.path.join(src, f'poppy_{n}_back.png'),
                     'right': os.path.join(src, f'poppy_{n}_right.png')}
            if os.path.exists(views['right']):
                from PIL import Image, ImageOps
                views['left'] = os.path.join(out, f'_{n}_left.png'); ImageOps.mirror(Image.open(views['right'])).save(views['left'])
            say(n, space, 'endpoints', [(p.get('parameter_name'), p.get('parameter_has_default')) for p in params])
            kw = {}
            for p in params:
                pn = p.get('parameter_name') or ''
                if pn == 'image': kw[pn] = img
                elif pn.startswith('mv_image_'):
                    v = pn[len('mv_image_'):]
                    kw[pn] = handle_file(views[v]) if v in views and os.path.exists(views[v]) else None
                elif pn == 'caption': kw[pn] = None
                elif pn == 'steps': kw[pn] = 30
                elif pn == 'octree_resolution': kw[pn] = 256
                elif pn in ('target_face_num', 'face_count', 'max_facenum'): kw[pn] = 60000
                elif pn == 'check_box_rembg': kw[pn] = True
                elif pn == 'randomize_seed': kw[pn] = False
                elif pn == 'seed': kw[pn] = 1234
            say(n, space, ep, 'textured' if textured else 'shape only')
            # the free GPU time refills over time: when it says "try again in m:ss" (a few minutes), wait and try again
            import re, time
            for attempt in range(6):
                try:
                    res = c.predict(api_name=ep, **kw); break
                except Exception as e:
                    m = re.search(r'Try again in (\d+):(\d+):(\d+)', str(e))
                    wait = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) if m else None
                    if wait is None or wait > 15 * 60 or attempt == 5: raise
                    say(f'  out of GPU time, waiting {wait + 20} s'); time.sleep(wait + 20)
            say('  result:', str(res)[:400])
            save(res, n, ('tex' if textured else 'shape'))
        except Exception as e:
            say('  failed:', repr(e)[:500])
log.close()
