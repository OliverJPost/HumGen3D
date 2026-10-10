---
permalink: process
cssclasses:
  - overview
description: Export Human Generator characters from Blender to Unity, Unreal Engine, Godot and other programs, or make a frozen copy in your file. Pick a recipe, press one button.
---
# Export and process humans

The **Process** tab turns a Human Generator human into a game-ready character file (FBX or glTF), a plain mesh file (OBJ, Alembic), or a frozen, lightweight copy inside your Blender file. You pick a *recipe* for the program you are going to use, check the folder, and press one button. Everything else, like baking textures, converting the hair to hair cards and building a clean skeleton with the right bone names, happens automatically.

> [!info] Your human stays as it is
> Processing never changes the human you select. The result is always a **processed copy**: a file on disk, or a copy in your scene that you can delete at any time. Keep editing the original, and process it again whenever you like.

## Quickstart

1. Select your human (click any part of it) and open the **Process** tab at the top of the Human Generator panel.
2. Choose a **Recipe**: *Unity*, *Unreal*, *Godot*, *Mixamo*, *Generic game* or *Blender render copy*. The recipe fills in every option below it.
3. Optionally change the **Folder** at the bottom. When left empty, the files go to the `export_results` folder inside your Human Generator content folder.
4. Press **Export to FBX** (the button is named after the output you chose). A progress bar appears in the status bar at the bottom of Blender; press `Esc` to cancel.
   ![[process_progress.webp|500]]
5. When it's done, a popup lists the files that were written and the triangle count. **Open folder** takes you there.
   ![[process_result_popup.webp|300]]

That is all most people need. The rest of this guide explains what the sections do when you want to change something.

> [!tip]- Python API - Processing a human
> The whole Process tab is one call. Load a recipe, change what you want, and run it:
> ```python
> from HumGen3D import Human
> from HumGen3D.human.process.settings import ExportSettings
>
> human = Human.from_existing(bpy.context.object)
> settings = ExportSettings.from_recipe("unity")
> settings.output.folder = "/path/to/MyGame/Assets/Characters"
> result = human.process.run(settings)
> print(result.files)
> ```
> See [Processing humans from Python](<Python API>) for the full tour, and [[ProcessSettings]] and [[ExportSettings]] for the reference.

## The Process tab

![[process_panel.jpg|520]]

1. **Recipe**. A recipe is the saved state of the whole tab, tuned for one program. Changing any option below marks the recipe as *(modified)*; the two icons next to it reset the changes or save them as a recipe of your own. See [[Recipes]].
2. **Output**. What you get: a file format, or *In this file* for a processed copy in your scene. See [[Output]].
3. **LOD levels**. How many levels of detail to make, 1 to 4. Each level is a complete, smaller copy of the character. See [[Optimize Meshes]].
4. **Sections**. Each section is one step of the process. The checkbox in its header turns the step on or off, the grey text on the right summarizes what it is set to. Open a section to change its options:
    - [[Optimize Meshes]]: reduce the body, clothing, eyes and teeth, and remove the skin hidden under clothing.
    - [[Haircards]]: replace the particle hair by textured hair cards, which files can carry.
    - [[Skeleton]]: turn the rig into a clean game skeleton with the bone names and rest pose the engine expects.
    - [[Shape Keys]]: choose which shape keys stay as blend shapes, and which are baked in or removed.
    - [[Bake Textures]]: bake the skin, eye, hair and clothing materials to texture maps, packed the way the engine expects.
    - [[Animations]]: export the animations of the human or clips from the library, fitted to the new skeleton.
    - [[Scripts]]: run your own Python scripts at any point of the process.
5. **Name and Folder**. The name of the files and the prefix of every object, material and texture (`{name}` is the name of the human), and where the files go. See [[Output]].
6. **Process button**. Processes every selected human. Above it you see how many humans are selected, below it the checks that found something.

> [!info] Checks before it runs
> The tab checks your settings against the selected human while you work. A **red** line is an error that stops the process, for example a folder that can't be written. A **grey** line with a warning icon is something to be aware of, for example *"The hair is particle hair, which no file format carries"*; the process still runs. The warnings are repeated in the popup afterwards.

## What happens when you press the button

Each selected human is processed one after the other, with the same settings. For every LOD level the add-on makes a fresh copy of the human and runs the sections on it, in this order: shape keys, hair cards, eyes and teeth, texture baking, mesh reduction, skeleton, naming. Then the levels are joined under one skeleton, the animation clips are prepared, and the file is written. The copy is removed again afterwards, unless the output is *In this file* or you asked to keep it.

> [!note]- How long does it take?
> Texture baking is the slow part: every material is baked pass by pass. With the default 2k textures a human with an outfit takes around a minute on a fast computer, more with hair cards and more LOD levels. Lower the resolution in [[Bake Textures]] for quick test exports, and raise it again for the final one.

## Several humans at once

Select more than one human and the button changes to *Export 3 humans to FBX*. Each human gets its own files, named after it, in the same folder. Open the *humans selected* list above the button to see which ones are included.

## Processed copies in your file

With the *In this file* output (the *Blender render copy* recipe) the result stays in your scene, two meters behind the original, in a collection called *Processing Results*. A processed copy is frozen: the Human Generator panel doesn't edit it, but shows buttons to jump to the original, process it again, or load the settings it was made with. See [[Output#Processed copies]].

![[process_processed_human.webp|420]]

> [!warning] Things to know
> - The Process tab is not available in the **trial version**.
> - **Rigify** humans can't get a game skeleton. Their Rigify rig is exported as it is, everything else works.
> - **Humans made before version 4** can't be processed.
> - The original human is never changed, so there is nothing to undo. If you still want the original gone after exporting, delete it yourself.

## Guides per program

- [[Export to Unity]]
- [[Export to Unreal Engine]]
- [[Export to Godot]]
- [[Export to Mixamo]]
- [[Process/Python API|Python API]]: process humans from your own scripts, also from the command line.
