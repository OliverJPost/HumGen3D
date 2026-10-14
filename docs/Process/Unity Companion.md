---
description: Download and install the free Human Generator 3D Companion for Unity, the package that sets up exported Human Generator characters on import - Humanoid rig, materials, hair and skin shaders.
---
> [!info] Part of the [[Process/Overview|Process guide]]

> [!earlyaccess] Early access
> The new process system is only in the early access version of Human Generator. It replaces the process tab of earlier versions, which is deprecated. Details can still change. If something doesn't work, or the result is not what you expected, [let us know](https://humgen3d.com/feedback/process), on the Discord or by email.

# Human Generator 3D Companion for Unity

A free Unity package that sets up a character exported with the **Unity** recipe the moment Unity imports it: the Humanoid avatar, the texture types, a material per part for your render pipeline, two-sided hair cards with a hair shader that lights them along their strands, and a skin shader in URP. Without it you do the steps of [[Export to Unity#In Unity]] by hand.

**[Download the Unity Companion (.tgz)](https://github.com/OliverJPost/humgen3d-companion-unity/releases/latest/download/humgen3d-companion-unity.tgz)**

| | |
| --- | --- |
| Tested with | Unity 6000.6 with the Built-in render pipeline and URP 17.2. HDRP materials are set up but not reviewed. |
| Needs | A character exported by the early access version of Human Generator, with its `.humgen3d.json` file next to it |
| Licence | MIT, the source is on [GitHub](https://github.com/OliverJPost/humgen3d-companion-unity) |

## Install

1. Download `humgen3d-companion-unity.tgz` and save it in the `Packages` folder of your Unity project. Unity keeps reading the package from where it is, so don't leave it in your Downloads folder.
2. In Unity, open **Window > Package Manager**, click **+** at the top left and choose **Install package from tarball...**.
3. Pick the `.tgz` file. *Human Generator 3D Companion* appears in the list of packages.

> [!tip]- Install from Git instead
> With Git installed, choose **Install package from git URL...** and enter
> `https://github.com/OliverJPost/humgen3d-companion-unity.git`. Add `#v0.7.0` to the end to stay on one version.

## Use

Export with the **Unity** recipe to a folder inside your project's `Assets`. Unity imports `Jake.fbx`, the `Textures` folder and `Jake.humgen3d.json`, and the Companion sets the character up; the Console shows *Human Generator 3D Companion: set up Jake.fbx*. After a new character is imported, a window opens with the [[Export to Unity#In Unity|import settings]]: the hair and skin shading and the haircap. Change the defaults for the whole project in **Edit > Project Settings > Human Generator 3D**, and the settings of one character with **Human Generator 3D > Import Settings...** in the right-click menu of its `.fbx`.

> [!info] Only characters with their .humgen3d.json file
> Human Generator writes `Jake.humgen3d.json` next to every exported character. It tells the Companion which files belong to the character and what each material is. The Companion only changes files that such a file lists, so other characters in your project are never touched, and the [[Output#Naming|naming scheme]] doesn't matter. Keep the file next to the character when you copy it into the project. Characters exported by earlier versions of Human Generator don't have it; export them again.

## Update

Download the new `.tgz`, replace the old file in your `Packages` folder, and in the Package Manager select the Companion and install it from the new tarball again. The characters are imported again with the new version.

## Remove

Select *Human Generator 3D Companion* in the Package Manager and press **Remove**. The characters keep the materials that were made for them until they are imported again.
