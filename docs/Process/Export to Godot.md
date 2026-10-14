---
description: "Export a Human Generator character from Blender to Godot 4 as a .glb with a humanoid skeleton, baked textures, hair cards and blend shapes, plus the Companion."
---
# Export to Godot

> [!earlyaccess] Early access
> The process system is new and only in the early access version of Human Generator. It replaces the process tab of version 4.0, which is deprecated. Details can still change; if something doesn't work or looks wrong, [let us know](https://humgen3d.com/feedback/process).

The **Godot** recipe of the Process tab exports a Human Generator human from Blender as one `.glb` file with everything inside: a skeleton with the names of Godot's humanoid profile, the meshes, the face as blend shapes, hair cards and the textures. The free [[Godot Companion]] adds the hair shader, the skin scattering and the bone map on import.

## In Blender

1. Select the human, open the **Process** tab and choose the **Godot** recipe.
2. Set the **Folder** to a folder inside your Godot project, so Godot imports the file straight away.
3. Press **Export to glTF Binary**.

> [!note]- What the recipe sets, and why
> | Setting | Value | Why |
> | --- | --- | --- |
> | [[Output]] | glTF Binary (.glb), textures embedded | One file, the format Godot reads natively |
> | [[Skeleton]] | **Humanoid** names, **T-pose**, root bone `Root` | Godot's humanoid skeleton profile maps the bones by name |
> | [[Bake Textures]] | **Metallic-Roughness** packing, **OpenGL** normal map, PNG | What glTF materials define and Godot expects |
> | [[Shape Keys]] | Face rig, expressions and correctives kept, sliders baked | Blend shapes for the face |

## In Godot

> [!tip] Let the Companion do this
> The [[Godot Companion]] is a free, open source editor plugin that does the steps below on import: a shipped hair shader on the cards that lights them along their strands, alpha scissor at 0.15 with alpha to coverage, subsurface scattering on the skin, a humanoid `BoneMap` on the skeleton and an `AnimationPlayer`. Install it once and skip to the troubleshooting.

Tested with Godot 4.7 and Blender 5.1: all 56 bones of the humanoid profile match by name, the hair cards import as Alpha Scissor with both sides shown, and the blend shapes come through. By hand:

1. **Import**: with the file inside the project, Godot imports `Jake.glb` as a scene. Drag it into your scene, or open it with *Advanced Import Settings* to change how it is imported.
2. **Skeleton**: to use the character with animations made for other humanoid characters, open the import settings, select the *Skeleton3D* and under *Retarget* set *Bone Map* to a new `BoneMap` with the `SkeletonProfileHumanoid` profile. The bones match without manual mapping, as they carry the profile's names.
3. **Materials**: the materials come in with the metallic-roughness textures assigned. The hair cards import with *Alpha Scissor* transparency at 0.5 and *Cull Mode* disabled. Lower the scissor to about 0.15 and turn on *Alpha Antialiasing: Alpha To Coverage* with MSAA on the camera: Godot discards everything under the scissor before alpha to coverage, so at 0.5 the fine strands are lost and the hair looks sparse, see [[Haircards#In the engine]]. For skin that looks like it does in Blender, turn on *Subsurface Scattering* in skin mode on the `_Skin` material, see [[Bake Textures#Skin in a game engine]].
4. **Blend shapes**: the face blend shapes are on the body's *MeshInstance3D* and can be animated or driven from a script.

> [!note]- Hair shading and the haircap as a mesh
> The standard material shades the cards as flat surfaces; the flow map next to the file (`Jake_HairCards_Flow.png`, not inside the `.glb` as no material input reads it) is for a hair shader with highlights along the strands, see [[Haircards#Hair shading]]. With *Haircap* set to *As meshes* the haircap imports as alpha blend with a depth pre-pass.

> [!feedback] Did Godot import it like this?
> These steps are what we see in Godot 4. If your import differs, or a step is missing, we want to know which one, and your Godot version. [Tell us](https://humgen3d.com/feedback/process?page=godot&step=import).

## Troubleshooting

- **The skin looks pressed in**: the normal map direction. Godot uses OpenGL (Y+), the recipe sets it.
- **The hair is solid or sparse**: the hair material needs *Alpha Scissor* at about 0.15 with alpha to coverage, see step 3, and PNG textures.
- **The eyes look wrong**: the character was exported with the original eyes. Set the eyes to *High* or lower in [[Optimize Meshes]].
- **Need the textures as files**: choose *glTF + textures* as output; the textures are then written next to the `.gltf` file.

> [!feedback] A problem that is not listed?
> Tell us what you saw and what you expected. [Tell us](https://humgen3d.com/feedback/process?page=godot&step=troubleshooting).

## Frequently asked questions

### How do I export a Human Generator character to Godot 4?

Select the human in Blender, choose the *Godot* recipe in the Process tab, set the folder to a folder inside your Godot project and press *Export to glTF Binary*. Godot imports the `.glb` as a scene with the skeleton, blend shapes and textures; the Companion plugin adds the hair shader and bone map.

### Does the skeleton work with Godot's humanoid retargeting?

Yes. The bones carry the names of `SkeletonProfileHumanoid`, so a `BoneMap` with that profile matches all of them without manual mapping, and animations made for other humanoid characters play on it.

### Why does the hair look sparse at the default alpha scissor?

Godot discards every texel under the scissor threshold before alpha to coverage runs, so at 0.5 the fine strands of the cards are cut away. Set the scissor to about 0.15 with MSAA and alpha to coverage; the Companion does this.
