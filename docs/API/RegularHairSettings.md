---
accessor: human.hair.regular_hair
---
> Class for manipulating regular (head) hair of human.

Accessible from: `human.hair.regular_hair`
Inherits from [[ImportableHair]], [[BaseHair]], [[PreviewCollectionContent]], [[SavableContent]]


### Properties
---
##### Fast Or Accurate:
```py
human.hair.regular_hair.fast_or_accurate
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Haircard Obj:
```py
human.hair.regular_hair.haircard_obj
>>> Optional[bpy_types.Object]
```
*Read-only*
Blender object of haircards IF generated.   
`Returns Optional[bpy_types.Object] `

---
##### Hue:
```py
human.hair.regular_hair.hue
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Lightness:
```py
human.hair.regular_hair.lightness
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Materials:
```py
human.hair.regular_hair.materials
>>> list
```
*Read-only*
List of materials used for this type of hair.  Usually singleton, but will contain multiple values if haircards are generated.   
`Returns list `

---
##### Modifiers:
```py
human.hair.regular_hair.modifiers
>>> PropCollection
```
*Read-only*
Modifiers associated with the particle systems of this hair type.   
`Returns `[[PropCollection]]` `

---
##### Nodes:
```py
human.hair.regular_hair.nodes
>>> PropCollection
```
*Read-only*
PropCollection of nodes used in the materials for this type of hair. # noqa   
`Returns `[[PropCollection]]` `

---
##### Particle Systems:
```py
human.hair.regular_hair.particle_systems
>>> PropCollection
```
*Read-only*
Get propcollection of particle systems on the human used by this hair type.   
`Returns `[[PropCollection]]` `

---
##### Redness:
```py
human.hair.regular_hair.redness
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Remove Number Suffix:
```py
human.hair.regular_hair.remove_number_suffix
>>> 'function' object has no attribute 'fget'
```
Remove the number suffix from the passed name (i.e. Box.004 becomes Box).   
`Returns 'function' object has no attribute 'fget' `

---
##### Root Lightness:
```py
human.hair.regular_hair.root_lightness
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Root Redness:
```py
human.hair.regular_hair.root_redness
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Roots:
```py
human.hair.regular_hair.roots
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Roots Hue:
```py
human.hair.regular_hair.roots_hue
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Roughness:
```py
human.hair.regular_hair.roughness
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Salt And Pepper:
```py
human.hair.regular_hair.salt_and_pepper
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Save Objects Optimized:
```py
human.hair.regular_hair.save_objects_optimized
>>> 'function' object has no attribute 'fget'
```
Saves the passed objects as a new blend file.  opening the file in the background to make it as small as possible   
`Returns 'function' object has no attribute 'fget' `

---
### Methods
---
##### As Dict
```py
human.hair.regular_hair.as_dict()
>>> dict
```
*Inherited from [[BaseHair]]*
Returns dict of eyebrow settings.   


**Returns:**
- `returns (dict)`: dict[str, Any]

---
##### Convert To Haircards
```py
human.hair.regular_hair.convert_to_haircards(quality: Literal['high'], context: Optional[bpy_types.Context])
>>> Object
```
*Inherited from [[BaseHair]]*
Convert the hair of this type to haircards.  Will generate a mesh object consisting of a haircap and haircards. For eye systems only a haircap will be generated.   

**Arguments:**
- `quality (Literal['high'])`: Quality of the haircards. Defaults to high.
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided.  

**Returns:**
- `returns (`[bpy.types.Object](https://docs.blender.org/api/current/bpy.types.Object.html)`)`: bpy.types.Object

---
##### Delete All
```py
human.hair.regular_hair.delete_all()
>>> NoneType
```
*Inherited from [[BaseHair]]*
No description available.



---
##### Get Categories
```py
human.hair.regular_hair.get_categories()
>>> list
```
*Inherited from [[PreviewCollectionContent]]*
Get a list of categoris this content type is organized in.  You can choose one of these categories to filter the content retreived from get_options().   


**Returns:**
- `returns (list)`: list[str]

---
##### Get Evaluated Particle Systems
```py
human.hair.regular_hair.get_evaluated_particle_systems(context: Optional[bpy_types.Context])
>>> PropCollection
```
*Inherited from [[BaseHair]]*
Get an evaluated version of the particle systems of this hair type.   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided.  

**Returns:**
- `returns (`[[PropCollection]]`)`: PropCollection

---
##### Get Options
```py
human.hair.regular_hair.get_options(context: Optional[bpy_types.Context], category: str)
>>> List[str]
```
*Inherited from [[PreviewCollectionContent]]*
Get a list of options you can use for the set() method of this content.  These represent the choises the user sees in the UI. The output is a list of relative paths to the content files, starting from the Human Generator folder.   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided.
- `category (str)`: Category to filter the content by. Defaults to "All". You can get a list of categories from the get_categories() method.  

**Returns:**
- `returns (List[str])`: List[str]

---
##### Randomize
```py
human.hair.regular_hair.randomize(context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[ImportableHair]]*
Pick a random hairstyle from the library and apply it to the human.   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided. 


---
##### Randomize Color
```py
human.hair.regular_hair.randomize_color()
>>> NoneType
```
*Inherited from [[BaseHair]]*
Randomize the color of the hair of this type. 



---
##### Refresh Pcoll
```py
human.hair.regular_hair.refresh_pcoll(context: Optional[bpy_types.Context], override_category: Optional[str], ignore_searchterm: bool)
>>> NoneType
```
*Inherited from [[PreviewCollectionContent]]*
Refresh the items of this preview collection.  This is low level functionality, you should not need to use this. It is used to refresh the list of possible content for this human. If you use get_options() this is automatically done for you.   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided.
- `override_category (Optional[str])`: Override the category to use, if not provided all items regardless of category will be shown.
- `ignore_searchterm (bool)`: If True, the searchterm set by the user will be ignored. Defaults to False. 


---
##### Remove All
```py
human.hair.regular_hair.remove_all()
>>> NoneType
```
*Inherited from [[ImportableHair]]*
Remove all modifiers of this hair type from the human. 



---
##### Save To Library
```py
human.hair.regular_hair.save_to_library(particle_system_names: list, hairstyle_name: str, category: str, for_male: bool, for_female: bool, thumbnail: Optional[bpy.types.Image], context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[ImportableHair]]*
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
human.hair.regular_hair.set(preset: str, context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[ImportableHair]]*
Loads hair system the user selected.   

**Arguments:**
- `preset (str)`: Name of the preset to load. Must be in the preview collection. Options can be retreived from `get_options()`.
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided. 


---
##### Set Random
```py
human.hair.regular_hair.set_random(context: Optional[bpy_types.Context], update_ui: bool)
>>> NoneType
```
*Inherited from [[PreviewCollectionContent]]*
Set this content type to a random content item.  This will use random.choice to select a random item from the output of get_options().   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided.
- `update_ui (bool)`: Will also show the chosen item as the active thumbnail in the template_icon_view. Defaults to False. 


---
