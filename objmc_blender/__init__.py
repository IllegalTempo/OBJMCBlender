"""OBJMC Blender: selected meshes to Minecraft Java resource packs."""
import traceback

import bpy
from bpy.props import CollectionProperty, BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty, StringProperty

from . import exporter, preview
from .mesh import source_scene

bl_info = {
    'name': 'OBJMC Blender', 'author': 'OBJMCBLENDER contributors; objmc by Godlander',
    'version': (0, 4, 2), 'blender': (5, 1, 0),
    'location': '3D View > Sidebar > OBJMC', 'category': 'Import-Export',
    'description': 'Export Minecraft resource packs with first-person and armor stand head previews',
}


def _clip_action_changed(clip, context):
    if clip.action:
        import math
        clip.frame_start = math.floor(clip.action.frame_range[0])
        clip.frame_end = math.ceil(clip.action.frame_range[1])
        clip.slot_identifier = 'AUTO'


def _project_type_changed(settings, context):
    if settings.project_type == 'THIRD_PERSON':
        # Apply third-person defaults once; preserve saved or explicitly edited values.
        if not settings.is_property_set('head_translation'):
            settings.head_translation = (0, -42, 0)
        if not settings.is_property_set('head_scale'):
            settings.head_scale = (1.5, 1.5, 1.5)
    preview.update_preview(settings, context)


_clip_slot_cache = {}


def _clip_slots(clip, context):
    items = [('AUTO', 'Automatic', 'Use the matching object slot, or the only compatible slot')]
    if clip.action:
        items += [(slot.identifier, slot.name_display, slot.identifier)
                  for slot in clip.action.slots if slot.target_id_type == 'OBJECT']
    _clip_slot_cache[clip.as_pointer()] = items
    return items


class OBJMCClip(bpy.types.PropertyGroup):
    name: StringProperty(name='Clip Name', default='idle')
    enabled: BoolProperty(name='Enabled', default=True)
    target: PointerProperty(name='Animated Object / Rig', type=bpy.types.Object)
    action: PointerProperty(name='Action', type=bpy.types.Action, update=_clip_action_changed)
    slot_identifier: EnumProperty(name='Action Slot', items=_clip_slots)
    frame_start: IntProperty(name='Start', default=1)
    frame_end: IntProperty(name='End', default=20)
    frame_step: IntProperty(name='Step', default=1, min=1)
    auto_duration: BoolProperty(name='Duration from Scene FPS', default=True)
    duration: IntProperty(name='Duration (Ticks)', default=20, min=1, max=65535)
    easing: EnumProperty(name='Interpolation', items=[('0','None',''),('1','Linear',''),('2','Cubic',''),('3','Bezier','')], default='1')
    autoplay: BoolProperty(name='Loop Animation', default=True)


