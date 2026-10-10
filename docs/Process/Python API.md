---
description: Export and process Human Generator characters from Python - run a recipe on a human, change the settings, process many humans in a batch or from the command line, and use the single steps.
---
> [!info] Part of the [[Process/Overview|Process guide]] and the [[API/Overview|Python API]]

> [!warning] Early access
> The new process system is only in the early access version of Human Generator. It replaces the process tab of earlier versions, which is deprecated. Details can still change. If something doesn't work, or the result is not what you expected, [let us know](https://humgen3d.com/feedback/process), on the Discord or by email.

# Processing humans from Python

Everything the Process tab does is available from Python, through `human.process`. The settings of the tab are one object, [[ExportSettings]], and one call processes a human with them. This page walks through the common cases; the reference is on [[ProcessSettings]] and [[ExportSettings]].

## Run a recipe

```python
import bpy
from HumGen3D import Human
from HumGen3D.human.process.settings import ExportSettings

human = Human.from_existing(bpy.context.object)

settings = ExportSettings.from_recipe("unity")   # "unity", "unreal", "godot", "mixamo", "generic", "blender"
settings.output.folder = "/path/to/MyGame/Assets/Characters"

result = human.process.run(settings)
print(result.files)        # ['/path/to/MyGame/Assets/Characters/Jake.fbx']
print(result.summary())    # what the popup shows, with the triangle count and warnings
```

`run` does exactly what the button does: the human is not changed, a processed copy is made per LOD level, written to the files and removed again. The [[ExportResult]] tells what was made: `files`, the processed `humans` left in the file, `warnings`, the `triangles` per level and the `seconds` it took.

Recipes of your own are loaded by their path inside the `process_templates` folder of the content folder, `ExportSettings.from_recipe("MyGame/Mobile characters.json")`, or by any absolute path.

## Change the settings

The settings mirror the sections of the tab. Every field has the same name and values as the [[Recipes|recipe file]]:

```python
settings = ExportSettings.from_recipe("unreal")
settings.output.format = "glb"                 # see Output
settings.output.name = "Hero_{name}"
settings.lods = [QualitySettings.from_tier("high"), QualitySettings.from_tier("low")]
settings.meshes.remove_hidden_skin = False
settings.haircards.enabled = False
settings.skeleton.names = "humanoid"
settings.skeleton.rest_pose = "t_pose"
settings.shape_keys.body = "keep"
settings.textures.set_resolution_tier("1k")
settings.textures.workflow = "metallic_roughness"
```

<!-- hidden while the Animations section is experimental; the example also had:
settings.animations.enabled = True
settings.animations.source = "library"
-->

Or start from the defaults with `ExportSettings()` and set what you need. The classes per section: [[OutputSettings]], [[QualitySettings]], [[MeshSettings]], [[HaircardSettings]], [[SkeletonSettings]], [[ShapeKeySettings]], [[TextureBakeSettings]]<!--, [[AnimationClipSettings]]--> and [[ScriptsSettings]]. `settings.to_dict()` and `ExportSettings.from_dict()` turn them into plain data, `settings.save_recipe("MyGame", "Hero")` saves them as a recipe for the interface.

## Check before running

The tab's red and grey lines come from `preflight`. Use it to validate settings without changing anything:

```python
check = human.process.preflight(settings)
if not check.ok:
    print("\n".join(check.errors))     # these would make run() raise
for warning in check.warnings:
    print("warning:", warning)
```

`run` raises a `HumGenException` when the preflight finds an error, or when a step fails; the copies made so far are removed.

## Several humans

Every human in the scene, with the same settings:

```python
from HumGen3D.common import find_multiple_in_list

rigs = find_multiple_in_list(bpy.context.scene.objects)
for human in (Human.from_existing(rig) for rig in rigs):
    result = human.process.run(settings)
    print(human.name, result.files)
```

## Progress

`run` accepts a callback that gets the fraction done, for a progress bar of your own:

```python
result = human.process.run(settings, progress=lambda fraction: print(f"{fraction:.0%}"))
```

For a modal operator that must keep Blender responsive, `human.process.run_steps(settings)` gives the same work as a generator that yields the fraction after every short chunk; that is what the Process button uses.

## From the command line

Blender in background mode, for a build step or a render farm. The add-on must be enabled in the Blender preferences of the machine:

```bash
blender -b characters.blend --python export_characters.py
```

```python
# export_characters.py
import bpy
from HumGen3D import Human
from HumGen3D.common import find_multiple_in_list
from HumGen3D.human.process.settings import ExportSettings

settings = ExportSettings.from_recipe("godot")
settings.output.folder = "/builds/characters"

for rig in find_multiple_in_list(bpy.context.scene.objects):
    human = Human.from_existing(rig)
    result = human.process.run(settings, context=bpy.context)
    print(result.summary())
```

> [!info] Passing context
> As everywhere in the API, `context` is optional and `bpy.context` is used when you leave it out. Inside an operator or an add-on of your own, pass the context you were given. See [[API/Overview#Passing context]].

## The single steps

`run` is a sequence of steps, each a method of [[ProcessSettings]] that takes the matching section of the settings, or plain arguments. You can call them yourself, for example to make a game-ready copy without exporting it, or to insert something between two steps. The steps change the human they are called on and can't be undone, so call them on a duplicate:

```python
from HumGen3D.human.process.settings import QualitySettings, SkeletonSettings

copy = human.duplicate()
copy.process.set_shape_keys(body="keep", face="bake", age="bake")
copy.process.convert_to_haircards("medium")
copy.process.bake_textures(settings.textures, folder="/path/to/textures")
copy.process.set_quality(QualitySettings.from_tier("medium"))
copy.process.convert_to_game_rig(settings=SkeletonSettings(names="humanoid", rest_pose="t_pose"))
copy.process.apply_names()
copy.export.write("/path/to/Jake", settings.output)
# or, to keep it in the file as a frozen result:
copy.process.mark_as_processed(human)
```

<!-- hidden while the Animations section is experimental; before the export the example also had:
clips = copy.process.prepare_clips(source=human)
copy.export.write("/path/to/Jake", settings.output, animation="strips")
-->

The order matters and is the one `run` uses: shape keys first, so the later steps carry only the keys that stay; hair cards, game eyes and teeth before baking, as they change the materials; baking before the meshes are reduced; the skeleton after the meshes; names last. Each step that changes the human for good refuses to run twice (`copy.process.has_haircards`, `was_baked`, `has_game_rig`, …). For one file with several LOD levels, make one copy per level and join them with [[ProcessSettings#merge_levels]].

Two more steps exist for scripts: [[ProcessSettings#apply_modifiers]] applies modifiers while keeping the shape keys, which Blender itself refuses, and [[ProcessSettings#remove_hidden_skin]] deletes the body under the clothing. To write a human to a file without any processing, use [[ExportBuilder]] (`human.export.to_fbx`, `to_glb`, `to_gltf_separate`, `to_obj`, `to_abc`).

## Reading a processed human

```python
copy = Human.from_existing(bpy.context.object)
copy.process.is_processed        # True for a frozen result
copy.process.settings            # the ExportSettings it was made with, None otherwise
```

> [!example] Scripts in the interface
> If you want your code to run as part of a recipe that others use from the Process tab, write it as a [[Scripts|script]]: a file with a `main(context, human)` function that runs at a stage of the process.
