"""Minimal RGBA8 Pillow-compatible surface used by objmc.

Data textures must bypass Blender's color management. PNG is written directly,
with no gamma/profile chunks and no changes to the encoder's metadata bytes.
"""
import struct
import zlib


class Image:
    def __init__(self, size, data):
        self.size = tuple(size)
        self.data = bytearray(data)
        if len(self.data) != size[0] * size[1] * 4:
            raise ValueError('RGBA buffer size does not match image dimensions.')

    @classmethod
    def new(cls, mode, size, color):
        if mode != 'RGBA':
            raise ValueError('Only RGBA images are supported.')
        return cls(size, bytes(color) * (size[0] * size[1]))

    @staticmethod
    def open(image):
        if not isinstance(image, Image):
            raise ValueError('Encoder expects an in-memory RGBA image.')
        return image

    def _index(self, xy):
        x, y = xy
        if not (0 <= x < self.size[0] and 0 <= y < self.size[1]):
            raise IndexError(f'Pixel {xy} outside {self.size}.')
        return (y * self.size[0] + x) * 4

    def putpixel(self, xy, color):
        index = self._index(xy)
        if len(color) == 3:
            color = (*color, 255)
        if len(color) != 4:
            raise ValueError('Pixel must contain RGB or RGBA channels.')
        self.data[index:index+4] = bytes(color)

    def getpixel(self, xy):
        index = self._index(xy)
        return tuple(self.data[index:index+4])

    def paste(self, source, xy):
        x, y = xy
        w, h = source.size
        self._index((x, y))
        self._index((x+w-1, y+h-1))
        for row in range(h):
            start = ((y + row) * self.size[0] + x) * 4
            self.data[start:start+w*4] = source.data[row*w*4:(row+1)*w*4]

    def save(self, path):
        def chunk(kind, data):
            return (struct.pack('>I', len(data)) + kind + data
                    + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff))
        w, h = self.size
        stride = w * 4
        rows = b''.join(b'\0' + self.data[y*stride:(y+1)*stride] for y in range(h))
        header = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
        with open(path, 'wb') as handle:
            handle.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header)
                         + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))

    def close(self):
        pass


class ImageOps:
    @staticmethod
    def flip(image):
        w, h = image.size
        stride = w * 4
        return Image(image.size, b''.join(image.data[y*stride:(y+1)*stride]
                                         for y in range(h-1, -1, -1)))
