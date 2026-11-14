"""Resource-pack paths and transactional output, independent of Blender."""
import json
import os
from pathlib import Path
import re
import shutil
import tempfile


def validate_resource(namespace, name):
    if not re.fullmatch(r'[a-z0-9_-]+(?:\.[a-z0-9_-]+)*', namespace):
        raise ValueError('Namespace must contain lowercase letters, digits, dots, _ or -.')
    if not re.fullmatch(r'[a-z0-9_./-]+', name) or any(
            part in ('', '.', '..') for part in name.split('/')):
        raise ValueError('Item path must be lowercase, with no empty, . or .. segments.')


def item_definition(namespace, name):
    validate_resource(namespace, name)
    return {'model': {'type': 'minecraft:model', 'model': f'{namespace}:item/{name}',
                      'tints': [{'type': 'minecraft:constant', 'value': 0}]}}


def context_item_definition(namespace, name, target, project_type, hide_third_person=False):
    """Hide display contexts without degenerating the shader carrier geometry."""
    validate_resource(namespace, name)
    resource = f'{namespace}:item/{name}'
    tint = 16777215 if target == '26.3' else 0
    def model(suffix=''):
        return {'type': 'minecraft:model', 'model': resource+suffix,
                'tints': [{'type': 'minecraft:constant', 'value': tint}]}
    hidden = set()
    if project_type == 'THIRD_PERSON':
        hidden.update(('firstperson_righthand', 'firstperson_lefthand'))
    elif hide_third_person:
        hidden.update(('thirdperson_righthand', 'thirdperson_lefthand', 'head'))
    cases = []
    if hidden:
        cases.append({'when': sorted(hidden), 'model': {'type': 'minecraft:empty'}})
    if target == '26.3':
        for suffix, slots in [
            ('__objcubed_right', ['firstperson_righthand']),
            ('__objcubed_left', ['firstperson_lefthand']),
            ('__objcubed_ground', ['ground', 'on_shelf']),
            ('__objcubed_head', ['head']),
        ]:
            visible = [slot for slot in slots if slot not in hidden]
            if visible:
                cases.append({'when': visible, 'model': model(suffix)})
    return {'hand_animation_on_swap': False, 'model': {
        'type': 'minecraft:select', 'property': 'minecraft:display_context',
        'cases': cases, 'fallback': model()}}


def pack_metadata(pack_format, description):
    if pack_format < 1:
        raise ValueError('Pack format must be positive.')
    return {'pack': {'pack_format': pack_format, 'min_format': pack_format,
                     'max_format': pack_format, 'description': description}}


def give_command(namespace, name, base_item):
    validate_resource(namespace, name)
    validate_resource('minecraft', base_item)
    return f'/give @s minecraft:{base_item}[minecraft:item_model="{namespace}:{name}"]'


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def validate_pack_root(destination):
    destination = Path(destination).resolve()
    metadata = destination / 'pack.mcmeta'
    if not destination.is_dir() or not metadata.is_file():
        raise ValueError('Select the resource-pack root folder containing pack.mcmeta.')
    try:
        value = json.loads(metadata.read_text(encoding='utf-8-sig'))
        if not isinstance(value, dict) or not isinstance(value.get('pack'), dict):
            raise ValueError('Missing pack object')
    except (ValueError, OSError) as error:
        raise ValueError('The selected folder must contain valid pack.mcmeta metadata.') from error
    return destination


def publish_resources(destination, paths, build):
    """Replace only the named resources, restoring previous files on failure."""
    destination = validate_pack_root(destination)
    paths = [Path(path) for path in paths]
    if not paths or len(set(paths)) != len(paths):
        raise ValueError('Choose distinct resource paths.')
    for path in paths:
        if path.is_absolute() or any(part in ('.', '..') for part in path.parts):
            raise ValueError('Resources must stay inside the selected pack.')
        target = destination / path
        if not target.resolve().is_relative_to(destination):
            raise ValueError('Resource path points outside the selected pack.')
        if target.exists() and not target.is_file():
            raise ValueError(f'Resource destination is not a file: {path}')
    stage = Path(tempfile.mkdtemp(prefix='.objmc-resources-', dir=destination))
    changed, created_dirs = [], []
    keep_backups = False
    try:
        build(stage)
        backup = stage / '.backups'
        backup.mkdir()
        for index, path in enumerate(paths):
            if not (stage / path).is_file():
                raise ValueError(f'Export did not produce {path}.')
            target = destination / path
            if target.exists():
                shutil.copy2(target, backup / str(index))
        try:
            for index, path in enumerate(paths):
                target = destination / path
                missing = []
                parent = target.parent
                while parent != destination and not parent.exists():
                    missing.append(parent)
                    parent = parent.parent
                for parent in reversed(missing):
                    parent.mkdir()
                    created_dirs.append(parent)
                os.replace(stage / path, target)
                changed.append((index, target))
        except Exception:
            try:
                for index, target in reversed(changed):
                    previous = backup / str(index)
                    if previous.exists():
                        os.replace(previous, target)
                    else:
                        target.unlink()
            except Exception as error:
                keep_backups = True
                raise RuntimeError(f'Could not restore resources; previous files are preserved in {backup}') from error
            raise
    finally:
        for parent in reversed(created_dirs):
            try:
                parent.rmdir()
            except OSError:
                pass
        if not keep_backups:
            shutil.rmtree(stage)
    return destination


def adapt_model_26_3(model):
    """26.3 removed element shade; preserve unshaded behavior with its replacement."""
    for element in model.get('elements', []):
        if element.pop('shade', None) is False:
            element['shade_direction_override'] = 'up'
    return model


def install_item_shaders_26_3(destination):
    """Install the pinned obj-cubed shader files; retain unrelated pack assets."""
    destination = validate_pack_root(destination)
    source = Path(__file__).parent / 'objcubed_26_3'
    files = sorted(p for p in source.rglob('*') if p.is_file())
    relative = [p.relative_to(source) for p in files]
    metadata = json.loads((destination / 'pack.mcmeta').read_text(encoding='utf-8-sig'))
    metadata['pack'].pop('pack_format', None)
    metadata['pack']['min_format'] = [97, 1]
    metadata['pack']['max_format'] = [97, 1]
    def build(stage):
        for src, target in zip(files, relative):
            (stage / target).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, stage / target)
        shutil.copy2(Path(__file__).parent / 'LICENSE-objcubed.txt', stage / 'LICENSE-objcubed.txt')
        write_json(stage / 'pack.mcmeta', metadata)
    return publish_resources(destination, relative + [Path('pack.mcmeta'), Path('LICENSE-objcubed.txt')], build)
