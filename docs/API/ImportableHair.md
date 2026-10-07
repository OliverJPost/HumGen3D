##### Randomize
```py
human.hair.face_hair.randomize(context: Optional[bpy_types.Context])
>>> NoneType
```
Pick a random hairstyle from the library and apply it to the human.   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided. 


---
##### Remove All
```py
human.hair.face_hair.remove_all()
>>> NoneType
```
Remove all modifiers of this hair type from the human. 



---
##### Save To Library
```py
human.hair.face_hair.save_to_library(particle_system_names: list, hairstyle_name: str, category: str, for_male: bool, for_female: bool, thumbnail: Optional[bpy.types.Image], context: Optional[bpy_types.Context])
>>> NoneType
```
Save the currently active hair system of this type to the HG library.   

**Arguments:**
- `particle_system_names (list)`: Names of the particle systems to save.
- `hairstyle_name (str)`: Name to save this hairstyle as.
- `category (str)`: Category to save this hairstyle in. If this category does not already exist, a new folder will be created.
- `for_male (bool)`: Whether this hairstyle is available for male humans.
- `for_female (bool)`: Whether this hairstyle is available for female humans.
- `thumbnail (Optional[bpy.types.Image])`: Thumbnail to save with this hairstyle. Pass a Blender Image object here. If None, no thumbnail will be used.
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided. 


---
##### Set
```py
human.hair.face_hair.set(preset: str, context: Optional[bpy_types.Context])
>>> NoneType
```
Loads hair system the user selected.   

**Arguments:**
- `preset (str)`: Name of the preset to load. Must be in the preview collection. Options can be retreived from `get_options()`.
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided. 


---
