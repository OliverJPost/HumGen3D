---
permalink: haircards
description: Convert the particle hair of Human Generator characters to textured hair cards for export to Unity, Unreal, Godot and other programs, and choose how many triangles they get.
---
> [!info] Part of the [[Process/Overview|Process guide]]

> [!warning] Early access
> The new process system is only in the early access version of Human Generator. It replaces the process tab of earlier versions, which is deprecated. Details can still change. If something doesn't work, or the result is not what you expected, [let us know](https://humgen3d.com/feedback/process), on the Discord or by email.

# Haircards

```compare
before: compare_hair_particles.webp | Particle hair
after: compare_hair_cards.webp | Hair cards
```

The hair, eyebrows, eyelashes and beards of Human Generator are particle hair: thousands of strands that only Blender can render. No file format carries them. **Haircards** replaces every hair system by a mesh of textured, transparent cards that follows the strands, the way hair is made for games. The cards are skinned to the head, so they move with the character.

![[process_haircards.webp|520]]

You get one mesh per hair type (*Hair*, *Eyebrows*, *Eyelashes*, *FaceHair*), each with two parts: a **haircap**, a textured skin under the cards so the scalp doesn't show through, and the **cards**. Their textures (color, normal, roughness and alpha) are baked by [[Bake Textures]] along with everything else.

## Quality

The quality sets the triangle budget of the cards. The thumbnails show what you get; the triangle count next to *Hair* is for the hairstyle of the selected human.

| Quality | Scalp hair | Face hair (eyebrows, lashes, beard) | Use it for |
| --- | --- | --- | --- |
| ![[haircards_ultra.webp\|64]] **Ultra** | up to 24,000 triangles | up to 10,000 | Hero characters seen up close |
| ![[haircards_high.webp\|64]] **High** | up to 12,000 | up to 7,000 | The default, most characters |
| ![[haircards_medium.webp\|64]] **Medium** | up to 7,000 | up to 5,000 | Secondary characters |
| ![[haircards_low.webp\|64]] **Low** | up to 4,500 | up to 3,500 | Crowds, distant LOD levels |
| ![[haircards_haircap_only.webp\|64]] **Haircap** | only the haircap texture on the skin, no cards | | Mobile, the last LOD level |

With more than one [[Optimize Meshes|LOD level]] every level has its own quality, and its own hair card textures, as the layout of the cards changes with the quality.

> [!note] Automatic hair cards
> The cards are generated from the strands. Hand-made hair cards will always look better, and some hairstyles, like afros and very curly styles, are hard for the generator and come out rough. Check the result in Blender with *Keep copy in this file* before you commit to a hairstyle for a hero character.

## In the engine

The alpha of the cards is the transparency between the strands. Two things to set on the hair materials in the other program, if its importer doesn't do it:

- Use an **alpha clip / cutout** material (alpha scissor in Godot, masked in Unreal, Alpha Clipping in Unity), not blended transparency, so the cards sort correctly.
- Make the material **two-sided**, as the cards are single planes.

Keep the texture format at **PNG**: JPEG has no alpha channel, and the tab warns you when both are chosen. By default the alpha is packed into the alpha channel of the color texture, as engines expect; see [[Bake Textures]].

## When the section is off

The particle hair is not converted. For a file export that means a bald character, and the tab warns you about it. Turn it off for a render copy that stays in Blender, where the particle hair renders fine and looks better.

> [!tip]- Python API - Hair cards
> ```python
> settings.haircards.enabled = True
> settings.lods[0].haircards = "medium"   # "ultra", "high", "medium", "low", "haircap_only"
> ```
> To convert the hair of a human in place (on a `human.duplicate()`, the particle hair is removed):
> ```python
> cards = human.process.convert_to_haircards("high")
> ```
> See [[ProcessSettings#convert_to_haircards]] and, for one hair type at a time, [[RegularHairSettings#convert_to_haircards]].
