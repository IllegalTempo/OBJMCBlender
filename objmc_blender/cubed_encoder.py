"""Minimal item encoding for obj-cubed 26.3v4 (MIT; LICENSE-objcubed.txt).

Layout and carrier conventions follow objcubed.js at release 26.3v4.
Single static atlas, flat shading and evaluated vertex animation are supported.
Blender's world origin stays the pivot; coordinates are already block-relative.
"""
import copy
import math

from . import encoder
from .pixels import Image


def encode(objs, texture, *, duration=1, easing=1, autoplay=True, flipuv=False,
           noshadow=False, hand_scales=((1, 1, 1), (1, 1, 1)), head_scale=(1, 1, 1)):
    positions, uvs, vertices = [], [], []
    pm, um = {}, {}
    source_w, th = texture.size
    tw = max(16, source_w)
    nfaces = 0
    for path in objs:
        frame = encoder.readobj(str(path), nfaces)
        nfaces = len(frame['faces'])
        for face in frame['faces']:
            if len(face) != 3:
                raise ValueError('obj-cubed export requires triangulated input.')
            for vi, ti in [face[0], face[1], face[2], face[2]]:
                pos = tuple(frame['positions'][vi])
                uv = tuple(frame['uvs'][ti][:2])
                uv = (uv[0] * source_w / tw, uv[1])
                if pos not in pm:
                    pm[pos] = len(positions)
                    positions.append(pos)
                if uv not in um:
                    um[uv] = len(uvs)
                    uvs.append(uv)
                vertices.append((pm[pos], um[uv]))
    if not nfaces:
        raise ValueError('No faces to encode.')
    nframes, nv = len(objs), nfaces * 4
    uvh = math.ceil(nfaces / tw)
    vph = math.ceil(len(positions) * 3 / tw)
    vth = math.ceil(len(uvs) * 2 / tw)
    vh = math.ceil(len(vertices) * 2 / tw)
    height = 2 + uvh + th + vph + vth + vh
    if vph > 65535 or vth > 65535 or height > 32768:
        raise ValueError('Encoded texture too tall; use a wider atlas or fewer frames.')
    if max(len(positions), len(uvs), nframes, duration) > 16777215:
        raise ValueError('obj-cubed 24-bit data limit exceeded.')
    out = Image.new('RGBA', (tw, height), (0, 0, 0, 0))
    def put(x, y, *rgba):
        out.putpixel((x, y), rgba if len(rgba) == 4 else (*rgba, 255))
    def u24(n):
        n = int(n)
        return ((n >> 16) & 255, (n >> 8) & 255, n & 255)
    put(0, 0, 12, 34, 56)
    put(1, 0, tw >> 8, tw & 255, th >> 8)
    put(2, 0, (nv >> 24) & 255, (nv >> 16) & 255, (nv >> 8) & 255)
    put(3, 0, *u24(nframes), 1)
    put(4, 0, *u24(duration), 128 | (64 if autoplay else 0) | (easing << 4))
    put(5, 0, vph >> 8, vph & 255, vth >> 8)
    put(6, 0, (128 if noshadow else 0) | 32 | 28, 0, 2)
    put(7, 0, th & 255, nv & 255, vth & 255)
    # Identity GUI transform, encoded at q16 across opaque RGB bytes.
    for start, values, low, high in [(8, (1,1,1), 0,4), (10,(0,0,0),-128,128),
                                    (12,(0,0,0),0,360), (14,(0,0,0),-128,128)]:
        packed = []
        for value in values:
            q = math.floor((value-low)/(high-low)*65535+0.5)
            packed.extend((q >> 8, q & 255))
        put(start, 0, *packed[:3])
        put(start+1, 0, *packed[3:])
    for x in range(tw):
        put(x, 1, 0, 0, 0)
    # Two explicit hand contexts and one shared ground/shelf lift context.
    for i, scale in enumerate(hand_scales):
        sz = abs(scale[2]) if abs(abs(scale[2])-min(abs(scale[0]),abs(scale[1]))) > 1e-4 else 0
        q = math.floor(min(4, sz)/4*65535+0.5)
        put(i, 1, q >> 8, q & 255, 2)
    put(2, 1, 0, 0, 1)
    sz = abs(head_scale[2]) if abs(abs(head_scale[2])-min(abs(head_scale[0]), abs(head_scale[1]))) > 1e-4 else 0
    q = math.floor(min(4, sz)/4*65535+0.5)
    put(3, 1, q >> 8, q & 255, 0)
    put(5, 1, 8, 0, 2)
    elements = []
    for i in range(nfaces):
        x, y = i % tw, i // tw + 2
        put(x, y, x >> 8, x & 255, y >> 8, y & 255)
        elements.append({'from': [8,8,8], 'to': [24,24,8], 'faces': {'north': {
            'uv': [(x+.1)*16/tw, (y+.1)*16/height, (x+.9)*16/tw, (y+.9)*16/height],
            'texture': '#0', 'tintindex': 0}}})
    for y in range(th):
        sy = y if flipuv else th-1-y
        for x in range(source_w):
            put(x, 2+uvh+y, *texture.getpixel((x, sy)))
    base = 2+uvh+th
    for i, pos in enumerate(positions):
        for axis, value in enumerate(pos):
            if not math.isfinite(value) or not -128 <= value < 128:
                raise ValueError('Position outside obj-cubed range [-128, 128).')
            p = i*3+axis
            put(p % tw, base+p//tw, *u24(8388608+value*65536))
    base += vph
    for i, uv in enumerate(uvs):
        for axis, value in enumerate(uv):
            p = i*2+axis
            put(p % tw, base+p//tw, *u24(max(0,min(1,value))*65535))
    base += vth
    for i, pair in enumerate(vertices):
        for j, value in enumerate(pair):
            p = i*2+j
            put(p % tw, base+p//tw, *u24(value))
    return {'elements': elements}, out


def slot_variant(model, marker, lift=False):
    result = copy.deepcopy(model)
    for element in result['elements']:
        if lift:
            element['from'][1] += 8
            element['to'][1] += 8
        uv = element['faces']['north']['uv']
        texel = (uv[2]-uv[0]) / .8
        midpoint = uv[0]-.1*texel + (.5+marker*.035)*texel
        uv[0], uv[2] = midpoint-.2*texel, midpoint+.2*texel
    return result
