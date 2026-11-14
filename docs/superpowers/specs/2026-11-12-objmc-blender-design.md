# OBJMC Blender

Build a Blender 5.1 extension exporting selected evaluated meshes and optional
constant-topology animation to a complete Minecraft Java resource pack using
Godlander's MIT-licensed objmc encoder. Provide a separate first-person preview
scene, left/right hand transforms, FOV, and a block arm reference.

The user approved proceeding with the proposed in-Blender preview. Implementation
choices: bundle the upstream encoder and shaders, replace Pillow with a small
RGBA image adapter, use Minecraft 1.21.11 (resource format 75) as the bundled
shader target, and allow explicit custom metadata and shader directories.
Do not claim arbitrary Minecraft-version compatibility. Preview is a static
approximation of the idle held-item view, not a Minecraft renderer.

Export new pack directories transactionally; replacing an existing directory
requires an explicit UI checkbox. Never merge over another pack's shaders.
Use one shared UV-mapped texture atlas; material baking is out of scope.
Reject changing topology, invalid UVs, and coordinates outside objmc's range.
Preserve the original scene, selection and current frame. Preview uses evaluated
mesh snapshots and does not modify original objects. Hand settings live on the
source scene and are exported for both hands.

Approaches considered: external objmc process requires Python/Pillow setup;
bundled encoder avoids external dependencies and is the chosen implementation;
rewriting objmc would create unnecessary format compatibility risk.

Upstream shaders cancel held-item rotation and scale; the bundled hand branch
will omit that cancellation so model display transforms remain usable. Document
the small patch and retain attribution. No game-tested accuracy claim.
