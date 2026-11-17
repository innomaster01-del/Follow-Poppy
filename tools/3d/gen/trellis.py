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
