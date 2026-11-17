"""Image → 3D with Microsoft TRELLIS.2 (MIT licence) on its Hugging Face Space, run from CI (this needs the internet).
For each picture in tools/3d/gen/in: generates a textured GLB into gen-out/. First it writes the Space's API to
gen-out/api.txt, so the call can be matched to what the Space actually offers.
usage: python trellis.py <in dir> <out dir> [space]"""
import os, sys, glob, shutil, traceback, json
from gradio_client import Client, handle_file

src, out = sys.argv[1], sys.argv[2]
space = sys.argv[3] if len(sys.argv) > 3 else "microsoft/TRELLIS.2"
os.makedirs(out, exist_ok=True)
log = open(os.path.join(out, "log.txt"), "a")
def say(*a):
    print(*a, flush=True); print(*a, file=log, flush=True)

token = os.environ.get("HF_TOKEN") or None
say("space", space, "token", bool(token))
try:
    client = Client(space, token=token)
    api = client.view_api(return_format="dict", print_info=False)
    with open(os.path.join(out, "api.txt"), "w") as f: f.write(json.dumps(api, indent=1, default=str))
    say("endpoints", list(api.get("named_endpoints", {}).keys()))
except Exception:
    say(traceback.format_exc())
    # other image-to-3D Spaces to try
    for alt in ["trellis-community/TRELLIS", "JeffreyXiang/TRELLIS", "tencent/Hunyuan3D-2"]:
        try:
            c = Client(alt, token=token); a = c.view_api(return_format="dict", print_info=False)
            with open(os.path.join(out, "api_" + alt.replace("/", "_") + ".txt"), "w") as f: f.write(json.dumps(a, indent=1, default=str))
            say("ok", alt, list(a.get("named_endpoints", {}).keys()))
        except Exception as e:
            say("fail", alt, repr(e)[:300])

# ---- generate each picture: a session, the Space's own background removal, the 3D, then the GLB ----
def run(path):
    name = os.path.splitext(os.path.basename(path))[0]
    c = Client(space, token=token)
    try: c.predict(api_name="/start_session")
    except Exception as e: say("start_session:", repr(e)[:200])
    pre = c.predict(handle_file(path), api_name="/preprocess_image")
    say(name, "preprocessed", str(pre)[:200])
    shutil.copy(pre if isinstance(pre, str) else pre.get("path"), os.path.join(out, name + "_pre.png"))
    img = handle_file(pre if isinstance(pre, str) else pre.get("path"))
    prev = c.predict(img, 0, "1024", 7.5, 0.7, 12, 5.0, 7.5, 0.5, 12, 3.0, 1.0, 0.0, 12, 3.0, api_name="/image_to_3d")
    say(name, "3d done", str(prev)[:200])
    res = c.predict(60000, 1024, api_name="/extract_glb")
    glb = res[1] if isinstance(res, (list, tuple)) else res
    if isinstance(glb, dict): glb = glb.get("path") or glb.get("value")
    shutil.copy(glb, os.path.join(out, name + ".glb"))
    say(name, "glb", os.path.getsize(os.path.join(out, name + ".glb")), "bytes")

for p in sorted(glob.glob(os.path.join(src, "*.png")) + glob.glob(os.path.join(src, "*.jpg"))):
    try: run(p)
    except Exception: say(os.path.basename(p), traceback.format_exc()[-1500:])
