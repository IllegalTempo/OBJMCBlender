"""Export model JSON and encoded PNG into a selected existing resource pack."""
from contextlib import redirect_stdout, contextmanager
import io
import json
from pathlib import Path
import tempfile
import shutil

import bpy

from . import core, encoder, cubed_encoder, atlas
from .mesh import image_pixels, selected_meshes, snapshot, source_layer, source_scene, topology_signature, write_obj


def resource_paths(namespace, item_path, target):
    paths = [Path('assets') / namespace / folder / (item_path + suffix)
             for folder, suffix in [('models/item', '.json'), ('textures/item', '.png')]]
    if target == '26.3':
        paths += [Path('assets') / namespace / 'models/item' / (item_path+suffix+'.json')
                  for suffix in ('__objcubed_right', '__objcubed_left', '__objcubed_ground', '__objcubed_head')]
    paths.append(Path('assets') / namespace / 'items' / (item_path+'.json'))
    return paths


@contextmanager
def clip_action(scene, clip):
    target = clip.target
    if target is None or target.name not in scene.objects or clip.action is None:
        raise ValueError(f'{clip.name}: choose an animated object in the source scene and an Action.')
    slots = [slot for slot in clip.action.slots if slot.target_id_type == 'OBJECT']
    if clip.slot_identifier != 'AUTO':
        slots = [slot for slot in slots if slot.identifier == clip.slot_identifier]
    elif len(slots) > 1:
        slots = [slot for slot in slots if slot.name_display == target.name]
    if len(slots) != 1:
        raise ValueError(f'{clip.name}: choose an unambiguous Action Slot for {target.name}.')
    if target.animation_data and target.animation_data.use_tweak_mode:
        raise ValueError(f'{clip.name}: exit NLA Tweak Mode before exporting Actions.')
    existed = target.animation_data is not None
    animation = target.animation_data_create()
    previous = (animation.action, animation.action_slot, animation.use_nla,
                animation.action_blend_type, animation.action_influence)
    frame, subframe = scene.frame_current, scene.frame_subframe
    try:
        animation.action = clip.action
        animation.action_slot = slots[0]
        animation.use_nla = False
        animation.action_blend_type = 'REPLACE'
        animation.action_influence = 1.0
        scene.frame_set(frame, subframe=subframe)
        yield
    finally:
        if existed:
            animation.action = previous[0]
            if previous[1] is not None:
                animation.action_slot = previous[1]
            animation.use_nla = previous[2]
            animation.action_blend_type = previous[3]
            animation.action_influence = previous[4]
        else:
            target.animation_data_clear()
        scene.frame_set(frame, subframe=subframe)


def export_clips(context, active_only=False):
    """Build every requested clip before publishing any files to the actual pack."""
    settings = source_scene(context).objmc
    if active_only:
        if not 0 <= settings.active_clip < len(settings.clips):
            raise ValueError('Add and select an animation clip first.')
        clips = [settings.clips[settings.active_clip]]
    else:
        clips = [clip for clip in settings.clips if clip.enabled]
    if not clips:
        raise ValueError('Enable at least one animation clip.')
    if not settings.output_directory.strip():
        raise ValueError('Choose a resource-pack folder first.')
    destination = core.validate_pack_root(bpy.path.abspath(settings.output_directory))
    base = settings.item_path
    names, paths = set(), []
    for clip in clips:
        core.validate_resource(settings.namespace, clip.name)
        if clip.name in names or '__objcubed_' in clip.name:
            raise ValueError('Clip names must be unique and must not contain __objcubed_.')
        names.add(clip.name)
        if clip.frame_end < clip.frame_start:
            raise ValueError(f'{clip.name}: end frame must be at or after start frame.')
        if (clip.frame_end-clip.frame_start)//clip.frame_step+1 > 4096:
            raise ValueError(f'{clip.name}: limit the clip to 4096 sampled frames.')
        if clip.target is None or clip.action is None:
            raise ValueError(f'{clip.name}: choose an animated object / rig and Action.')
        paths += resource_paths(settings.namespace, base+'/'+clip.name, settings.minecraft_target)
    fields = ('item_path','output_directory','animation','frame_start','frame_end','frame_step',
              'auto_duration','duration','easing','autoplay')
    original = {field: getattr(settings, field) for field in fields}
    def build(stage):
        # Each clip uses the same validated writer against a private staging pack.
        shutil.copy2(destination / 'pack.mcmeta', stage / 'pack.mcmeta')
        settings.output_directory = str(stage)
        settings.animation = True
        for clip in clips:
            settings.item_path = base+'/'+clip.name
            for field in fields[3:]:
                setattr(settings, field, getattr(clip, field))
            with clip_action(source_scene(context), clip):
                export_resources(context)
    try:
        return core.publish_resources(destination, paths, build)
    finally:
        for field, value in original.items():
            setattr(settings, field, value)

