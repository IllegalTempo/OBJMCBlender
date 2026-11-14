import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType('cubed_test_package')
package.__path__ = [str(ROOT / 'objmc_blender')]
sys.modules[package.__name__] = package
spec = importlib.util.spec_from_file_location('cubed_test_package.cubed_encoder', ROOT / 'objmc_blender/cubed_encoder.py')
cubed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cubed)


class CubedEncodingTests(unittest.TestCase):
    def test_geometry_animation_roundtrips_and_triangle_padding_is_degenerate(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for i in range(2):
                path = Path(tmp) / f'{i}.obj'
                path.write_text(f'v {i} 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt 0 1\nf 1/1 2/2 3/3\n')
                paths.append(path)
            texture = cubed.Image.new('RGBA', (8,8), (100,120,140,255))
            model, out = cubed.encode(paths, texture, duration=20)
        w, h = out.size
        self.assertEqual(w, 16)
        self.assertEqual(out.getpixel((0,0)), (12,34,56,255))
        self.assertEqual(out.getpixel((3,0)), (0,0,2,1))
        self.assertEqual(out.getpixel((7,0))[1], 4)
        vph = out.getpixel((5,0))[0]*256+out.getpixel((5,0))[1]
        vth = out.getpixel((5,0))[2]*256+out.getpixel((7,0))[2]
        base = 2+1+8
        def u24(pixel):
            return pixel[0]*65536+pixel[1]*256+pixel[2]
        def read(index, row):
            return out.getpixel((index % w, row+index//w))
        def pos(index):
            return tuple(u24(read(index*3+j,base))/65536-128 for j in range(3))
        verts = [(u24(read(i*2,base+vph+vth)), u24(read(i*2+1,base+vph+vth))) for i in range(8)]
        self.assertEqual(verts[2], verts[3])
        self.assertEqual(verts[6], verts[7])
        self.assertEqual(pos(verts[0][0]), (0,0,0))
        self.assertEqual(pos(verts[4][0]), (1,0,0))
        self.assertEqual(out.getpixel((5,1)), (8,0,2,255))
        self.assertEqual(out.getpixel((0,1))[2], 2)
        self.assertEqual(out.getpixel((2,1))[2], 1)
        # Original UV u=1 spans only the unpadded half of an 8px atlas.
        uv_index = verts[1][1]
        self.assertAlmostEqual(u24(read(uv_index*2,base+vph))/65535, .5, places=4)
        variant = cubed.slot_variant(model, 1)
        uv = variant['elements'][0]['faces']['north']['uv']
        self.assertAlmostEqual((uv[0]+uv[2])*.5*w/16, .535)
        self.assertNotEqual(model, variant)


if __name__ == '__main__':
    unittest.main()
