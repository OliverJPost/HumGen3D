---
description: "Export a Human Generator character from Blender with a Mixamo skeleton, the skeleton the Mixamo library animations are made for, and upload it to mixamo.com."
---
# Export to Mixamo

> [!earlyaccess] Early access
> The process system is new and only in the early access version of Human Generator. It replaces the process tab of version 4.0, which is deprecated. Details can still change; if something doesn't work or looks wrong, [let us know](https://humgen3d.com/feedback/process).

The **Mixamo** recipe of the Process tab exports a Human Generator human from Blender as an FBX with the Mixamo skeleton: the Mixamo bone names, a T-pose and no root bone. Animations from the Mixamo library are made for that skeleton, so they play on your character without retargeting, on mixamo.com or in your engine.

## In Blender

1. Select the human, open the **Process** tab and choose the **Mixamo** recipe.
2. In the Output box, open *Advanced* and set **Textures** to *Embedded* if you are going to upload the character to Mixamo, so the textures travel inside the FBX.
3. Press **Export to FBX**.

> [!note]- What the recipe sets, and why
> | Setting | Value | Why |
> | --- | --- | --- |
> | [[Output]] | FBX, textures in a `Textures` folder | Mixamo and most tools read FBX |
> | [[Skeleton]] | **Mixamo** names, **T-pose**, no root bone | The Mixamo skeleton, as its animations are made for it |
> | [[Bake Textures]] | Separate maps, **OpenGL** normal map, PNG | Plain maps that every program reads |

## On mixamo.com

1. **Upload character** and choose the FBX (with embedded textures, or a `.zip` with the FBX and its `Textures` folder).
2. The skeleton has the Mixamo names and the T-pose that the library animations are made for. Preview any animation on your character and download it, with or without the skin.
3. Back in Blender, or in your engine, the downloaded clips use the same bone names as the export.

> [!tip] Mixamo animations in your engine
> You don't need Mixamo for the character itself. Export the character with the Mixamo recipe to your engine, download the animations from Mixamo *without skin*, and they play on the character as they share the skeleton.

> [!feedback] Did Mixamo accept the character like this?
> Mixamo changes without notice. If the upload went differently, we want to know what it did. [Tell us](https://humgen3d.com/feedback/process?page=mixamo&step=upload).

## Troubleshooting

- **Mixamo wants to auto-rig the character**: upload the FBX with the skeleton included; if it still offers the auto-rigger, check afterwards that the blend shapes and textures survived.
- **The textures are missing after upload**: they were next to the file instead of inside it. Export with *Textures: Embedded*, or zip the FBX with the `Textures` folder.
- **The hair is solid** in your engine: the hair material needs alpha clipping and PNG textures, see [[Haircards#In the engine]].

> [!feedback] A problem that is not listed?
> Tell us what you saw and what you expected. [Tell us](https://humgen3d.com/feedback/process?page=mixamo&step=troubleshooting).

## Frequently asked questions

### Can I use Mixamo animations on a Human Generator character?

Yes. Export with the *Mixamo* recipe and the character has the Mixamo skeleton. Upload it to mixamo.com to preview and download animations on it, or download the animations without skin and play them on the exported character in your engine.

### Do I need to auto-rig the character on Mixamo?

No. The FBX already has a Mixamo-named skeleton with skin weights, so upload it as a rigged character and skip the auto-rigger.
