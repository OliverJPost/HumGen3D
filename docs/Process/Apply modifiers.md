---
permalink: modapply
---

> [!info] Part of the [[Process/Overview|Processing System]]

*Applying modifiers to your humans while preserving shape keys.*

By default Blender does not allow you to apply modifiers on objects that have shape keys. Human Generator humans use shape keys for body deformations, facial expressions, corrective deformations and more. Therefore, we added this system to preserve these shape keys while still being able to apply modifiers.

>[!warning]
>Apply Modifiers should only be used when finished with other Human Generator functions. 
>
>Using this system will **always** break the following functionality:
> - Changing Live Keys (body/face deformations that are not loaded as shape keys)
> - Changing the height of the human
> - Changing the age of the human
>   
> When applying modifiers that change the topology/vertex count of the model, the following functionality will be broken:
> - Adding the face rig
> - Adding 1-click expressions
> - Adding hairstyles
> - Saving custom shape keys, hairstyles, expressions
>   
> When applying the armature modifier, the following functionality will be broken:
> - Adding/changing pose
> - Generating Rigify
>   
> It's possible that further systems are broken that are not mentioned here

The "Apply Modifiers" panel consists of these 3 sections:
1. [[#Selecting Modifiers]]
2. [[#Filtering objects]]
3. [[#Options]]

![[CleanShot 2023-03-13 at 11.39.37@2x.webp]]

### Selecting Modifiers
This section shows a list of all modifier types that are present on the selected humans (The processing system works on all selected humans). On the left of each item is a checkbox. By checking this box, the processing system will apply all modifiers of this type on all objects of these humans. If you don't want to apply the modifier on some objects, either [[#Filtering objects|filter the objects]] or set the specific modifiers to hidden in the Blender modifier tab.


>[!note]
>The following modifiers can not be applied using Apply Modifiers
>1. Particle Systems
>2. Decimate (Due to the inconsistent vertex order when applying on different shape key variations)


### Filtering objects
These four buttons allow you to filter which objects are considered by "Apply modifiers". By default all object types are considered. Disabling some object types will update the counter in the [[#Selecting Modifiers|Selecting modifiers]] section.

>[!note]
>At the time of writing, haircard objects are not considered by the Modifier Apply system.

### Options
The modifier applying system has two further options:
1. Keep Shapekeys: This is enabled by default, since it's the main purpose of this system. All shape keys except the Live Key permanent and temporary keys will be transfered.
2. Apply hidden modifiers: As the name implies, turning this on will also apply modifiers that are hidden in either the viewport or the rendered window.

>[!tip] Python API
>Currently Apply Modifiers is not easily accessible through our API. A current workaround would be to manually do the following steps:
>```python
>from HumGen3D.human.process.apply_modifiers import apply_modifiers, refresh_modapply
>
> # Set rig as active object
> context.view_layer.objects.active = human.objects.rig  
> # Refresh list of modifier types
refresh_modapply(None, context)  
> # Get CollectionProperty of list of modifier types
> col = context.scene.modapply_col  
>   
> # Set a specific modifier type as enabled. NOTE: All types besides Armature and Subdivision Surface are automatically enabled  
> for item in col:  
>     if item.mod_type == "ARMATURE":  
>         item.enabled = True  
>  
> # Call the apply_modifiers function directly
> apply_modifiers(human, context=context)
>```

