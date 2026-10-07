> Class for adding/changing the outfit of a human.

    Most of the functionality of this class comes from the [[BaseClothing]] class,
    since outfits and footwear work the same.
    

Accessible from: `human.clothing.outfit`
Inherits from [[BaseClothing]], [[PreviewCollectionContent]], [[SavableContent]]


### Properties
---
##### Objects:
```py
human.clothing.outfit.objects
>>> list
```
*Read-only*
Get a list of the objects this human's outfit consists of.   
`Returns list `

---
##### Pattern:
```py
human.clothing.outfit.pattern
>>> PatternSettings
```
*Read-only*
Gives access to PatternSettings to add/change patterns on this clothing.   
`Returns `[[PatternSettings]]` `

---
##### Remove Number Suffix:
```py
human.clothing.outfit.remove_number_suffix
>>> 'function' object has no attribute 'fget'
```
Remove the number suffix from the passed name (i.e. Box.004 becomes Box).   
`Returns 'function' object has no attribute 'fget' `

---
##### Save Objects Optimized:
```py
human.clothing.outfit.save_objects_optimized
>>> 'function' object has no attribute 'fget'
```
Saves the passed objects as a new blend file.  opening the file in the background to make it as small as possible   
`Returns 'function' object has no attribute 'fget' `

---
### Methods
---
##### Add Obj
```py
human.clothing.outfit.add_obj(cloth_obj: Object, cloth_type: Literal['pants', 'top', 'full'], context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[BaseClothing]]*
Add an object you created yourself as footwear to this human.   

**Arguments:**
- `cloth_obj (`[bpy.types.Object](https://docs.blender.org/api/current/bpy.types.Object.html)`)`: Blender object to add as footwear. Make sure it's located in the correct place (on the feet of this human).
- `cloth_type (Literal['pants', 'top', 'full'])`: What part of the body this clothing item covers. This influences what corrective shapekeys are added to the item.
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided. 


---
##### As Dict
```py
human.clothing.outfit.as_dict()
>>> dict
```
*Inherited from [[BaseClothing]]*
Returns a dictionary representation of this clothing.   


**Returns:**
- `returns (dict)`: dict[str, Any]

---
##### Deform Cloth To Human
```py
human.clothing.outfit.deform_cloth_to_human(context: Context, cloth_obj: Object)
>>> NoneType
```
*Inherited from [[BaseClothing]]*
Deforms the cloth object to the shape of the active HumGen human.  Mainly meant for internal use, but might be useful. Expects the passed cloth_obj to fit for a standard HG human with no adjustments. Will modify the hsape of the object to fit the evaluated shape of the human, with body proportions and height taken into account.   

**Arguments:**
- `context (`[bpy.types.Context](https://docs.blender.org/api/current/bpy.types.Context.html)`)`: Blender context.
- `cloth_obj (`[bpy.types.Object](https://docs.blender.org/api/current/bpy.types.Object.html)`)`: cloth object to deform 


---
##### Get Categories
```py
human.clothing.outfit.get_categories()
>>> list
```
*Inherited from [[PreviewCollectionContent]]*
Get a list of categoris this content type is organized in.  You can choose one of these categories to filter the content retreived from get_options().   


**Returns:**
- `returns (list)`: list[str]

---
##### Get Options
```py
human.clothing.outfit.get_options(context: Optional[bpy_types.Context], category: str)
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
##### Randomize Colors
```py
human.clothing.outfit.randomize_colors(cloth_obj: Object, context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[BaseClothing]]*
Randomizes the colors of the passed clothing object.   

**Arguments:**
- `cloth_obj (`[bpy.types.Object](https://docs.blender.org/api/current/bpy.types.Object.html)`)`: Blender object that is currently loaded on this human as clothing.
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided. 


---
##### Refresh Pcoll
```py
human.clothing.outfit.refresh_pcoll(context: Optional[bpy_types.Context], override_category: Optional[str], ignore_searchterm: bool)
>>> NoneType
```
*Inherited from [[PreviewCollectionContent]]*
Refresh the items of this preview collection.  This is low level functionality, you should not need to use this. It is used to refresh the list of possible content for this human. If you use get_options() this is automatically done for you.   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided.
- `override_category (Optional[str])`: Override the category to use, if not provided all items regardless of category will be shown.
- `ignore_searchterm (bool)`: If True, the searchterm set by the user will be ignored. Defaults to False. 


---
##### Remove
```py
human.clothing.outfit.remove()
>>> list
```
*Inherited from [[BaseClothing]]*
Removes the cloth objects of this category that are currently on the human.   


**Returns:**
- `returns (list)`: list

---
##### Save To Library
```py
human.clothing.outfit.save_to_library(name: str, for_male: bool, for_female: bool, open_when_finished: bool, category: str, thumbnail: Optional[bpy.types.Image], context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[BaseClothing]]*
Save the currently active footwear/clothing to the HumGen library.  This will make this item accessible in future projects.   

**Arguments:**
- `name (str)`: Name of the item to save.
- `for_male (bool)`: Whether to make the item available for male humans. Defaults to True.
- `for_female (bool)`: Whether to make the item available for female humans. Defaults to True.
- `open_when_finished (bool)`: Whether to open the created .blend files in new windows after saving. Defaults to False.
- `category (str)`: Category to save the item to. Defaults to "Custom". This is the folder the item will be saved in.
- `thumbnail (Optional[bpy.types.Image])`: Image to use as thumbnail for the item. Has to be loaded in Blender. If None, NO thumbnail will be saved.
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided. 


---
##### Set
```py
human.clothing.outfit.set(preset: str, context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[BaseClothing]]*
Gets called by pcoll_outfit or pcoll_footwear to load the selected outfit.   

**Arguments:**
- `preset (str)`: Relative path of the preset to load. Get options from the `get_options` method.
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided. 


---
##### Set Random
```py
human.clothing.outfit.set_random(context: Optional[bpy_types.Context], update_ui: bool)
>>> NoneType
```
*Inherited from [[PreviewCollectionContent]]*
Set this content type to a random content item.  This will use random.choice to select a random item from the output of get_options().   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided.
- `update_ui (bool)`: Will also show the chosen item as the active thumbnail in the template_icon_view. Defaults to False. 


---
##### Set Texture Resolution
```py
human.clothing.outfit.set_texture_resolution(clothing_item: Object, resolution_category: Literal['high', 'optimised', 'performance'])
>>> NoneType
```
*Inherited from [[BaseClothing]]*
Sets the texture resolution of the passed clothing to the passed resolution.   

**Arguments:**
- `clothing_item (`[bpy.types.Object](https://docs.blender.org/api/current/bpy.types.Object.html)`)`: Blender object that is currently loaded on this human as clothing.
- `resolution_category (Literal['high', 'optimised', 'performance'])`:  Resolution category to set the textures to. 


---