class OBJMCSettings(bpy.types.PropertyGroup):
    project_type: EnumProperty(name='Project Type', items=[
        ('FIRST_PERSON', 'First Person', 'Held-item project with Minecraft hands'),
        ('THIRD_PERSON', 'Third Person', 'Armor stand head display and full Minecraft model')],
        default='FIRST_PERSON', update=_project_type_changed)
    hide_third_person: BoolProperty(name='Hide in Third Person', default=False,
        description='Hide third-person held and head views in Minecraft; keep inventory and ground display')
    head_rotation: FloatVectorProperty(name='Rotation (Degrees)', size=3, default=(0,0,0), min=-360, max=360, update=preview.update_preview)
    head_translation: FloatVectorProperty(name='Translation (Pixels)', size=3, default=(0,0,0), min=-80, max=80, update=preview.update_preview)
    head_scale: FloatVectorProperty(name='Scale', size=3, default=(1,1,1), min=0.001, max=4, update=preview.update_preview)
    output_directory: StringProperty(name='Resource Pack', subtype='DIR_PATH',
                                    description='Select an existing resource-pack root containing pack.mcmeta')
    minecraft_target: EnumProperty(name='Minecraft Target', items=[('26.3', 'obj-cubed / Java 26.3', 'Pinned obj-cubed 26.3v4 encoding and shaders'), ('1.21.11', 'Java 1.21.11 (Legacy)', 'Original objmc model format')], default='26.3', update=preview.update_preview)
    namespace: StringProperty(name='Namespace', default='objmc')
    item_path: StringProperty(name='Item Path', default='my_item')
    base_item: StringProperty(name='Base Item', default='stick', description='Vanilla item used by the generated give command')
    auto_textures: BoolProperty(name='Auto Combine Textures', default=True, description='Build a temporary atlas from selected materials and remap export UVs without editing meshes')
    texture: PointerProperty(name='Texture Atlas', type=bpy.types.Image, update=preview.update_preview)
    geometry_scale: FloatProperty(name='Blocks per Unit', default=1.0, min=0.0001, max=1000,
                                 description='One Blender unit equals this many Minecraft blocks; world origin is the model pivot', update=preview.update_preview)
    use_clips: BoolProperty(name='Export Action Clips', default=False)
    clips: CollectionProperty(type=OBJMCClip)
    active_clip: IntProperty(default=0, min=0)
    animation: BoolProperty(name='Export Animation', default=False)
    frame_start: IntProperty(name='Start', default=1, min=0)
    frame_end: IntProperty(name='End', default=20, min=0)
    frame_step: IntProperty(name='Step', default=1, min=1)
    auto_duration: BoolProperty(name='Duration from Scene FPS', default=True)
    duration: IntProperty(name='Duration (Ticks)', default=20, min=1, max=65535)
    easing: EnumProperty(name='Interpolation', items=[('0', 'None', ''), ('1', 'Linear', ''), ('2', 'Cubic', ''), ('3', 'Bezier', '')], default='1')
    autoplay: BoolProperty(name='Loop Animation', default=True)
    flipuv: BoolProperty(name='Flip UV', default=False)
    noshadow: BoolProperty(name='Disable Face Shading', default=False)
    hand: EnumProperty(name='Preview Hand', items=[('RIGHT', 'Right', ''), ('LEFT', 'Left', '')], update=preview.update_preview)
    fov: FloatProperty(name='Vertical FOV', default=70, min=30, max=110, update=preview.update_preview)
    right_rotation: FloatVectorProperty(name='Rotation (Degrees)', size=3, default=(0, 0, 0), min=-360, max=360, update=preview.update_preview)
    left_rotation: FloatVectorProperty(name='Rotation (Degrees)', size=3, default=(0, 0, 0), min=-360, max=360, update=preview.update_preview)
    right_translation: FloatVectorProperty(name='Translation (Pixels)', size=3, default=(0, 0, 0), min=-80, max=80, update=preview.update_preview)
    left_translation: FloatVectorProperty(name='Translation (Pixels)', size=3, default=(0, 0, 0), min=-80, max=80, update=preview.update_preview)
    right_scale: FloatVectorProperty(name='Scale', size=3, default=(1, 1, 1), min=0, max=4, update=preview.update_preview)
    left_scale: FloatVectorProperty(name='Scale', size=3, default=(1, 1, 1), min=0, max=4, update=preview.update_preview)
    last_status: StringProperty(default='Select your UV-mapped meshes to begin.')


class OBJMC_OT_new_project(bpy.types.Operator):
    bl_idname = 'objmc.new_project'
    bl_label = 'New OBJMC Project'
    bl_description = 'Create an empty OBJMC project scene, preserving existing scenes and unsaved work'
    bl_options = {'REGISTER', 'UNDO'}

    project_type: EnumProperty(items=[('FIRST_PERSON', 'First Person', ''), ('THIRD_PERSON', 'Third Person', '')])

    def execute(self, context):
        if context.scene.objmc_source:
            preview.close_preview(context)
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        name = 'First Person OBJMC Project' if self.project_type == 'FIRST_PERSON' else 'Third Person OBJMC Project'
        scene = bpy.data.scenes.new(name)
        scene.objmc.project_type = self.project_type
        context.window.scene = scene
        return {'FINISHED'}


def _new_project_menu(self, context):
    self.layout.separator()
    for kind, label in [('FIRST_PERSON', 'First Person OBJMC Project'), ('THIRD_PERSON', 'Third Person OBJMC Project')]:
        self.layout.operator('objmc.new_project', text=label).project_type = kind


class OBJMC_OT_export(bpy.types.Operator):
    bl_idname = 'objmc.export_resources'
    bl_label = 'Export Resources'
    bl_description = 'Write model JSON and encoded PNG into the selected resource pack; replace only matching resource files'

    def execute(self, context):
        settings = source_scene(context).objmc
        try:
            path = exporter.export_clips(context) if settings.use_clips else exporter.export_resources(context)
            settings.last_status = 'Exported: ' + str(path)
            self.report({'INFO'}, settings.last_status)
            return {'FINISHED'}
        except Exception as error:
            traceback.print_exc()
            settings.last_status = str(error)
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class OBJMC_UL_clips(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, 'enabled', text='')
        layout.prop(item, 'name', text='', emboss=False)
        layout.label(text=item.action.name if item.action else 'Choose Action')


