---
description: "Fix common problems with the Human Generator Process tab in Blender: red and grey lines, missing recipes, slow exports, bald or solid hair, idle Companions."
---
# Troubleshooting the Process tab

> [!earlyaccess] Early access
> The process system is new and only in the early access version of Human Generator. It replaces the process tab of version 4.0, which is deprecated. Details can still change; if something doesn't work or looks wrong, [let us know](https://humgen3d.com/feedback/process).

Problems with the Process tab itself. What to do in the engine is on the pages per program: [[Export to Unity#Troubleshooting|Unity]], [[Export to Unreal Engine#Troubleshooting|Unreal Engine]], [[Export to Godot#Troubleshooting|Godot]], [[Export to Mixamo#Troubleshooting|Mixamo]].

## The red lines under the button

A red line is a problem that stops the process. They come from the check that runs before anything changes:

| Red line | What to do |
| --- | --- |
| *This is a processed human, process its original instead* | You selected a processed copy. Use **Go to original human** in its panel, see [[Output#Processed copies]] |
| *Humans made before version 4 can't be processed* | Make the human again in version 4 or newer |
| *This human was already processed in place (...)* | The process tab of version 4.0 changed this human itself. Process a human that wasn't processed, see [[Known Limitations#Humans]] |
| *Save the blend file first, the folder is relative to it* | The folder starts with `//`. Save the file, or pick an absolute folder |
| *Can't write to ...* | Pick a folder you have write access to |
| *The bone names file of the skeleton does not exist* | Pick the file again in [[Skeleton]], or choose built-in names |
| *Script not found: ...* | The script moved or was deleted. Pick it again in [[Scripts]] |

Grey lines are warnings: the process runs, but have a look. The popup after processing repeats them.

## A recipe is missing from the list

The list leaves out recipe files that can't be read, for example a broken JSON file or a recipe of the old process tab that can't be converted. The reason is written to Blender's console. Fix the file, or save the recipe again from the tab. See [[Recipe Format]].

## Processing takes long

Texture baking takes most of the time, a minute or two for a dressed human at 2k. Lower the resolution in [[Bake Textures]] for quick test exports. Press `Esc` to cancel; the copies made so far are removed and your human is not changed.

## The character is bald, or the hair is solid

- **Bald**: the [[Haircards]] section is off, and particle hair can't be exported.
- **Solid hair**: the textures were saved as JPEG, which has no alpha. Use PNG in [[Bake Textures]]. In the engine, the hair material needs alpha clipping; the Companions set that.

## The Companion didn't set up the character

- Check that `Jake.humgen3d.json` is next to `Jake.fbx` or `Jake.glb` in your project. The Companions only set up characters with this file, see [[Output#The .humgen3d.json file]].
- The engine's console says *made by a newer Human Generator 3D*: update the Companion, see the [[Unity Companion|Unity]], [[Unreal Engine Companion|Unreal Engine]] or [[Godot Companion|Godot]] page.
- Check that the Companion is installed and enabled, see the same pages.

## Something else

Look at Blender's console for the error (on Windows: *Window > Toggle System Console*; on macOS and Linux, start Blender from a terminal), and [tell us](https://humgen3d.com/feedback/process?page=troubleshooting) what you did and what you saw.
