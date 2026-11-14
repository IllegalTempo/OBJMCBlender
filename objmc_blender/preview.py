"""Isolated, approximate Minecraft idle hand view. Originals are never moved."""
import math

import bpy
from mathutils import Matrix, Vector

from .mesh import TO_MINECRAFT, is_mesh_source, snapshot, source_layer, source_scene

_view_states = []


def _rotation(degrees):
    x, y, z = (math.radians(v) for v in degrees)
    return Matrix.Rotation(x, 4, 'X') @ Matrix.Rotation(y, 4, 'Y') @ Matrix.Rotation(z, 4, 'Z')


def hand_matrix(settings):
    """Minecraft-style camera space: +X right, +Y up, camera looks toward -Z."""
    left = settings.hand == 'LEFT'
    side = -1 if left else 1
    hand = 'left' if left else 'right'
    rotation = list(getattr(settings, hand+'_rotation'))
    translation = list(getattr(settings, hand+'_translation'))
    scale = getattr(settings, hand+'_scale')
    # ItemTransform mirrors X translation, Y/Z rotation in the left hand.
    translation[0] *= side
    rotation[1] *= side
    rotation[2] *= side
    if settings.minecraft_target == '26.3':
        # obj-cubed reconstructs the actual vanilla display basis from its
        # carrier. The legacy zx flip and fixed Y turn do not belong here.
        # At zero swing, vanilla attack-transform Y turns cancel each other.
        return (Matrix.Translation((side*0.56, -0.52, -0.72))
                @ Matrix.Translation(Vector(translation)/16)
                @ _rotation(rotation)
                @ Matrix.Diagonal((*scale, 1))
                @ TO_MINECRAFT
                @ Matrix.Scale(settings.geometry_scale, 4))
    return (Matrix.Translation((side*0.56, -0.52, -0.72))
            @ Matrix.Rotation(math.radians(side*45), 4, 'Y')
            @ Matrix.Translation(Vector(translation)/16)
            @ _rotation(rotation)
            @ Matrix.Diagonal((*scale, 1))
            @ Matrix.Diagonal((-1, 1, -1, 1))
            @ TO_MINECRAFT
            @ Matrix.Scale(settings.geometry_scale, 4))


def update_preview(settings, context):
    source = settings.id_data
    for scene in bpy.data.scenes:
        if scene.objmc_source != source:
            continue
        if scene.get('objmc_preview_type') == 'THIRD_PERSON':
            from .third_person import head_matrix
            matrix = head_matrix(settings)
        else:
            matrix = hand_matrix(settings)
        for obj in scene.objects:
            role = obj.get('objmc_role')
            if role == 'item':
                obj.matrix_world = matrix
            elif role == 'camera':
                obj.data.angle_y = math.radians(settings.fov)
        if context.screen:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()


def _material(name, color, image=None):
    material = bpy.data.materials.new(name)
    material['objmc_preview'] = True
    material.diffuse_color = color
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = color
    shader.inputs['Roughness'].default_value = 0.85
    if image:
        texture = material.node_tree.nodes.new('ShaderNodeTexImage')
        texture.image = image
        texture.interpolation = 'Closest'
        material.node_tree.links.new(texture.outputs['Color'], shader.inputs['Base Color'])
        material.node_tree.links.new(texture.outputs['Alpha'], shader.inputs['Alpha'])
    return material


def _object(scene, name, vertices, faces, material, role):
    mesh = bpy.data.meshes.new(name)
    mesh['objmc_preview'] = True
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj['objmc_role'] = role
    obj['objmc_preview_owned'] = True
    scene.collection.objects.link(obj)
    mesh.materials.append(material)
    return obj


def _box(scene, name, material, role):
    vertices = [(x/2, y/2, z/2) for x, y, z in
                [(-1,-1,-1), (1,-1,-1), (1,1,-1), (-1,1,-1),
                 (-1,-1,1), (1,-1,1), (1,1,1), (-1,1,1)]]
    faces = [(0,3,2,1), (4,5,6,7), (0,1,5,4), (1,2,6,5), (2,3,7,6), (3,0,4,7)]
    return _object(scene, name, vertices, faces, material, role)


def _destroy(scene):
    for entry in list(_view_states):
        owner, area, overlays, shading, view = entry
        if owner == scene:
            try:
                if area.type == 'VIEW_3D':
                    space = area.spaces.active
                    space.overlay.show_overlays = overlays
                    space.shading.type = shading
                    for name, value in view.items():
                        setattr(space.region_3d, name, value)
            except ReferenceError:
                pass
            _view_states.remove(entry)
    source = scene.objmc_source
    for obj in list(scene.objects):
        if not obj.get('objmc_preview_owned'):
            # Preserve edits made in the preview, including linked originals.
            if source and len(obj.users_scene) == 1 and obj.name not in source.objects:
                source.collection.objects.link(obj)
            continue
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Camera):
                bpy.data.cameras.remove(data)
            elif isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)
    world = scene.world
    bpy.data.scenes.remove(scene)
    if world and world.users == 0 and world.get('objmc_preview_owned'):
        bpy.data.worlds.remove(world)
    for material in list(bpy.data.materials):
        if material.get('objmc_preview') and material.users == 0:
            bpy.data.materials.remove(material)


def return_windows_to_source(context, scene):
    source = scene.objmc_source
    layer = source.view_layers.get(scene.get('objmc_source_layer', ''))
    for window in context.window_manager.windows:
        if window.scene == scene:
            window.scene = source
            if layer:
                window.view_layer = layer


