---
description: "Download and install the free Human Generator 3D Companion for Godot, which sets up exported characters on import: hair shader, skin scattering and bone map."
---
# Human Generator 3D Companion for Godot

> [!earlyaccess] Early access
> The process system is new and only in the early access version of Human Generator. It replaces the process tab of version 4.0, which is deprecated. Details can still change; if something doesn't work or looks wrong, [let us know](https://humgen3d.com/feedback/process).

A free Godot editor plugin that sets up a character exported with the **Godot** recipe when Godot imports it: a hair shader on the cards that lights them along their strands, subsurface scattering on the skin, a humanoid `BoneMap` on the skeleton and an `AnimationPlayer`. Without it you do the steps of [[Export to Godot#In Godot]] by hand.

**[Download the Godot Companion (.zip)](https://github.com/OliverJPost/humgen3d-companion-godot/releases/latest/download/humgen3d-companion-godot.zip)**

| | |
| --- | --- |
| Tested with | Godot 4.7 |
| Needs | A character exported by the early access version of Human Generator, with its `.humgen3d.json` file and flow map next to it |
| Licence | MIT, the source is on [GitHub](https://github.com/OliverJPost/humgen3d-companion-godot) |

## Install

1. Unzip the download into your project folder, so you get `addons/humgen3d_companion/plugin.cfg` inside the project. If the project already has an `addons` folder, the Companion goes next to what is in it.
2. In Godot, open **Project > Project Settings > Plugins** and turn on **Human Generator 3D Companion**.

## Use

Export with the **Godot** recipe to a folder inside your project. Godot imports `Jake.glb`, and the Companion sets it up as part of the import. What it does can be changed per file in the **Import** dock, under the `humgen3d/` options; press *Reimport* after changing them.

> [!warning] Only characters with their .humgen3d.json file
> Human Generator writes `Jake.humgen3d.json` next to every exported character. It tells the Companion which files belong to the character, what each material is and where the flow map of the hair is. The Companion only sets up a file that such a file lists, so other characters in your project are never touched, and the [[Output#Naming|naming scheme]] doesn't matter. Characters exported by earlier versions of Human Generator don't have it; export them again.

## Update

Delete the `addons/humgen3d_companion` folder, unzip the new version in its place, and reimport your characters (select them in the FileSystem dock and press *Reimport*) to set them up with the new version.

## Remove

Turn the plugin off in **Project Settings > Plugins** and delete the `addons/humgen3d_companion` folder. Characters keep their setup until they are imported again.
