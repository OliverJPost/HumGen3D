---
permalink: lod
description: Reduce the polygon count of Human Generator characters for games and crowds - body, clothing, eye and teeth quality, levels of detail (LOD) and removing the skin under clothing.
---
> [!info] Part of the [[Process/Overview|Process guide]]

> [!warning] Early access
> The process system is new and in early access: it works, but details can still change, and your experience with it shapes what comes next. Found a problem, or something you miss? Let us know on [[Contact Us|Discord or by mail]].

# Optimize meshes and LOD levels

```compare
before: compare_mesh_full.webp | Full resolution
after: compare_mesh_optimized.webp | Optimized mesh
```

A Human Generator human is made for close-up rendering: about 50,000 triangles for the body alone, plus layered eyes with a transparent cornea and detailed teeth. **Optimize Meshes** brings that down to what a game or a crowd needs, and replaces the layered eyes by simple *game eyes* that every engine can render.

![[process_meshes.webp|520]]

Every part has its own picker. Click a thumbnail and the triangle count next to the part updates, the total is shown at the bottom.

| Part | Options |
| --- | --- |
| **Body** | ![[lod_body_original.webp\|72]] **Original**, about 50,500 triangles. ![[lod_body_lower_face.webp\|72]] **Lower face**, about 36,000: the face gets the same density as the body, which is plenty unless the camera is close. ![[lod_body_quarter.webp\|72]] **1/4th**, about 9,600: the whole body at a quarter, for crowds and mobile. |
| **Clothing** | **Original**, or decimated to **High** (half the triangles), **Medium** (a quarter) or **Low** (a tenth). |
| **Eyes** | ![[lod_eyes_original.webp\|72]] **Original**: the layered eyes of Human Generator, about 10,600 triangles, which only render in Blender. ![[lod_eyes_high.webp\|72]] **High** (3,600), **Medium** (900) and **Low** (200) are game eyes with one opaque layer. |
| **Teeth** | **Original** (12,400), **Medium** (4,600) or **Low** (3,300 triangles). |

> [!warning] The original eyes are not game ready
> The transparent cornea of the original eyes relies on Blender's material system. In other programs it renders as a solid shell, hiding the iris. Keep the eyes at *High* or lower for any file export; the tab warns you when they are set to *Original*.

**Remove skin under clothing** (on by default) deletes the parts of the body that the clothing covers. In Blender this is done by mask modifiers, which exporters don't apply, so without it the whole body is in the file under every garment. Turn it off if you plan to swap or remove the clothing in the engine.

#### Advanced

**Remove clothing subdivision** and **Remove clothing solidify** strip those modifiers from the clothing before it is exported. Exporters apply modifiers, so a subdivision modifier would multiply the triangles of the clothing by four, and a solidify modifier doubles them. Leave both on for games; turn them off if you make a render copy and want the clothing exactly as it is in Blender.

## LOD levels

Set **LOD levels** at the top of the tab to 2, 3 or 4 and every part gets one row per level: level 0 is the full character, each further level a lighter one. A new level starts one quality tier below the previous one, so you only adjust what you want. The totals at the bottom show the triangles of each level.

![[process_lod_levels.webp|520]]

Each level is a complete copy of the character with its own hair cards, so the levels can be swapped freely. In a file export the levels share one skeleton and one set of textures (only the eyes and hair cards get their own, their UVs change with the quality), and the meshes are named `Jake_Body_LOD0`, `Jake_Body_LOD1`, … Unity turns these into an LOD group on import, other engines have an import option for LOD meshes. With *In this file* each level is a separate processed copy.

> [!tip]- The quality tiers
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

> [!note] Using lower detail inside Blender
> Render times in Blender hardly change with fewer triangles; the texture resolution matters far more for speed and memory. See the [[Skin|Skin guide]] for lowering the texture resolution of a human, or [[Bake Textures]] for a baked copy.

> [!note] Trial version
> The body can't be reduced in the trial version. Clothing, eyes and teeth can.

> [!tip]- Python API - Mesh quality
> ```python
> from HumGen3D.human.process.settings import QualitySettings
>
> settings.lods = [QualitySettings.from_tier("high"), QualitySettings.from_tier("low")]
> settings.lods[1].clothing = "medium"
> settings.meshes.remove_hidden_skin = False
> ```
> To reduce a human in place (do this on a `human.duplicate()`, it can't be undone), use `human.process.set_quality(QualitySettings.from_tier("medium"))`, or the single steps of [[LodSettings]] (`human.process.lod`). See [[QualitySettings]], [[MeshSettings]] and [[ProcessSettings#set_quality]].
