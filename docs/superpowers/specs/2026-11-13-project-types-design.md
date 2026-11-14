# OBJMC project types

User authorized implementation with the recommended full Steve/Alex skin importer.
First Person keeps existing settings, imported hands, clip workflows and preview.
Third Person replaces the hands UI with Import Minecraft Model (64x64 skin, wide
or narrow arms, optional outer clothing, shared root/body/head/limb rig).

File > New gains First Person OBJMC Project and Third Person OBJMC Project.
Implementation choice: each creates a fresh empty source scene in the current
blend, preserving existing scenes and unsaved work. Scene settings hold the
project type; existing scenes default to First Person. The sidebar also exposes
the type for existing models.

Third-person preview uses an isolated scene with a normal-size neutral armor
stand, a perspective camera and evaluated source meshes attached to its head.
Head rotation/translation/scale are exported in the head display slot and applied
to the preview. Source geometry is never changed. Closing or refreshing restores
the original viewport including its rotation, position and zoom.

First Person has optional Hide in Third Person (default off), affecting both
third-person hands and head contexts. Third Person always hides first-person
hands, retaining world/head and inventory/ground display. Both resource export
and active/all clip export use the same context routing. Use minecraft:empty,
not zero scale, which would degenerate the shader carrier. Legacy now also writes
an item definition so visibility routing works there, with zero tint retained.

Keep bundled shaders unchanged. Add a head carrier context for exact depth scale
in obj-cubed. Armor stand preview is approximate and must be verified in game.
Release 0.4.0 includes the prior viewport restoration fix.

Approach: shared per-scene mode and existing export/preview lifecycle, rather than
duplicated add-ons or global settings. This preserves old blend compatibility.
