# Adapted from Godlander/objmc, MIT license (see LICENSE-objmc.txt).
# Generated with tools/adapt_encoder.py. Pillow, GUI and CLI removed.
import math
import json
from .pixels import Image, ImageOps

count = [0, 0]
mem = {"positions": {}, "uvs": {}}
data = {"positions": [], "uvs": [], "vertices": []}
js = {}
runtex = ""
visibility = 7

def exit():
    raise ValueError("objmc rejected the input; see export log for details.")

class col:
    head = "\033[95m"
    blue = "\033[94m"
    cyan = "\033[96m"
    green = "\033[92m"
    warn = "\033[93mWarning: "
    err = "\033[91mError: "
    end = "\033[0m"
    bold = "\033[1m"
    underline = "\033[4m"

def readobj(name, nfaces):
    obj = open(name, "r", encoding="utf-8")
    d = {"positions": [], "uvs": [], "faces": []}
    for line in obj:
        if line.startswith("v "):
            d["positions"].append(
                tuple([float(i) for i in " ".join(line.split()).split(" ")[1:]])
            )
        if line.startswith("vt "):
            d["uvs"].append(
                tuple([float(i) for i in " ".join(line.split()).split(" ")[1:]])
            )
        if line.startswith("f "):
            d["faces"].append(
                tuple(
                    [
                        [int(i) - 1 for i in vert.split("/")]
                        for vert in " ".join(line.split()).split(" ")[1:]
                    ]
                )
            )
    obj.close()
    if nfaces > 0 and len(d["faces"]) != nfaces:
        print(col.err + "mismatched obj face count" + col.end)
        exit()
    return d

def indexvert(o, vert):
    global count
    global mem
    global data
    v = []
    pos = o["positions"][vert[0]]
    uv = o["uvs"][vert[1]]
    posh = ",".join([str(i) for i in pos])
    uvh = ",".join([str(i) for i in uv])
    try:
        v.append(mem["positions"][posh])
    except:
        mem["positions"][posh] = count[0]
        data["positions"].append(pos)
        v.append(count[0])
        count[0] += 1
    try:
        v.append(mem["uvs"][uvh])
    except:
        mem["uvs"][uvh] = count[1]
        data["uvs"].append(uv)
        v.append(count[1])
        count[1] += 1
    data["vertices"].append(v)

def indexobj(o, frame, nframes, nfaces):
    for faceid in range(0, len(o["faces"])):
        if faceid % 1000 == 0:
            print(
                "Reading obj ",
                frame + 1,
                " of ",
                nframes,
                "...",
                "{:>15.2f}".format((frame * nfaces + faceid) * 100 / (nframes * nfaces)),
                "%\033[K",
                sep="",
                end="\r",
            )
        face = o["faces"][faceid]
        for vert in face[:4]:
            indexvert(o, vert)
        if len(face) == 3:
            indexvert(o, face[1])
        if len(face) > 4:
            print(col.warn + "Found N-Gon" + col.end)

def getheader(out, faceid, x, y, ty):
    posx = faceid % x
    posy = math.floor(faceid / x) + 1
    out.putpixel(
        (posx, posy),
        (int(posx / 256) % 256, posx % 256, int(posy / 256) % 256, posy % 256),
    )
    return [
        (posx + 0.1) * 16 / x,
        (posy + 0.1) * 16 / ty,
        (posx + 0.9) * 16 / x,
        (posy + 0.9) * 16 / ty,
    ]

def newelement(out, index, x, y, ty):
    cube = {
        "from": [8, 0, 8],
        "to": [24, 16, 8],
        "faces": {
            "north": {
                "uv": getheader(out, index, x, y, ty),
                "texture": "#0",
                "tintindex": 0,
            }
        },
    }
    js["elements"].append(cube)

def getposition(i):
    x = 8388608 + ((data["positions"][i][0]) * 65536) * scale + offset[0] * 65536
    y = 8388608 + ((data["positions"][i][1]) * 65536) * scale + offset[1] * 65536
    z = 8388608 + ((data["positions"][i][2]) * 65536) * scale + offset[2] * 65536

    rgb = []
    rgb.append((int((x / 65536) % 256), int((x / 256) % 256), int(x % 256), 255))
    rgb.append((int((y / 65536) % 256), int((y / 256) % 256), int(y % 256), 255))
    rgb.append((int((z / 65536) % 256), int((z / 256) % 256), int(z % 256), 255))
    return rgb

def getuv(i):
    x = (data["uvs"][i][0]) * 65535
    y = (data["uvs"][i][1]) * 65535
    rgb = []
    rgb.append((int((x / 65536) % 256), int((x / 256) % 256), int(x % 256), 255))
    rgb.append((int((y / 65536) % 256), int((y / 256) % 256), int(y % 256), 255))
    return rgb

