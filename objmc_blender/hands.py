"""Import editable Minecraft arms using the standard 64x64 skin layout."""
import bpy


def _arm(collection, image, material, hand, width, sleeve, cursor):
    # Blender +Z is up; front faces -Y. Origin is the shoulder pivot.
    grow = 0.25 if sleeve else 0
    x, y = width / 2 + grow, 2 + grow
    vertices = [(a / 16, b / 16, c / 16) for a, b, c in
                [(-x,-y,-12-grow), (x,-y,-12-grow), (x,y,-12-grow), (-x,y,-12-grow),
                 (-x,-y,grow), (x,-y,grow), (x,y,grow), (-x,y,grow)]]
    faces = [(0,1,5,4), (2,3,7,6), (3,0,4,7), (1,2,6,5), (4,5,6,7), (3,2,1,0)]
    u, v = ((40, 32) if sleeve else (40, 16)) if hand == 'RIGHT' else (
        (48, 48) if sleeve else (32, 48))
    # Front, back, outer side, inner side, top and bottom rectangles.
    rects = [(u+4,v+4,width,12), (u+8+width,v+4,width,12),
             (u,v+4,4,12), (u+4+width,v+4,4,12),
             (u+4,v,width,4), (u+4+width,v,width,4)]
    mesh = bpy.data.meshes.new('Minecraft Arm Mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    uv = mesh.uv_layers.new(name='Skin UV')
    for poly, (rx, ry, rw, rh) in zip(mesh.polygons, rects):
        coords = [(rx,ry+rh), (rx+rw,ry+rh), (rx+rw,ry), (rx,ry)]
        for loop, (px, py) in zip(poly.loop_indices, coords):
            uv.data[loop].uv = (px / 64, 1 - py / 64)
    obj = bpy.data.objects.new('Minecraft '+hand.title()+(' Sleeve' if sleeve else ' Arm'), mesh)
    collection.objects.link(obj)
    obj.location = cursor
    obj.location.x += (-1 if hand == 'RIGHT' else 1) * (4 + width / 2) / 16
    obj['objmc_hand'] = hand
    obj['objmc_sleeve'] = sleeve
    mesh.materials.append(material)
    return obj


def _merge_sleeve(arm, sleeve):
    """One editable arm object with disconnected base/outer shells and two materials."""
    old, outer = arm.data, sleeve.data
    vertices = [tuple(v.co) for v in old.vertices] + [tuple(v.co) for v in outer.vertices]
    offset = len(old.vertices)
    faces = [tuple(p.vertices) for p in old.polygons]
    faces += [tuple(i+offset for i in p.vertices) for p in outer.polygons]
    mesh = bpy.data.meshes.new('Minecraft Layered Arm Mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.materials.append(old.materials[0])
    mesh.materials.append(outer.materials[0])
    uv = mesh.uv_layers.new(name='Skin UV')
    coords = [tuple(v.uv) for v in old.uv_layers.active.data] + [tuple(v.uv) for v in outer.uv_layers.active.data]
    for target, value in zip(uv.data, coords):
        target.uv = value
    for poly in mesh.polygons:
        poly.material_index = int(poly.index >= len(old.polygons))
    arm.data = mesh
    arm['objmc_layered_hand'] = True
    bpy.data.objects.remove(sleeve, do_unlink=True)
    bpy.data.meshes.remove(outer)
    bpy.data.meshes.remove(old)


def _rig_hands(context, collection, arms):
    """Rigid shoulder bones: all base and sleeve vertices share one bone per arm."""
    data = bpy.data.armatures.new('Minecraft Hands Skeleton')
    rig = bpy.data.objects.new('Minecraft Hands Rig', data)
    collection.objects.link(rig)
    rig.location = context.scene.cursor.location
    rig.show_in_front = True
    rig['objmc_hands_rig'] = True
    layer = context.view_layer
    active = layer.objects.active
    selected = [obj for obj in layer.objects if obj.select_get(view_layer=layer)]
    try:
        for obj in selected:
            obj.select_set(False, view_layer=layer)
        rig.select_set(True, view_layer=layer)
        layer.objects.active = rig
        bpy.ops.object.mode_set(mode='EDIT')
        root = data.edit_bones.new('root')
        root.head, root.tail = (0,0,0.125), (0,0,0.375)
        root.use_deform = False
        for arm in arms:
            name = 'arm.R' if arm['objmc_hand'] == 'RIGHT' else 'arm.L'
            bone = data.edit_bones.new(name)
            head = arm.location - rig.location
            bone.head = head
            bone.tail = (head.x, head.y, head.z-12/16)
            bone.parent = root
            bone.use_connect = False
        bpy.ops.object.mode_set(mode='OBJECT')
        for arm in arms:
            transform = arm.matrix_world.copy()
            arm.parent = rig
            arm.matrix_world = transform
            group = arm.vertex_groups.new(name='arm.R' if arm['objmc_hand'] == 'RIGHT' else 'arm.L')
            group.add(list(range(len(arm.data.vertices))), 1.0, 'REPLACE')
            modifier = arm.modifiers.new('Minecraft Hands Rig', 'ARMATURE')
            modifier.object = rig
    finally:
        if rig.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        rig.select_set(False, view_layer=layer)
        for obj in selected:
            obj.select_set(True, view_layer=layer)
        layer.objects.active = active
    return rig


def import_hands(context, image, slim=False, sleeves=True):
    if image is None or tuple(image.size) != (64, 64):
        raise ValueError('Choose a standard 64 x 64 Minecraft skin PNG.')
    if context.scene.objmc_source:
        raise ValueError('Use Back to Model before importing hands.')
    if context.mode != 'OBJECT':
        raise ValueError('Switch to Object Mode before importing hands.')
    material = bpy.data.materials.new('Minecraft Skin')
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value = 1
    texture = material.node_tree.nodes.new('ShaderNodeTexImage')
    texture.image = image
    texture.interpolation = 'Closest'
    material.node_tree.links.new(texture.outputs['Color'], shader.inputs['Base Color'])
    # Base skin is opaque; only the outer clothing layer uses skin transparency.
    outer = None
    if sleeves:
        outer = material.copy()
        outer.name = 'Minecraft Skin Sleeves'
        tex = next(n for n in outer.node_tree.nodes if n.type == 'TEX_IMAGE')
        bsdf = outer.node_tree.nodes.get('Principled BSDF')
        outer.node_tree.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
        outer.surface_render_method = 'DITHERED'
    collection = bpy.data.collections.new('Minecraft Hands')
    context.scene.collection.children.link(collection)
    arms = []
    for hand in ('RIGHT', 'LEFT'):
        arm = _arm(collection, image, material, hand, 3 if slim else 4, False, context.scene.cursor.location)
        if sleeves:
            sleeve = _arm(collection, image, outer, hand, 3 if slim else 4, True, context.scene.cursor.location)
            _merge_sleeve(arm, sleeve)
        arms.append(arm)
    context.view_layer.update()
    _rig_hands(context, collection, arms)
    context.view_layer.update()
    return collection
