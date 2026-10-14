---
description: Reference of the Human Generator recipe file - every section, option and allowed value of the JSON that the Process tab saves and the Python ExportSettings hold.
---
> [!info] Part of the [[Process/Overview|Process guide]]

> [!earlyaccess] Early access
> The new process system is only in the early access version of Human Generator. It replaces the process tab of earlier versions, which is deprecated. Details can still change. If something doesn't work, or the result is not what you expected, [let us know](https://humgen3d.com/feedback/process), on the Discord or by email.

# Recipe format

A [[Recipes|recipe]] is a JSON file with the state of the whole Process tab. The sections and options are the same as those of [[ExportSettings]] in Python, with the same names and values. Every option can be left out: it then gets the default in the tables below, so a recipe only needs what it changes. Options the add-on doesn't know are ignored, and so are files that can't be read: those are left out of the recipe list.

Your recipes live in the `process_templates` folder of your content folder, in a subfolder per group; the subfolder is the group name in the list, and recipes directly in `process_templates` are listed under *Saved*.

```json
{
    "version": 2,
    "output": {"format": "fbx", "naming": "plain", "textures": "folder"},
    "lods": [{"body": "original", "clothing": "high", "eyes": "high", "teeth": "medium", "haircards": "high"}],
    "skeleton": {"names": "humanoid", "rest_pose": "t_pose"},
    "textures": {"workflow": "metallic_smoothness", "resolution": {"body": 4096}}
}
```

## Top level

