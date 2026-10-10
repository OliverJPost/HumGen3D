---
description: How to export a Human Generator character from Blender with a Mixamo skeleton, so animations from the Mixamo library play on it without retargeting.
---
> [!info] Part of the [[Process/Overview|Process guide]]

# Export to Mixamo

The **Mixamo** recipe of the Process tab makes an FBX with the Mixamo skeleton: the Mixamo bone names, a T-pose and no root bone. Animations from the Mixamo library are made for that skeleton, so they play on the character as they are, and tools that expect a Mixamo rig work with it.

## In Blender

1. Select the human, open the **Process** tab and choose the **Mixamo** recipe.
2. In the Output box, open *Advanced* and set **Textures** to *Embedded* if you are going to upload the character to Mixamo, so the textures travel inside the FBX.
3. Press **Export to FBX**.

What the recipe sets, and why:

| Setting | Value | Why |
| --- | --- | --- |
| [[Output]] | FBX, textures in a `Textures` folder | Mixamo and most tools read FBX |
| [[Skeleton]] | **Mixamo** names, **T-pose**, no root bone | The Mixamo skeleton, as its animations are made for it |
| [[Bake Textures]] | Separate maps, **OpenGL** normal map, PNG | Plain maps that every program reads |
| [[Animations]] | One file per clip | The Mixamo clips you download come one per file too |

## On mixamo.com

1. **Upload character** and choose the FBX (with embedded textures, or a `.zip` with the FBX and its `Textures` folder).
2. The skeleton has the Mixamo names and the T-pose, so the library animations play on it directly. Preview any animation on your character and download it, with or without the skin.
3. Back in Blender, or in your engine, the downloaded clips match the exported skeleton bone for bone.

> [!tip] Mixamo animations in your engine
> You don't need Mixamo for the character itself. Export the character with the Mixamo recipe to your engine, download the animations from Mixamo *without skin*, and they play on the character as they share the skeleton.

#### Troubleshooting

- **Mixamo wants to auto-rig the character**: upload the FBX with the skeleton included; if it still offers the auto-rigger, you can let it, the mesh, blend shapes and textures are kept.
- **The textures are missing after upload**: they were next to the file instead of inside it. Export with *Textures: Embedded*, or zip the FBX with the `Textures` folder.
- **The hair is solid** in your engine: the hair material needs alpha clipping and PNG textures, see [[Haircards]].
