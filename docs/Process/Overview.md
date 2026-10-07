---
permalink: process
cssclasses:
  - overview
---
# The processing system
This system allows you to quickly apply recipes to multiple humans in one go. This includes many options, like haircards, texture baking, and exporting.

>[!warning] Use as final step
>A lot of options in the processing systems modify the humans in a way that breaks other functionality. There is no way to revert except regular undo (`ctrl+z` / `cmd+z`).
>
> Each section in the documentation warns you what systems might be broken by using that option. 
> 
> If you want to keep a backup of your human, use `Duplicate humans` (or `Export humans`) instead of `Replace humans`. 


![[Screenshot_Blender_000170.webp]]
1. **Recipe selection**: Want to use an existing processing recipe? Choose one from this dropdown and all options will be automatically selected.
2. **Save custom recipe**: Save your current settings as a new processing recipe.
3. **Selected humans dropdown**: The system will process all selected humans. This dropdown shows how many and which humans are selected.
4. **Processing options**: These are the options you can enable for the process system. *Enable the checkbox to turn on this process option.* For more detail see [[#Process options]].
5. **Output settings**: Here you select what should happen with the selected humans. For more detail see [[#Output settings]].
6. **Process button**: Click here to run the process on all selected humans

### Process options
Here you find the documentation on the different process options:
- [[Texture baking]]
- [[Haircards]]
- [[Levels of Detail]]
- [[Apply modifiers]]
- [[Other renaming]]
- [[Bone Renaming]]
- [[Custom scripts]]
### Output settings
##### Replace Humans
This will apply all processing options directly on the selected humans. You will not have the original humans anymore afterwards, only the processed humans.

##### Duplicate Humans
This will duplicate all selected humans before processing them, and place them 2 meters behind the original humans. The processing will only be applied to the duplicated humans.

##### Export Humans
Want to export the human as a file? This output option does that. 
![[Screenshot_Blender_000192 1.webp]]
1. **Baking format**: The image format that the baked textures will be saved as.
2. **File format**: The file format that the human will be saved as.
3. **Filename**: The filename of the human file. `{name}` will be replaced with the name of the human (e.g. "Jake")
4. **Folder**: The folder all the files will be saved to. If kept empty, it will be the "output" folder in the directory that you installed the Human Generator packs in. (Forgot where that is? Check the Human Generator preferences `edit>preferences>add-ons>Human Generator`)

>[!info]
>The export option applies all the selected processing options **ONLY** to the exported human. The human inside the Blender file does not get the processing options applied. If you want to apply the processing to both the Blender file and the exported human, first apply the processing using `Replace humans` and then run processing again with everything disabled but with `Export Humans`.

