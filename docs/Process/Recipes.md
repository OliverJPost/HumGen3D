---
description: What the built-in Unity, Unreal, Godot, Mixamo and Blender recipes of Human Generator set, and how to save, reuse and share recipes of your own.
---
> [!info] Part of the [[Process/Overview|Process guide]]

> [!warning] Early access
> The process system is new and in early access: it works, but details can still change, and your experience with it shapes what comes next. Found a problem, or something you miss? Let us know on [[Contact Us|Discord or by mail]].

# Recipes

A recipe is the complete state of the Process tab, saved under a name. Picking one from the **Recipe** dropdown fills in every option: the output format, the skeleton, how the textures are packed, which shape keys stay. You normally pick the recipe of the program you export to and never touch the rest.

## Built-in recipes

| Recipe | Output | Skeleton | Textures | Animations |
| --- | --- | --- | --- | --- |
| **Unity** | FBX, textures in a folder next to it | Humanoid names, T-pose, root bone, meters | Metallic-Smoothness, DirectX normal map | One file per clip (`Jake@Run.fbx`), root motion on the root bone |
| **Unreal** | FBX with the `SK_`/`M_`/`T_` prefixes of the Unreal style guide | Mannequin names, A-pose, root bone, centimeters | ORM, DirectX normal map | One file with all clips, root motion on the root bone |
| **Godot** | glTF Binary (.glb) with the textures inside | Humanoid names, T-pose, root bone | Metallic-Roughness, OpenGL normal map | Clips inside the character file, root motion on the root bone |
| **Mixamo** | FBX, textures in a folder | Mixamo names, T-pose, no root bone | Separate maps, OpenGL normal map | One file per clip |
| **Generic game** | FBX, textures in a folder | Human Generator names, A-pose, root bone | Separate maps, OpenGL normal map | One file with all clips |
| **Blender render copy** | In this file | Off, the full rig stays | Off, the materials stay as they are | Off |

Every built-in recipe makes **one LOD level** at the *High* quality, converts the hair to **high** hair cards, keeps the face rig, the 1-click expressions and the corrective shape keys, and bakes the body, face and age sliders into the mesh. Unreal removes the correctives, as its retargeting tools don't use them. Animations are off everywhere until you turn them on.

Each program has its own page with what the recipe does and what to do on the other side: [[Export to Unity]], [[Export to Unreal Engine]], [[Export to Godot]], [[Export to Mixamo]].

## Changing a recipe

Change any option and the dropdown shows the recipe as **(modified)**, with two icons next to it:

![[process_recipe_modified.webp|520]]

- **Reset** (the arrow) puts every option back to the recipe.
- **Save** (the tick) saves your changes as a recipe of your own.

Your changes are kept in the Blender file, so you can close and reopen it without losing them.

## Saving your own recipes

Press the save icon, give the recipe a name and choose a **group**. The groups are the headings of the dropdown; create a new one for a project, or add the recipe to an existing group. A recipe with the same name as an existing one overwrites it, the dialog warns you.

Your recipes are files in the `process_templates` folder of your Human Generator content folder, one subfolder per group:

```
<content folder>/process_templates/MyGame/Mobile characters.json
```

> [!tip] Sharing a recipe
> A recipe is one JSON file. Copy it into the `process_templates` folder on another computer, or commit it with your project, and it shows up in the dropdown there.

> [!example] A recipe per target
> It pays off to save a recipe per use: *MyGame hero* with 4k textures and three LOD levels, *MyGame crowd* with 1k textures and the *Mobile* quality, *Preview* with 512 textures for quick checks. Switching between them is one click, and every human you export the same way comes out the same.

## Inside a recipe file

A recipe is readable JSON with the same structure as the Python [[ExportSettings]]. Options that are missing get their default, so a recipe only needs to hold what you care about:

```json
{
    "version": 2,
    "label": "MyGame crowd",
    "output": {"format": "fbx", "naming": "plain", "textures": "folder"},
    "lods": [
        {"body": 2, "clothing": "low", "eyes": "low", "teeth": 2, "haircards": "low", "bones_per_vertex": 4}
    ],
    "skeleton": {"enabled": true, "names": "humanoid", "rest_pose": "t_pose"},
    "textures": {"workflow": "metallic_smoothness", "normal_map": "directx"},
    "animations": {"enabled": false}
}
```

Recipes saved with the process system of earlier versions are converted when they are loaded.

> [!tip]- Python API - Recipes
> ```python
> from HumGen3D.human.process.settings import ExportSettings
>
> settings = ExportSettings.from_recipe("unity")      # a built-in one
> settings = ExportSettings.from_recipe("MyGame/Mobile characters.json")  # one of yours
> settings = ExportSettings.from_recipe("/any/path/recipe.json")
>
> settings.textures.set_resolution_tier("1k")
> settings.save_recipe("MyGame", "Mobile characters")  # into the content folder
> ```
> See [[ExportSettings#from_recipe]] and [[ExportSettings#save_recipe]].