class OBJMC_OT_add_clip(bpy.types.Operator):
    bl_idname = 'objmc.add_clip'
    bl_label = 'Add Action Clip'
    bl_options = {'UNDO'}

    def execute(self, context):
        from .mesh import source_layer
        source = source_scene(context)
        settings = source.objmc
        clip = settings.clips.add()
        used = {c.name for c in settings.clips if c != clip}
        index = 1
        while 'clip_'+str(index) in used:
            index += 1
        clip.name = 'clip_'+str(index)
        clip.target = source_layer(context, source).objects.active
        if clip.target and clip.target.animation_data:
            clip.action = clip.target.animation_data.action
        settings.active_clip = len(settings.clips)-1
        settings.use_clips = True
        return {'FINISHED'}


class OBJMC_OT_remove_clip(bpy.types.Operator):
    bl_idname = 'objmc.remove_clip'
    bl_label = 'Remove Action Clip'
    bl_options = {'UNDO'}

    def execute(self, context):
        settings = source_scene(context).objmc
        if 0 <= settings.active_clip < len(settings.clips):
            settings.clips.remove(settings.active_clip)
            settings.active_clip = max(0,min(settings.active_clip,len(settings.clips)-1))
        return {'FINISHED'}


class OBJMC_OT_export_clip(bpy.types.Operator):
    bl_idname = 'objmc.export_clip'
    bl_label = 'Export Active Clip'

    def execute(self, context):
        try:
            exporter.export_clips(context, active_only=True)
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Active clip exported')
        return {'FINISHED'}


class OBJMC_OT_install_shaders(bpy.types.Operator):
    bl_idname = 'objmc.install_item_shaders'
    bl_label = 'Install obj-cubed 26.3 Shaders'
    bl_description = 'Install obj-cubed 26.3v4 shader files; set pack metadata to 97.1. Other assets are preserved'

    def execute(self, context):
        from .core import install_item_shaders_26_3
        settings = source_scene(context).objmc
        try:
            if not settings.output_directory.strip():
                raise ValueError('Choose your resource-pack folder first.')
            install_item_shaders_26_3(bpy.path.abspath(settings.output_directory))
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Installed obj-cubed 26.3v4 shaders and updated pack.mcmeta. Test rendering in-game.')
        return {'FINISHED'}


class OBJMC_OT_import_hands(bpy.types.Operator):
    bl_idname = 'objmc.import_hands'
    bl_label = 'Import Minecraft Hands'
    bl_description = 'Choose a 64x64 skin PNG and import two arms with a shared animation rig at the 3D cursor'
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default='*.png', options={'HIDDEN'})
    arm_width: EnumProperty(name='Arm Width', items=[('WIDE', 'Wide (Steve)', '4-pixel arms'), ('NARROW', 'Narrow (Alex)', '3-pixel arms')], default='WIDE')
    sleeves: BoolProperty(name='Include Sleeve Layer', default=True)

    def draw(self, context):
        self.layout.prop(self, 'arm_width')
        self.layout.prop(self, 'sleeves')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and not context.scene.objmc_source

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from .hands import import_hands
        from pathlib import Path
        image = None
        try:
            path = Path(bpy.path.abspath(self.filepath))
            if path.suffix.lower() != '.png' or not path.is_file():
                raise ValueError('Choose an existing skin PNG file.')
            image = bpy.data.images.load(str(path), check_existing=False)
            if tuple(image.size) != (64, 64):
                raise ValueError('Choose a standard 64 x 64 Minecraft skin PNG.')
            image.pack()
            if isinstance(self, OBJMC_OT_import_model):
                from .player import import_player
                import_player(context, image, self.arm_width == 'NARROW', self.outer_layers)
            else:
                import_hands(context, image, self.arm_width == 'NARROW', self.sleeves)
        except Exception as error:
            if image and image.users == 0:
                bpy.data.images.remove(image)
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        message = ('Imported full Minecraft model and Minecraft Player Rig.' if isinstance(self, OBJMC_OT_import_model)
                   else 'Imported both arms and Minecraft Hands Rig.')
        self.report({'INFO'}, message+' Select the rig and enter Pose Mode to animate.')
        return {'FINISHED'}


