---
description: How to export a Human Generator character from Blender to Unreal Engine 5 as an FBX skeletal mesh with Mannequin bone names, ORM textures and morph targets, and how to import it.
---
> [!info] Part of the [[Process/Overview|Process guide]]

> [!warning] Early access
> The process system is new and in early access: it works, but details can still change, and your experience with it shapes what comes next. Found a problem, or something you miss? [Let us know](https://humgen3d.com/feedback/process), on Discord or privately by mail.

# Export to Unreal Engine

The **Unreal** recipe of the Process tab makes an FBX skeletal mesh in centimeters, with the bone names of the Unreal Mannequin, textures packed as ORM and the `SK_`, `M_` and `T_` prefixes of the Unreal style guide.

## In Blender

1. Select the human, open the **Process** tab and choose the **Unreal** recipe.
2. Set the **Folder**, turn on [[Animations]] if you want clips, and press **Export to FBX**.

What the recipe sets, and why:

| Setting | Value | Why |
| --- | --- | --- |
| [[Output]] | FBX, **Unreal prefixes** naming, textures in a `Textures` folder | `SK_Jake`, `M_Jake_Skin`, `T_Jake_Body_BC` as the style guide names them |
| [[Skeleton]] | **Unreal** Mannequin names, **A-pose**, root bone `root`, **centimeters** | The Mannequin's names, rest pose and units, so the mesh imports at scale 1 and retargets to Mannequin animations |
| [[Bake Textures]] | **ORM** packing, **DirectX** normal map, PNG | Occlusion, roughness and metallic in one texture, the Unreal convention |
| [[Shape Keys]] | Face rig and expressions kept, correctives removed, sliders baked | Morph targets for the face; the correctives would be static in Unreal |
| [[Animations]] | One file with all clips, root motion on the root bone | Each take becomes an Animation Sequence |

## In Unreal Engine

1. **Import**: drag `SK_Jake.fbx` into the Content Browser. In the FBX Import Options keep *Skeletal Mesh* on, leave *Skeleton* empty to create one, and turn on **Import Morph Targets** for the blend shapes (it is off by default). The textures are imported along with the mesh.
2. **Materials**: a material per part is created with the base color and normal map connected. The ORM texture needs wiring once: open the material, add `T_Jake_Body_ORM` with *sRGB* off, and connect **R to Ambient Occlusion, G to Roughness, B to Metallic**.
3. **Hair**: set the hair materials to *Masked* blend mode, connect the alpha channel of the color texture to *Opacity Mask*, and make them *Two Sided*.
4. **Animation**: import `SK_Jake_Animations.fbx` onto the skeleton that was created; every take becomes an Animation Sequence. Animations made for the Mannequin retarget with the IK Retargeter, the bone names and A-pose make the chains line up.

#### Troubleshooting

- **The character is tiny or huge**: the units. The recipe exports centimeters; check that *Units* in the [[Skeleton]] section is still *Centimeters* and the import scale is 1.
- **No morph targets**: *Import Morph Targets* was off in the import dialog. Reimport with it on.
- **Roughness and metallic look wrong**: the ORM texture is not wired, or has sRGB on. See step 2.
- **The skin looks pressed in**: the normal map direction, Unreal expects DirectX (Y−).
- **The hair is solid**: the hair material needs the Masked blend mode, see step 3, and PNG textures.
