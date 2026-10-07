---
permalink: baking
---

> [!info] Part of the [[Process/Overview|Processing System]]

Want to export to another software? Or do you want to simplify the texture set-up? Texture baking is the solution, and HG can do it automatically.

>[!tip] Resolution
>Do you just want lower resolution textures to use inside Blender? You can change the texture resolution in the [[Skin]] menu.

![[Screenshot_Blender_000194.webp]]
1. **Sample count:** This determines the quality of the output. A higher sample count gives better quality, but also increases the time the baking takes.
2. **Resolution categories**: Here you can choose the output resolution of the textures that are being baked.
3. **Haircards resolution**: This will only be available if you have haircards enabled.

##### Where do the textures get saved?
At the bottom of the processing panel you see this when baking is enabled:
![[Screenshot_Blender_000196.webp]]
Here you can select what file format the textures are saved as and in which folder. If the folder field is left empty the textures are saved to the `output` folder inside the directory where you installed the HG content packs.