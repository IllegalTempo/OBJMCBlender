# OBJMC Project Types Implementation Plan

> Execute inline with superpowers:executing-plans; user requested proceed.

**Goal:** Two project modes, armor stand head preview and rigged skin model import.
**Architecture:** Per-scene settings share the export and preview lifecycle.
**Tech Stack:** Blender 5.1 Python, existing encoders, Minecraft display contexts.
**Spec:** ../specs/2026-11-13-project-types-design.md

## Global Constraints
- Preserve existing first-person projects and viewport restoration.
- No new dependencies or changes to pinned shaders.
- Both export buttons honor mode visibility; reference stand is never exported.

## Review Focus
- Existing scenes default to First Person; new projects do not delete prior scenes.
- Hidden contexts must use empty models, preserving shader carrier geometry.
- Skin UVs, narrow arms and outer shells must deform with their matching bones.
- Preview refresh/close must restore viewport and preserve source geometry.
- Legacy exports need context routing too; clip transactions remain atomic.

### Task 1: Project mode and export routing
- [x] Add failing integration tests for new scenes, mode defaults, visibility and clips.
- [x] Implement settings, File > New callbacks, context item definitions and head variant.
- [x] Run Blender integration and pure tests.

### Task 2: Full skin model importer
- [x] Add failing integration tests for six parts, UVs and shared rig deformation.
- [x] Implement player.py and the skin-picker operator; reuse arm mesh/material helpers.
- [x] Run integration tests for wide/narrow arms and clothing on/off.

### Task 3: Armor stand preview
- [x] Add failing integration tests for head transform, isolated reference and restoration.
- [x] Implement third_person.py and reuse preview lifecycle and viewport state.
- [x] Run full integration suite, including refresh/navigation and export from preview.

### Task 4: Release
- [x] Review implementation against spec, fix material findings, run all tests.
- [x] Update documentation and version 0.4.0, build and verify ZIP, provide download.

## Execution record
No git metadata exists in this workspace; work is performed in place with tests.
New-scene, visibility, full-player and armor-stand regressions were observed failing
before implementation, then passed. Starting a new project from preview was also
tested failing, then fixed to close the preview and restore viewport state first.
Independent reviewer found no Critical/Important issues. Minor selection observation
is intentional: importing preserves selection, matching the existing hands importer;
the README now explicitly tells users to select imported meshes before export.
Final verification: 27 Blender integration tests and 14 pure Python tests passed;
0.4.0 ZIP contains 53 files and passes ZIP integrity validation. A diagnostic
full-player skin was rendered on the reference stand for visual inspection.
Minecraft in-game rendering remains unverified.
Visual inspection caught a sideways preview camera (Blender tracking assumed Z-up
for Minecraft Y-up geometry). The camera horizon/up regression failed before the
explicit Y-up basis fix, then passed with the full suite.
