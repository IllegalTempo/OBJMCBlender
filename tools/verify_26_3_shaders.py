"""Compile item shader variants with the installed Minecraft ShaderC library.

Reads Minecraft 26.3 includes and LWJGL's native compiler, without launching game.
"""
import ctypes as c
import os
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MC = Path(os.environ['APPDATA']) / '.minecraft'
PACK = ROOT / 'objmc_blender/objcubed_26_3'
TMP = ROOT / '.test-temp/shader-validation'
TMP.mkdir(exist_ok=True)
with zipfile.ZipFile(MC / 'libraries/org/lwjgl/lwjgl-shaderc/3.4.3/lwjgl-shaderc-3.4.3-natives-windows.jar') as z:
    name = next(n for n in z.namelist() if n.endswith('/shaderc.dll'))
    dll = TMP / 'shaderc.dll'
    dll.write_bytes(z.read(name))
lib = c.CDLL(str(dll))
def bind(name, restype, args):
    f = getattr(lib, name)
    f.restype, f.argtypes = restype, args
    return f
ptr, uint, char = c.c_void_p, c.c_uint, c.c_char_p
init = bind('shaderc_compiler_initialize', ptr, [])
options_init = bind('shaderc_compile_options_initialize', ptr, [])
target = bind('shaderc_compile_options_set_target_env', None, [ptr,uint,uint])
spirv = bind('shaderc_compile_options_set_target_spirv', None, [ptr,uint])
auto_bind = bind('shaderc_compile_options_set_auto_bind_uniforms', None, [ptr,c.c_bool])
compile_shader = bind('shaderc_compile_into_spv',ptr,[ptr,char,c.c_size_t,uint,char,char,ptr])
status = bind('shaderc_result_get_compilation_status',uint,[ptr])
message = bind('shaderc_result_get_error_message',char,[ptr])
release_result = bind('shaderc_result_release',None,[ptr])
release_options = bind('shaderc_compile_options_release',None,[ptr])
release_compiler = bind('shaderc_compiler_release',None,[ptr])
compiler = init()
with zipfile.ZipFile(MC / 'versions/26.3/26.3.jar') as jar:
    def expand(source, stack=()):
        def inc(match):
            namespace, name = match[1].split(':',1)
            key = f'assets/{namespace}/shaders/include/{name}'
            if key in stack:
                raise ValueError('Recursive include: '+key)
            local = PACK / key
            content = local.read_text(encoding='utf-8') if local.exists() else jar.read(key).decode()
            return expand(content, (*stack,key))
        return re.sub(r'^\s*#include\s+<([^>]+)>', inc, source, flags=re.M)
    variants = {
        'solid': {}, 'cutout': {'ALPHA_CUTOUT': '0.1'},
        'glint': {'GLINT': '1'}, 'special_glint': {'GLINT': '1', 'GLINT_SPECIAL': '1'},
        'oit_depth': {'OIT': '1', 'OIT_ALPHA_ONLY': '1', 'OIT_DEPTH_BOUNDS': '1'},
        'oit_transmittance': {'OIT': '1', 'OIT_ALPHA_ONLY': '1', 'OIT_TRANSMITTANCE': '1',
                             'OIT_WAVELET_RANK': '3', 'OIT_COEFF_COUNT': '8', 'OIT_COEFF_ATTACHMENT_COUNT': '2'},
        'oit_accumulate': {'OIT': '1', 'OIT_ACCUMULATE': '1', 'OIT_WAVELET_RANK': '3',
                           'OIT_COEFF_COUNT': '8', 'OIT_COEFF_ATTACHMENT_COUNT': '2'},
    }
    count = 0
    try:
        for backend in ('OpenGL','Vulkan'):
            opts = options_init()
            target(opts, 1 if backend == 'OpenGL' else 0, 450 if backend == 'OpenGL' else 4198400)
            spirv(opts, 0x010300)
            auto_bind(opts, True)
            try:
                for name, defines in variants.items():
                    flags = {'OIT_WAVELET_RANK': '3', 'OIT_COEFF_COUNT': '8', 'OIT_COEFF_ATTACHMENT_COUNT': '2', **defines}
                    if backend == 'Vulkan':
                        flags['RENDERPEARL_DEPTH_IS_ZERO_TO_ONE'] = '1'
                    for stage, kind in [('vsh',0),('fsh',1)]:
                        source = expand((PACK / f'assets/minecraft/shaders/core/item.{stage}').read_text(encoding='utf-8'))
                        version, rest = source.split('\n',1)
                        source = version+'\n'+''.join(f'#define {k} {v}\n' for k,v in flags.items())+rest
                        code = source.encode()
                        result = compile_shader(compiler,code,len(code),kind,b'item',b'main',opts)
                        try:
                            if status(result):
                                raise RuntimeError(f'{backend}/{name}/{stage}: '+message(result).decode()[:3000])
                        finally:
                            release_result(result)
                        count += 1
            finally:
                release_options(opts)
    finally:
        release_compiler(compiler)
print(f'{count} item shader variants compiled successfully (OpenGL and Vulkan).')
