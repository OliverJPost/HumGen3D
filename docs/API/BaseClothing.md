##### Add Obj
```py
human.clothing.footwear.add_obj(cloth_obj: Object, context: Optional[bpy_types.Context])
>>> NoneType
```
Add an object you created yourself as footwear to this human.   

**Arguments:**
- `cloth_obj (`[bpy.types.Object](https://docs.blender.org/api/current/bpy.types.Object.html)`)`: Blender object to add as footwear. Make sure it's located in the correct place (on the feet of this human).
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided. 


---
##### As Dict
```py
human.clothing.footwear.as_dict()
>>> dict
```
Returns a dictionary representation of this clothing.   


**Returns:**
- `returns (dict)`: dict[str, Any]

---
##### Deform Cloth To Human
```py
human.clothing.footwear.deform_cloth_to_human(context: Context, cloth_obj: Object)
>>> NoneType
```
Deforms the cloth object to the shape of the active HumGen human.  Mainly meant for internal use, but might be useful. Expects the passed cloth_obj to fit for a standard HG human with no adjustments. Will modify the hsape of the object to fit the evaluated shape of the human, with body proportions and height taken into account.   

**Arguments:**
- `context (`[bpy.types.Context](https://docs.blender.org/api/current/bpy.types.Context.html)`)`: Blender context.
- `cloth_obj (`[bpy.types.Object](https://docs.blender.org/api/current/bpy.types.Object.html)`)`: cloth object to deform 


---
##### Randomize Colors
```py
human.clothing.footwear.randomize_colors(cloth_obj: Object, context: Optional[bpy_types.Context])
>>> NoneType
```
Randomizes the colors of the passed clothing object.   

**Arguments:**
- `cloth_obj (`[bpy.types.Object](https://docs.blender.org/api/current/bpy.types.Object.html)`)`: Blender object that is currently loaded on this human as clothing.
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided. 


---
##### Remove
```py
human.clothing.footwear.remove()
>>> list
```
Removes the cloth objects of this category that are currently on the human.   


**Returns:**
- `returns (list)`: list

---
##### Save To Library
```py
human.clothing.footwear.save_to_library(name: str, for_male: bool, for_female: bool, open_when_finished: bool, category: str, thumbnail: Optional[bpy.types.Image], context: Optional[bpy_types.Context])
>>> NoneType
```
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
human.clothing.footwear.set(preset: str, context: Optional[bpy_types.Context])
>>> NoneType
```
Gets called by pcoll_outfit or pcoll_footwear to load the selected outfit.   

**Arguments:**
- `preset (str)`: Relative path of the preset to load. Get options from the `get_options` method.
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided. 


---
##### Set Texture Resolution
```py
human.clothing.footwear.set_texture_resolution(clothing_item: Object, resolution_category: Literal['high', 'optimised', 'performance'])
>>> NoneType
```
Sets the texture resolution of the passed clothing to the passed resolution.   

**Arguments:**
- `clothing_item (`[bpy.types.Object](https://docs.blender.org/api/current/bpy.types.Object.html)`)`: Blender object that is currently loaded on this human as clothing.
- `resolution_category (Literal['high', 'optimised', 'performance'])`:  Resolution category to set the textures to. 


---
