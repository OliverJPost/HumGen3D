---
description: How to export a Human Generator character from Blender to Unreal Engine 5 as an FBX skeletal mesh with Mannequin bone names, ORM textures and morph targets, and how to import it.
---
> [!info] Part of the [[Process/Overview|Process guide]]

> [!earlyaccess] Early access
> The new process system is only in the early access version of Human Generator. It replaces the process tab of earlier versions, which is deprecated. Details can still change. If something doesn't work, or the result is not what you expected, [let us know](https://humgen3d.com/feedback/process), on the Discord or by email.

# Export to Unreal Engine

The **Unreal** recipe of the Process tab makes an FBX skeletal mesh in centimeters, with the bone names of the Unreal Mannequin, textures packed as ORM and the `SK_`, `M_` and `T_` prefixes of the Unreal style guide.

## In Blender

1. Select the human, open the **Process** tab and choose the **Unreal** recipe.
2. Set the **Folder**<!--, turn on [[Animations]] if you want clips--> and press **Export to FBX**.

What the recipe sets, and why:

| Setting | Value | Why |
| --- | --- | --- |
| [[Output]] | FBX, **Unreal prefixes** naming, textures in a `Textures` folder | `SK_Jake`, `M_Jake_Skin`, `T_Jake_Body_BC` as the style guide names them |
| [[Skeleton]] | **Unreal** Mannequin names, **A-pose**, root bone `root`, **centimeters** | The Mannequin's names, rest pose and units, so the mesh imports at scale 1 and retargets to Mannequin animations |
| [[Bake Textures]] | **ORM** packing, **DirectX** normal map, PNG | Occlusion, roughness and metallic in one texture, the Unreal convention |
| [[Shape Keys]] | Face rig and expressions kept, correctives removed, sliders baked | Morph targets for the face; the correctives would be static in Unreal |

<!-- hidden while the Animations section is experimental:
| [[Animations]] | One file with all clips, root motion on the root bone | Each take becomes an Animation Sequence |
-->

## In Unreal Engine

Tested with Unreal Engine 5.8 and Blender 5.1: the skeletal mesh imports at 176 cm with the Mannequin bone names, 81 morph targets, and a material per part with the base color and normal map connected.

1. **Import**: drag `SK_Jake.fbx` into the Content Browser. Unreal 5.4 and later import it through Interchange: keep *Skeletal Mesh* on, leave *Skeleton* empty to create one, and the morph targets come along. In the legacy FBX importer, turn on **Import Morph Targets** (it is off there). The textures in the `Textures` folder next to the file are imported along with the mesh.
2. **Materials**: a material instance per part is created with the base color and normal map connected. The ORM texture needs wiring once: open the material, add `T_Jake_Body_ORM` with *sRGB* off, and connect **R to Ambient Occlusion, G to Roughness, B to Metallic**.
3. **Hair**: set the hair materials to *Masked* blend mode, connect the alpha channel of the color texture to *Opacity Mask*, and make them *Two Sided*.
   <!-- 4. **Animation**: import `SK_Jake_Animations.fbx` onto the skeleton that was created; every take becomes an Animation Sequence. Animations made for the Mannequin retarget with the IK Retargeter, the bone names and A-pose make the chains line up. -->

> [!feedback] Did Unreal import it like this?
> These steps are what we see in Unreal Engine 5. If your import differs, or a step is missing, we want to know which one, and your engine version. [Tell us](https://humgen3d.com/feedback/process?page=unreal&step=import).

#### Troubleshooting

- **The character is tiny or huge**: the units. The recipe exports centimeters; check that *Units* in the [[Skeleton]] section is still *Centimeters* and the import scale is 1.
- **No morph targets**: the legacy FBX importer has *Import Morph Targets* off by default. Reimport with it on.
- **Roughness and metallic look wrong**: the ORM texture is not wired, or has sRGB on. See step 2.
- **The skin looks pressed in**: the normal map direction, Unreal expects DirectX (Y−).
- **The hair is solid**: the hair material needs the Masked blend mode, see step 3, and PNG textures.

> [!feedback] A problem that is not listed?
> Tell us what you saw and what you expected. [Tell us](https://humgen3d.com/feedback/process?page=unreal&step=troubleshooting).
