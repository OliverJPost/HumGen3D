---
permalink: haircards
description: Convert the particle hair of Human Generator characters to textured hair cards for export to Unity, Unreal, Godot and other programs, and choose how many triangles they get.
---
> [!info] Part of the [[Process/Overview|Process guide]]

> [!earlyaccess] Early access
> The new process system is only in the early access version of Human Generator. It replaces the process tab of earlier versions, which is deprecated. Details can still change. If something doesn't work, or the result is not what you expected, [let us know](https://humgen3d.com/feedback/process), on the Discord or by email.

# Haircards

```compare
before: compare_hair_particles.webp | Particle hair
after: compare_hair_cards.webp | Hair cards
```

The hair, eyebrows, eyelashes and beards of Human Generator are particle hair: thousands of strands that only Blender can render. No file format carries them. **Haircards** replaces every hair system by a mesh of textured, transparent cards generated from the strands. The cards are skinned to the head and neck, so they move with it; long hair does not follow the shoulders.

> [!note] Automatic hair cards
> The cards are generated from the strands. Hand-made hair cards will always look better, and some hairstyles come out rougher than others. Check the result in Blender with *Keep copy in this file* before you commit to a hairstyle for a hero character.

![[process_haircards.webp|520]]

Scalp hair and beards get a **haircap**, the hair painted on the skin under the cards so the scalp doesn't show through, and the **cards**. The haircap is solid where hair with cards lies over the scalp and fades to a see-through film of painted strands over the last centimetres to the hairline, so the skin never shows between the cards and the cap doesn't end in a line beyond them. Hair that is too short for cards keeps the film everywhere. Eyebrows get a haircap only, and eyelashes are pre-made lash strips, one mesh each.

### Haircap on skin or as meshes

With **Haircap: On skin** (the default) the haircaps of the hair, beard and eyebrows are painted into the textures of the skin when they are baked, and they are not in the result as meshes. The skin is opaque, so there is nothing for the engine to sort or blend, no transparent mesh over the skin, and a few thousand triangles and a material less. At the 2k skin textures of the engine recipes the hair on the skin is as sharp as on a 1k haircap of its own.

Choose **As meshes** to get the haircaps as blended meshes of their own (*Haircap*, *FaceHair* and *Eyebrows*, next to *HairCards* and *FaceHairCards*), when you want to hide or swap the hair in the engine without a second skin texture, or for a bald version of the same character. The option only applies when the textures are baked: a copy in this file without baking keeps its haircaps as meshes. The eyelashes are always a mesh, their textures are the *Haircap* textures.

## Quality

The quality sets the triangle budget of the cards. The thumbnails show what you get; the triangle count next to *Hair* is the budget for the hair types the selected human has.

| Quality | Scalp hair | Beard | Use it for |
| --- | --- | --- | --- |
| ![[haircards_ultra.webp\|64]] **Ultra** | up to 24,000 triangles | up to 10,000 | Hero characters seen up close |
| ![[haircards_high.webp\|64]] **High** | up to 12,000 | up to 7,000 | The default, most characters |
| ![[haircards_medium.webp\|64]] **Medium** | up to 7,000 | up to 5,000 | Secondary characters |
| ![[haircards_low.webp\|64]] **Low** | up to 4,500 | up to 3,500 | Crowds, distant LOD levels |
| ![[haircards_haircap_only.webp\|64]] **Haircap only** | only the haircap texture on the skin, no cards | | Mobile, the last LOD level |

The budget is spent where it shows. A card in the mass of the hair is one of many layers, which hide that it is flat and where it bends. A lock that **hangs free** of the rest of the hair shows both, so it gets more segments, which keeps its bends smooth against the background, and a second card across the first, so it is not a line when you look along it. Cards that stand on the head, as in an afro, get that second card too. The cards in the mass of the hair pay for it with fewer segments.

#### Afros, curls and locks

Hair that **stands on the head**, like an afro, short curls or a flat top, is looked at along its hairs. Cards that follow the hairs are seen from their side and their tip there, so the hairstyle used to come out as a see-through burst of spikes. Such hair also gets **shells**: cards that lie across the hairs, each a tuft of the surface of the hairstyle with ragged edges, with the hair below it drawn onto it as you see it from outside, the outer hairs light and the deeper ones dark. Tall hair gets two layers of them, so the inner one shows through the gaps of the outer one. They cost a few hundred triangles. The cards along the hairs are still there for the outline of the hairstyle, where the shells are seen from their side.

**Curls** are told from hair that just bends around the head by how much a hair winds around its own line. A card of curls follows that line instead of the wobble of the average hair, is wide enough to show whole curls and has no highlight, as curls scatter the light. **Locks**, as in dreadlocks, get one pair of crossing cards each, as the hairs around one parent hair become one clump. Where locks stand apart there are no shells, as you look past them deep into the hairstyle.

