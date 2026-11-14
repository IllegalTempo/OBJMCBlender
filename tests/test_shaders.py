from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ShaderTests(unittest.TestCase):
    def test_objcubed_shaders_match_pinned_release(self):
        import hashlib
        import json
        manifest = json.loads((ROOT / 'vendor/objcubed_manifest.json').read_text())
        self.assertEqual(manifest['ref'], '26.3v4')
        self.assertEqual(len(manifest['files']), 22)
        for entry in manifest['files']:
            path = ROOT / 'objmc_blender/objcubed_26_3' / entry['path'].removeprefix('objcubed/')
            data = path.read_bytes()
            blob = b'blob ' + str(len(data)).encode() + b'\0' + data
            self.assertEqual(hashlib.sha1(blob).hexdigest(), entry['sha'], str(path))

    def test_decoder_accepts_both_encoder_compression_markers(self):
        source = (ROOT / 'objmc_blender/shaders/include/objmc_main.glsl').read_text()
        self.assertIn('marker == ivec4(12,34,56,78) || marker == ivec4(12,34,56,79)', source)


if __name__ == '__main__':
    unittest.main()
