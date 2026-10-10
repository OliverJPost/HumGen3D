---
permalink: baking
description: Bake the skin, eye, hair and clothing materials of Human Generator characters to texture maps for Unity, Unreal, Godot or Blender - resolution, PNG or JPEG, ORM and metallic-smoothness packing, normal map direction.
---
> [!info] Part of the [[Process/Overview|Process guide]]

> [!warning] Early access
> The process system is new and in early access: it works, but details can still change, and your experience with it shapes what comes next. Found a problem, or something you miss? Let us know on [[Contact Us|Discord or by mail]].

# Bake textures

```compare
before: compare_textures_2k.webp | 2k textures
after: compare_textures_512.webp | 512 px textures
```

The skin, eyes and hair of a Human Generator human are procedural materials: node trees that mix textures, colors and masks at render time. Other programs can't read them. **Bake textures** renders every material to plain image maps and replaces it by a simple material with those images, which any program reads. The materials are copied first, so the original human keeps its procedural ones.

![[process_textures.webp|520]]

You get one set of textures per part: the **body** (skin), each piece of **clothing**, the **eyes**, the **teeth** and the **hair** (the cards, and one shared haircap for the hair, eyebrows and eyelashes). The maps are written to the texture folder of the [[Output]] and named after the part and the pass, `Jake_Body_BaseColor.png`.

Inputs that don't get a map of their own, like the specular of the skin and the hair cards, are kept as one value on the baked material, so the result looks like the original from every program.

## Resolution

One choice sets the resolution of every part, with the body and clothing largest and the small parts smaller:

| Tier | Body | Clothing | Hair | Eyes | Teeth |
| --- | --- | --- | --- | --- | --- |
| **4k** | 4096 | 4096 | 2048 | 1024 | 512 |
| **2k** (default) | 2048 | 2048 | 1024 | 512 | 512 |
| **1k** | 1024 | 1024 | 512 | 256 | 256 |
| **512** | 512 | 512 | 256 | 128 | 128 |

2k is right for most characters. Use 4k for a hero seen up close, 1k or 512 for crowds, mobile and quick test exports. The resolution is also the main factor in how long baking takes and how large the export is: a 4k set is four times the pixels of a 2k set.

## Format

**PNG** is lossless and keeps the alpha channel the hair cards need. **JPEG** gives much smaller files but has no alpha, so the hair cards lose their transparency; the tab warns when both are chosen. Use JPEG for characters without hair cards, or when size matters more than the hair.

## Material setup

How the maps are packed, so the materials in the engine work without rewiring. The recipes set these to what the engine expects.

#### Workflow

- **Separate maps**: one grayscale image each for roughness and metallic. Readable everywhere, the most files.
- **Metallic-Roughness**: roughness in the green channel, metallic in the blue, as glTF and Godot expect.
- **ORM**: occlusion in red, roughness in green, metallic in blue. The convention of Unreal Engine.
- **Metallic-Smoothness**: metallic in RGB and *smoothness* (the inverse of roughness) in the alpha channel. What the Unity Standard and URP Lit shaders read.

#### Normal map

The two conventions differ in the direction of the green channel. Choose the wrong one and the bumps of the skin look pressed in. **OpenGL (Y+)** is used by Blender, Godot, glTF and three.js. **DirectX (Y−)** is used by Unity and Unreal Engine by default.

## Advanced

**Resolution per set** sets each part on its own; the tier at the top then reads *Custom*. **Passes** chooses which maps are baked per part. Base color and normal are what every material needs; roughness and metallic can be left out for parts where they are constant (the add-on already skips maps whose inputs are plain values and puts the value on the material instead). Alpha is only needed for the hair.

**Pack hair alpha into color** puts the transparency of the hair cards in the alpha channel of their color texture, which is how engines expect it. Off, the alpha is a separate grayscale map. **Samples** is the number of render samples per pixel. 4 is enough as the maps are baked from the material inputs rather than lit; raise it if you see noise in a normal map.

## Baking a copy for Blender

For the *In this file* output the section is optional. Turn it on to get a copy with simple image materials, which renders faster and uses far less memory than the procedural skin, for example for a crowd or for a scene that goes to a render farm. The baked materials are wired so the copy renders in Blender the same way, including packed maps. Turn it off to keep the procedural materials on the copy.

> [!note] Only want a lower resolution inside Blender?
> You don't need to bake for that. The [[Skin|Skin section]] lets you switch the skin textures of a human to a lower resolution.

> [!note]- How baking works, and why it takes a while
> Every material is baked pass by pass, and each pass is a small render. A human with an outfit has around ten materials and four passes each, so there are around forty renders at 2k; around a minute on a fast computer, and longer for several LOD levels, although the levels after the first only bake the eyes and hair cards and share the rest. The bake runs on the CPU on purpose, which turned out faster than starting the GPU for every pass.

> [!tip]- Python API - Baking
> ```python
> settings.textures.set_resolution_tier("1k")
> settings.textures.resolution["body"] = 4096
> settings.textures.workflow = "orm"        # "separate", "metallic_roughness", "orm", "metallic_smoothness"
> settings.textures.normal_map = "directx"  # or "opengl"
> settings.textures.passes["clothing"] = ["base_color", "normal"]
> ```
> To bake a human in place (on a `human.duplicate()`; the materials are replaced):
> ```python
> images = human.process.bake_textures(settings.textures, folder="/path/to/textures")
> ```
> See [[TextureBakeSettings]] and [[ProcessSettings#bake_textures]].
