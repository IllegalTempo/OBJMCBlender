import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pack_core', ROOT / 'objmc_blender/core.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class PackTests(unittest.TestCase):
    def test_resource_paths_reject_escape_and_invalid_names(self):
        for namespace, name in [('A', 'thing'), ('demo', '../bad'), ('demo', '/bad'),
                                ('demo', 'a//b'), ('demo', 'a\\b'), ('demo', 'a.b/..')]:
            with self.subTest(namespace=namespace, name=name), self.assertRaises(ValueError):
                core.validate_resource(namespace, name)
        core.validate_resource('demo_pack', 'weapons/sword')

    def test_item_uses_explicit_zero_tint_and_namespaced_model(self):
        result = core.item_definition('demo', 'sword')
        self.assertEqual(result['model']['model'], 'demo:item/sword')
        self.assertEqual(result['model']['tints'], [{'type': 'minecraft:constant', 'value': 0}])

    def test_resource_build_failure_preserves_existing_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'pack'
            dest.mkdir()
            (dest / 'pack.mcmeta').write_text('{"pack": {"pack_format": 75}}')
            (dest / 'keep.txt').write_text('original')
            def fail(stage):
                (stage / 'partial').write_text('bad')
                raise ValueError('conversion failed')
            with self.assertRaises(ValueError):
                core.publish_resources(dest, ['assets/demo/model.json', 'assets/demo/texture.png'], fail)
            self.assertEqual((dest / 'keep.txt').read_text(), 'original')
            self.assertEqual(list(Path(tmp).iterdir()), [dest])

    def test_publish_resources_updates_only_requested_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'pack'
            dest.mkdir()
            (dest / 'pack.mcmeta').write_text('{"pack": {"pack_format": 75}}')
            (dest / 'old').write_text('old')
            (dest / 'model.json').write_text('previous')
            def build(stage):
                (stage / 'model.json').write_text('new')
                (stage / 'texture.png').write_bytes(b'png')
            core.publish_resources(dest, ['model.json', 'texture.png'], build)
            self.assertEqual((dest / 'old').read_text(), 'old')
            self.assertEqual((dest / 'model.json').read_text(), 'new')
            self.assertEqual((dest / 'texture.png').read_bytes(), b'png')

    def test_second_file_failure_rolls_back_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest / 'pack.mcmeta').write_text('{"pack": {}}')
            (dest / 'model.json').write_text('old model')
            (dest / 'texture.png').write_bytes(b'old png')
            def build(stage):
                (stage / 'model.json').write_text('new')
                (stage / 'texture.png').write_bytes(b'new png')
            real_replace = core.os.replace
            def fail_second(src, dst):
                if Path(src).name == 'texture.png' and Path(src).parent.name != '.backups':
                    raise OSError('simulated write failure')
                return real_replace(src, dst)
            with patch.object(core.os, 'replace', side_effect=fail_second), self.assertRaises(OSError):
                core.publish_resources(dest, ['model.json', 'texture.png'], build)
            self.assertEqual((dest / 'model.json').read_text(), 'old model')
            self.assertEqual((dest / 'texture.png').read_bytes(), b'old png')

    def test_resources_require_pack_root_and_cannot_escape_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            with self.assertRaisesRegex(ValueError, 'pack.mcmeta'):
                core.publish_resources(dest, ['model.json'], lambda p: None)
            (dest / 'pack.mcmeta').write_text('{"pack": {}}')
            with self.assertRaises(ValueError):
                core.publish_resources(dest, ['../escape.json'], lambda p: None)

    def test_26_3_model_replaces_removed_shade_field(self):
        model = {'elements': [{'shade': False}, {'shade': True}, {'from': [0,0,0]}]}
        core.adapt_model_26_3(model)
        self.assertEqual(model['elements'][0], {'shade_direction_override': 'up'})
        self.assertNotIn('shade', model['elements'][1])
        self.assertNotIn('shade_direction_override', model['elements'][1])

    def test_metadata_and_command_target_selected_resource(self):
        self.assertEqual(core.pack_metadata(75, 'Test')['pack']['min_format'], 75)
        self.assertIn('minecraft:item_model="demo:sword"', core.give_command('demo', 'sword', 'stick'))


if __name__ == '__main__':
    unittest.main()