class OBJMC_OT_import_model(bpy.types.Operator):
    bl_idname = 'objmc.import_model'
    bl_label = 'Import Minecraft Model'
    bl_description = 'Choose a 64x64 skin PNG and import a full rigged Steve or Alex model at the 3D cursor'
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default='*.png', options={'HIDDEN'})
    arm_width: EnumProperty(name='Arm Width', items=[('WIDE', 'Wide (Steve)', '4-pixel arms'), ('NARROW', 'Narrow (Alex)', '3-pixel arms')], default='WIDE')
    outer_layers: BoolProperty(name='Include Outer Clothing Layer', default=True)

    def draw(self, context):
        self.layout.prop(self, 'arm_width')
        self.layout.prop(self, 'outer_layers')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and not context.scene.objmc_source

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        return OBJMC_OT_import_hands.execute(self, context)


class OBJMC_OT_preview(bpy.types.Operator):
    bl_idname = 'objmc.preview'
    bl_label = 'Open / Refresh First-Person Preview'
    bl_description = 'Preview source meshes in first person or equipped on an armor stand head, according to Project Type'

    def execute(self, context):
        try:
            preview.create_preview(context)
            return {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class OBJMC_OT_close_preview(bpy.types.Operator):
    bl_idname = 'objmc.close_preview'
    bl_label = 'Back to Model'

    def execute(self, context):
        preview.close_preview(context)
        return {'FINISHED'}


class OBJMC_OT_copy_command(bpy.types.Operator):
    bl_idname = 'objmc.copy_command'
    bl_label = 'Copy Give Command'

    def execute(self, context):
        from .core import give_command
        settings = source_scene(context).objmc
        try:
            context.window_manager.clipboard = give_command(settings.namespace, settings.item_path + ('/'+settings.clips[settings.active_clip].name if settings.use_clips and 0 <= settings.active_clip < len(settings.clips) else ''), settings.base_item)
        except ValueError as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Give command copied')
        return {'FINISHED'}


class OBJMC_PT_main(bpy.types.Panel):
    bl_label = 'OBJMC · Resource Pack'
    bl_idname = 'OBJMC_PT_main'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'OBJMC'

    def draw(self, context):
        layout = self.layout
        settings = source_scene(context).objmc
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.label(text='Selected meshes → Minecraft Java', icon='EXPORT')
        layout.prop(settings, 'project_type')
        if settings.project_type == 'FIRST_PERSON':
            layout.prop(settings, 'hide_third_person')
        else:
            layout.label(text='First-person rendering is hidden.', icon='HIDE_ON')
        layout.prop(settings, 'auto_textures')
        if not settings.auto_textures:
            layout.prop(settings, 'texture')
        for prop in ('geometry_scale', 'namespace', 'item_path', 'base_item'):
            layout.prop(settings, prop)
        layout.separator()
        layout.prop(settings, 'minecraft_target')
        layout.prop(settings, 'output_directory')
        if settings.minecraft_target == '26.3':
            layout.operator('objmc.install_item_shaders', icon='SHADING_RENDERED')
            layout.label(text='Updates shaders and pack.mcmeta (97.1).', icon='INFO')
        layout.label(text='Writes model JSON + encoded PNG.', icon='INFO')
        if settings.minecraft_target == '26.3':
            layout.label(text='Includes hand variants and item definition.')
        row = layout.row()
        row.scale_y = 1.5
        row.operator('objmc.export_resources', icon='EXPORT')
        layout.operator('objmc.copy_command', icon='COPYDOWN')
        box = layout.box()
        box.label(text=settings.last_status[:100], icon='INFO')


class OBJMC_PT_animation(bpy.types.Panel):
    bl_label = 'Animation & Encoding'
    bl_idname = 'OBJMC_PT_animation'
    bl_parent_id = 'OBJMC_PT_main'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'OBJMC'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = source_scene(context).objmc
        layout.prop(settings, 'use_clips')
        if settings.use_clips:
            row = layout.row()
            row.template_list('OBJMC_UL_clips', '', settings, 'clips', settings, 'active_clip', rows=3)
            buttons = row.column(align=True)
            buttons.operator('objmc.add_clip', text='', icon='ADD')
            buttons.operator('objmc.remove_clip', text='', icon='REMOVE')
            if 0 <= settings.active_clip < len(settings.clips):
                clip = settings.clips[settings.active_clip]
                layout.prop(clip, 'target')
                layout.prop(clip, 'action')
                if clip.action and len(clip.action.slots) > 1:
                    layout.prop(clip, 'slot_identifier')
                row = layout.row(align=True)
                for field in ('frame_start', 'frame_end', 'frame_step'):
                    row.prop(clip, field)
                layout.prop(clip, 'auto_duration')
                if not clip.auto_duration:
                    layout.prop(clip, 'duration')
                layout.prop(clip, 'easing')
                layout.prop(clip, 'autoplay')
                layout.operator('objmc.export_clip', icon='EXPORT')
                layout.label(text='Copy Give Command uses the active clip.')
            layout.label(text='Export Resources exports all enabled clips.')
            return
        layout.prop(settings, 'animation')
        if settings.animation:
            row = layout.row(align=True)
            for prop in ('frame_start', 'frame_end', 'frame_step'):
                row.prop(settings, prop)
            layout.prop(settings, 'auto_duration')
            if not settings.auto_duration:
                layout.prop(settings, 'duration')
            layout.prop(settings, 'easing')
            layout.prop(settings, 'autoplay')
            layout.label(text='Stable topology required at every frame.', icon='INFO')
        layout.prop(settings, 'flipuv')
        layout.prop(settings, 'noshadow')


class OBJMC_PT_preview(bpy.types.Panel):
    bl_label = 'First-Person Holding Screen'
    bl_idname = 'OBJMC_PT_preview'
    bl_parent_id = 'OBJMC_PT_main'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'OBJMC'

    @classmethod
    def poll(cls, context):
        return source_scene(context).objmc.project_type == 'FIRST_PERSON'

    def draw(self, context):
        layout = self.layout
        settings = source_scene(context).objmc
        layout.operator('objmc.import_hands', icon='IMPORT')
        layout.operator('objmc.preview', icon='VIEW_CAMERA')
        if context.scene.objmc_source:
            layout.operator('objmc.close_preview', icon='LOOP_BACK')
        layout.prop(settings, 'hand', expand=True)
        layout.prop(settings, 'fov')
        hand = 'left' if settings.hand == 'LEFT' else 'right'
        for prop in ('rotation', 'translation', 'scale'):
            layout.prop(settings, hand+'_'+prop)
        layout.label(text='Approximate idle pose; verify in Minecraft.', icon='INFO')
        layout.label(text='Refresh after changing mesh or texture.')


class OBJMC_PT_third_person(bpy.types.Panel):
    bl_label = 'Third-person Armor Stand Display'
    bl_idname = 'OBJMC_PT_third_person'
    bl_parent_id = 'OBJMC_PT_main'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'OBJMC'

    @classmethod
    def poll(cls, context):
        return source_scene(context).objmc.project_type == 'THIRD_PERSON'

    def draw(self, context):
        layout = self.layout
        settings = source_scene(context).objmc
        layout.operator('objmc.import_model', icon='IMPORT')
        layout.operator('objmc.preview', text='Open / Refresh Armor Stand Preview', icon='VIEW_CAMERA')
        if context.scene.objmc_source:
            layout.operator('objmc.close_preview', icon='LOOP_BACK')
        layout.prop(settings, 'fov')
        layout.label(text='Equipped on the armor stand head:')
        for prop in ('rotation', 'translation', 'scale'):
            layout.prop(settings, 'head_'+prop)
        layout.label(text='Reference stand is never exported.', icon='INFO')
        layout.label(text='Approximate display; verify in Minecraft.')
        layout.label(text='Refresh after changing mesh or texture.')


CLASSES = (OBJMCClip, OBJMCSettings, OBJMC_OT_new_project, OBJMC_UL_clips, OBJMC_OT_add_clip, OBJMC_OT_remove_clip, OBJMC_OT_export_clip, OBJMC_OT_install_shaders, OBJMC_OT_import_hands, OBJMC_OT_import_model, OBJMC_OT_export, OBJMC_OT_preview, OBJMC_OT_close_preview,
           OBJMC_OT_copy_command, OBJMC_PT_main, OBJMC_PT_animation, OBJMC_PT_preview, OBJMC_PT_third_person)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.objmc = PointerProperty(type=OBJMCSettings)
    bpy.types.Scene.objmc_source = PointerProperty(type=bpy.types.Scene)
    bpy.types.TOPBAR_MT_file_new.append(_new_project_menu)


def unregister():
    bpy.types.TOPBAR_MT_file_new.remove(_new_project_menu)
    # Exit preview scenes before removing the source-scene pointer property.
    for scene in list(bpy.data.scenes):
        if scene.objmc_source:
            preview.return_windows_to_source(bpy.context, scene)
            preview._destroy(scene)
    del bpy.types.Scene.objmc_source
    del bpy.types.Scene.objmc
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