| Key | Default | Values |
| --- | --- | --- |
| `version` | `2` | The version of the format. Recipes of the process tab of 4.0 (no version) are converted when they are loaded. |
| `label` | | The name in the recipe list, only read for the built-in recipes. Yours are listed by file name. |
| `output` | | See [[#output]] |
| `lods` | one level | A list with one entry per LOD level, the first is the full character. See [[#lods]] |
| `meshes`, `haircards`, `skeleton`, `shape_keys`, `textures`, `scripts` | | One object per section of the tab, see below |

## output

See [[Output]].

| Key | Default | Values |
| --- | --- | --- |
| `format` | `"fbx"` | `"in_file"`, `"fbx"`, `"glb"`, `"gltf"`, `"obj"`, `"abc"` |
| `folder` | `""` | Where the files go. Empty for `export_results` in the content folder, `//` at the start for a folder relative to the blend file |
| `name` | `"{name}"` | Name of the files and prefix of the datablocks, `{name}` is the name of the human |
| `naming` | `"plain"` | `"plain"`, `"unreal"`, `"custom"` |
| `naming_templates` | | For `"custom"` naming: `rig`, `mesh`, `material` and `texture`, with the tokens `{name}`, `{part}` and `{pass}`. Defaults `"{name}"`, `"{name}_{part}"`, `"{name}_{part}"`, `"{name}_{part}_{pass}"` |
| `textures` | `"folder"` | `"folder"`, `"next_to_file"`, `"embedded"` |
| `keep_copy` | `false` | Keep the processed copy in the file after writing it |
| `fbx` | | `axis_forward` (`"-Z"`), `axis_up` (`"Y"`), `primary_bone_axis` (`"Y"`), `secondary_bone_axis` (`"X"`), each one of `"X"`, `"Y"`, `"Z"`, `"-X"`, `"-Y"`, `"-Z"`; `leaf_bones` (`false`), `custom_properties` (`false`), `triangulate` (`false`), `smoothing` (`"FACE"`, `"EDGE"` or `"OFF"`) |
| `gltf` | | `tangents` (`false`), `image_format` (`"AUTO"` or `"JPEG"`), `draco` (`false`) |

## lods

See [[Optimize Meshes]]. Each entry of the list:

| Key | Default | Values |
| --- | --- | --- |
| `body` | `"original"` | `"original"`, `"lower_face"`, `"quarter"` |
| `clothing` | `"high"` | `"original"`, `"high"`, `"medium"`, `"low"` |
| `eyes` | `"high"` | `"original"` (the layered eyes, not for engines), `"high"`, `"medium"`, `"low"` |
| `teeth` | `"medium"` | `"original"`, `"medium"`, `"low"` |
| `haircards` | `"high"` | `"ultra"`, `"high"`, `"medium"`, `"low"`, `"haircap_only"` |
| `bones_per_vertex` | `4` | `2`, `4`, `8`, or `0` for no limit |

## meshes

| Key | Default | Values |
| --- | --- | --- |
| `enabled` | `true` | Off keeps every mesh as it is, the quality of the levels then only changes the hair cards |
| `remove_hidden_skin` | `true` | Remove the skin under the clothing |
| `remove_clothing_subdiv` | `true` | Remove the subdivision modifiers of the clothing |
| `remove_clothing_solidify` | `true` | Remove the solidify modifiers of the clothing |

## haircards

| Key | Default | Values |
| --- | --- | --- |
| `enabled` | `true` | Turn the particle hair into hair cards. The quality is per LOD level, the haircap is under `textures` |

## skeleton

See [[Skeleton]].

| Key | Default | Values |
| --- | --- | --- |
| `enabled` | `true` | |
| `names` | `"humanoid"` | `"humgen"`, `"humanoid"`, `"unreal"`, `"mixamo"`, `"custom"` |
| `names_file` | `""` | Path of the JSON file with the bone names, for `"custom"` |
| `rest_pose` | `"t_pose"` | `"a_pose"`, `"t_pose"` |
| `root_bone` | `true` | Add a root bone at the origin |
| `root_bone_name` | `"Root"` | |
| `keep_eyes`, `keep_jaw`, `keep_breasts` | `true` | Keep these bones, otherwise their weights go to the parent bone |
| `keep_metacarpals` | `false` | Keep the palm bones |
| `units` | `"meters"` | `"meters"`, `"centimeters"`. FBX only |

## shape_keys

See [[Shape Keys]].

| Key | Default | Values |
| --- | --- | --- |
| `enabled` | `true` | Off removes the driven keys and bakes the sliders |
| `face_rig`, `expressions`, `correctives` | `"keep"` | `"keep"`, `"remove"` |
| `body`, `face`, `age` | `"bake"` | `"keep"`, `"bake"`, `"remove"` |
| `keep` | `{}` | Per group the names of the keys to keep, as the tab lists them, for example `{"expressions": ["Smile", "Angry"]}`. A group that is left out keeps all its keys |
| `lod0_only` | `true` | Only the first LOD level gets the blend shapes |

## textures

See [[Bake Textures]].

| Key | Default | Values |
| --- | --- | --- |
| `enabled` | `true` | Only a choice for the *In this file* output; files always get textures |
| `resolution` | `{"body": 2048, "clothing": 2048, "eyes": 512, "teeth": 512, "hair": 1024}` | Pixels per texture set: `128` to `4096` |
| `passes` | per set, see [[Bake Textures]] | Per texture set the maps to bake: `"base_color"`, `"normal"`, `"roughness"`, `"metallic"`, `"alpha"`, `"flow"`. The sets are `body`, `clothing`, `eyes`, `teeth` and `hair` |
| `workflow` | `"separate"` | `"separate"`, `"metallic_roughness"`, `"orm"`, `"metallic_smoothness"` |
| `normal_map` | `"opengl"` | `"opengl"`, `"directx"` |
| `file_format` | `"png"` | `"png"`, `"jpeg"` |
| `pack_hair_alpha` | `true` | Put the alpha of the hair in the alpha channel of its base color, instead of a map of its own |
| `haircap_in_skin` | `true` | Paint the haircaps into the skin textures (*On skin*); `false` exports them as meshes (*As meshes*) |
| `samples` | `4` | Render samples per pixel. The tab offers 4, 16 and 64 |

## scripts

See [[Scripts]].

| Key | Default | Values |
| --- | --- | --- |
| `enabled` | `false` | |
| `items` | `[]` | A list of scripts, each with `path`, `stage`, `args` (an object with the arguments of its `main` function) and `on_error` (`"stop"` or `"skip"`) |

The stages are `"start"`, `"before_haircards"`, `"before_baking"`, `"before_meshes"`, `"before_skeleton"`, `"after_processing"`, `"before_export"` and `"after_export"`.