```compare
before: compare_hair_afro_before.webp | Cards along the hairs only
after: compare_hair_afro_after.webp | With shells
```

With more than one [[Optimize Meshes|LOD level]] every level has its own quality, and its own hair card textures, as the layout of the cards changes with the quality.

> [!feedback] Which hairstyle came out rough?
> The generator handles some styles worse than others. The name of the hairstyle and a screenshot help us improve it. [Tell us](https://humgen3d.com/feedback/process?page=haircards&step=quality).

## Textures of the cards

The cards are textured with a **strand atlas that is generated for the hairstyle**. Cards of the same length, width, density and curl share a part of it, and the hairs of their clumps are drawn into that part where they are on the cards (for curls the hairs of one of the clumps, as the average of curls that don't line up is noise), with their width, their own length, their tapered tips and a brightness variation between hairs. So the cards of a short, sparse clump show the hairs it has, a dense clump is dense, the tips of the cards end where the hairs end, and no card is cut through strands at its sides. The atlas is packed into the file with the human and baked along with the other textures by [[Bake Textures]]. A hair finer than a texel of the atlas is drawn one texel wide, and fewer of them are drawn so the coverage of the clump stays the same; that is what lets fine hair survive the cut-out of a game engine.

## In the engine

The alpha of the cards is the coverage of the strands: full strands with anti-aliased edges, cut out at **half alpha**, which is what the cutout materials of Unity, Unreal and Godot default to. Every strand the hair material draws at a fifth of full opacity or more is solid in the baked alpha, so the fine strands survive the cut-out; below that the alpha fades out as drawn, which alpha-to-coverage and dithering turn into soft edges. In Blender the cards render translucent, which is why they look softer there; a game engine can't sort translucent cards, so the export bakes the coverage instead and fades the strands out at the sides of every card. Two things to set on the hair materials in the other program, if its importer doesn't do it:

- Use an **alpha clip / cutout** material (alpha scissor in Godot, masked in Unreal, Alpha Clipping in Unity) at the default threshold of 0.5, not blended transparency, so the cards don't sort wrongly against each other. Godot is the exception: it discards everything under the scissor before alpha to coverage, which loses the fine strands and the anti-aliased edges, so with MSAA on set its scissor to about 0.15 (the Companion does); Unity's alpha to mask and Unreal's dithered mask keep them as partial coverage at 0.5.
- Make the material **two-sided**, as the cards are single planes.

#### Hair shading

Lit as a flat surface, a card has its highlight across the card and mirrors the sky; hair reflects along its strands. So the cards also get a **flow map** (`Jake_HairCards_Flow.png`): the direction of the strands on the card in the red and green channels, in the UV space of the card from root to tip, and a random value per strand in blue. The Companions use it to shade the cards as hair: a white highlight and one in the hair color that run along the strands and are shifted apart (Kajiya-Kay with the two lobes of Marschner), broken up between the strands by the noise, which also varies the color from strand to strand. In Unity the Companion assigns a shipped URP shader, in Unreal the cards get the *Hair* shading model with the flow map as the strand tangent, in Godot a shipped shader. A plain lit material ignores the map. With embedded textures the flow map is written next to the file, as an embedded texture can only be one a material input reads.

The shaders of the Companions for Unity and Godot also **fade a card out when you look along it**, where it would be a line with all its strands pressed into it, down to its solid strands; the cards around it, or the card across it, show the hair there instead. In Unreal the cards master does the same. The normals of the cards follow the shape of the head, so the whole hairstyle is lit as one volume, and the normal map is relative to the card itself.

```compare
before: compare_hair_shading_before.webp | Lit as cards
after: compare_hair_shading_after.webp | Shaded as hair
```

The alpha and normal maps of the hair are baked at the size of the strand atlas and scaled down to the texture size, so a strand finer than a texel still counts and the normals of the cap don't turn to noise. Engines average the alpha for their mipmaps, which makes cut-out strands thinner with distance. Unity (*Preserve Coverage* on the texture) and Unreal (*Alpha Coverage* on the texture) can scale the mipmaps so the strands keep their width; the Companions set that up. For the soft look of Blender in Unreal, the Companion dithers the opacity mask, which the temporal anti-aliasing resolves to translucent-looking strands.

Keep the texture format at **PNG**: with JPEG the alpha becomes a separate map that not every importer uses, and the tab warns you when both are chosen. By default the alpha is packed into the alpha channel of the color texture, as engines expect; see [[Bake Textures]].

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
