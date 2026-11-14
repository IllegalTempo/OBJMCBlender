import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pixels', ROOT / 'objmc_blender/pixels.py')
pixels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pixels)


class PixelTests(unittest.TestCase):
    def test_rgb_pixel_defaults_alpha_without_shrinking_buffer(self):
        image = pixels.Image.new('RGBA', (8, 8), (0, 0, 0, 0))
        image.putpixel((0, 0), (1, 2, 3))
        self.assertEqual(len(image.data), 8*8*4)
        self.assertEqual(image.getpixel((0, 0)), (1, 2, 3, 255))

    def test_png_metadata_bytes_survive_without_color_conversion(self):
        image = pixels.Image.new('RGBA', (8, 8), (0, 0, 0, 0))
        image.putpixel((0, 0), (12, 34, 56, 79))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'data.png'
            image.save(path)
            data = path.read_bytes()
        self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
        cursor, compressed = 8, b''
        while cursor < len(data):
            n = struct.unpack('>I', data[cursor:cursor+4])[0]
            kind = data[cursor+4:cursor+8]
            chunk = data[cursor+8:cursor+8+n]
            if kind == b'IDAT':
                compressed += chunk
            cursor += n + 12
        raw = zlib.decompress(compressed)
        self.assertEqual(raw[:5], bytes([0, 12, 34, 56, 79]))

    def test_flip_and_paste_preserve_rows(self):
        src = pixels.Image.new('RGBA', (1, 2), (1, 2, 3, 4))
        src.putpixel((0, 1), (5, 6, 7, 8))
        dst = pixels.Image.new('RGBA', (2, 3), (0, 0, 0, 0))
        dst.paste(pixels.ImageOps.flip(src), (1, 1))
        self.assertEqual(dst.getpixel((1, 1)), (5, 6, 7, 8))
        self.assertEqual(dst.getpixel((1, 2)), (1, 2, 3, 4))


if __name__ == '__main__':
    unittest.main()
