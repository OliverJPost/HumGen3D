---
description: "Export a Human Generator character from Blender to Unreal Engine 5 as a skeletal mesh with Mannequin bones, ORM textures, hair cards and morph targets."
---
# Export to Unreal Engine

> [!earlyaccess] Early access
> The process system is new and only in the early access version of Human Generator. It replaces the process tab of version 4.0, which is deprecated. Details can still change; if something doesn't work or looks wrong, [let us know](https://humgen3d.com/feedback/process).

The **Unreal** recipe of the Process tab exports a Human Generator human from Blender as an FBX skeletal mesh for Unreal Engine 5: in centimeters, with the bone names and A-pose of the Unreal Mannequin, textures packed as ORM, the face as morph targets, hair cards, and the `SK_`, `M_` and `T_` prefixes of the Unreal style guide. The free [[Unreal Engine Companion]] builds the materials after the import.

## In Blender

1. Select the human, open the **Process** tab and choose the **Unreal** recipe.
2. Set the **Folder** and press **Export to FBX**.

> [!note]- What the recipe sets, and why
> | Setting | Value | Why |
> | --- | --- | --- |
> | [[Output]] | FBX, **Unreal prefixes** naming, textures in a `Textures` folder | `SK_Jake`, `M_Jake_Skin`, `T_Jake_Body_BC` as the style guide names them |
> | [[Skeleton]] | **Unreal** Mannequin names, **A-pose**, root bone `root`, **centimeters** | The Mannequin's names, rest pose and units, so the mesh imports at scale 1 and retargets to Mannequin animations |
> | [[Bake Textures]] | **ORM** packing, **DirectX** normal map, PNG | Occlusion, roughness and metallic in one texture, the Unreal convention |
> | [[Shape Keys]] | Face rig and expressions kept, correctives removed, sliders baked | Morph targets for the face; the correctives would be static in Unreal |

## In Unreal Engine

> [!tip] Let the Companion do this
> The [[Unreal Engine Companion]] is a free, open source plugin that does every step below after the import: the ORM and flow textures, master materials with an instance per part, masked and dithered two-sided hair with the *Hair* shading model on the cards, and the *Subsurface Profile* shading model on the skin, which it needs to look like it does in Blender. Install it once and skip to the troubleshooting.

Tested with Unreal Engine 5.8 and Blender 5.1: the skeletal mesh imports at 176 cm with the Mannequin bone names, 81 morph targets, and a material per part with the base color and normal map connected. By hand:

1. **Import**: drag `Jake.fbx` into the Content Browser. Unreal Engine 5.8 imports it through Interchange: keep *Skeletal Mesh* on, leave *Skeleton* empty to create one, and the morph targets come along. In the legacy FBX importer, turn on **Import Morph Targets** (it is off there). The textures in the `Textures` folder next to the file are imported along with the mesh.
2. **Materials**: a material instance per part is created with the base color and normal map connected. The ORM texture needs wiring once: open the material, add `T_Jake_Body_ORM` with *sRGB* off, and connect **R to Ambient Occlusion, G to Roughness, B to Metallic**.
3. **Hair**: set the hair materials to *Masked* blend mode, connect the alpha channel of the color texture to *Opacity Mask*, and make them *Two Sided*. For the cards, the *Hair* shading model with the red and green of `T_Jake_HairCards_Flow` (scaled from 0..1 to -1..1, third component 0) as the *Tangent* gives highlights that run along the strands instead of across the card, see [[Haircards#Hair shading]].

> [!feedback] Did Unreal import it like this?
> These steps are what we see in Unreal Engine 5. If your import differs, or a step is missing, we want to know which one, and your engine version. [Tell us](https://humgen3d.com/feedback/process?page=unreal&step=import).

## Troubleshooting

- **The character is tiny or huge**: the units. The recipe exports centimeters; check that *Units* in the [[Skeleton]] section is still *Centimeters* and the import scale is 1.
- **No morph targets**: the legacy FBX importer has *Import Morph Targets* off by default. Reimport with it on.
- **Roughness and metallic look wrong**: the ORM texture is not wired, or has sRGB on. See step 2.
- **The skin looks pressed in**: the normal map direction, Unreal expects DirectX (Y−).
- **The hair is solid**: the hair material needs the Masked blend mode, see step 3, and PNG textures.

> [!feedback] A problem that is not listed?
> Tell us what you saw and what you expected. [Tell us](https://humgen3d.com/feedback/process?page=unreal&step=troubleshooting).

## Frequently asked questions

### How do I export a Human Generator character to Unreal Engine 5?

Select the human in Blender, choose the *Unreal* recipe in the Process tab, set the folder and press *Export to FBX*. Drag the FBX into the Content Browser; it imports as a skeletal mesh with the Mannequin bone names and morph targets. The Companion plugin then wires the ORM, hair and skin materials.

### Can I use Mannequin animations on the character?

Yes. The skeleton has the Mannequin bone names and the A-pose, so the IK Retargeter lines the chains up and Mannequin animations retarget to it.

### Why does it need to be in centimeters?

Unreal's unit is the centimeter. The recipe exports in centimeters so the character imports at scale 1 instead of 0.01, which keeps physics, retargeting and the editor tools at their defaults.