def export_resources(context):
    scene = source_scene(context)
    settings = scene.objmc
    core.validate_resource(settings.namespace, settings.item_path)
    if not settings.output_directory.strip():
        raise ValueError('Choose a resource-pack folder containing pack.mcmeta.')
    destination = core.validate_pack_root(bpy.path.abspath(settings.output_directory))
    if settings.animation and settings.frame_end < settings.frame_start:
        raise ValueError('Animation end frame must be at or after start frame.')
    objects = selected_meshes(scene, source_layer(context, scene))
    texture = None if settings.auto_textures else image_pixels(settings.texture)
    original_frame, original_subframe = scene.frame_current, scene.frame_subframe
    frames = list(range(settings.frame_start, settings.frame_end+1, settings.frame_step)) if settings.animation else [original_frame]
    if len(frames) > 4096:
        raise ValueError('Limit the export to 4096 sampled frames or fewer.')
    log = io.StringIO()

    def build(stage):
        assets = stage / 'assets' / settings.namespace
        model_path = assets / 'models/item' / (settings.item_path + '.json')
        texture_path = assets / 'textures/item' / (settings.item_path + '.png')
        model_path.parent.mkdir(parents=True, exist_ok=True)
        texture_path.parent.mkdir(parents=True, exist_ok=True)
        # Private inputs live in the staging directory, never in global temp/cwd.
        with tempfile.TemporaryDirectory(prefix='inputs-', dir=stage) as tmp:
            paths, signature = [], None
            export_texture, remap = texture, None
            for index, frame in enumerate(frames):
                scene.frame_set(frame, subframe=0 if settings.animation else original_subframe)
                data = snapshot(context, scene, objects)
                current = topology_signature(data)
                if signature is not None and signature != current:
                    raise ValueError(f'Frame {frame}: topology changed. Use stable vertices and face order throughout the animation.')
                signature = current
                if settings.auto_textures:
                    if remap is None:
                        export_texture, remap = atlas.build_atlas(data)
                    remap(data)
                path = Path(tmp) / f'frame_{index:05}.obj'
                write_obj(path, data, settings.geometry_scale)
                paths.append(path)
            duration = settings.duration if settings.animation else 1
            if settings.animation and settings.auto_duration:
                fps = scene.render.fps / scene.render.fps_base
                duration = max(1, round((settings.frame_end-settings.frame_start+1) * 20 / fps))
            with redirect_stdout(log):
                if settings.minecraft_target == '26.3':
                    model, encoded = cubed_encoder.encode(
                        paths, export_texture, duration=duration, easing=int(settings.easing),
                        autoplay=settings.autoplay, flipuv=settings.flipuv, noshadow=settings.noshadow,
                        hand_scales=(settings.right_scale, settings.left_scale), head_scale=settings.head_scale)
                    encoded.save(texture_path)
                else:
                    encoder.convert(paths, export_texture, model_path, texture_path, duration=duration,
                                    easing=int(settings.easing), autoplay=settings.autoplay,
                                    flipuv=settings.flipuv, noshadow=settings.noshadow)
                    model = json.loads(model_path.read_text(encoding='utf-8'))
        resource = f'{settings.namespace}:item/{settings.item_path}'
        model['textures'] = {'0': resource, 'particle': resource}
        for hand in ('right', 'left'):
            model.setdefault('display', {})[f'firstperson_{hand}hand'] = {
                'rotation': list(getattr(settings, hand+'_rotation')),
                'translation': list(getattr(settings, hand+'_translation')),
                'scale': list(getattr(settings, hand+'_scale')),
            }
        if settings.minecraft_target == '26.3':
            core.adapt_model_26_3(model)
            identity = {'rotation': [0,0,0], 'translation': [0,0,0], 'scale': [1,1,1]}
            for slot in ('gui', 'ground', 'fixed', 'head', 'on_shelf', 'thirdperson_righthand', 'thirdperson_lefthand'):
                model['display'][slot] = dict(identity)
            model['display']['head'] = {key: list(getattr(settings, 'head_'+key))
                                       for key in ('rotation', 'translation', 'scale')}
            for suffix, marker, slots in [
                ('__objcubed_right', 1, ['firstperson_righthand']),
                ('__objcubed_left', 2, ['firstperson_lefthand']),
                ('__objcubed_ground', 3, ['ground', 'on_shelf']),
                ('__objcubed_head', 4, ['head']),
            ]:
                variant = cubed_encoder.slot_variant(model, marker, marker == 3)
                core.write_json(assets / 'models/item' / (settings.item_path+suffix+'.json'), variant)
        model.setdefault('display', {})['head'] = {key: list(getattr(settings, 'head_'+key))
                                                  for key in ('rotation', 'translation', 'scale')}
        definition = core.context_item_definition(settings.namespace, settings.item_path,
                    settings.minecraft_target, settings.project_type, settings.hide_third_person)
        core.write_json(assets / 'items' / (settings.item_path+'.json'), definition)
        core.write_json(model_path, model)
    try:
        paths = resource_paths(settings.namespace, settings.item_path, settings.minecraft_target)
        return core.publish_resources(destination, paths, build)
    finally:
        scene.frame_set(original_frame, subframe=original_subframe)