def create_preview(context):
    source = source_scene(context)
    settings = source.objmc
    third_person = settings.project_type == 'THIRD_PERSON'
    layer = source_layer(context, source)
    layer.update()
    objects = sorted((obj for obj in layer.objects if is_mesh_source(obj)), key=lambda obj: obj.name)
    if not objects:
        raise ValueError('No meshes in the source view layer.')
    data = snapshot(context, source, objects)
    for existing in list(bpy.data.scenes):
        if existing.objmc_source == source:
            return_windows_to_source(context, existing)
            _destroy(existing)
    scene = bpy.data.scenes.new('OBJMC · Third Person' if third_person else 'OBJMC · First Person')
    scene.objmc_source = source
    scene['objmc_preview_type'] = settings.project_type
    scene['objmc_source_layer'] = layer.name
    try:
        scene.render.engine = 'BLENDER_EEVEE'
        scene.render.resolution_x, scene.render.resolution_y = 1280, 720
        scene.render.resolution_percentage = 100
        scene.view_settings.view_transform = 'Standard'
        scene.world = bpy.data.worlds.new('OBJMC Preview Sky')
        scene.world['objmc_preview_owned'] = True
        scene.world.use_nodes = True
        scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.30, 0.45, 0.65, 1)
        scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.8
        atlas = _material('OBJMC Preview Atlas', (0.7, 0.7, 0.7, 1), settings.texture)
        skin_materials = {}
        for item in data:
            obj = _object(scene, 'Held · '+item['name'], item['vertices'], item['faces'], atlas, 'item')
            if (settings.auto_textures or item.get('use_skin_materials')) and item['materials']:
                obj.data.materials.clear()
                for original in item['materials']:
                    if original is None:
                        obj.data.materials.append(atlas)
                        continue
                    key = original.as_pointer()
                    if key not in skin_materials:
                        material = original.copy()
                        material.name = 'OBJMC Preview Skin'
                        material['objmc_preview'] = True
                        skin_materials[key] = material
                    obj.data.materials.append(skin_materials[key])
                for poly, index in zip(obj.data.polygons, item['material_indices']):
                    poly.material_index = index
            uv_layer = obj.data.uv_layers.new(name='UVMap')
            for poly, face_uv in zip(obj.data.polygons, item['uvs']):
                for index, uv in zip(poly.loop_indices, face_uv):
                    uv_layer.data[index].uv = uv
        ground_mat = _material('OBJMC Ground', (0.12, 0.19, 0.13, 1))
        ground_y = 0 if third_person else -1.6
        near = 40 if third_person else 2
        _object(scene, 'Ground reference', [(-40,ground_y,near), (40,ground_y,near), (40,ground_y,-60), (-40,ground_y,-60)],
                [(0,1,2,3)], ground_mat, 'ground')
        camera_data = bpy.data.cameras.new('OBJMC First Person')
        camera_data.type = 'PERSP'
        camera_data.sensor_fit = 'VERTICAL'
        camera_data.clip_start = 0.01
        camera = bpy.data.objects.new('OBJMC First Person', camera_data)
        camera['objmc_role'] = 'camera'
        camera['objmc_preview_owned'] = True
        scene.collection.objects.link(camera)
        scene.camera = camera
        if third_person:
            from .third_person import add_armor_stand
            add_armor_stand(scene)
            camera.location = (3, 2.6, 5)
            # Preview geometry is Minecraft Y-up; to_track_quat assumes world Z-up.
            backward = (camera.location-Vector((0,1.5,0))).normalized()
            right = Vector((0,1,0)).cross(backward).normalized()
            up = backward.cross(right)
            camera.rotation_euler = Matrix((right, up, backward)).transposed().to_euler()
        light_data = bpy.data.lights.new('OBJMC Preview Light', 'AREA')
        light_data.energy, light_data.shape, light_data.size = 250, 'DISK', 4
        light = bpy.data.objects.new('OBJMC Preview Light', light_data)
        light['objmc_preview_owned'] = True
        scene.collection.objects.link(light)
        light.location = (-2, 3, 1)
        light.rotation_euler = (Vector((0, -0.4, -1))-light.location).to_track_quat('-Z', 'Y').to_euler()
        update_preview(settings, context)
        if context.screen:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    space = area.spaces.active
                    _view_states.append((scene, area, space.overlay.show_overlays,
                                         space.shading.type, {
                                             'view_location': space.region_3d.view_location.copy(),
                                             'view_rotation': space.region_3d.view_rotation.copy(),
                                             'view_distance': space.region_3d.view_distance,
                                             'view_camera_offset': tuple(space.region_3d.view_camera_offset),
                                             'view_camera_zoom': space.region_3d.view_camera_zoom,
                                             'view_perspective': space.region_3d.view_perspective,
                                         }))
        if context.window:
            context.window.scene = scene
        if context.screen:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.spaces.active.region_3d.view_perspective = 'CAMERA'
                    # Overlays belong to the shared editor, not the preview scene.
                    # Keep vertex dots and gizmos visible on direct scene switches.
                    area.spaces.active.shading.type = 'MATERIAL'
        return scene
    except Exception:
        return_windows_to_source(context, scene)
        _destroy(scene)
        raise


def close_preview(context):
    scene = context.scene
    source = scene.objmc_source
    if not source:
        raise ValueError('Open an OBJMC preview first.')
    return_windows_to_source(context, scene)
    _destroy(scene)
