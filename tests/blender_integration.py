"""Run with Blender --background --factory-startup --python tests/blender_integration.py."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tempfile.tempdir = str(ROOT / '.test-temp')
Path(tempfile.tempdir).mkdir(exist_ok=True)
import objmc_blender as addon
from objmc_blender import exporter, preview


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        addon.register()

    @classmethod
    def tearDownClass(cls):
        addon.unregister()
        addon.register()
        addon.unregister()

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene = bpy.context.scene
        bpy.ops.mesh.primitive_cube_add(size=0.35)
        self.obj = bpy.context.object
        image = bpy.data.images.new('Test atlas', width=16, height=16)
        image.generated_color = (0.25, 0.5, 1.0, 1.0)
        self.settings = self.scene.objmc
        self.settings.auto_textures = False
        self.settings.minecraft_target = '1.21.11'
        self.settings.texture = image
        self.settings.namespace = 'demo'
        self.settings.item_path = 'weapons/test'

    def pack_root(self, tmp):
        root = Path(tmp)
        (root / 'pack.mcmeta').write_text('{"pack":{"pack_format":75,"description":"Keep me"}}')
        (root / 'unrelated.txt').write_text('preserved')
        return root

    def linked_asset(self, directory, nested=False, tagged=True):
        collection = bpy.data.collections.new('Shared asset')
        mesh = self.obj.data.copy()
        asset = bpy.data.objects.new('Shared mesh', mesh)
        asset.location.x = 0.5
        if tagged:
            asset['objmc_player_part'] = 'body'
        material = bpy.data.materials.new('Shared skin material')
        material.use_nodes = True
        texture = material.node_tree.nodes.new('ShaderNodeTexImage')
        texture.image = self.settings.texture
        material.node_tree.links.new(texture.outputs['Color'], material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
        mesh.materials.append(material)
        child = None
        if nested:
            child = bpy.data.collections.new('Nested asset')
            child.objects.link(asset)
            child.instance_offset = (0.1,0.2,0.3)
            nested_obj = bpy.data.objects.new('Nested instance', None)
            nested_obj.instance_type, nested_obj.instance_collection = 'COLLECTION', child
            nested_obj.location.y = 0.25
            collection.objects.link(nested_obj)
        else:
            collection.objects.link(asset)
        path = str(Path(directory) / 'shared.blend')
        bpy.data.libraries.write(path, {collection})
        bpy.data.objects.remove(asset, do_unlink=True)
        if nested:
            bpy.data.objects.remove(nested_obj, do_unlink=True)
            bpy.data.collections.remove(child)
        bpy.data.collections.remove(collection)
        bpy.data.meshes.remove(mesh)
        with bpy.data.libraries.load(path, link=True) as (data_from, data_to):
            data_to.collections = ['Shared asset']
        return data_to.collections[0]

    def test_untagged_linked_instances_snapshot_with_local_geometry(self):
        from objmc_blender.mesh import selected_meshes, snapshot
        with tempfile.TemporaryDirectory() as tmp:
            collection = self.linked_asset(tmp, tagged=False)
            self.assertFalse(collection.objects[0].get('objmc_player_part'))
            for index in range(6):
                obj = bpy.data.objects.new('Local mesh '+str(index), self.obj.data.copy())
                self.scene.collection.objects.link(obj)
                obj.location.z = index/10
                obj.select_set(True)
            instance = bpy.data.objects.new('Untagged linked sword', None)
            instance.instance_type, instance.instance_collection = 'COLLECTION', collection
            self.scene.collection.objects.link(instance)
            instance.select_set(True)
            for frame in range(1,5):
                self.scene.frame_set(frame)
                data = snapshot(bpy.context, self.scene, selected_meshes(self.scene, bpy.context.view_layer))
                self.assertEqual(len(data), 8)
                linked = next(item for item in data if item['name'].startswith(instance.name+'/'))
                self.assertFalse(linked['use_skin_materials'])
                self.assertEqual(len(linked['faces']), 12)

    def test_linked_collection_instances_export_with_selected_local_mesh(self):
        with tempfile.TemporaryDirectory() as tmp:
            collection = self.linked_asset(tmp)
            instance = bpy.data.objects.new('Linked model', None)
            instance.instance_type, instance.instance_collection = 'COLLECTION', collection
            self.scene.collection.objects.link(instance)
            instance.location.x = 2
            instance.select_set(True)
            root = self.pack_root(tmp)
            self.settings.output_directory = tmp
            exporter.export_resources(bpy.context)
            model = json.loads((root / 'assets/demo/models/item/weapons/test.json').read_text())
            self.assertEqual(len(model['elements']), 24, 'Selected linked collection was silently omitted')
            self.assertIsNotNone(collection.library)
            self.assertIsNotNone(collection.objects[0].data.library)

    def test_linked_nested_instances_preserve_transform_and_clip_animation(self):
        from objmc_blender.mesh import selected_meshes, snapshot
        with tempfile.TemporaryDirectory() as tmp:
            collection = self.linked_asset(tmp, nested=True)
            instance = bpy.data.objects.new('Animated linked model', None)
            instance.instance_type, instance.instance_collection = 'COLLECTION', collection
            self.scene.collection.objects.link(instance)
            instance.location = (1,2,3)
            instance.rotation_euler.z = 0.4
            instance.scale = (-2,1,1)
            self.obj.select_set(False)
            instance.select_set(True)
            instance.keyframe_insert(data_path='location', frame=1)
            instance.location.z += 1
            instance.keyframe_insert(data_path='location', frame=2)
            clip = self.settings.clips.add()
            clip.name, clip.target, clip.action = 'move', instance, instance.animation_data.action
            self.settings.minecraft_target = '26.3'
            self.scene.frame_set(1)
            selected = selected_meshes(self.scene, bpy.context.view_layer)
            first = snapshot(bpy.context, self.scene, selected)
            self.assertEqual(len(first), 1)
            graph = bpy.context.evaluated_depsgraph_get()
            expected = next([tuple(i.matrix_world @ v.co) for v in i.object.data.vertices]
                            for i in graph.object_instances if i.is_instance and i.object.type == 'MESH')
            for actual, wanted in zip(first[0]['vertices'], expected):
                self.assertEqual(actual, wanted)
            self.scene.frame_set(2)
            second = snapshot(bpy.context, self.scene, selected)
            self.assertEqual(first[0]['name'], second[0]['name'])
            self.assertAlmostEqual(second[0]['vertices'][0][2]-first[0]['vertices'][0][2], 1)
            root = self.pack_root(tmp)
            self.settings.output_directory = tmp
            self.settings.auto_textures = True
            for active_only in (False, True):
                exporter.export_clips(bpy.context, active_only=active_only)
                model = json.loads((root / 'assets/demo/models/item/weapons/test/move.json').read_text())
                self.assertEqual(len(model['elements']), 12)
            self.assertEqual(self.scene.frame_current, 2)
            self.assertTrue(instance.select_get())
            self.assertFalse(self.obj.select_get())

    def test_linked_instance_preview_keeps_materials_and_source_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            collection = self.linked_asset(tmp)
            instance = bpy.data.objects.new('Preview linked model', None)
            instance.instance_type, instance.instance_collection = 'COLLECTION', collection
            self.scene.collection.objects.link(instance)
            scene = preview.create_preview(bpy.context)
            try:
                items = [o for o in scene.objects if o.get('objmc_role') == 'item']
                self.assertEqual(len(items), 2)
                linked = next(o for o in items if 'Shared mesh' in o.name)
                self.assertTrue(any(n.type == 'TEX_IMAGE' for n in linked.active_material.node_tree.nodes))
                self.assertIsNot(linked.active_material, collection.objects[0].active_material)
            finally:
                preview.close_preview(bpy.context)
            self.assertIsNotNone(collection.library)
            self.assertIs(instance.instance_collection, collection)

    def test_directly_linked_mesh_exports_when_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            collection = self.linked_asset(tmp)
            path = collection.library.filepath
            with bpy.data.libraries.load(path, link=True) as (data_from, data_to):
                data_to.objects = ['Shared mesh']
            linked = data_to.objects[0]
            self.scene.collection.objects.link(linked)
            self.obj.select_set(False)
            linked.select_set(True)
            root = self.pack_root(tmp)
            self.settings.output_directory = tmp
            exporter.export_resources(bpy.context)
            model = json.loads((root / 'assets/demo/models/item/weapons/test.json').read_text())
            self.assertEqual(len(model['elements']), 12)

    def test_only_selected_collection_instances_export_without_duplicates(self):
        from objmc_blender.mesh import selected_meshes, snapshot
        with tempfile.TemporaryDirectory() as tmp:
            collection = self.linked_asset(tmp)
            self.obj.select_set(False)
            for name, x, selected in [('First copy',0,True), ('Second copy',2,True), ('Unselected copy',10,False)]:
                instance = bpy.data.objects.new(name, None)
                instance.instance_type, instance.instance_collection = 'COLLECTION', collection
                self.scene.collection.objects.link(instance)
                instance.location.x = x
                instance.select_set(selected)
            data = snapshot(bpy.context, self.scene, selected_meshes(self.scene, bpy.context.view_layer))
            self.assertEqual(len(data), 2)
            self.assertEqual(len({item['name'] for item in data}), 2)
            self.assertLess(max(v[0] for item in data for v in item['vertices']), 3)
            root = self.pack_root(tmp)
            self.settings.output_directory = tmp
            exporter.export_resources(bpy.context)
            model = json.loads((root / 'assets/demo/models/item/weapons/test.json').read_text())
            self.assertEqual(len(model['elements']), 24)

    def test_local_object_using_linked_mesh_data_exports_animation(self):
        with tempfile.TemporaryDirectory() as tmp:
            collection = self.linked_asset(tmp)
            shared_mesh = collection.objects[0].data
            obj = bpy.data.objects.new('Local object linked mesh data', shared_mesh)
            self.scene.collection.objects.link(obj)
            self.obj.select_set(False)
            obj.select_set(True)
            self.assertIsNotNone(obj.data.library)
            self.assertIsNone(obj.library)
            obj.keyframe_insert(data_path='location', frame=1)
            obj.location.z = 0.5
            obj.keyframe_insert(data_path='location', frame=2)
            clip = self.settings.clips.add()
            clip.name, clip.target, clip.action = 'linked_mesh', obj, obj.animation_data.action
            root = self.pack_root(tmp)
            self.settings.output_directory = tmp
            exporter.export_clips(bpy.context, active_only=True)
            model = json.loads((root / 'assets/demo/models/item/weapons/test/linked_mesh.json').read_text())
            self.assertEqual(len(model['elements']), 12)
            self.assertIs(obj.data, shared_mesh)

    def test_import_full_player_skin_has_six_parts_and_deforming_rig(self):
        from objmc_blender.player import import_player
        from objmc_blender.mesh import snapshot
        skin = bpy.data.images.new('Full player skin', width=64, height=64)
        self.scene.cursor.location = (1, 2, 3)
        selected = list(bpy.context.selected_objects)
        active = bpy.context.view_layer.objects.active
        for slim, layers in [(False, True), (True, False)]:
            collection = import_player(bpy.context, skin, slim=slim, outer_layers=layers)
            parts = {o['objmc_player_part']: o for o in collection.objects if o.type == 'MESH'}
            self.assertEqual(set(parts), {'head', 'body', 'arm.R', 'arm.L', 'leg.R', 'leg.L'})
            rig = next(o for o in collection.objects if o.type == 'ARMATURE')
            self.assertEqual(set(rig.data.bones.keys()), set(parts) | {'root'})
            self.assertEqual(list(bpy.context.selected_objects), selected)
            self.assertIs(bpy.context.view_layer.objects.active, active)
            for bone, obj in parts.items():
                self.assertEqual(len(obj.data.vertices), 16 if layers else 8)
                self.assertEqual(obj.modifiers[0].object, rig)
                self.assertEqual(obj.vertex_groups[0].name, bone)
                self.assertEqual(len(obj.data.materials), 2 if layers else 1)
            width = max(v.co.x for v in parts['arm.R'].data.vertices)-min(v.co.x for v in parts['arm.R'].data.vertices)
            self.assertAlmostEqual(width*16, (3 if slim else 4) + (0.5 if layers else 0))
            uv = parts['head'].data.uv_layers.active.data[0].uv
            self.assertAlmostEqual(uv.x, 8/64)
            self.assertAlmostEqual(uv.y, 48/64)
            before = snapshot(bpy.context, self.scene, [parts['head']])[0]['vertices']
            rig.pose.bones['head'].rotation_mode = 'XYZ'
            rig.pose.bones['head'].rotation_euler.z = 0.6
            self.scene.frame_set(self.scene.frame_current)
            after = snapshot(bpy.context, self.scene, [parts['head']])[0]['vertices']
            self.assertNotEqual(before, after)
            self.assertEqual(len(before), len(after))

    def test_import_model_operator_loads_and_packs_skin(self):
        skin = bpy.data.images.new('Model input', width=64, height=64)
        with tempfile.TemporaryDirectory() as tmp:
            skin.filepath_raw = str(Path(tmp) / 'skin.png')
            skin.file_format = 'PNG'
            skin.save()
            self.assertEqual(bpy.ops.objmc.import_model(filepath=skin.filepath_raw, arm_width='NARROW', outer_layers=False), {'FINISHED'})
        rig = next(o for o in self.scene.objects if o.get('objmc_player_rig'))
        self.assertEqual(len(rig.data.bones), 7)
        head = next(o for o in self.scene.objects if o.get('objmc_player_part') == 'head')
        image = next(n.image for n in head.active_material.node_tree.nodes if n.type == 'TEX_IMAGE')
        self.assertTrue(image.packed_file)

    def test_third_person_preview_head_attachment_and_restore(self):
        from mathutils import Vector
        from objmc_blender.third_person import head_matrix
        self.settings.project_type = 'THIRD_PERSON'
        self.settings.minecraft_target = '26.3'
        self.settings.head_translation = (0,0,0)
        self.settings.head_scale = (1,1,1)
        point = head_matrix(self.settings) @ Vector((0,0,0))
        self.assertAlmostEqual(point.y, 27/16)
        original = self.obj.matrix_world.copy()
        region = next(a.spaces.active.region_3d for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
        location, rotation, distance = region.view_location.copy(), region.view_rotation.copy(), region.view_distance
        scene = preview.create_preview(bpy.context)
        self.assertTrue(any(o.get('objmc_role') == 'armor_stand' for o in scene.objects))
        camera_right = scene.camera.rotation_euler.to_matrix() @ Vector((1,0,0))
        camera_up = scene.camera.rotation_euler.to_matrix() @ Vector((0,1,0))
        self.assertAlmostEqual(camera_right.y, 0, places=6, msg='Camera horizon is tilted in Minecraft Y-up space')
        self.assertGreater(camera_up.y, 0.9, 'Armor stand should appear upright')
        self.assertFalse(any(o.get('objmc_role') == 'armor_stand' for o in self.scene.objects))
        held = next(o for o in scene.objects if o.get('objmc_role') == 'item')
        before = held.matrix_world.copy()
        self.settings.head_translation[1] = 16
        preview.update_preview(self.settings, bpy.context)
        self.assertNotEqual(held.matrix_world, before)
        self.assertAlmostEqual(held.matrix_world.translation.y, 27/16+0.625)
        region.view_location = (7,8,9)
        preview.create_preview(bpy.context)
        self.assertEqual(len([s for s in bpy.data.scenes if s.objmc_source == self.scene]), 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = self.pack_root(tmp)
            self.settings.output_directory = tmp
            exporter.export_resources(bpy.context)
            model = json.loads((root / 'assets/demo/models/item/weapons/test.json').read_text())
            self.assertEqual(len(model['elements']), 12, 'Reference stand was included in exported geometry')
        preview.close_preview(bpy.context)
        self.assertEqual(self.obj.matrix_world, original)
        self.assertEqual(region.view_location, location)
        self.assertEqual(region.view_rotation, rotation)
        self.assertAlmostEqual(region.view_distance, distance)
        self.assertFalse(preview._view_states)

    def test_active_clip_and_all_clips_apply_project_visibility(self):
        self.obj.keyframe_insert(data_path='location', frame=1)
        self.obj.location.z = 0.2
        self.obj.keyframe_insert(data_path='location', frame=2)
        clip = self.settings.clips.add()
        clip.name, clip.target, clip.action = 'idle', self.obj, self.obj.animation_data.action
        self.settings.active_clip = 0
        self.settings.minecraft_target = '26.3'
        with tempfile.TemporaryDirectory() as tmp:
            root = self.pack_root(tmp)
            self.settings.output_directory = tmp
            for active_only in (False, True):
                for mode in ('FIRST_PERSON', 'THIRD_PERSON'):
                    self.settings.project_type = mode
                    self.settings.hide_third_person = True
                    exporter.export_clips(bpy.context, active_only=active_only)
                    definition = json.loads((root / 'assets/demo/items/weapons/test/idle.json').read_text())
                    hidden = next(c['when'] for c in definition['model']['cases'] if c['model']['type'] == 'minecraft:empty')
                    self.assertEqual(set(hidden), {'firstperson_righthand','firstperson_lefthand'} if mode == 'THIRD_PERSON'
                        else {'thirdperson_righthand','thirdperson_lefthand','head'})
                    self.assertEqual(self.settings.item_path, 'weapons/test')

    def test_project_types_create_fresh_scenes_and_preserve_existing_work(self):
        self.assertEqual(self.settings.project_type, 'FIRST_PERSON')
        original = self.scene
        for kind in ('THIRD_PERSON', 'FIRST_PERSON'):
            self.assertEqual(bpy.ops.objmc.new_project(project_type=kind), {'FINISHED'})
            self.assertEqual(bpy.context.scene.objmc.project_type, kind)
            self.assertFalse(bpy.context.scene.objects)
            self.assertIn(original.name, bpy.data.scenes)
            self.assertIn(self.obj.name, original.objects)

    def test_third_person_defaults_and_custom_head_settings_are_preserved(self):
        self.assertEqual(tuple(self.settings.head_translation), (0,0,0))
        self.assertEqual(tuple(self.settings.head_scale), (1,1,1))
        self.settings.project_type = 'THIRD_PERSON'
        self.assertEqual(tuple(self.settings.head_rotation), (0,0,0))
        self.assertEqual(tuple(self.settings.head_translation), (0,-42,0))
        self.assertEqual(tuple(self.settings.head_scale), (1.5,1.5,1.5))
        self.settings.head_translation = (1,-30,2)
        self.settings.head_scale = (2,2,2)
        self.settings.project_type = 'FIRST_PERSON'
        self.settings.project_type = 'THIRD_PERSON'
        self.assertEqual(tuple(self.settings.head_translation), (1,-30,2))
        self.assertEqual(tuple(self.settings.head_scale), (2,2,2))
        bpy.ops.objmc.new_project(project_type='THIRD_PERSON')
        self.assertEqual(tuple(bpy.context.scene.objmc.head_translation), (0,-42,0))
        self.assertEqual(tuple(bpy.context.scene.objmc.head_scale), (1.5,1.5,1.5))

    def test_new_project_leaves_preview_and_restores_original_view(self):
        region = next(a.spaces.active.region_3d for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
        original_perspective = region.view_perspective
        scene = preview.create_preview(bpy.context)
        name = scene.name
        self.assertEqual(bpy.ops.objmc.new_project(project_type='THIRD_PERSON'), {'FINISHED'})
        self.assertNotIn(name, bpy.data.scenes)
        self.assertFalse(preview._view_states)
        self.assertEqual(region.view_perspective, original_perspective)

    def test_project_visibility_routes_both_backends_without_zero_scale(self):
        first = ('firstperson_righthand', 'firstperson_lefthand')
        third = ('thirdperson_righthand', 'thirdperson_lefthand', 'head')
        with tempfile.TemporaryDirectory() as tmp:
            root = self.pack_root(tmp)
            self.settings.output_directory = tmp
            for backend in ('26.3', '1.21.11'):
                self.settings.minecraft_target = backend
                for mode, hide in [('FIRST_PERSON', False), ('FIRST_PERSON', True), ('THIRD_PERSON', False)]:
                    self.settings.project_type = mode
                    self.settings.hide_third_person = hide
                    exporter.export_resources(bpy.context)
                    definition = json.loads((root / 'assets/demo/items/weapons/test.json').read_text())
                    selector = definition['model']
                    def route(slot):
                        return next((case['model'] for case in selector['cases'] if slot in case['when']), selector['fallback'])
                    for slot in first:
                        self.assertEqual(route(slot)['type'] == 'minecraft:empty', mode == 'THIRD_PERSON')
                    for slot in third:
                        self.assertEqual(route(slot)['type'] == 'minecraft:empty', mode == 'FIRST_PERSON' and hide)
                    self.assertEqual(route('gui')['type'], 'minecraft:model')
                    model = json.loads((root / 'assets/demo/models/item/weapons/test.json').read_text())
                    self.assertNotIn(0, model['display']['firstperson_righthand']['scale'])

    def test_head_transform_is_exported_with_depth_scale_context(self):
        self.settings.project_type = 'THIRD_PERSON'
        self.settings.minecraft_target = '26.3'
        self.settings.head_rotation = (10, 20, 30)
        self.settings.head_translation = (1, 2, 3)
        self.settings.head_scale = (1, 1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            root = self.pack_root(tmp)
            self.settings.output_directory = tmp
            exporter.export_resources(bpy.context)
            model = json.loads((root / 'assets/demo/models/item/weapons/test__objcubed_head.json').read_text())
            self.assertEqual(model['display']['head'], {'rotation': [10,20,30], 'translation': [1,2,3], 'scale': [1,1,2]})
            # Blender loads pixels bottom-up; encoded row 1 supplies head context 4.
            image = bpy.data.images.load(str(root / 'assets/demo/textures/item/weapons/test.png'), check_existing=False)
            start = ((image.size[1]-2)*image.size[0]+3)*4
            pixel = tuple(round(v*255) for v in image.pixels[start:start+4])
            self.assertEqual(pixel[:3], (128, 0, 0))
            bpy.data.images.remove(image)

    def test_export_only_resources_into_existing_pack_and_preserve_source(self):
        self.scene.frame_set(7)
        self.obj.keyframe_insert(data_path='location', frame=1)
        self.obj.location.z = 0.2
        self.obj.keyframe_insert(data_path='location', frame=3)
        self.settings.animation = True
        self.settings.frame_start = 1
        self.settings.frame_end = 3
        with tempfile.TemporaryDirectory() as tmp:
            root = self.pack_root(tmp)
            metadata = (root / 'pack.mcmeta').read_bytes()
            self.settings.output_directory = tmp
            result = exporter.export_resources(bpy.context)
            self.assertEqual(result, root.resolve())
            model = json.loads((result / 'assets/demo/models/item/weapons/test.json').read_text())
            self.assertEqual(len(model['elements']), 12)
            self.assertEqual(model['textures']['0'], 'demo:item/weapons/test')
            self.assertEqual(model['display']['firstperson_righthand']['rotation'], [0, 0, 0])
            self.assertTrue((result / 'assets/demo/textures/item/weapons/test.png').is_file())
            self.assertEqual((root / 'pack.mcmeta').read_bytes(), metadata)
            self.assertEqual((root / 'unrelated.txt').read_text(), 'preserved')
            self.assertEqual({p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()},
                             {'pack.mcmeta', 'unrelated.txt', 'assets/demo/models/item/weapons/test.json',
                              'assets/demo/textures/item/weapons/test.png', 'assets/demo/items/weapons/test.json'})
            # Re-export replaces these two assets, without replacing the pack.
            self.settings.right_translation = (1, 2, 3)
            exporter.export_resources(bpy.context)
            model = json.loads((result / 'assets/demo/models/item/weapons/test.json').read_text())
            self.assertEqual(model['display']['firstperson_righthand']['translation'], [1, 2, 3])
        self.assertEqual(self.scene.frame_current, 7)
        self.assertTrue(self.obj.select_get())
        self.assertEqual(len(self.scene.objects), 1)

    def test_snapshot_triangulates_quads_without_changing_source(self):
        from objmc_blender.mesh import snapshot, write_obj
        data = snapshot(bpy.context, self.scene, [self.obj])
        self.assertEqual(len(data[0]['faces']), 12)
        self.assertTrue(all(len(face) == 3 for face in data[0]['faces']))
        self.assertTrue(all(len(uv) == 3 for uv in data[0]['uvs']))
        self.assertEqual(len(data[0]['material_indices']), 12)
        self.assertEqual(len(self.obj.data.polygons), 6)
        self.assertTrue(all(len(p.vertices) == 4 for p in self.obj.data.polygons))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'triangles.obj'
            write_obj(path, data, 1)
            faces = [line.split() for line in path.read_text().splitlines() if line.startswith('f ')]
            self.assertEqual(len(faces), 12)
            self.assertTrue(all(len(face) == 4 for face in faces))

    def test_import_skin_hands(self):
        from objmc_blender import hands
        image = bpy.data.images.new('Skin', width=64, height=64)
        original_selection = list(bpy.context.selected_objects)
        collection = hands.import_hands(bpy.context, image, slim=True, sleeves=True)
        self.assertEqual(len(collection.objects), 3)
        arms = [o for o in collection.objects if o.type == 'MESH']
        self.assertEqual({o['objmc_hand'] for o in arms}, {'LEFT', 'RIGHT'})
        for obj in arms:
            self.assertAlmostEqual(obj.dimensions.x, 3.5 / 16)
            self.assertAlmostEqual(obj.dimensions.z, 12.5 / 16)
            self.assertEqual(len(obj.data.polygons), 12)
            self.assertEqual({p.material_index for p in obj.data.polygons}, {0, 1})
            self.assertEqual(len(obj.data.materials), 2)
            tex = next(n for n in obj.active_material.node_tree.nodes if n.type == 'TEX_IMAGE')
            self.assertEqual(tex.image, image)
            self.assertEqual(tex.interpolation, 'Closest')
            self.assertTrue(all(0 <= v <= 1 for uv in obj.data.uv_layers.active.data for v in uv.uv))
        self.assertEqual(list(bpy.context.selected_objects), original_selection)
        bad = bpy.data.images.new('Invalid skin', width=16, height=16)
        count = len(bpy.data.objects)
        with self.assertRaisesRegex(ValueError, '64'):
            hands.import_hands(bpy.context, bad)
        self.assertEqual(len(bpy.data.objects), count)

    def test_import_hands_button_loads_and_packs_png(self):
        from objmc_blender.pixels import Image
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'skin.png'
            Image.new('RGBA', (64, 64), (180, 120, 80, 255)).save(path)
            result = bpy.ops.objmc.import_hands(filepath=str(path), arm_width='WIDE', sleeves=False)
            self.assertEqual(result, {'FINISHED'})
            arms = [o for o in self.scene.objects if o.get('objmc_hand')]
            self.assertEqual(len(arms), 2)
            for arm in arms:
                self.assertAlmostEqual(arm.dimensions.x, 4 / 16)
                texture = next(n for n in arm.active_material.node_tree.nodes if n.type == 'TEX_IMAGE')
                self.assertIsNotNone(texture.image.packed_file)
                # Front face occupies the correct, separate arm region in the skin.
                uv = arm.data.uv_layers.active.data[0].uv
                self.assertAlmostEqual(uv.x, (44 if arm['objmc_hand'] == 'RIGHT' else 36) / 64)
                self.assertAlmostEqual(uv.y, 1 - (32 if arm['objmc_hand'] == 'RIGHT' else 64) / 64)

    def test_first_person_preview_shows_imported_skin_hands_only(self):
        from objmc_blender import hands
        skin = bpy.data.images.new('Skin reference', width=64, height=64)
        arms = hands.import_hands(bpy.context, skin)
        for obj in arms.objects:
            obj.select_set(True)
        scene = preview.create_preview(bpy.context)
        try:
            self.assertFalse(any(o.get('objmc_role') == 'arm' for o in scene.objects))
            items = [o for o in scene.objects if o.get('objmc_role') == 'item']
            self.assertEqual(len(items), 3)
            textured = [o for o in items if any(n.type == 'TEX_IMAGE' and n.image == skin
                        for n in o.active_material.node_tree.nodes)]
            self.assertEqual(len(textured), 2)
            self.assertTrue(all(o.data.materials[0] != arms.objects[0].active_material for o in textured))
        finally:
            preview.close_preview(bpy.context)

    def test_preview_displays_all_meshes_without_changing_selection(self):
        bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0.4, 0, 0))
        second = bpy.context.object
        second.select_set(False)
        self.obj.select_set(False)
        preview.create_preview(bpy.context)
        items = [o for o in bpy.context.scene.objects if o.get('objmc_role') == 'item']
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].matrix_world, items[1].matrix_world)
        preview.create_preview(bpy.context)
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.get('objmc_role') == 'item']), 2)
        preview.close_preview(bpy.context)
        self.assertFalse(second.select_get())
        self.assertFalse(self.obj.select_get())

    def test_objcubed_26_3_export_and_shader_install(self):
        from objmc_blender import core
        self.settings.minecraft_target = '26.3'
        with tempfile.TemporaryDirectory() as tmp:
            root = self.pack_root(tmp)
            self.settings.output_directory = tmp
            exporter.export_resources(bpy.context)
            model = json.loads((root / 'assets/demo/models/item/weapons/test.json').read_text())
            self.assertEqual(len(model['elements']), 12)
            self.assertEqual(model['elements'][0]['from'], [8,8,8])
            item = json.loads((root / 'assets/demo/items/weapons/test.json').read_text())
            self.assertEqual(item['model']['property'], 'minecraft:display_context')
            self.assertEqual(len(item['model']['cases']), 4)
            self.assertFalse(item['hand_animation_on_swap'])
            right = root / 'assets/demo/models/item/weapons/test__objcubed_right.json'
            self.assertTrue(right.is_file())
            image = bpy.data.images.load(str(root / 'assets/demo/textures/item/weapons/test.png'), check_existing=False)
            start = (image.size[1]-1)*image.size[0]*4
            self.assertEqual(tuple(round(v*255) for v in image.pixels[start:start+4]), (12,34,56,255))
            bpy.data.images.remove(image)
            core.install_item_shaders_26_3(root)
            metadata = json.loads((root / 'pack.mcmeta').read_text())
            self.assertEqual(metadata['pack']['min_format'], [97,1])
            self.assertEqual(metadata['pack']['description'], 'Keep me')
            self.assertEqual((root / 'unrelated.txt').read_text(), 'preserved')
            self.assertIn('OC_REPEATED_ITEM_CARRIER', (root / 'assets/minecraft/shaders/core/item.vsh').read_text())
            self.assertTrue((root / 'LICENSE-objcubed.txt').is_file())

    def test_auto_atlas_combines_selected_material_images_without_editing_uvs(self):
        from objmc_blender import atlas
        from objmc_blender.mesh import snapshot
        images = []
        for name, color in [('Red', (1,0,0,1)), ('Blue', (0,0,1,1))]:
            image = bpy.data.images.new(name, width=8, height=8)
            image.generated_color = color
            images.append(image)
            material = bpy.data.materials.new(name)
            material.use_nodes = True
            tex = material.node_tree.nodes.new('ShaderNodeTexImage')
            tex.image = image
            material.node_tree.links.new(tex.outputs['Color'], material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
            self.obj.data.materials.append(material)
        for poly in self.obj.data.polygons:
            poly.material_index = poly.index % 2
        before = [tuple(uv.uv) for uv in self.obj.data.uv_layers.active.data]
        data = snapshot(bpy.context, self.scene, [self.obj])
        texture, remap = atlas.build_atlas(data)
        remap(data)
        colors = set()
        for face_uv in data[0]['uvs']:
            u = sum(p[0] for p in face_uv) / 3
            v = sum(p[1] for p in face_uv) / 3
            x, y = int(u*texture.size[0]), int((1-v)*texture.size[1])
            colors.add(texture.getpixel((x,y)))
        self.assertEqual(colors, {(255,0,0,255), (0,0,255,255)})
        bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0.5,0,0))
        second = bpy.context.object
        second.data.materials.append(self.obj.data.materials[1])
        self.obj.select_set(True)
        self.settings.animation = True
        self.settings.frame_start = 1
        self.settings.frame_end = 2
        self.settings.auto_textures = True
        self.settings.texture = None
        self.settings.minecraft_target = '26.3'
        with tempfile.TemporaryDirectory() as tmp:
            self.pack_root(tmp)
            self.settings.output_directory = tmp
            result = exporter.export_resources(bpy.context)
            self.assertTrue((result / 'assets/demo/textures/item/weapons/test.png').is_file())
            model = json.loads((result / 'assets/demo/models/item/weapons/test.json').read_text())
            self.assertEqual(len(model['elements']), 24)
        self.assertEqual([tuple(uv.uv) for uv in self.obj.data.uv_layers.active.data], before)

    def test_objcubed_preview_uses_unflipped_idle_item_coordinates(self):
        from mathutils import Vector
        self.settings.minecraft_target = '26.3'
        self.settings.hand = 'RIGHT'
        matrix = preview.hand_matrix(self.settings)
        point = matrix @ Vector((0.1, 0, 0))
        self.assertAlmostEqual(point.x, 0.66, places=5)
        self.assertAlmostEqual(point.y, -0.52, places=5)
        self.assertAlmostEqual(point.z, -0.72, places=5)
        self.settings.hand = 'LEFT'
        self.settings.left_translation = (2, 3, 4)
        point = preview.hand_matrix(self.settings) @ Vector((0, 0, 0))
        self.assertAlmostEqual(point.x, -0.56-2/16, places=5)
        self.assertAlmostEqual(point.y, -0.52+3/16, places=5)
        self.assertAlmostEqual(point.z, -0.72+4/16, places=5)

    def test_export_named_clips_and_restore_settings(self):
        self.settings.minecraft_target = '26.3'
        actions = []
        for name, start, end in [('idle',1,2), ('attack',3,5)]:
            if self.obj.animation_data:
                self.obj.animation_data.action = None
            self.obj.location.x = len(actions)*0.5
            self.obj.keyframe_insert(data_path='location', frame=start)
            self.obj.location.z = 0.2
            self.obj.keyframe_insert(data_path='location', frame=end)
            action = self.obj.animation_data.action
            action.name = name
            actions.append(action)
            clip = self.settings.clips.add()
            clip.name = name
            clip.target = self.obj
            clip.action = action
            clip.frame_start, clip.frame_end = start, end
        original_action = self.obj.animation_data.action
        self.scene.frame_set(9)
        original_path = self.settings.item_path
        with tempfile.TemporaryDirectory() as tmp:
            root = self.pack_root(tmp)
            self.settings.output_directory = tmp
            exporter.export_clips(bpy.context)
            for name in ('idle','attack'):
                self.assertTrue((root / f'assets/demo/models/item/weapons/test/{name}.json').is_file())
                self.assertTrue((root / f'assets/demo/textures/item/weapons/test/{name}.png').is_file())
                self.assertTrue((root / f'assets/demo/items/weapons/test/{name}.json').is_file())
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            from unittest.mock import patch
            real_encode = exporter.cubed_encoder.encode
            calls = []
            def fail_second(*args, **kwargs):
                calls.append(1)
                if len(calls) == 2:
                    raise ValueError('Simulated second clip conversion failure')
                return real_encode(*args, **kwargs)
            with patch.object(exporter.cubed_encoder, 'encode', side_effect=fail_second):
                with self.assertRaisesRegex(ValueError, 'second clip'):
                    exporter.export_clips(bpy.context)
            self.assertEqual(before, {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()})
            self.assertIs(self.obj.animation_data.action, original_action)
            self.assertEqual(self.scene.frame_current, 9)
            self.settings.clips[1].name = 'idle'
            with self.assertRaises(ValueError):
                exporter.export_clips(bpy.context)
            self.assertEqual(before, {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()})
        self.assertIs(self.obj.animation_data.action, original_action)
        self.assertEqual(self.settings.item_path, original_path)
        self.assertFalse(self.settings.animation)
        self.assertEqual(self.scene.frame_current, 9)

    def test_import_hands_rig_deforms_both_skin_and_sleeve(self):
        from objmc_blender import hands
        from objmc_blender.mesh import snapshot
        original_active = bpy.context.view_layer.objects.active
        original_selected = list(bpy.context.selected_objects)
        self.scene.cursor.location = (1,2,3)
        skin = bpy.data.images.new('Rig skin', width=64, height=64)
        collection = hands.import_hands(bpy.context, skin)
        rig = next(o for o in collection.objects if o.type == 'ARMATURE')
        self.assertEqual(set(rig.data.bones.keys()), {'root', 'arm.R', 'arm.L'})
        arms = [o for o in collection.objects if o.type == 'MESH']
        right = next(o for o in arms if o['objmc_hand'] == 'RIGHT')
        left = next(o for o in arms if o['objmc_hand'] == 'LEFT')
        before = snapshot(bpy.context, self.scene, [right, left])
        rig.pose.bones['arm.R'].location.x = 0.25
        rig.pose.bones['arm.R'].keyframe_insert(data_path='location', frame=1)
        after = snapshot(bpy.context, self.scene, [right, left])
        self.assertNotEqual(before[0]['vertices'], after[0]['vertices'])
        self.assertEqual(before[1]['vertices'], after[1]['vertices'])
        from mathutils import Vector
        base_delta = Vector(after[0]['vertices'][0])-Vector(before[0]['vertices'][0])
        sleeve_delta = Vector(after[0]['vertices'][8])-Vector(before[0]['vertices'][8])
        self.assertLess((base_delta-sleeve_delta).length, 1e-5)
        for arm in arms:
            self.assertIs(arm.parent, rig)
            self.assertIs(next(m for m in arm.modifiers if m.type == 'ARMATURE').object, rig)
        self.assertIs(bpy.context.view_layer.objects.active, original_active)
        self.assertEqual(list(bpy.context.selected_objects), original_selected)
        self.assertEqual(bpy.context.mode, 'OBJECT')
        self.assertIsNotNone(rig.animation_data.action)

    def test_invalid_uv_fails_without_output(self):
        self.obj.data.uv_layers.remove(self.obj.data.uv_layers.active)
        self.obj.data.update()
        with tempfile.TemporaryDirectory() as tmp:
            self.pack_root(tmp)
            self.settings.output_directory = tmp
            with self.assertRaisesRegex(ValueError, 'UV'):
                exporter.export_resources(bpy.context)
            self.assertEqual({p.name for p in Path(tmp).iterdir()}, {'pack.mcmeta', 'unrelated.txt'})

    def test_topology_change_restores_frame(self):
        mod = self.obj.modifiers.new('Changing topology', 'BUILD')
        mod.frame_start = 1
        mod.frame_duration = 4
        self.settings.animation = True
        self.settings.frame_start = 1
        self.settings.frame_end = 5
        self.scene.frame_set(12)
        with tempfile.TemporaryDirectory() as tmp:
            self.pack_root(tmp)
            self.settings.output_directory = tmp
            with self.assertRaises(ValueError):
                exporter.export_resources(bpy.context)
        self.assertEqual(self.scene.frame_current, 12)

    def test_preview_is_separate_and_updates_both_hands(self):
        original = self.obj.matrix_world.copy()
        areas = [(a, a.spaces.active.overlay.show_overlays,
                  a.spaces.active.shading.type,
                  a.spaces.active.region_3d.view_perspective)
                 for a in bpy.context.screen.areas if a.type == 'VIEW_3D']
        scene = preview.create_preview(bpy.context)
        self.assertIs(scene.objmc_source, self.scene)
        self.assertIs(bpy.context.window.scene, scene)
        held = next(obj for obj in scene.objects if obj.get('objmc_role') == 'item')
        right = held.matrix_world.copy()
        self.settings.hand = 'LEFT'
        self.settings.left_translation = (2, 3, 4)
        preview.update_preview(self.settings, bpy.context)
        self.assertNotEqual(right, held.matrix_world)
        self.assertEqual(self.obj.matrix_world, original)
        preview_name = scene.name
        preview.close_preview(bpy.context)
        self.assertIs(bpy.context.window.scene, self.scene)
        self.assertEqual(len(self.scene.objects), 1)
        self.assertNotIn(preview_name, bpy.data.scenes)
        for area, overlays, shading, perspective in areas:
            self.assertEqual(area.spaces.active.overlay.show_overlays, overlays)
            self.assertEqual(area.spaces.active.shading.type, shading)
            self.assertEqual(area.spaces.active.region_3d.view_perspective, perspective)

    def test_preview_restores_original_view_after_navigation_and_refresh(self):
        from mathutils import Quaternion
        regions = [a.spaces.active.region_3d for a in bpy.context.screen.areas if a.type == 'VIEW_3D']
        self.assertTrue(regions)
        for region in regions:
            region.view_perspective = 'ORTHO'
            region.view_location = (2, -3, 4)
            region.view_rotation = Quaternion((1, 2, 3), 0.7)
            region.view_distance = 7.5
        expected = [(r.view_location.copy(), r.view_rotation.copy(), r.view_distance) for r in regions]
        preview.create_preview(bpy.context)
        for region in regions:
            region.view_location = (10, 20, 30)
            region.view_rotation = Quaternion((0, 1, 0), 1.4)
            region.view_distance = 25
        preview.create_preview(bpy.context)
        preview.close_preview(bpy.context)
        for region, (location, rotation, distance) in zip(regions, expected):
            self.assertLess((region.view_location - location).length, 1e-6)
            self.assertLess(region.view_rotation.rotation_difference(rotation).angle, 1e-6)
            self.assertAlmostEqual(region.view_distance, distance)
            self.assertEqual(region.view_perspective, 'ORTHO')

    def test_preview_keeps_editing_overlays_when_scene_is_switched_directly(self):
        spaces = [a.spaces.active for a in bpy.context.screen.areas if a.type == 'VIEW_3D']
        self.assertTrue(spaces, 'Regression requires a real 3D viewport')
        for space in spaces:
            space.overlay.show_overlays = True
            space.show_gizmo = True
        preview_scene = preview.create_preview(bpy.context)
        try:
            bpy.context.window.scene = self.scene
            bpy.ops.object.mode_set(mode='EDIT')
            for space in spaces:
                self.assertTrue(space.overlay.show_overlays, 'Preview hid vertex dots after direct scene switch')
                self.assertTrue(space.show_gizmo)
        finally:
            if self.obj.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.context.window.scene = preview_scene
            preview.close_preview(bpy.context)

    def test_encoder_exact_header_and_nonsquare_texture(self):
        from objmc_blender import encoder
        from objmc_blender.pixels import Image
        image = Image.new('RGBA', (16, 8), (128, 64, 32, 255))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            obj = path / 'one.obj'
            obj.write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt 0 1\nf 1/1 2/2 3/3\n')
            encoder.convert([obj], image, path / 'model.json', path / 'encoded.png', duration=1)
            packed = bpy.data.images.load(str(path / 'encoded.png'), check_existing=False)
            self.assertEqual(tuple(packed.size)[0], 16)
            # Blender pixels are bottom-up; metadata is in the first PNG row.
            start = (packed.size[1] - 1) * packed.size[0] * 4
            self.assertEqual(tuple(round(x * 255) for x in packed.pixels[start:start+4]), (12, 34, 56, 79))
            bpy.data.images.remove(packed)

    def test_preview_cleanup_preserves_linked_original_and_user_objects(self):
        original_name = self.obj.name
        scene = preview.create_preview(bpy.context)
        scene.collection.objects.link(self.obj)
        foreign = bpy.data.objects.new('User object', None)
        scene.collection.objects.link(foreign)
        preview.close_preview(bpy.context)
        self.assertIn(original_name, bpy.data.objects)
        self.assertIn(original_name, self.scene.objects)
        self.assertIn('User object', self.scene.objects)

    def test_export_uses_active_view_layer_selection(self):
        layer = self.scene.view_layers.new('Alternate')
        bpy.context.window.view_layer = layer
        self.obj.select_set(False, view_layer=self.scene.view_layers[0])
        self.obj.select_set(True, view_layer=layer)
        with tempfile.TemporaryDirectory() as tmp:
            self.pack_root(tmp)
            self.settings.output_directory = tmp
            result = exporter.export_resources(bpy.context)
            self.assertTrue((result / 'pack.mcmeta').is_file())
            preview.create_preview(bpy.context)
            result = exporter.export_resources(bpy.context)
            self.assertTrue((result / 'pack.mcmeta').is_file())
            preview.close_preview(bpy.context)
            self.assertEqual(bpy.context.view_layer.name, 'Alternate')


suite = unittest.defaultTestLoader.loadTestsFromTestCase(IntegrationTests)
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    sys.exit(1)
