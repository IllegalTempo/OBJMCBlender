"""Pack selected material images and remap temporary snapshot UVs only."""
import math

from .mesh import image_pixels
from .pixels import Image


def material_image(material):
    if material is None or not material.use_nodes:
        raise ValueError('Auto textures requires materials with an image connected to Principled Base Color.')
    outputs = [n for n in material.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output]
    if not outputs or not outputs[0].inputs['Surface'].is_linked:
        raise ValueError(f'{material.name}: connect a Principled BSDF to Material Output.')
    def upstream(socket):
        if not socket.is_linked:
            return None
        node = socket.links[0].from_node
        while node.type == 'REROUTE':
            if not node.inputs[0].is_linked:
                return None
            node = node.inputs[0].links[0].from_node
        return node
    shader = upstream(outputs[0].inputs['Surface'])
    if shader is None or shader.type != 'BSDF_PRINCIPLED':
        raise ValueError(f'{material.name}: bake mixed or procedural shaders to an image first.')
    texture = upstream(shader.inputs['Base Color'])
    if texture is None or texture.type != 'TEX_IMAGE' or texture.image is None:
        raise ValueError(f'{material.name}: connect an Image Texture directly to Base Color, or bake the material first.')
    vector = upstream(texture.inputs['Vector'])
    if texture.projection != 'FLAT' or (vector is not None and vector.type not in {'UVMAP', 'TEX_COORD'}):
        raise ValueError(f'{material.name}: bake texture mapping nodes before auto export.')
    if vector is not None and vector.type == 'TEX_COORD' and texture.inputs['Vector'].links[0].from_socket.name != 'UV':
        raise ValueError(f'{material.name}: use UV coordinates for the image texture.')
    return texture.image, vector.uv_map if vector is not None and vector.type == 'UVMAP' else ''


def build_atlas(data):
    images, bindings = {}, {}
    def face_binding(item, index):
        slot = item['material_indices'][index]
        materials = item['materials']
        material = materials[slot] if slot < len(materials) else None
        image, uv_map = material_image(material)
        if uv_map and uv_map != item.get('uv_map', ''):
            raise ValueError(f'{item["name"]}: make material UV map {uv_map!r} the active UV map before exporting.')
        return image
    for item in data:
        for i in range(len(item['faces'])):
            image = face_binding(item, i)
            key = image.as_pointer()
            if key not in images:
                images[key] = image_pixels(image, minimum=1)
            bindings[(item['name'], i)] = key
    # Stable shelf packing with two-pixel edge extrusion to prevent texture bleed.
    padding = 2
    entries = sorted(images.items(), key=lambda pair: (-pair[1].size[1], -pair[1].size[0], pair[0]))
    area = sum((im.size[0]+4)*(im.size[1]+4) for _, im in entries)
    width = 1 << (max(16, max(im.size[0]+4 for _,im in entries), math.ceil(math.sqrt(area)))-1).bit_length()
    regions, x, y, row_h = {}, 0, 0, 0
    for key, im in entries:
        w,h = im.size
        if x+w+4 > width:
            y, x, row_h = y+row_h, 0, 0
        regions[key] = (x+padding, y+padding, w,h)
        x += w+4
        row_h = max(row_h,h+4)
    height = 1 << (max(8,y+row_h)-1).bit_length()
    if width > 8192 or height > 8192:
        raise ValueError('Combined atlas exceeds 8192 pixels per side; reduce source image sizes.')
    atlas = Image.new('RGBA', (width,height), (0,0,0,0))
    for key, im in entries:
        x,y,w,h = regions[key]
        atlas.paste(im,(x,y))
        for py in range(-padding,h+padding):
            for px in range(-padding,w+padding):
                if 0 <= px < w and 0 <= py < h:
                    continue
                atlas.putpixel((x+px,y+py), im.getpixel((min(w-1,max(0,px)),min(h-1,max(0,py)))))
    def remap(snapshot):
        for item in snapshot:
            mapped = []
            for i, face_uv in enumerate(item['uvs']):
                image = face_binding(item,i)
                key = bindings.get((item['name'],i))
                if image.as_pointer() != key:
                    raise ValueError(f'{item["name"]}: material image changed during animation; use static textures.')
                x,y,w,h = regions[key]
                mapped.append(tuple(((x+u*w)/width, (height-y-h+v*h)/height) for u,v in face_uv))
            item['uvs'] = mapped
    return atlas, remap
