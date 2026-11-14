"""Evaluated mesh snapshots shared by export and first-person preview."""
from array import array
import math

import bpy
from mathutils import Matrix

from .pixels import Image

# Blender Z-up to Minecraft Y-up, one Blender unit = one block before scale.
TO_MINECRAFT = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))


def source_scene(context):
    return context.scene.objmc_source or context.scene


def source_layer(context, scene):
    if context.scene == scene:
        return context.view_layer
    return scene.view_layers.get(context.scene.get('objmc_source_layer', '')) or scene.view_layers[0]


def is_mesh_source(obj):
    """Objects that supply geometry directly or through a collection instance."""
    return obj.type == 'MESH' or (obj.instance_type == 'COLLECTION' and obj.instance_collection is not None)


def selected_meshes(scene, layer=None):
    layer = layer or scene.view_layers[0]
    layer.update()
    objects = [obj for obj in layer.objects if is_mesh_source(obj) and obj.select_get(view_layer=layer)]
    if not objects:
        raise ValueError('Select at least one mesh or collection instance in your source scene.')
    return sorted(objects, key=lambda obj: obj.name)


def snapshot(context, scene, objects):
    """Return world-space geometry/UVs with stable face order; free evaluated meshes."""
    result = []
    with context.temp_override(scene=scene, view_layer=source_layer(context, scene)):
        context.view_layer.update()
        depsgraph = context.evaluated_depsgraph_get()
        jobs = []
        instance_roots = set()
        for obj in objects:
            if obj.type == 'MESH':
                evaluated = obj.evaluated_get(depsgraph)
                jobs.append((obj.name, obj, evaluated.matrix_world.copy()))
            if obj.instance_type == 'COLLECTION' and obj.instance_collection is not None:
                instance_roots.add(obj)
        if instance_roots:
            instance_jobs = []
            for instance in depsgraph.object_instances:
                if not instance.is_instance or instance.object.type != 'MESH' or instance.parent is None:
                    continue
                root = instance.parent.original
                if root not in instance_roots:
                    continue
                # Instance objects are temporary and invalid after the iterator moves.
                # Keep only stable original IDs and copied matrices. Persistent IDs
                # distinguish repeated/nested instances across animation frames.
                identity = ','.join(str(i) for i in instance.persistent_id)
                original = instance.object.original
                name = f'{root.name}/{original.name}[{identity}]'
                instance_jobs.append((name, original, instance.matrix_world.copy()))
            jobs.extend(sorted(instance_jobs, key=lambda job: job[0]))
        for name, original, matrix in jobs:
            evaluated = original.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            try:
                if not mesh.polygons:
                    raise ValueError(f'{name}: evaluated mesh has no faces.')
                if not mesh.uv_layers.active:
                    raise ValueError(f'{name}: add a UV map before exporting.')
                vertices = [tuple(matrix @ v.co) for v in mesh.vertices]
                uv_layer = mesh.uv_layers.active.data
                mesh.calc_loop_triangles()
                ngon_triangles = {}
                for tri in mesh.loop_triangles:
                    ngon_triangles.setdefault(tri.polygon_index, []).append(tuple(tri.loops))
                faces, uvs = [], []
                mirrored = matrix.determinant() < 0
                for poly in mesh.polygons:
                    loops = ngon_triangles[poly.index]
                    for face_loops in loops:
                        if mirrored:
                            face_loops = tuple(reversed(face_loops))
                        faces.append(tuple(mesh.loops[i].vertex_index for i in face_loops))
                        uv = tuple(tuple(uv_layer[i].uv) for i in face_loops)
                        if any(not math.isfinite(x) or not 0 <= x <= 1 for pair in uv for x in pair):
                            raise ValueError(f'{name}: UV coordinates must be within 0–1; use an atlas.')
                        uvs.append(uv)
                result.append({'name': name, 'vertices': vertices, 'faces': faces,
                               'use_skin_materials': bool(original.get('objmc_hand') or original.get('objmc_player_part')),
                               'uvs': uvs, 'uv_map': mesh.uv_layers.active.name, 'materials': list(mesh.materials),
                               'material_indices': [p.material_index for p in mesh.polygons
                                                    for _ in ngon_triangles[p.index]]})
            finally:
                evaluated.to_mesh_clear()
    return result


def topology_signature(snapshot_data):
    return tuple((s['name'], len(s['vertices']), tuple(s['faces'])) for s in snapshot_data)


def write_obj(path, snapshot_data, geometry_scale):
    vertex_offset, uv_index = 0, 0
    with open(path, 'w', encoding='utf-8') as handle:
        for item in snapshot_data:
            for x, y, z in item['vertices']:
                point = (x * geometry_scale, z * geometry_scale, -y * geometry_scale)
                if any(not math.isfinite(n) or n < -128 or n >= 128 for n in point):
                    raise ValueError(f'{item["name"]}: geometry exceeds objmc range [-128, 128) blocks; reduce scale or move toward origin.')
                handle.write('v ' + ' '.join(format(n, '.9g') for n in point) + '\n')
            for face, uvs in zip(item['faces'], item['uvs']):
                entries = []
                for vertex, (u, v) in zip(face, uvs):
                    uv_index += 1
                    handle.write(f'vt {u:.9g} {v:.9g}\n')
                    entries.append(f'{vertex_offset + vertex + 1}/{uv_index}')
                handle.write('f ' + ' '.join(entries) + '\n')
            vertex_offset += len(item['vertices'])


def image_pixels(image, minimum=8):
    if image is None:
        raise ValueError('Choose a shared texture atlas image.')
    if image.source not in {'FILE', 'GENERATED'}:
        raise ValueError('Use a single image texture, not a movie, sequence or UDIM.')
    w, h = image.size
    if w < minimum or h < minimum:
        raise ValueError('Texture atlas must be at least 8 × 8 pixels.')
    if w > 65535 or h > 65535:
        raise ValueError('Texture dimensions exceed objmc header limits.')
    values = array('f', [0.0]) * (w*h*4)
    image.pixels.foreach_get(values)
    data = bytearray(w*h*4)
    for y in range(h):
        for x in range(w):
            src = ((h-1-y)*w+x)*4
            dst = (y*w+x)*4
            for channel in range(4):
                value = values[src+channel]
                # Byte-backed images expose encoded samples; float images are linear.
                if image.is_float and channel < 3:
                    value = 12.92*value if value <= 0.0031308 else 1.055*max(0, value)**(1/2.4)-0.055
                data[dst+channel] = round(max(0, min(1, value))*255)
    return Image((w, h), data)
