# OBJMC Blender Implementation Plan

> Execute inline; user authorized proceeding with sensible defaults.

Goal: installable Blender 5.1 extension with objmc pack export and hand preview.
Architecture: pure-Python pack and image modules, upstream encoder core, Blender
mesh extraction and preview modules, sidebar UI. No runtime downloads.
Spec: ../specs/2026-11-12-objmc-blender-design.md

## Global constraints
- Blender >= 5.1; bundled Minecraft shader target 1.21.11, resource format 75.
- No dependency installation, scene destruction, or implicit pack overwrite.
- A single shared texture atlas and stable topology per animation.

## Review focus
- Malformed resource paths must not escape export root.
- Existing output remains intact if conversion fails.
- Animation failure restores source frame and frees temporary meshes.
- Encoded PNG preserves exact metadata bytes.
- Preview closure restores the source scene and leaves source objects intact.

## Tasks
- [x] Test pack path validation, metadata, item definition and overwrite behavior;
  implement core.py with atomic directory publishing.
- [x] Test exact PNG bytes and encoder header; adapt upstream functions into
  encoder.py and implement pixels.py without Pillow.
- [x] Test Blender registration, evaluated UV mesh snapshots, animation topology,
  scene preservation, left/right preview updates and export; implement mesh.py,
  preview.py and __init__.py.
- [x] Run full suite in Blender 5.1.2, inspect a preview render, package ZIP and
  document installation, usage and known limitations.

## Completion evidence

2026-11-12: nine pure-Python tests and seven Blender integration tests pass.
ZIP integrity passed; Blender's extension CLI successfully parsed the manifest.
Inspected the generated first-person sword preview. Minecraft rendering remains
unverified. Independent review found preview foreign-object deletion, incorrect
view-layer selection and un-restored viewport state; all fixed with regressions
observed failing before the fixes and passing afterwards.

Implementation rulings: work directly in the user's empty designated project
folder (no existing Git checkout); use bundled 1.21.11 shader profile with custom
shader option; retain a static approximate preview and a shared-atlas workflow.
No deferred review findings.
