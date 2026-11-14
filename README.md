# OBJMC Blender

Blender **5.1+** extension for exporting selected meshes and constant-topology
animation to Minecraft Java resource packs using [obj-cubed](https://github.com/JagerMeistars/obj-cubed) for Java 26.3
and original [objmc](https://github.com/Godlander/objmc) for legacy Java 1.21.11.
Includes first-person held-item and third-person armor stand head previews.

## Install

1. In Blender, open **Edit → Preferences → Get Extensions**.
2. Open the menu at the upper right and choose **Install from Disk**.
3. Choose `objmc_blender-0.4.2.zip`, then enable **OBJMC Blender** if necessary.
4. In the 3D View, press **N** and open the **OBJMC** tab.

No separate Python, Pillow, network access, or objmc installation is needed.

## Project types (0.4.0)

Open **File > New > First Person OBJMC Project** or
**File > New > Third Person OBJMC Project**. Each creates an empty project scene
in the current blend file, preserving your existing scenes and unsaved work.
Use Blender's scene selector to return to another project. Existing files default
to First Person; change **OBJMC > Project Type** to use an existing scene in either mode.

- **First Person** keeps the hands importer and holding screen. Enable
  **Hide in Third Person** to hide both third-person hand contexts and the head
  context in Minecraft.
- **Third Person** replaces the hands panel with **Third-person Armor Stand Display**.
  **Import Minecraft Model** loads a standard 64x64 skin PNG as a full Steve/Alex
  player with six editable parts, a shared **Minecraft Player Rig**, and optional
  outer clothing. One pixel is 1/16 Blender unit; feet start at the 3D cursor.
  Choose Wide (Steve) or Narrow (Alex) in the file picker.
  Select the imported meshes before exporting; import preserves your prior
  selection. Pose the shared rig and use its Actions for clip exports.
- **Open / Refresh Armor Stand Preview** shows all source-view-layer meshes
  equipped on the head of a neutral, normal-size armor stand. Change the head
  Rotation, Translation (model pixels) and Scale; the same values are exported.
  New Third Person projects default to rotation **(0, 0, 0)**, translation
  **(0, -42, 0)** and scale **(1.5, 1.5, 1.5)**. Existing custom head settings
  are preserved when switching project type.
  The stand is an isolated preview reference and is never exported. The preview
  is approximate; verify placement in Minecraft.
- Third Person always hides both first-person hand contexts. Inventory, dropped
  items, frames and third-person/head views remain visible. This is a resource
  pack setting, so no Minecraft options-menu change is required.

Visibility applies to **Export Resources**, all enabled Action Clips and
**Export Active Clip**, for both targets. It uses empty item-model branches,
preserving the encoded carrier geometry. Both targets now write their namespaced
item definition; re-export replaces that definition for this item path.

**Back to Model** restores the original viewport rotation, position, zoom,
perspective, camera framing, shading and overlays, including after a refresh.

## Export Resources (Minecraft Java 26.3)

### Linked models (0.4.1)

**0.4.2 fixes a crash in 0.4.1 when exporting linked collection instances.**
The mesh snapshot now retains stable original object IDs and copies instance
transforms, then obtains evaluated geometry safely. It no longer retains Blender's
temporary instance objects after dependency-graph iteration. The reported crash
was reproduced from a saved linked-model scene in an isolated Blender 5.3 process.
Integration coverage runs on Blender 5.1.2 and 5.3.0, including instance transforms,
materials, animation, selection and viewport restoration.

Selected linked collection instances are now exported along with selected meshes.
Select the collection instance object in the scene together with any local meshes
you want included, then use Export Resources or Export Active Clip. You can leave
**Instance Collections** enabled when using File > Link; making instances real or
appending a duplicate is unnecessary. Directly linked mesh objects also work when
selected. Selecting only an armature does not select its meshes automatically.

Nested instances retain their evaluated placement, collection offsets, scaling,
materials and animation. Unselected instances are excluded from export. Previews
include linked collection instances alongside the source view layer's meshes.
Source linked data remains unchanged. To edit or replace a linked rig's Action,
create a Blender library override so the rig can be edited in the current scene;
the collection-instance object's own transform animation can be used directly.

The default backend is **obj-cubed 26.3v4**, pinned to commit
`1755b00bb5754fb30aed13abd51fa44c63cdf562`. Original objmc remains available as
**Java 1.21.11 (Legacy)** in **Minecraft Target**.

1. UV-map each selected mesh. **Auto Combine Textures** is enabled by default:
   images connected to material Base Color are packed into a temporary atlas,
   and export UVs are remapped without changing source meshes or materials.
   Supports multiple materials per object and separate textures per object.
   UVs must be within 0-1. Procedural, mixed, or mapped shaders need baking first.
2. Place the model around the world origin, its pivot. **Blocks per Unit** sets
   size. Evaluated geometry is triangulated without modifying the source mesh.
3. Choose Namespace and Item Path (disable Auto Combine Textures to use a
   manually prepared Texture Atlas), for example `my_pack` and
   `weapons/sword`. Select an existing resource-pack folder with `pack.mcmeta`.
4. For 26.3, click **Install obj-cubed 26.3 Shaders** once. This installs the
   pinned shader files and license and sets `pack.mcmeta` to resource version
   **97.1**, preserving its description and other fields. Matching shader files
   are replaced; other pack assets remain intact. Use a dedicated model pack
   when other packs also customize core shaders.
5. Click **Export Resources**. This writes the encoded PNG and model JSON,
   first-person right/left and ground/shelf model variants, and the namespaced
   item definition. Reload resources in Minecraft and use **Copy Give Command**.

26.3 output paths:

- `assets/<namespace>/textures/item/<item path>.png`
- `assets/<namespace>/models/item/<item path>.json`
- `assets/<namespace>/models/item/<item path>__objcubed_right.json`
- `assets/<namespace>/models/item/<item path>__objcubed_left.json`
- `assets/<namespace>/models/item/<item path>__objcubed_ground.json`
- `assets/<namespace>/models/item/<item path>__objcubed_head.json`
- `assets/<namespace>/items/<item path>.json`

The extra model variants carry explicit display contexts: 26.3 uses the same
projection for first-person and world rendering, so shaders cannot infer hands
reliably from projection alone. Item definitions use white constant tint for
obj-cubed; old objmc zero-tint definitions must not be reused.

Re-export replaces these named resources transactionally. Export itself does
not change shaders or metadata; the separate shader installer does. Conversion
failure preserves the previous resources. Legacy mode writes the original model
JSON, PNG and a context-selecting item definition, and requires compatible
1.21.11 shaders.

Implemented here: a single static atlas, flat directional shading (or Disable
Face Shading), stable-topology vertex animation, and hand display transforms.
obj-cubed's Blockbench-only controls for equipment export, runtime player skins,
animated textures and generated datapacks are not exposed by this Blender add-on.
Imported skin hands and full player models remain ordinary editable Blender meshes.

**Validation:** checked export and shader installation in Blender 5.1.2.
**In-game rendering of Blender-generated obj-cubed resources remains unverified.**
The obj-cubed project reports its own 26.3v4 checks; these do not substitute for
an in-game test of this integration.

## First-person holding screen

Version 0.3.1 separates obj-cubed and legacy preview transforms. The 26.3 preview
omits the old objmc X/Z flip and fixed 45-degree turn. It represents a stationary,
fully equipped item. Match FOV and hand settings when comparing screenshots;
Minecraft lighting, movement and shader effects can still differ.


The first-person preview displays all meshes in the active source view layer,
regardless of selection. Imported hands and sleeves are included with their skin
materials. No plain block hand is generated. Click
**Open / Refresh First-Person Preview** after changing your objects. Source
selection is preserved; Export Resources still exports selected meshes only.

The preview preserves your overlay visibility when entering preview, so direct
scene switching does not hide edit-mode vertices.

Click **Open / Refresh First-Person Preview**. A separate
scene shows only the item and ground reference through a perspective camera.
Use **Right / Left** to edit that hand's rotation (degrees), translation (Minecraft
model pixels, 16 per block), and scale. Both hands' settings are exported as
`firstperson_righthand` and `firstperson_lefthand` display transforms. Minecraft
mirrors X translation and Y/Z rotation for the left hand.

FOV is a preview control; it is not exported. Click
**Back to Model** to close the preview and restore the previous viewport settings.
Refresh after changing the source mesh, current animation frame or atlas image.
Back to Model also restores the viewport's original viewing angle, position and zoom.
Original meshes are not moved or edited. Export while in preview still uses the
selected meshes from the source scene and view layer.

This is an **approximate static idle-pose preview**, not Minecraft's renderer.
Verify placement in the game. It does not simulate view bobbing, swinging,
equip/use animations, player skins or objmc's shader interpolation. The 26.3 backend uses explicit hand display-context models and the upstream
obj-cubed shaders. The legacy shader has a separate display-transform adjustment.

## Animation

Enable **Export Animation**, set the inclusive frame range and step, then choose
interpolation. Every sampled frame must have the same vertex count, face indices
and face order. Armatures and shape keys work when topology stays constant;
Build/remesh/animated topology modifiers usually do not.

**Duration from Scene FPS** converts the frame span to Minecraft's 20 ticks per
second; disable it to enter a duration manually. **Loop Animation** enables shader
autoplay. Turning it off holds the first frame. Animated textures and texture
baking are not implemented in this version. Scene frame and selection are
preserved after success and failure. Maximum sampled frame count is 4096.

## Compatibility and validation

- Tested registration/unregistration, export and preview in **Blender 5.1.2**.
- Tests cover transactional output, path validation, exact PNG metadata bytes,
  animated export, topology rejection, missing UVs, active view layers, preservation
  of source/foreign objects, and preview viewport restoration.
- Older preview/demo assets in `dist/` predate the 26.3 backend.
- **Minecraft rendering has not been tested in-game.** Shader mod compatibility
  and other Minecraft releases are not guaranteed. Bundled upstream shaders use
  GLSL 4.50 and subgroup operations; actual GPU/driver support must be checked.
- Geometry must fit within `[-128, 128)` blocks per coordinate after export scale.
- Auto Combine Textures packs Base Color image textures; procedural nodes are not baked.
- Large models/animations can create tall encoded textures and slow export.
  Keep face counts low. Encoded PNGs contain geometry: do not resize, optimize,
  repaint or run them through color management.

## Development

Production files live in `objmc_blender/`; `vendor/objmc_upstream.py` retains the
upstream source snapshot. `tools/adapt_encoder.py` regenerates the encoder core,
keeping the upstream encoding algorithm but replacing Pillow, GUI and CLI setup.
Read `objmc_blender/UPSTREAM.md` before refreshing the upstream snapshot.

Compile 26.3 item shader variants against the installed client using
`python tools/verify_26_3_shaders.py` (development check, requires local 26.3 files).

Run pure Python tests with `python -m unittest discover -s tests -v`.
Run Blender integration tests with:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' --background --factory-startup --python-exit-code 1 --python tests/blender_integration.py
```

Use `python tools/build_extension.py` to create the installable ZIP, and run
`tools/render_demo.py` with Blender to regenerate the sample pack and preview.

The extension is GPL-3.0-or-later. objmc's encoder and shaders are MIT-licensed;
their original notice is retained in `LICENSE-objmc.txt`.

## Import Minecraft Hands

In Object Mode, open **OBJMC > First-Person Holding Screen > Import Minecraft Hands**.
Choose a standard **64 x 64 PNG skin**. In the file picker options, choose
**Arm Width: Wide (Steve)** for 4-pixel arms or **Narrow (Alex)** for 3-pixel arms.
**Include Sleeve Layer** imports the outer clothing layer as well.

Both editable arms appear at the 3D cursor in a new **Minecraft Hands** collection,
with shoulder pivots. Each arm is one object containing its skin and sleeve
shells, with separate opaque base and transparent sleeve material slots. One skin pixel equals
1/16 Blender unit. Use Material Preview to see the skin. The skin is packed into
the blend file when saved. Existing selection and viewport settings are preserved.
The arms are bound to a shared Minecraft Hands Rig in your model scene; imported arms and sleeves are included in the first-person
preview with their skin texture. Legacy 64x32 skins are not supported.

## Export separate items from Blender Actions

1. Select all meshes to include in each item. Open **Animation & Encoding** and
   enable **Export Action Clips**.
2. Click **+** to add a clip. Enter a unique lowercase resource name, such as
   `idle` or `attack`.
3. Set **Animated Object / Rig** to the object whose Action should change
   (normally the armature controlling your meshes). Choose its **Action**.
   The frame range starts from the Action range; you can trim it or change Step.
   For multi-slot Actions, choose the matching **Action Slot** if automatic
   matching is ambiguous.
4. Set duration, interpolation and looping independently for each clip.
5. **Export Resources** exports every checked clip. **Export Active Clip** exports
   only the highlighted clip, even when its Enabled box is off.
6. **Copy Give Command** uses the highlighted clip while Action Clips is enabled.

For an Item Path of `weapons/sword`, the clips become
`<namespace>:weapons/sword/idle` and `<namespace>:weapons/sword/attack`.
Each gets its own encoded PNG, model variants and (26.3) item definition.
Enable both clips to export both; no datapack or automatic in-game clip switching
is generated. With legacy export, create the corresponding item definitions yourself.

Each clip switches one object's Action; one armature can drive multiple selected
meshes. Other objects retain their current animation. NLA blending on the target
is temporarily disabled, and its previous Action, slot, NLA setting, blend mode,
frame and export settings are restored after success or failure. All requested
clips are built before any resources are published into your pack. Renamed or
disabled clips' previously exported assets are retained.

## Animate imported hands

Import Minecraft Hands now creates **Minecraft Hands Rig** alongside the two
arm meshes. Each arm contains its base and optional sleeve geometry, rigidly
weighted to `arm.R` or `arm.L`; both bones are parented to a non-deforming `root`.
The shoulder pivots match the imported geometry, for both Wide and Narrow skins.
No elbow bending is introduced. Existing selection and Object Mode are restored.

Select **Minecraft Hands Rig**, enter **Pose Mode**, pose the arm bones and insert
keyframes. Create separate Actions in the Action Editor. In **Export Action Clips**,
choose this rig as **Animated Object / Rig**, choose the Action, and select the
arm meshes (plus any other meshes you want included) for export. The Armature
modifier is evaluated automatically, preserving stable animation topology.

Re-import hands to get the new rig; previously imported meshes are not changed.
#   O B J M C B l e n d e r  
 