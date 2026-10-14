---
description: "Export a Human Generator character from Blender to Unity as a Humanoid FBX with baked textures, hair cards and blend shapes, set up by the free Companion."
---
# Export to Unity

> [!earlyaccess] Early access
> The process system is new and only in the early access version of Human Generator. It replaces the process tab of version 4.0, which is deprecated. Details can still change; if something doesn't work or looks wrong, [let us know](https://humgen3d.com/feedback/process).

The **Unity** recipe of the Process tab exports a Human Generator human from Blender as an FBX that Unity imports as a Humanoid character: a T-posed skeleton with the Humanoid bone names, the face as blend shapes, hair cards, and textures packed for the Standard and URP Lit shaders. The free [[Unity Companion]] sets everything up the moment Unity imports the file.

## In Blender

1. Select the human, open the **Process** tab and choose the **Unity** recipe.
2. Set the **Folder** to a folder inside your project's `Assets`, so Unity imports the files straight away.
3. Press **Export to FBX**.

> [!note]- What the recipe sets, and why
> | Setting | Value | Why |
> | --- | --- | --- |
> | [[Output]] | FBX, textures in a `Textures` folder next to it | Unity finds textures in a *Textures* folder next to the model |
> | [[Skeleton]] | **Humanoid** names, **T-pose**, root bone `Root`, 4 bones per vertex, meters | Unity's Humanoid avatar maps the bones by name; it expects a T-pose |
> | [[Bake Textures]] | **Metallic-Smoothness** packing, **OpenGL** normal map, PNG | What the Standard and URP Lit shaders read |
> | [[Shape Keys]] | Face rig, expressions and correctives kept, sliders baked | The face as blend shapes, the body fixed |

## In Unity

> [!tip] Let the Companion do this
> The [[Unity Companion]] is a free, open source package that does every step below the moment Unity imports the file: the Humanoid avatar, the texture types, materials for your render pipeline, two-sided cutout hair with a hair shader that lights the cards along their strands, and a skin shader in URP. Install it once and skip to the troubleshooting.

Tested with Unity 6000.6 and Blender 5.1: the avatar maps all 55 Humanoid bones, every material gets its base color and normal map, and the blend shapes come through. By hand:

1. **Import**: with the folder inside `Assets`, Unity imports `Jake.fbx` and the `Textures` folder by itself.
2. **Rig**: select `Jake.fbx`, open the *Rig* tab of the Inspector, set *Animation Type* to **Humanoid** with *Avatar Definition: Create From This Model*, and press *Apply*. Unity maps the bones by name.
3. **Materials**: Unity creates a material per part and finds the textures next to the model. When it asks to mark the normal maps as *Normal map*, press *Fix now*. If a material has an empty *Metallic* slot, drop its `_MetallicSmoothness` texture in; the smoothness is read from the alpha channel. The materials inside the model are read-only; use *Extract Materials* on the Materials tab of the importer to edit them.
4. **Hair**: set the hair materials to *Cutout* (Built-in) or *Alpha Clipping* (URP, HDRP) and make them two-sided (*Render Face: Both* in URP and HDRP; the Built-in Standard shader has no two-sided option, so use a double-sided shader there). A Lit material shades the cards as flat surfaces; for highlights that run along the strands use a hair shader with the `Jake_HairCards_Flow` map, see [[Haircards#Hair shading]].

> [!note]- Haircap as meshes in URP
> With *Haircap* set to [[Haircards#Haircap on skin or as meshes|As meshes]], the haircap materials (`Jake_Haircap`, `Jake_FaceHair`) fade out at the hairline and want a blended material (*Fade* in Built-in). In URP set them to *Alpha Clipping* at about 0.4 as well: URP 17 does not draw a blended skinned cap at all, so the scalp shows skin under the hair. With MSAA on, *Alpha to Mask* softens the hairline again.

> [!feedback] Did Unity import it like this?
> These steps are what we see in Unity. If your import differs, or a step is missing, we want to know which one, and your Unity version. [Tell us](https://humgen3d.com/feedback/process?page=unity&step=import).

> [!info] Blend shapes and LOD levels
> The face rig and the expressions are blend shapes of the body's Skinned Mesh Renderer; face capture tools for Unity drive the FACS names directly. The corrective keys are driven by bones in Blender and are static in Unity unless you drive them yourself; remove them in [[Shape Keys]] if you don't. Export with 2 or 3 [[Optimize Meshes|LOD levels]] and Unity turns the `_LOD0`, `_LOD1` meshes into an LOD Group on import.

## Troubleshooting

- **The skin looks dented, or a seam shows at the shoulders**: the normal map direction. Unity reads OpenGL (Y+) normal maps; the recipe sets it, check it wasn't changed to DirectX.
- **The hair is solid**: the hair material needs alpha clipping, see above. Make sure the textures were exported as PNG, not JPEG.
- **The scalp shows skin under the hair (URP)**: with *Haircap* set to *As meshes*, the haircap material is blended, which URP does not draw on a skinned mesh. Set `Jake_Haircap` and `Jake_FaceHair` to *Alpha Clipping* at 0.4; the Companion does this.
- **The skin looks oiled or wet**: the smoothness map at full strength with the reflectance of URP Lit. Lower *Smoothness* on `Jake_Skin` to about 0.7; the Companion does this and gives the skin its skin shader in URP.
- **The eyes look like glass balls**: the character was exported with the original eyes. Set the eyes to *High* or lower in [[Optimize Meshes]].
- **Arms are raised or lowered in every animation**: the rest pose of the character and the animation differ. Animations made in the A-pose need the A-pose rest pose.

> [!feedback] A problem that is not listed?
> Tell us what you saw and what you expected. [Tell us](https://humgen3d.com/feedback/process?page=unity&step=troubleshooting).

## Frequently asked questions

### How do I export a Human Generator character to Unity?

Select the human in Blender, choose the *Unity* recipe in the Process tab, set the folder to a folder inside your project's `Assets` and press *Export to FBX*. Unity imports the FBX and its textures; set the rig to Humanoid, or install the Companion package, which does that and the materials for you.

### Which render pipelines are supported?

The Companion is tested with the Built-in render pipeline and URP; it sets up HDRP materials too, but those are not reviewed yet. Without the Companion the textures work with the Standard and URP Lit shaders as exported.

### Does the character animate with Mecanim and Humanoid clips?

Yes. The skeleton maps to the Humanoid avatar by name, so any Humanoid animation retargets to it, and there is a root bone for root motion.
