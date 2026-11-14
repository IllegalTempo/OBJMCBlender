"""Approximate normal-size armor stand head display in Minecraft Y-up space."""
import math
from mathutils import Matrix, Vector

from .mesh import TO_MINECRAFT


def head_matrix(settings):
    from .preview import _rotation
    # ArmorStandModel head pivot: (0,1,0) below model y=24. CustomHeadLayer
    # translates up .25 blocks, turns 180 degrees and applies .625 item scale.
    # Source: installed 26.3 client CustomHeadLayer.translateToHead bytecode.
    return (Matrix.Translation((0,27/16,0))
            @ Matrix.Rotation(math.pi, 4, 'Y')
            @ Matrix.Scale(0.625, 4)
            @ Matrix.Translation(Vector(settings.head_translation)/16)
            @ _rotation(settings.head_rotation)
            @ Matrix.Diagonal((*settings.head_scale, 1))
            @ TO_MINECRAFT
            @ Matrix.Scale(settings.geometry_scale, 4))


def add_armor_stand(scene):
    from .preview import _box, _material
    wood = _material('OBJMC Armor Stand Wood', (0.40,0.25,0.11,1))
    stone = _material('OBJMC Armor Stand Base', (0.48,0.48,0.46,1))
    # Neutral normal-size silhouette, in model pixels. Arms use a straight pose.
    for name, size, center, material in [
        ('Base Plate', (12,1,12), (0,0.5,0), stone),
        ('Right Leg', (2,11,2), (-1.9,6.5,0), wood),
        ('Left Leg', (2,11,2), (1.9,6.5,0), wood),
        ('Waist', (8,2,2), (0,13,0), wood),
        ('Right Body Stick', (2,7,2), (-3,17.5,0), wood),
        ('Left Body Stick', (2,7,2), (3,17.5,0), wood),
        ('Shoulder', (12,3,3), (0,22.5,0), wood),
        ('Right Arm', (2,12,2), (-6,16,0), wood),
        ('Left Arm', (2,12,2), (6,16,0), wood),
        ('Head Post', (2,7,2), (0,26.5,0), wood),
    ]:
        obj = _box(scene, 'Armor Stand '+name, material, 'armor_stand')
        obj.location = Vector(center)/16
        obj.scale = Vector(size)/16
        obj.hide_select = True