def getvert(i, compression_enabled):
    poi = data["vertices"][i][0]
    uvi = data["vertices"][i][1]
    rgb = []

    if compression_enabled:
        if uvi >= 256:
            raise "UVI exceeds 256"
        rgb.append(
            (
                int((poi / 65536) % 256),
                int((poi / 256) % 256),
                int(poi % 256),
                uvi % 256 + 1,
            )
        )
    else:
        rgb.append(
            (int((poi / 65536) % 256), int((poi / 256) % 256), int(poi % 256), 255)
        )
        rgb.append(
            (int((uvi / 65536) % 256), int((uvi / 256) % 256), int(uvi % 256), 255)
        )

    return rgb

def objmc(
    objs,
    texs,
    output,
    sc,
    off,
    duration,
    easing,
    interpolation,
    colorbehavior,
    autorotate,
    autoplay,
    flipuv,
    noshadow,
    nopow,
    compression,
):
    global offset
    global scale
    offset = off
    scale = sc
    global count
    global mem
    global data
    count = [0, 0]
    mem = {"positions": {}, "uvs": {}}
    data = {"positions": [], "uvs": [], "vertices": []}

    # file extension optional
    if output[0][-5:] != ".json":
        output[0] += ".json"
    if output[1][-4:] != ".png":
        output[1] += ".png"

    ntextures = len(texs)
    nframes = len(objs)

    # input error checking
    if ntextures < 1 or nframes < 1:
        print(col.err + "must have a obj and a texture" + col.end)
        exit()
    if duration == 0:
        duration = nframes
    if duration < 1 or duration > 65536:
        print(col.err + "duration must be between 1 and 65536" + col.end)
        exit()
    tex = Image.open(texs[0])
    x, y = tex.size
    if x < 8:
        print(col.err + "minimum texture size is 8x8" + col.end)
        exit()

    print("\n" + col.cyan + "objmc start " + runtex + col.end)
    # read obj
    print(
        "Reading obj 1 of ",
        nframes,
        "...",
        "{:>15.2f}".format(0),
        "%\033[K",
        sep="",
        end="\r",
    )
    o = readobj(objs[0], 0)
    nfaces = len(o["faces"])
    indexobj(o, 0, nframes, nfaces)
    if nframes > 1:
        for frame in range(1, nframes):
            o = readobj(objs[frame], nfaces)
            indexobj(o, frame, nframes, nfaces)

    nvertices = nfaces * 4
    texheight = ntextures * y
    uvheight = math.ceil(nfaces / x)
    vpheight = math.ceil(len(data["positions"]) * 3 / x)
    vtheight = math.ceil(len(data["uvs"]) * 2 / x)

    compression_enabled = (
        len(data["uvs"]) <= 255 if compression == None else compression
    )

    vheight = math.ceil(len(data["vertices"]) * (1 if compression_enabled else 2) / x)
    # make height power of 2
    ty = 1 + uvheight + texheight + vpheight + vtheight + vheight
    if not nopow:
        ty = 1 << (ty - 1).bit_length()
    if (ty > 4096 and x < 4096) or (ty > 8 * x):
        print(
            col.warn
            + "output height may be too high, consider increasing width of input texture or reducing number of frames to bring the output texture closer to a square."
            + col.end
        )

    # parse color behavior
    cbarr = ["pitch", "yaw", "roll", "time", "scale", "overlay", "hurt"]
    ca = [cbarr.index(i) for i in colorbehavior]
    cb = (ca[0] << 6) + (ca[1] << 3) + (ca[2])

    # initial info
    print("%\033[K", end="\r")
    print("compression enabled:", compression_enabled)
    print(
        "faces: ",
        nfaces,
        ", verts: ",
        nvertices,
        ", tex: ",
        (x, y),
        ", flipuv: ",
        flipuv,
        sep="",
    )
    if nframes > 1 or ntextures > 1:
        print("objs: ", nframes, ", easing: ", easing, sep="")
        print("texs: ", ntextures, ", interpolation: ", interpolation, sep="")
        print(
            "duration: ",
            duration,
            "t",
            ", ",
            duration / 20,
            "s, autoplay: ",
            autoplay,
            sep="",
        )
    print(
        "uvhead: ",
        uvheight,
        ", vph: ",
        vpheight,
        ", vth: ",
        vtheight,
        ", vh: ",
        vheight,
        ", total: ",
        ty,
        sep="",
    )
    print(
        "colorbehavior: ",
        " ".join(colorbehavior),
        " (",
        cb,
        ")",
        ", autorotate: ",
        autorotate,
        sep="",
    )
    print("offset: ", offset, ", scale: ", scale, ", noshadow: ", noshadow, sep="")
    print(
        "visible:",
        " world" if visibility & 4 > 0 else "",
        " hand" if visibility & 2 > 0 else "",
        " gui" if visibility & 1 > 0 else "",
        sep="",
    )
    print("Creating Files...", end="\r")
    # write to json model
    model = open(output[0], "w")
    # create out image with correct dimensions
    out = Image.new("RGBA", (x, int(ty)), (0, 0, 0, 0))

    # header
    # | 2^32   | 2^16x2   | 2^32      | 2^24 + 2^8   | 2^24    + \1 2^1  + 2^2   + 2^2  \2| 2^16x2       | 2^1     + 2^2       + 2^3    \1 + 2^1 + 2^8   \16|
    # | marker | tex size | nvertices | nobjs, ntexs | duration, autoplay, easing, interp | data heights | noshadow, autorotate, visibility, colorbehavior  |
    # 0: marker
    out.putpixel((0, 0), (12, 34, 56, 79 if compression_enabled else 78))
    # 1: texsize
    out.putpixel((1, 0), (int(x / 256), x % 256, int(y / 256), y % 256))
    # 2: nvertices
    out.putpixel(
        (2, 0),
        (
            int(nvertices / 16777216) % 256,
            int(nvertices / 65536) % 256,
            int(nvertices / 256) % 256,
            nvertices % 256,
        ),
    )
    # 3: nobjs, ntexs
    out.putpixel(
        (3, 0),
        (
            int(nframes / 65536) % 256,
            int(nframes / 256) % 256,
            nframes % 256,
            ntextures,
        ),
    )
    # 4: duration, autoplay, easing
    out.putpixel(
        (4, 0),
        (
            int(duration / 65536) % 256,
            int(duration / 256) % 256,
            duration % 256,
            128 + (int(autoplay) << 6) + (easing << 4) + (interpolation << 2),
        ),
    )
    # 5: data heights
    out.putpixel(
        (5, 0),
        (
            int(vpheight / 256) % 256,
            int(vpheight) % 256,
            int(vtheight / 256) % 256,
            vtheight % 256,
        ),
    )
    # 6: noshadow, autorotate, visibility, colorbehavior
    out.putpixel(
        (6, 0),
        (
            (int(noshadow) << 7)
            + (autorotate << 5)
            + (visibility << 2)
            + int(cb / 256),
            cb % 256,
            255,
        ),
    )

    # actual texture
    for i in range(0, len(texs)):
        tex = Image.open(texs[i])
        nx, ny = tex.size
        if nx != x or ny != y:
            print(col.err + "mismatched texture sizes" + col.end)
            exit()
        if flipuv:
            out.paste(tex, (0, 1 + uvheight + (i * y)))
        else:
            out.paste(ImageOps.flip(tex), (0, 1 + uvheight + (i * y)))

    # generate json model elements and uv header
    global js
    js = {
        "textures": {"0": output[1].split(".")[0]},
        "elements": [],
        "display": {
            "thirdperson_righthand": {"rotation": [85, 0, 0]},
            "thirdperson_lefthand": {"rotation": [85, 0, 0]},
        },
    }
    for i in range(0, nfaces):
        newelement(out, i, x, y, ty)

    print("Writing json model...\033[K", end="\r")
    model.write(json.dumps(js, separators=(",", ":")))
    model.close()

    print("Writing position data...\033[K", end="\r")
    y = 1 + uvheight + texheight
    for i in range(0, len(data["positions"])):
        a = getposition(i)
        for j in range(0, 3):
            p = i * 3 + j
            out.putpixel((p % x, y + math.floor(p / x)), a[j])

    print("Writing uv data...\033[K", end="\r")
    y = 1 + uvheight + texheight + vpheight
    for i in range(0, len(data["uvs"])):
        a = getuv(i)
        for j in range(0, 2):
            p = i * 2 + j
            out.putpixel((p % x, y + math.floor(p / x)), a[j])
    print("Writing vertex data...\033[K", end="\r")
    y = 1 + uvheight + texheight + vpheight + vtheight
    for i in range(0, len(data["vertices"])):
        a = getvert(i, compression_enabled)

        if compression_enabled:
            out.putpixel((i % x, y + math.floor(i / x)), a[0])
        else:
            for j in range(0, 2):
                p = i * 2 + j
                out.putpixel((p % x, y + math.floor(p / x)), a[j])

    print("Saving files...\033[K", end="\r")
    out.save(output[1])
    out.close()
    print(col.green + "Complete\033[K" + col.end)

def convert(objs, texture, model_path, texture_path, *, duration=1, easing=1,
            autoplay=True, flipuv=False, noshadow=False):
    global visibility
    visibility = 7
    objmc([str(p) for p in objs], [texture], [str(model_path), str(texture_path)],
          1.0, (0, 0, 0), duration, easing, 0,
          ["pitch", "yaw", "roll"], 1, autoplay, flipuv, noshadow, False, None)
