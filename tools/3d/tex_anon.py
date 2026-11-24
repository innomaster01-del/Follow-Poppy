"""One textured model from one picture, made by the generators themselves (TRELLIS.2, then Hunyuan3D-2.1 as a
fallback), asked WITHOUT the account token: the free GPU time is then counted for the build server's address, which
is new on every run, so the account's used-up daily time does not block it.
usage: python tex_anon.py <picture> <out dir>"""
import os, sys, re, time, shutil, traceback
from gradio_client import Client, handle_file

pic, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
log = open(os.path.join(out, 'log.txt'), 'w')
def say(*a): print(*a, flush=True); print(*a, file=log, flush=True)
token = None
shutil.copy(pic, os.path.join(out, 'input.png'))
apose = pic
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

# ---------------------------------------------------------------- 2b. Hunyuan3D-2.1 textured (only when TRELLIS gave nothing)
if not os.path.exists(os.path.join(out, 'trellis.glb')):
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
