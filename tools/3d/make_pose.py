"""Makes the new character's pictures into the views a 3D model needs: the same bunny standing in a neutral A-pose,
from the front, the right side and the back (FLUX.1 Kontext, an image-editing model, on Hugging Face). Runs on the
build server. Writes out/<step>.png and out/log.txt.
usage: python make_pose.py <source dir> <out dir>"""
import os, sys, shutil, re, time, traceback
from gradio_client import Client, handle_file

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
log = open(os.path.join(out, 'log.txt'), 'w')
def say(*a): print(*a, flush=True); print(*a, file=log, flush=True)
token = os.environ.get('HF_TOKEN') or None
SPACES = ['black-forest-labs/FLUX.1-Kontext-Dev']
STYLE = ('Keep exactly the same character: same face, same big blue eyes, same white smooth soft fur, same pink and blue '
         'inner ears, same blue paw-pin emblem on the chest, same 3D cartoon style. Full body, pure white background, '
         'even soft light, no shadow, no text.')
STEPS = [
    ('front', 'pose_think.png', 'Make this bunny stand upright on its hind legs in a neutral A-pose, facing the camera: '
     'arms relaxed and slightly away from the body, hands open, legs slightly apart, feet flat, looking straight ahead, '
     'gentle smile, eyes open. ' + STYLE),
    ('side', 'front', 'Show this exact bunny from its right side: a full profile view facing right, same neutral A-pose. ' + STYLE),
    ('back', 'front', 'Show this exact bunny from behind: a full back view, same neutral A-pose, the round tail visible. ' + STYLE),
]

def run(client, api, img, prompt):
    params = client.view_api(return_format='dict', print_info=False)['named_endpoints'][api]['parameters']
    kw = {}
    for p in params:
        n = p.get('parameter_name') or ''
        if 'image' in n: kw[n] = handle_file(img)
        elif n == 'prompt': kw[n] = prompt
        elif n == 'seed': kw[n] = 7
        elif 'randomize' in n: kw[n] = False
        elif 'guidance' in n: kw[n] = 2.5
        elif 'step' in n: kw[n] = 28
    say('  params', sorted(kw))
    for attempt in range(6):
        try: return client.predict(api_name=api, **kw)
        except Exception as e:
            m = re.search(r'Try again in (\d+):(\d+):(\d+)', str(e))
            wait = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) if m else None
            if wait is None or wait > 15 * 60 or attempt == 5: raise
            say(f'  out of GPU time, waiting {wait + 20} s'); time.sleep(wait + 20)

def first_image(res):
    found = []
    def walk(x):
        if isinstance(x, str) and os.path.exists(x) and x.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')): found.append(x)
        elif isinstance(x, dict): [walk(v) for v in x.values()]
        elif isinstance(x, (list, tuple)): [walk(v) for v in x]
    walk(res); return found[0] if found else None

for space in SPACES:
    try:
        c = Client(space, token=token)
        eps = c.view_api(return_format='dict', print_info=False)['named_endpoints']
        say(space, 'endpoints', list(eps))
        api = next(e for e in eps if 'infer' in e) if any('infer' in e for e in eps) else list(eps)[0]
        for name, inp, prompt in STEPS:
            img = os.path.join(out, inp + '.png') if os.path.exists(os.path.join(out, inp + '.png')) else os.path.join(src, inp)
            say(name, 'from', os.path.basename(img))
            f = first_image(run(c, api, img, prompt))
            if not f: say('  no image back'); continue
            from PIL import Image
            Image.open(f).convert('RGB').save(os.path.join(out, name + '.png')); say('  ok', name)
        break
    except Exception as e:
        say(space, 'failed:', repr(e)[:600]); traceback.print_exc()
