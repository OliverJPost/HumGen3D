> Class for manipulating pose of human.

Accessible from: `human.pose`
Inherits from [[PreviewCollectionContent]], [[SavableContent]]


### Properties
---
##### Remove Number Suffix:
```py
human.pose.remove_number_suffix
>>> 'function' object has no attribute 'fget'
```
Remove the number suffix from the passed name (i.e. Box.004 becomes Box).   
`Returns 'function' object has no attribute 'fget' `

---
##### Save Objects Optimized:
```py
human.pose.save_objects_optimized
>>> 'function' object has no attribute 'fget'
```
Saves the passed objects as a new blend file.  opening the file in the background to make it as small as possible   
`Returns 'function' object has no attribute 'fget' `

---
### Methods
---
##### As Dict
```py
human.pose.as_dict()
>>> dict
```
*Inherited from [[Could not find source]]*
Pose settings as dict.   


**Returns:**
- `returns (dict)`: dict[str, Any]

---
##### Get Categories
```py
human.pose.get_categories()
>>> list
```
*Inherited from [[PreviewCollectionContent]]*
Get a list of categoris this content type is organized in.  You can choose one of these categories to filter the content retreived from get_options().   


**Returns:**
- `returns (list)`: list[str]

---
##### Get Options
```py
human.pose.get_options(context: Optional[bpy_types.Context], category: str)
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
human.pose.refresh_pcoll(context: Optional[bpy_types.Context], override_category: Optional[str], ignore_searchterm: bool)
>>> NoneType
```
*Inherited from [[PreviewCollectionContent]]*
Refresh the items of this preview collection.  This is low level functionality, you should not need to use this. It is used to refresh the list of possible content for this human. If you use get_options() this is automatically done for you.   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided.
- `override_category (Optional[str])`: Override the category to use, if not provided all items regardless of category will be shown.
- `ignore_searchterm (bool)`: If True, the searchterm set by the user will be ignored. Defaults to False. 


---
##### Save To Library
```py
human.pose.save_to_library(name: str, category: str, thumbnail: Optional[bpy.types.Image], context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[SavableContent]]*
Save current pose to the Human Generator pose library.   

**Arguments:**
- `name (str)`: Name to save the pose as.
- `category (str)`: Category to save the pose in. If the category does not exist, a new folder is created. Defaults to "Custom".
- `thumbnail (Optional[bpy.types.Image])`: Thumbnail to use for the pose. If None, no thumbnail is saved. Defaults to None.
- `context (Optional[bpy_types.Context])`: Context to use. Defaults to None. 


---
##### Set
```py
human.pose.set(preset: str, context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[PreviewCollectionContent]]*
Set a pose from the Human Generator pose library.   

**Arguments:**
- `preset (str)`: Name of the pose to set, you can get options from the `get_options` method.
- `context (Optional[bpy_types.Context])`: Context to use. Defaults to None. 


---
##### Set Random
```py
human.pose.set_random(context: Optional[bpy_types.Context], update_ui: bool)
>>> NoneType
```
*Inherited from [[PreviewCollectionContent]]*
Set this content type to a random content item.  This will use random.choice to select a random item from the output of get_options().   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided.
- `update_ui (bool)`: Will also show the chosen item as the active thumbnail in the template_icon_view. Defaults to False. 


---
