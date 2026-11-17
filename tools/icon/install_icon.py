"""Puts a square icon picture (no rounded corners) into the app's launcher icons: the adaptive icon (the picture fills
the visible middle two thirds of the background layer; the rest is the same picture blurred, for launcher motion; the
foreground layer is empty) and the legacy icons (rounded square).
usage: python3 install_icon.py <square.png> <res dir>"""
import sys
from PIL import Image, ImageDraw, ImageFilter
src = Image.open(sys.argv[1]).convert('RGB'); res = sys.argv[2]
S = src.width; B = S * 3 // 2
canvas = src.resize((B, B), Image.LANCZOS).filter(ImageFilter.GaussianBlur(S * 0.06))
m = Image.new('L', (S, S), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * 0.08), fill=255)
canvas.paste(src, ((B - S) // 2, (B - S) // 2), m.filter(ImageFilter.GaussianBlur(S * 0.02)))
empty = Image.new('RGBA', (B, B), (0, 0, 0, 0))
for name, size in [('mdpi', 108), ('hdpi', 162), ('xhdpi', 216), ('xxhdpi', 324), ('xxxhdpi', 432)]:
    canvas.resize((size, size), Image.LANCZOS).save(f'{res}/mipmap-{name}/ic_launcher_background.png', optimize=True)
    empty.resize((size, size)).save(f'{res}/mipmap-{name}/ic_launcher_foreground.png', optimize=True)
r = Image.new('L', (S, S), 0); ImageDraw.Draw(r).rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * 0.225), fill=255)
rounded = src.convert('RGBA'); rounded.putalpha(r)
for name, size in [('mdpi', 48), ('hdpi', 72), ('xhdpi', 96), ('xxhdpi', 144), ('xxxhdpi', 192)]:
    rounded.resize((size, size), Image.LANCZOS).save(f'{res}/mipmap-{name}/ic_launcher.png', optimize=True)
