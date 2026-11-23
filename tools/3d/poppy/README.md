# Follow Poppy: 3D models

Everything in `app/src/main/assets/models` is made by these scripts with three.js r128 (the copy inside the Pufi desktop
pet; any `three.min.js` r128 works):

    node export_poppy.js three.min.js poppy_build.js girl ../../../app/src/main/assets/models/poppy_girl.glb
    node export_poppy.js three.min.js poppy_build.js boy  ../../../app/src/main/assets/models/poppy_boy.glb
    node make_trail.js   three.min.js ../../../app/src/main/assets/models     # ribbon, chevron, paw prints, shadow
    python3 render_glb.py ../../../app/src/main/assets/models/poppy_girl.glb preview.png   # quick look without a GPU

- `poppy_build.js` is Poppy's original build code (`makePet`) from the desktop pet.
- Poppy's GLB has the parts the app moves (Body, Face, ArmL/ArmR, FootL/FootR, EarL/EarR), every face in its own
  node (EyeOpen/EyeHappy/EyeClosed L/R, MouthSmile/MouthGrin/MouthO; hidden ones at scale 0.0001), and two clips:
  `walk` (0.56 s) and `idle` (2.4 s).
- `gltf_writer.js` is the small GLB writer both scripts use.

## Poppy from the character pictures (since 2.7)

`poppy_girl.glb` / `poppy_boy.glb` are now built from the character sheet (`tools/3d/source/poppy_<n>_front/right/back.png`):

1. `make3d.yml` / `make3d.py` turn the three views into a shape with Hunyuan3D-2mv (Hugging Face, `HF_TOKEN` secret);
   the result lands on the `model-output` branch as `<n>_shape_0.glb`.
2. `python3 ../scan/build_poppy.py <n>_shape_0.glb <n> ../../../app/src/main/assets/models/poppy_<n>.glb preview.png`
   stands it up (1.35 tall, faces +z), reduces it, textures it from the pictures, skins it to the same joints
   (Body, Face, ArmL/R, FootL/R, EarL/R), adds the face patches (EyeClosed/EyeHappy L/R, MouthGrin, MouthO; EyeOpen and
   MouthSmile are the picture's own face) and the `walk` / `idle` clips. Only numpy, Pillow and scipy are needed.
