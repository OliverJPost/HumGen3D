> Class for changing the skin texture of the human.

Accessible from: `human.skin.texture`
Inherits from [[PreviewCollectionContent]]


### Methods
---
##### Get Categories
```py
human.skin.texture.get_categories()
>>> list
```
*Inherited from [[PreviewCollectionContent]]*
Get a list of categoris this content type is organized in.  You can choose one of these categories to filter the content retreived from get_options().   


**Returns:**
- `returns (list)`: list[str]

---
##### Get Options
```py
human.skin.texture.get_options(context: Optional[bpy_types.Context], category: str)
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
##### Refresh Pcoll
```py
human.skin.texture.refresh_pcoll(context: Optional[bpy_types.Context], override_category: Optional[str], ignore_searchterm: bool)
>>> NoneType
```
*Inherited from [[PreviewCollectionContent]]*
Refresh the items of this preview collection.  This is low level functionality, you should not need to use this. It is used to refresh the list of possible content for this human. If you use get_options() this is automatically done for you.   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided.
- `override_category (Optional[str])`: Override the category to use, if not provided all items regardless of category will be shown.
- `ignore_searchterm (bool)`: If True, the searchterm set by the user will be ignored. Defaults to False. 


---
##### Save Thumb
```py
human.skin.texture.save_thumb()
>>> None
```
*Inherited from [[Could not find source]]*
No description available.


**Returns:**
- `returns (None)`: 

---
##### Save To Library
```py
human.skin.texture.save_to_library(save_name: str, thumbnail: Optional[bpy.types.Image])
>>> NoneType
```
*Inherited from [[Could not find source]]*
No description available.

**Arguments:**
- `save_name (str)`: 
- `thumbnail (Optional[bpy.types.Image])`: 


---
##### Set
```py
human.skin.texture.set(textureset_path: str)
>>> NoneType
```
*Inherited from [[PreviewCollectionContent]]*
Set the skin texture from a textureset from the HumGen library.   

**Arguments:**
- `textureset_path (str)`: Relative path to the textureset. Can be found from the `get_options` method. 


---
##### Set Random
```py
human.skin.texture.set_random(context: Optional[bpy_types.Context], update_ui: bool)
>>> NoneType
```
*Inherited from [[PreviewCollectionContent]]*
Set this content type to a random content item.  This will use random.choice to select a random item from the output of get_options().   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided.
- `update_ui (bool)`: Will also show the chosen item as the active thumbnail in the template_icon_view. Defaults to False. 


---
