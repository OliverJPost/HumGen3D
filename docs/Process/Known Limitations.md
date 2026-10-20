---
description: "What the Human Generator process system can't do yet, or does differently from what you expect: Blender versions, humans it can't process, blend shapes, hair."
---
# Known limitations

> [!earlyaccess] Early access
> The process system is new and only in the early access version of Human Generator. It replaces the process tab of version 4.0, which is deprecated. Details can still change; if something doesn't work or looks wrong, [let us know](https://humgen3d.com/feedback/process).

What the process system can't do yet, or does differently from what you might expect. The list changes during the early access; if something here stops you, [tell us](https://humgen3d.com/feedback/process?page=limitations).

## Blender and engines

- Human Generator needs **Blender 4.2 or newer**, see [[Installation#Blender version]]. The process system is tested with Blender 5.1.
- The engine pages say which engine versions were tested: [[Export to Unity|Unity]] 6000.6 with the Built-in pipeline and URP 17.2, [[Export to Unreal Engine|Unreal Engine]] 5.8, [[Export to Godot|Godot]] 4.7. Other versions likely work but were not checked. In Unity, HDRP materials are set up by the [[Unity Companion]] but not reviewed.
- The Companions only set up characters with their `.humgen3d.json` file next to them, see [[Output#The .humgen3d.json file]]. Characters exported by earlier versions of Human Generator don't have it.

## Humans

- **Humans made before version 4** can't be processed.
- **Humans changed in place** by the process tab of Human Generator 4.0 (a lower level of detail, renamed bones or parts, applied modifiers) can't be processed again: they miss the vertices, bones or names the process system needs. Process the original human.
- **Hair cards made with version 4.0** are kept as they are: the hair types that weren't converted then (often the eyebrows and eyelashes) are left out, and the cards get no flow map. Remove the old hair cards and set the hairstyle again for cards from the new generator.
- **Rigify** humans keep their Rigify rig; the [[Skeleton]] section is skipped.
- Humans made with the **trial version** can't have their body reduced, see [[Optimize Meshes]].

## In the file

- **Particle hair** never ends up in a file; turn on [[Haircards]] or the character is bald.
- **Driven blend shapes are static**: the face rig and the corrective shape keys are driven by bones in Blender, and no file format carries those drivers. The blend shapes are there, but you drive them yourself in the engine, see [[Shape Keys#Keys driven by bones]].
- **Hair cards are generated**, not hand-made, and some hairstyles come out rougher than others; long hair doesn't follow the shoulders. See [[Haircards]].
- **OBJ and Alembic** have no skeleton and no blend shapes.
- The **skin** of the engine materials can't match Blender's subsurface scattering exactly; the Companions get close, see [[Bake Textures#Skin in a game engine]].

## Not in the early access yet

- **Animations**: the export of animation clips is still being tested and hidden, see [[Animations]].
- **Batch generator**: it has no process step. Process the humans it made by selecting them all in the Process tab, or from [[Process/Python API|Python]].
