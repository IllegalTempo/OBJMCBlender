"""Editable, rigidly skinned Steve/Alex model from a standard 64x64 skin."""
import bpy
from mathutils import Vector

from .hands import _arm, _merge_sleeve


def _part(collection, material, name, size, origin, bottom, uv_origin, grow=0):
    w, d, h = size
    x, y = w/2+grow, d/2+grow
    low, high = bottom-grow, bottom+h+grow
    vertices = [(a/16, b/16, c/16) for a,b,c in [
        (-x,-y,low), (x,-y,low), (x,y,low), (-x,y,low),
        (-x,-y,high), (x,-y,high), (x,y,high), (-x,y,high)]]
    faces = [(0,1,5,4), (2,3,7,6), (3,0,4,7), (1,2,6,5), (4,5,6,7), (3,2,1,0)]
    mesh = bpy.data.meshes.new('Minecraft '+name+' Mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    u,v = uv_origin
    rects = [(u+d,v+d,w,h), (u+2*d+w,v+d,w,h), (u,v+d,d,h),
             (u+d+w,v+d,d,h), (u+d,v,w,d), (u+d+w,v,w,d)]
    uv = mesh.uv_layers.new(name='Skin UV')
    for poly, (rx,ry,rw,rh) in zip(mesh.polygons, rects):
        for loop, (px,py) in zip(poly.loop_indices, [(rx,ry+rh),(rx+rw,ry+rh),(rx+rw,ry),(rx,ry)]):
            uv.data[loop].uv = (px/64, 1-py/64)
    mesh.materials.append(material)
    obj = bpy.data.objects.new('Minecraft '+name, mesh)
    collection.objects.link(obj)
    obj.location = origin
    return obj


def _rig_player(context, collection, parts, cursor):
    data = bpy.data.armatures.new('Minecraft Player Skeleton')
    rig = bpy.data.objects.new('Minecraft Player Rig', data)
    collection.objects.link(rig)
    rig.location = cursor
    rig.show_in_front = True
    rig['objmc_player_rig'] = True
    layer = context.view_layer
    active = layer.objects.active
    selected = [o for o in layer.objects if o.select_get(view_layer=layer)]
    try:
        for obj in selected:
            obj.select_set(False, view_layer=layer)
        rig.select_set(True, view_layer=layer)
        layer.objects.active = rig
        bpy.ops.object.mode_set(mode='EDIT')
        root = data.edit_bones.new('root')
        root.head, root.tail = (0,0,0), (0,0,0.25)
        root.use_deform = False
        pivots = {
            'body': ((0,0,24), (0,0,12), 'root'),
            'head': ((0,0,24), (0,0,32), 'body'),
            'arm.R': ((-5,0,24), (-5,0,12), 'body'),
            'arm.L': ((5,0,24), (5,0,12), 'body'),
            'leg.R': ((-2,0,12), (-2,0,0), 'root'),
            'leg.L': ((2,0,12), (2,0,0), 'root'),
        }
        for name, (head,tail,parent) in pivots.items():
            bone = data.edit_bones.new(name)
            bone.head, bone.tail = Vector(head)/16, Vector(tail)/16
            bone.parent = data.edit_bones[parent]
        bpy.ops.object.mode_set(mode='OBJECT')
        layer.update()
        for name, obj in parts.items():
            transform = obj.matrix_world.copy()
            obj.parent = rig
            obj.matrix_world = transform
            obj['objmc_player_part'] = name
            group = obj.vertex_groups.new(name=name)
            group.add(list(range(len(obj.data.vertices))), 1, 'REPLACE')
            modifier = obj.modifiers.new('Minecraft Player Rig', 'ARMATURE')
            modifier.object = rig
    finally:
        if rig.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        rig.select_set(False, view_layer=layer)
        for obj in selected:
            obj.select_set(True, view_layer=layer)
        layer.objects.active = active
    return rig


def import_player(context, image, slim=False, outer_layers=True):
    if image is None or tuple(image.size) != (64,64):
        raise ValueError('Choose a standard 64 x 64 Minecraft skin PNG.')
    if context.scene.objmc_source:
        raise ValueError('Use Back to Model before importing a Minecraft model.')
    if context.mode != 'OBJECT':
        raise ValueError('Switch to Object Mode before importing a Minecraft model.')
    material = bpy.data.materials.new('Minecraft Player Skin')
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Roughness'].default_value = 1
    texture = material.node_tree.nodes.new('ShaderNodeTexImage')
    texture.image, texture.interpolation = image, 'Closest'
    material.node_tree.links.new(texture.outputs['Color'], bsdf.inputs['Base Color'])
    outer = material.copy() if outer_layers else None
    if outer:
        outer.name = 'Minecraft Player Clothing'
        nodes = outer.node_tree.nodes
        outer.node_tree.links.new(next(n for n in nodes if n.type == 'TEX_IMAGE').outputs['Alpha'],
                                  nodes.get('Principled BSDF').inputs['Alpha'])
        outer.surface_render_method = 'DITHERED'
    collection = bpy.data.collections.new('Minecraft Model')
    context.scene.collection.children.link(collection)
    cursor = context.scene.cursor.location.copy()
    shoulder = cursor + Vector((0,0,24/16))
    parts = {}
    for side, hand in [('R','RIGHT'), ('L','LEFT')]:
        arm = _arm(collection, image, material, hand, 3 if slim else 4, False, shoulder)
        if outer:
            shell = _arm(collection, image, outer, hand, 3 if slim else 4, True, shoulder)
            _merge_sleeve(arm, shell)
        parts['arm.'+side] = arm
    for name, size, offset, bottom, uv, layer_uv in [
        ('head', (8,8,8), (0,0,24), 0, (0,0), (32,0)),
        ('body', (8,4,12), (0,0,24), -12, (16,16), (16,32)),
        ('leg.R', (4,4,12), (-2,0,12), -12, (0,16), (0,32)),
        ('leg.L', (4,4,12), (2,0,12), -12, (16,48), (0,48)),
    ]:
        origin = cursor + Vector(offset)/16
        obj = _part(collection, material, name, size, origin, bottom, uv)
        if outer:
            shell = _part(collection, outer, name+' Clothing', size, origin, bottom, layer_uv,
                          0.5 if name == 'head' else 0.25)
            _merge_sleeve(obj, shell)
        parts[name] = obj
    context.view_layer.update()
    _rig_player(context, collection, parts, cursor)
    context.view_layer.update()
    return collection
