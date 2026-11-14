"""Regenerate the bundled objmc core from the retained upstream snapshot."""
import ast
from pathlib import Path
import warnings

root = Path(__file__).resolve().parents[1]
source = (root / 'vendor/objmc_upstream.py').read_text(encoding='utf-8')
names = {'readobj', 'indexvert', 'indexobj', 'getheader', 'newelement',
         'getposition', 'getuv', 'getvert', 'objmc', 'col'}
with warnings.catch_warnings():
    warnings.simplefilter('ignore', SyntaxWarning)
    tree = ast.parse(source)
segments = [ast.get_source_segment(source, node) for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
header = '''# Adapted from Godlander/objmc, MIT license (see LICENSE-objmc.txt).
# Generated with tools/adapt_encoder.py. Pillow, GUI and CLI removed.
import math
import json
from .pixels import Image, ImageOps

count = [0, 0]
mem = {"positions": {}, "uvs": {}}
data = {"positions": [], "uvs": [], "vertices": []}
js = {}
runtex = ""
visibility = 7

def exit():
    raise ValueError("objmc rejected the input; see export log for details.")

'''
core = '\n\n'.join(segments)
# Upstream strips the path; explicit destination removes global cwd changes.
core = core.replace('out.save(output[1].split("/")[-1])', 'out.save(output[1])')
core = core.replace('"\\Reading obj "', '"Reading obj "')
footer = '''

def convert(objs, texture, model_path, texture_path, *, duration=1, easing=1,
            autoplay=True, flipuv=False, noshadow=False):
    global visibility
    visibility = 7
    objmc([str(p) for p in objs], [texture], [str(model_path), str(texture_path)],
          1.0, (0, 0, 0), duration, easing, 0,
          ["pitch", "yaw", "roll"], 1, autoplay, flipuv, noshadow, False, None)
'''
(root / 'objmc_blender/encoder.py').write_text(header + core + footer, encoding='utf-8')
