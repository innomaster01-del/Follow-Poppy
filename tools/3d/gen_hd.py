"""The new bunny as a clean, textured HD model, made by the open-source generators themselves (no hand projection):
1. FLUX.1 Kontext puts the bunny from the character sheet in a clean A-pose: arms well away from the body, open hands
   (no thumbs-up), legs apart, so nothing grows together in 3D;
2. TRELLIS.2 (Microsoft, MIT license) turns that picture into a textured PBR model; Hunyuan3D-2.1 (textured) as a
   second opinion.
Writes out/<step>.png / .glb and out/log.txt.   usage: python gen_hd.py <source dir> <out dir>"""
import os, sys, re, time, shutil, traceback, json
from gradio_client import Client, handle_file

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
log = open(os.path.join(out, 'log.txt'), 'w')
def say(*a): print(*a, flush=True); print(*a, file=log, flush=True)
token = os.environ.get('HF_TOKEN') or None

def retry(fn):
    for attempt in range(6):
        try: return fn()
        except Exception as e:
            m = re.search(r'Try again in (\d+):(\d+):(\d+)', str(e))
            wait = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) if m else None
            if wait is None or wait > 15 * 60 or attempt == 5: raise
            say(f'  out of GPU time, waiting {wait + 20} s'); time.sleep(wait + 20)

def files(res, exts):
    found = []
    def walk(x):
        if isinstance(x, str) and os.path.exists(x) and x.lower().endswith(exts): found.append(x)
        elif isinstance(x, dict): [walk(v) for v in x.values()]
        elif isinstance(x, (list, tuple)): [walk(v) for v in x]
    walk(res); return found

def endpoints(c):
    eps = c.view_api(return_format='dict', print_info=False)['named_endpoints']
    say('  endpoints', {k: [p.get('parameter_name') for p in v['parameters']] for k, v in eps.items()})
    return eps

# ---------------------------------------------------------------- 1. a clean A-pose picture
POSE = ('Make this exact bunny character stand upright facing the camera in a clean A-pose for a 3D model: both arms '
        'held well away from the body, angled down and out at about 45 degrees, with a clear gap between the arms and '
        'the body; hands open and relaxed, palms facing forward, no thumbs up, no fingers pointing; legs slightly apart, '
        'feet flat. Keep everything else identical: the same face, big blue eyes, white smooth fur, blue inner ears with '
        'a wide white rim, the blue paw-pin emblem on the chest, the same soft 3D cartoon style. Full body, centered, pure '
        'white background, even soft studio light, no shadow, no text, no whiskers sticking far out.')
apose = os.path.join(out, 'apose.png')
try:
    c = Client('black-forest-labs/FLUX.1-Kontext-Dev', token=token)
    eps = endpoints(c); api = next((e for e in eps if 'infer' in e), list(eps)[0])
    kw = {}
    for p in eps[api]['parameters']:
        n = p.get('parameter_name') or ''
        if 'image' in n: kw[n] = handle_file(os.path.join(src, 'stand_front.png'))
        elif n == 'prompt': kw[n] = POSE
        elif n == 'seed': kw[n] = 11
        elif 'randomize' in n: kw[n] = False
        elif 'guidance' in n: kw[n] = 2.5
        elif 'step' in n: kw[n] = 28
    f = files(retry(lambda: c.predict(api_name=api, **kw)), ('.png', '.jpg', '.jpeg', '.webp'))
    from PIL import Image
    Image.open(f[0]).convert('RGB').save(apose); say('A-pose ok')
except Exception as e:
    say('A-pose failed:', repr(e)[:500]); traceback.print_exc()
    shutil.copy(os.path.join(src, 'stand_front.png'), apose)

# ---------------------------------------------------------------- 2a. TRELLIS.2
for space in ['microsoft/TRELLIS.2']:
    try:
        c = Client(space, token=token)
        eps = endpoints(c)
        img = handle_file(apose)
        if '/preprocess_image' in eps:
            pf = files(retry(lambda: c.predict(img, api_name='/preprocess_image')), ('.png', '.webp', '.jpg'))
            if pf: img = handle_file(pf[0]); shutil.copy(pf[0], os.path.join(out, 'trellis_input.png'))
        api = '/image_to_3d'
        kw = {}
        for p in eps[api]['parameters']:
            n = p.get('parameter_name') or ''
            if n == 'image': kw[n] = img
            elif n == 'seed': kw[n] = 7
            elif n == 'resolution': kw[n] = '1024'
        say('  trellis generate', sorted(kw))
        r = retry(lambda: c.predict(api_name=api, **kw)); say('  generated', str(r)[:300])
        api2 = '/extract_glb'
        kw2 = {}
        for p in eps[api2]['parameters']:
            n = p.get('parameter_name') or ''
            if n == 'decimation_target': kw2[n] = 60000
            elif n == 'texture_size': kw2[n] = 2048
        r2 = retry(lambda: c.predict(api_name=api2, **kw2))
        g = files(r2, ('.glb',))
        if g: shutil.copy(g[0], os.path.join(out, 'trellis.glb')); say('TRELLIS.2 ok', os.path.getsize(g[0]))
        else: say('TRELLIS.2: no glb', str(r2)[:300])
    except Exception as e:
        say(space, 'failed:', repr(e)[:800]); traceback.print_exc()

# ---------------------------------------------------------------- 2b. Hunyuan3D-2.1 textured
try:
    c = Client('tencent/Hunyuan3D-2.1', token=token)
    eps = endpoints(c)
    api = '/generation_all'
    kw = {}
    for p in eps[api]['parameters']:
        n = p.get('parameter_name') or ''
        if n == 'image': kw[n] = handle_file(apose)
        elif n == 'seed': kw[n] = 7
        elif n == 'octree_resolution': kw[n] = 256
        elif n == 'num_inference_steps' or n == 'steps': kw[n] = 30
        elif 'mv_image' in n or n == 'caption': kw[n] = None
        elif n in ('check_box_rembg', 'randomize_seed'): kw[n] = n == 'check_box_rembg'
    r = retry(lambda: c.predict(api_name=api, **kw))
    g = files(r, ('.glb', '.obj'))
    say('  hunyuan files', g)
    for i, f in enumerate(g): shutil.copy(f, os.path.join(out, f'hunyuan_{i}' + os.path.splitext(f)[1]))
except Exception as e:
    say('Hunyuan3D-2.1 failed:', repr(e)[:800]); traceback.print_exc()
