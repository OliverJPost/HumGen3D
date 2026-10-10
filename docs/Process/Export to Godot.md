---
description: How to export a Human Generator character from Blender to Godot 4 as a glTF (.glb) with a humanoid skeleton, baked textures and blend shapes, and how to set it up in Godot.
---
> [!info] Part of the [[Process/Overview|Process guide]]

> [!earlyaccess] Early access
> The new process system is only in the early access version of Human Generator. It replaces the process tab of earlier versions, which is deprecated. Details can still change. If something doesn't work, or the result is not what you expected, [let us know](https://humgen3d.com/feedback/process), on the Discord or by email.

# Export to Godot

The **Godot** recipe of the Process tab makes one `.glb` file with everything inside: the humanoid skeleton, the meshes, the blend shapes and the textures<!-- and the animation clips-->.

## In Blender

1. Select the human, open the **Process** tab and choose the **Godot** recipe.
2. Set the **Folder** to a folder inside your Godot project, so Godot imports the file straight away.
3. Press **Export to glTF Binary**.<!-- Turn on [[Animations]] for clips first. -->

What the recipe sets, and why:

| Setting | Value | Why |
| --- | --- | --- |
| [[Output]] | glTF Binary (.glb), textures embedded | One file, the format Godot reads natively |
| [[Skeleton]] | **Humanoid** names, **T-pose**, root bone `Root` | Godot's humanoid skeleton profile maps the bones by name |
| [[Bake Textures]] | **Metallic-Roughness** packing, **OpenGL** normal map, PNG | What glTF materials define and Godot expects |
| [[Shape Keys]] | Face rig, expressions and correctives kept, sliders baked | Blend shapes for the face |

<!-- hidden while the Animations section is experimental:
| [[Animations]] | Clips in the mesh file, root motion on the root bone | The clips become an AnimationPlayer in the imported scene |
-->

## In Godot

Tested with Godot 4.7 and Blender 5.1: all 56 bones of the humanoid profile match by name, the hair cards import as Alpha Scissor with both sides shown, and the blend shapes come through.

1. **Import**: with the file inside the project, Godot imports `Jake.glb` as a scene. Drag it into your scene, or open it with *Advanced Import Settings* to change how it is imported.
2. **Skeleton**: to use the character with animations made for other humanoid characters, open the import settings, select the *Skeleton3D* and under *Retarget* set *Bone Map* to a new `BoneMap` with the `SkeletonProfileHumanoid` profile. The bones should match without manual mapping, as they carry the profile's names.
3. **Materials**: the materials come in with the metallic-roughness textures assigned. The hair cards import with *Alpha Scissor* transparency and *Cull Mode* disabled, so both sides of the cards show; the haircap imports as alpha blend with a depth pre-pass.
   <!-- 4. **Animation**: the clips are in the *AnimationPlayer* of the imported scene. For root motion, set the *Root Motion Track* of the AnimationPlayer or AnimationTree to the `Root` bone of the skeleton. -->
5. **Blend shapes**: the face blend shapes are on the body's *MeshInstance3D* and can be animated or driven from a script.

> [!feedback] Did Godot import it like this?
> These steps are what we see in Godot 4. If your import differs, or a step is missing, we want to know which one, and your Godot version. [Tell us](https://humgen3d.com/feedback/process?page=godot&step=import).

#### Troubleshooting

- **The skin looks pressed in**: the normal map direction. Godot uses OpenGL (Y+), the recipe sets it.
- **The hair is solid**: the hair material needs *Alpha Scissor*, see step 3, and PNG textures.
- **The eyes look wrong**: the character was exported with the original eyes. Set the eyes to *High* or lower in [[Optimize Meshes]].
- **Need the textures as files**: choose *glTF + textures* as output; the textures are then written next to the `.gltf` file.

> [!feedback] A problem that is not listed?
> Tell us what you saw and what you expected. [Tell us](https://humgen3d.com/feedback/process?page=godot&step=troubleshooting).
