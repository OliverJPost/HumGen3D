---
permalink: lod
---

> [!info] Part of the [[Process/Overview|Processing System]]

This processing option is for when you want less detailed geometry because of performance reasons. Mainly useful for background characters or exporting to game engines. 

> [!note] Using LoDs inside Blender for performance
> Inside Blender your render times will not improve substantially by lowering the level of detail, and it only slightly lowers the memory usage. The resolution of textures is much more important for improving both render times and memory usage. See [skin settings](guide/skin) or [baking](baking) on how to lower texture resolution.

>[!warning]
>Levels of Detail should only be used when finished with other Human Generator functions. 
>
>Using this system will **always** break the following functionality:
> - Changing Live Keys (body/face deformations that are not loaded as shape keys)
> - Changing the height of the human
> - Changing the age of the human
> - Adding the face rig
> - Adding 1-click expressions
> - Adding hairstyles
> - Saving custom shape keys, hairstyles, expressions
>   
> It's possible that further systems are broken that are not mentioned here

![[Screenshot_Blender_000174.webp]]
1. **Body LOD selector**: There are three options
	1. *Original resolution.* This keeps the body unchanged. The head has more detail than the body to have more detailed expressions. Around 25K faces. ![[Screenshot_Blender_000176.webp]]
	2. *Lower face resolution*: This equalizes the resolution of the body and the face. Around 18K faces. ![[Screenshot_Blender_000178.webp]]
	3. *1/4th original resolution*: This equalizes the resolution of the body and face and then removes one level of subdivision. Around 5K faces. This is not suitable for closeup rendering due to the low level of detail. ![[Pasted image 20230804100514.webp]]
2. **Clothing decimate ratio**: We use the decimate modifier (collapse method) for lowering the resolution of clothing. If you do not want to lower the geometric resolution of the clothing, set this value to 1.0. The lower the value, the lower the output resolution. NOTE: The resulting geometry is triangulated and not very clean.
3. **Remove clothing subdiv**: Removes any subdivision surface modifiers from the clothing.
4. **Remove clothing solidify**: Removes any solidify modifiers from the clothing.