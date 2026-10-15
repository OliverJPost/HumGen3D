---
description: "Download and install the free Human Generator 3D Companion for Unreal Engine, which sets up exported characters: ORM textures, skin, hair and hair cards."
---
# Human Generator 3D Companion for Unreal Engine

> [!earlyaccess] Early access
> The process system is new and only in the early access version of Human Generator. It replaces the process tab of version 4.0, which is deprecated. Details can still change; if something doesn't work or looks wrong, [let us know](https://humgen3d.com/feedback/process).

A free Unreal Engine plugin that sets up a character exported with the **Unreal** recipe right after the import: the ORM and flow textures, master materials with an instance per part, the *Subsurface Profile* shading model on the skin, masked, two-sided hair with the *Hair* shading model on the cards, and an eye material with the iris refracted behind the cornea. Without it you do the steps of [[Export to Unreal Engine#In Unreal Engine]] by hand.

**[Download the Unreal Engine Companion (.zip)](https://github.com/OliverJPost/humgen3d-companion-unreal/releases/latest/download/humgen3d-companion-unreal.zip)**

| | |
| --- | --- |
| Tested with | Unreal Engine 5.8, with the Interchange FBX import (the default) |
| Needs | A character exported by the early access version of Human Generator, with its `.humgen3d.json` file next to it, and the *Python Editor Script Plugin* that comes with Unreal |
| Licence | MIT, the source is on [GitHub](https://github.com/OliverJPost/humgen3d-companion-unreal) |

## Install

1. Close Unreal Editor.
2. Unzip the download into the `Plugins` folder of your project, so you get `MyProject/Plugins/HumGen3DCompanion/HumGen3DCompanion.uplugin`. Make the `Plugins` folder if your project doesn't have one.
3. Open the project. In **Edit > Plugins**, make sure **Python Editor Script Plugin** and **Human Generator 3D Companion** are both enabled, and restart the editor when it asks.

The plugin is Python and content only, so there is nothing to compile, also in a C++ project.

## Use

Export with the **Unreal** recipe and drag the `.fbx` into the Content Browser, with the `Textures` folder and the `.humgen3d.json` file still next to it on disk. When the import is done, the Companion sets the character up; the Output Log shows *Human Generator 3D Companion: set up SK_Jake*. After the first character, a dialog asks for the import settings: the hair, skin and eye shading and the haircap. Change the settings of one character later with **Human Generator 3D > Import Settings...** in the right-click menu of its skeletal mesh, and the defaults of the project in **Tools > Human Generator 3D > Project Defaults...**.

The master materials are made once, in `/Game/HumGen3D/`. A new version of the Companion updates them where they are, so your material instances keep working.

> [!warning] Only characters with their .humgen3d.json file
> Human Generator writes `Jake.humgen3d.json` next to every exported character (`Jake.fbx`). It tells the Companion which files belong to the character and what each material is. The Companion only sets up a mesh whose file has one, so other characters in your project are never touched, and the [[Output#Naming|naming scheme]] doesn't matter. Characters exported by earlier versions of Human Generator don't have it; export them again.

## Update

Close the editor, delete the `Plugins/HumGen3DCompanion` folder, and unzip the new version in its place.

## Remove

Close the editor and delete the `Plugins/HumGen3DCompanion` folder. The material instances and the masters in `/Game/HumGen3D/` stay; delete them yourself if you don't use them.
