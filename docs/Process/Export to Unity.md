---
description: How to export a Human Generator character from Blender to Unity as a Humanoid FBX with baked textures and blend shapes, and how to set it up in Unity.
---
> [!info] Part of the [[Process/Overview|Process guide]]

> [!warning] Early access
> The process system is new and in early access: it works, but details can still change, and your experience with it shapes what comes next. Found a problem, or something you miss? [Let us know](https://humgen3d.com/feedback/process), on Discord or privately by mail.

# Export to Unity

The **Unity** recipe of the Process tab makes an FBX that Unity imports as a Humanoid character, with the textures packed for the Standard and URP Lit shaders.

## In Blender

1. Select the human, open the **Process** tab and choose the **Unity** recipe.
2. Set the **Folder** to a folder inside your project's `Assets`, so Unity imports the files straight away.
   <!-- 3. Turn on [[Animations]] if you want clips, and tick the ones you need. -->
3. Press **Export to FBX**.

What the recipe sets, and why:

| Setting | Value | Why |
| --- | --- | --- |
| [[Output]] | FBX, textures in a `Textures` folder next to it | Unity finds textures in a *Textures* folder next to the model |
| [[Skeleton]] | **Humanoid** names, **T-pose**, root bone `Root`, 4 bones per vertex, meters | Unity's Humanoid avatar maps the bones by name; it expects a T-pose |
| [[Bake Textures]] | **Metallic-Smoothness** packing, **DirectX** normal map, PNG | What the Standard and URP Lit shaders read |
| [[Shape Keys]] | Face rig, expressions and correctives kept, sliders baked | The face as blend shapes, the body fixed |

<!-- hidden while the Animations section is experimental:
| [[Animations]] | One file per clip (`Jake@Run.fbx`), root motion on the root bone | Unity picks up `Model@Clip.fbx` files as the clips of the model |
-->

## In Unity

1. **Import**: with the folder inside `Assets`, Unity imports `Jake.fbx` and the `Textures` folder<!-- and any `Jake@Clip.fbx` files--> by itself.
2. **Rig**: select `Jake.fbx`, open the *Rig* tab of the Inspector, set *Animation Type* to **Humanoid** with *Avatar Definition: Create From This Model*, and press *Apply*. The avatar is configured without errors, as the bone names are the ones Unity looks for.
3. **Materials**: Unity creates a material per part and finds the textures next to the model. When it asks to mark the normal maps as *Normal map*, press *Fix now*. If a material has an empty *Metallic* slot, drop its `_MetallicSmoothness` texture in; the smoothness is read from the alpha channel.
4. **Hair**: set the hair materials to *Cutout* (Built-in) or *Alpha Clipping* (URP, HDRP) and make them two-sided, so the cards show their transparency.
   <!-- 5. **Animation**: the `Jake@Run.fbx` clips appear under the model and can be dropped into an Animator Controller. For root motion, enable *Apply Root Motion* on the Animator; the clips carry the movement on the root bone. -->

> [!note] Blend shapes
> The face rig and the expressions are blend shapes of the body's Skinned Mesh Renderer. Face capture tools for Unity drive the FACS names directly. The corrective keys are driven by bones in Blender and are static in Unity unless you drive them yourself; remove them in [[Shape Keys]] if you don't.

> [!tip] LOD levels
> Export with 2 or 3 [[Optimize Meshes|LOD levels]] and Unity turns the `_LOD0`, `_LOD1` meshes into an LOD Group on import.

#### Troubleshooting

- **The skin looks dented or inverted**: the normal map direction. Unity uses DirectX (Y−); the recipe sets it, check it wasn't changed.
- **The hair is solid**: the hair material needs alpha clipping, see above. Make sure the textures were exported as PNG, not JPEG.
- **The eyes look like glass balls**: the character was exported with the original eyes. Set the eyes to *High* or lower in [[Optimize Meshes]].
- **Arms are raised or lowered in every animation**: the rest pose of the character and the animation differ. Animations made in the A-pose need the A-pose rest pose.<!-- Humanoid retargeting handles the Human Generator clips. -->
