---
description: How to export a Human Generator character from Blender to Godot 4 as a glTF (.glb) with a humanoid skeleton, baked textures, blend shapes and animations, and how to set it up in Godot.
---
> [!info] Part of the [[Process/Overview|Process guide]]

> [!warning] Early access
> The process system is new and in early access: it works, but details can still change, and your experience with it shapes what comes next. Found a problem, or something you miss? Let us know on [[Contact Us|Discord or by mail]].

# Export to Godot

The **Godot** recipe of the Process tab makes one `.glb` file with everything inside: the humanoid skeleton, the meshes, the blend shapes, the textures and the animation clips.

## In Blender

1. Select the human, open the **Process** tab and choose the **Godot** recipe.
2. Set the **Folder** to a folder inside your Godot project, so Godot imports the file straight away.
3. Turn on [[Animations]] for clips, and press **Export to glTF Binary**.

What the recipe sets, and why:

| Setting | Value | Why |
| --- | --- | --- |
| [[Output]] | glTF Binary (.glb), textures embedded | One file, the format Godot reads natively |
| [[Skeleton]] | **Humanoid** names, **T-pose**, root bone `Root` | Godot's humanoid skeleton profile maps the bones by name |
| [[Bake Textures]] | **Metallic-Roughness** packing, **OpenGL** normal map, PNG | What glTF materials define and Godot expects |
| [[Shape Keys]] | Face rig, expressions and correctives kept, sliders baked | Blend shapes for the face |
| [[Animations]] | Clips in the mesh file, root motion on the root bone | The clips become an AnimationPlayer in the imported scene |

## In Godot

1. **Import**: with the file inside the project, Godot imports `Jake.glb` as a scene. Drag it into your scene, or open it with *Advanced Import Settings* to change how it is imported.
2. **Skeleton**: to use the character with animations made for other humanoid characters, open the import settings, select the *Skeleton3D* and under *Retarget* set *Bone Map* to a new `BoneMap` with the `SkeletonProfileHumanoid` profile. The bones are matched automatically, as they carry the profile's names.
3. **Materials**: the materials come in with the metallic-roughness textures assigned. The hair materials should import with *Alpha Scissor* transparency; if not, set *Transparency* to *Alpha Scissor* and *Cull Mode* to *Disabled* so both sides of the cards show.
4. **Animation**: the clips are in the *AnimationPlayer* of the imported scene. For root motion, set the *Root Motion Track* of the AnimationPlayer or AnimationTree to the `Root` bone of the skeleton.
5. **Blend shapes**: the face blend shapes are on the body's *MeshInstance3D* and can be animated or driven from a script.

#### Troubleshooting

- **The skin looks pressed in**: the normal map direction. Godot uses OpenGL (Y+), the recipe sets it.
- **The hair is solid**: the hair material needs *Alpha Scissor*, see step 3, and PNG textures.
- **The eyes look wrong**: the character was exported with the original eyes. Set the eyes to *High* or lower in [[Optimize Meshes]].
- **Need the textures as files**: choose *glTF + textures* as output; the textures are then written next to the `.gltf` file.
