---
permalink: otherrename
---

> [!info] Part of the [[Process/Overview|Processing System]]

This processing option is for renaming the objects and materials the human exists of according to templates. You can either manually change the template, or use one of the existing recipes. 

> [!tip] Want to reuse your naming template? Save it as a recipe ([[Process/Overview|Overview]]).

![[Screenshot_Blender_000182.webp]]
1. **Information about tokens**: This gives some definitions of the tokens you can use.
	1. `.` (a period before the name): Adding this at the start of the name will hide the object/material in any dropdowns. We use this by default for HG materials so they don't clutter your material list.
	2. `{name}` if you add this to one of your naming templates it will be replaced by the name of the human (e.g. `HG_{name}` becomes `HG_Jake` if the human is called Jake)
	3. `{original_name}` This is replaced by the default name of this object or this material. So if you want to revert to the default name that object or material gets from HG you can use this token. (e.g. if you renamed the body material to `MyBodyMat` using `{original_name` will revert it to `.Human`)
	4. `{custom}` This will be replaced by a custom piece of text you can define in the field below (2)
2. **Custom token field**: Enter here what `{custom}` should be replaced with
3. **Suffix**: Enter here what should be added to every name. (e.g. a suffix of `_LOD1` will name the body `HG_Body_LOD1` and the eyes `HG_Eyes_LOD1` etc.)
4. **Suffix checkbox**: You can enable/disable if the suffix should be added for objects and/or for material names
5. **Naming fields**: Here you can type your naming templates, using the tokens above

>[!warning]
>If an object already exists with that name, Blender will rename that existing object and add a number suffix (e.g. `.001`) at the end. Do not rely on your other objects having the same names after using this processing option. 