"""Create a reproducible preview and sample resource pack in dist/."""
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import objmc_blender
from objmc_blender import exporter, preview

objmc_blender.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = 'Sword · Source'
settings = scene.objmc
atlas = bpy.data.images.new('Sword Atlas', width=32, height=32)
pixels = []
for y in range(32):
    for x in range(32):
        shade = 0.8 if (x//4+y//4) % 2 else 1.0
        color = (0.12, 0.85, 0.92) if x < 16 else (0.38, 0.19, 0.075)
        pixels.extend([c*shade for c in color]+[1])
atlas.pixels = pixels
atlas.pack()
settings.texture = atlas
settings.namespace = 'objmc_demo'
settings.item_path = 'diamond_blade'
settings.output_directory = str(ROOT / 'dist/OBJMC_Demo_Pack')
if not (Path(settings.output_directory) / 'pack.mcmeta').is_file():
    raise RuntimeError('Prepare the demo resource pack with metadata and compatible shaders first.')
settings.geometry_scale = 0.6
settings.right_rotation = (0, -15, -10)
settings.right_translation = (-3, 4, 0)
settings.left_rotation = (0, -15, -10)
settings.left_translation = (-3, 4, 0)
parts = []
for name, size, location, metal in [
    ('Blade', (0.095, 0.035, 0.57), (0, 0, 0.24), True),
    ('Tip', (0.065, 0.035, 0.09), (0, 0, 0.57), True),
    ('Guard', (0.28, 0.07, 0.06), (0, 0, -0.075), True),
    ('Grip', (0.065, 0.065, 0.20), (0, 0, -0.20), False),
    ('Pommel', (0.11, 0.08, 0.07), (0, 0, -0.335), True),
]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    for uv in obj.data.uv_layers.active.data:
        uv.uv.x = (uv.uv.x*0.44 + (0.02 if metal else 0.52))
    parts.append(obj)
for obj in parts:
    obj.select_set(True)
pack = exporter.export_resources(bpy.context)
print('SAMPLE_PACK', pack)
preview_scene = preview.create_preview(bpy.context)
preview_scene.render.resolution_x = 960
preview_scene.render.resolution_y = 540
preview_scene.render.filepath = str(ROOT / 'dist/first_person_preview.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'dist/OBJMC_Demo.blend'))
bpy.ops.render.render(write_still=True)
print('PREVIEW_RENDER', preview_scene.render.filepath)
