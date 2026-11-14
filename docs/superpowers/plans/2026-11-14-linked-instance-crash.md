# Linked-instance export crash correction (0.4.2)

## Evidence

The Blender 5.3 crash report shows EXCEPTION_ACCESS_VIOLATION in
IDP_GetPropertyFromGroup, Python snapshot at evaluated.get for skin metadata.
A separate factory-startup 5.3 process reproduced the same crash from the saved
linked-model scene while snapshotting six local skin meshes and a linked sword.
The original saved scene and resource pack were never modified.

## Correction

Instance iteration now retains only stable original object IDs, copied world
matrices and persistent identity labels. Evaluated geometry is obtained from
original.evaluated_get after iteration. Custom properties are read from the
original ID. No temporary instance.object reference survives iteration.
Direct source meshes use the same original-ID path. Temporary meshes are cleared.

## Verification

- Saved-scene reproducer: crashed before, passes after (frames 22, 23 and 24;
  seven meshes, 450 triangulated faces each).
- Saved-scene static resource, active walk clip and all enabled clips exported
  successfully into a temporary test pack; original source and pack untouched.
- 35 integration tests pass on Blender 5.1.2 and 5.3.0, covering linked/direct
  meshes, nested instances, mirrored transforms, materials, clips and viewport state.
- New untagged linked-instance fixture adds mixed local/instanced geometry coverage.
  This generated fixture also passes before the fix; the saved-scene reproducer
  supplies the actual failing crash regression and must not be replaced by that fixture.
- 14 pure Python tests pass.

Test logs and the reproducer are in .test-temp/crash-investigation.
