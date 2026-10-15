---
permalink: lod
description: "Reduce the polygon count of Human Generator characters in Blender for games and crowds: body, clothing, eye and teeth quality, LOD levels, skin under clothing."
---
# Optimize meshes and LOD levels

> [!earlyaccess] Early access
> The process system is new and only in the early access version of Human Generator. It replaces the process tab of version 4.0, which is deprecated. Details can still change; if something doesn't work or looks wrong, [let us know](https://humgen3d.com/feedback/process).

A Human Generator human is made for close-up rendering: about 50,000 triangles for the body alone, plus layered eyes with a transparent cornea and detailed teeth. **Optimize Meshes** brings that down to what a game or a crowd needs, with one picker per part, and makes up to four LOD levels of the same character.

```compare
before: compare_mesh_full.webp | Full resolution
after: compare_mesh_optimized.webp | Optimized mesh
```

Every part has its own picker in the section. Click a thumbnail and the triangle count next to the part updates; the total is shown at the bottom.

## Body

```options
lod_body_original.webp | Original | About 50,500 triangles, the full mesh
lod_body_lower_face.webp | Lower face | About 36,000. The face gets the density of the body, plenty unless the camera is close
lod_body_quarter.webp | 1/4th | About 9,600. The whole body at a fifth of the triangles, for crowds and mobile
```

## Clothing

```options
lod_clothing_original.webp | Original | As made, with its modifiers removed
lod_clothing_high.webp | High | Roughly half the triangles
lod_clothing_medium.webp | Medium | A quarter
lod_clothing_low.webp | Low | A tenth
```

## Eyes

```options
lod_eyes_original.webp | Original | The layered eyes of Human Generator, about 10,600 triangles. Only render in Blender
lod_eyes_high.webp | High | 3,600 triangles, game eyes with one opaque layer
lod_eyes_medium.webp | Medium | 900 triangles
lod_eyes_low.webp | Low | 200 triangles
```

> [!warning] The original eyes are not game ready
> The transparent cornea of the original eyes relies on Blender's material system. In other programs it renders as a solid shell, hiding the iris. Keep the eyes at *High* or lower for any file export; the tab warns you when they are set to *Original*. Game eyes are one surface: the baked normal map gives the iris its cavity, and the [[Unity Companion]]'s eye shader refracts it behind the cornea; without such a shader they look flat up close, which is the trade-off.

## Teeth

```options
lod_teeth_original.webp | Original | 12,400 triangles
lod_teeth_medium.webp | Medium | 4,600 triangles
lod_teeth_low.webp | Low | 3,300 triangles
```

> [!feedback] Did the game eyes and the lower face hold up?
> Tell us at what camera distance they stopped looking right, and in which program. [Tell us](https://humgen3d.com/feedback/process?page=optimize-meshes&step=parts).

## Skin under clothing

**Remove skin under clothing** (on by default) deletes the parts of the body that the clothing covers. In Blender this is done by mask modifiers, which exporters don't apply, so without it the whole body is in the file under every garment. Turn it off if you plan to swap or remove the clothing in the engine.

> [!note]- Advanced: clothing modifiers
> **Remove clothing subdivision** and **Remove clothing solidify** strip those modifiers from the clothing before it is exported. Exporters apply modifiers, so a subdivision modifier would multiply the triangles of the clothing by four, and a solidify modifier doubles them. Leave both on for games; turn them off if you make a render copy and want the clothing exactly as it is in Blender.

## LOD levels

Set **LOD levels** at the top of the tab to 2, 3 or 4 and every part gets one row per level: level 0 is the full character, each further level a lighter one. A new level starts one quality tier below the previous one (from *Original* it starts at *High*), so you only adjust what you want. The totals at the bottom show the triangles of each level.

![[process_lod_levels.mp4]]

Each level is a complete copy of the character with its own hair cards. In a file export the levels share one skeleton and one set of textures (only the eyes and hair cards get their own, as their UVs change with the quality), and the meshes are named `Jake_Body_LOD0`, `Jake_Body_LOD1`, … Unity turns these into an LOD Group on import; other engines have an import option for LOD meshes. With *In this file* each level is a separate processed copy.

> [!note]- The quality tiers
> When you add a level, its parts are set from a tier. The tiers are also what the Python API uses:
>
> | Tier | Body | Clothing | Eyes | Teeth | Hair cards | Bones per vertex |
> | --- | --- | --- | --- | --- | --- | --- |
> | **Original** | Original | Original | Original | Original | Ultra | Unlimited |
> | **Ultra** | Original | Original | High | Original | Ultra | 8 |
> | **High** | Original | High | High | Medium | High | 4 |
> | **Medium** | Lower face | Medium | Medium | Medium | Medium | 4 |
> | **Low** | 1/4th | Low | Low | Low | Low | 4 |
> | **Mobile** | 1/4th | Low | Low | Low | Haircap only | 2 |

## When the section is off

With the checkbox off, every mesh stays as it is, including the original eyes, and nothing under it applies. That is what the *Blender render copy* recipe does, and with several LOD levels it means every level has the same meshes, so there is little point in having more than one.

> [!info] Lower detail inside Blender
> Render times in Cycles hardly change with fewer triangles; the texture resolution matters far more for speed and memory. See the [[Skin|Skin guide]] for lowering the texture resolution of a human, or [[Bake Textures]] for a baked copy.

> [!warning] Humans from the trial version
> The body of a human made with the trial version can't be reduced. Clothing, eyes and teeth can.

> [!python]- Mesh quality from Python
> ```python
> from HumGen3D import QualitySettings
>
> settings.lods = [QualitySettings.from_tier("high"), QualitySettings.from_tier("low")]
> settings.lods[1].clothing = "medium"
> settings.meshes.remove_hidden_skin = False
> ```
> To reduce a human in place (do this on a `human.duplicate()`, it can't be undone), use `human.process.set_quality(QualitySettings.from_tier("medium"))`, or the single steps of [[LodSettings]] (`human.process.lod`). See [[QualitySettings]], [[MeshSettings]] and [[ProcessSettings#set_quality]].
