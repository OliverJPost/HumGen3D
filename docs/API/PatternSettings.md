> Class for changing patterns on individual clothing items.

Accessible from: `human.clothing.footwear.pattern`
Inherits from [[PreviewCollectionContent]]


### Methods
---
##### Get Categories
```py
human.clothing.footwear.pattern.get_categories()
>>> list
```
*Inherited from [[PreviewCollectionContent]]*
Get a list of categoris this content type is organized in.  You can choose one of these categories to filter the content retreived from get_options().   


**Returns:**
- `returns (list)`: list[str]

---
##### Get Options
```py
human.clothing.footwear.pattern.get_options(context: Optional[bpy_types.Context], category: str)
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
human.clothing.footwear.pattern.refresh_pcoll(context: Optional[bpy_types.Context], override_category: Optional[str], ignore_searchterm: bool)
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
human.clothing.footwear.pattern.remove(obj: Object)
>>> NoneType
```
*Inherited from [[Could not find source]]*
Remove pattern from passed object.   

**Arguments:**
- `obj (`[bpy.types.Object](https://docs.blender.org/api/current/bpy.types.Object.html)`)`: Object to remove pattern from. 


---
##### Set
```py
human.clothing.footwear.pattern.set(preset: str, obj: Object)
>>> NoneType
```
*Inherited from [[PreviewCollectionContent]]*
Loads passed pattern on passed object.  NOTE: Expects passed object to use HG clothing material.   

**Arguments:**
- `preset (str)`: Relative path of pattern to load.
- `obj (`[bpy.types.Object](https://docs.blender.org/api/current/bpy.types.Object.html)`)`: Object to apply pattern to. 


---
##### Set Random
```py
human.clothing.footwear.pattern.set_random(obj: Object, context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[PreviewCollectionContent]]*
Set a random pattern as active on the passed object.   

**Arguments:**
- `obj (`[bpy.types.Object](https://docs.blender.org/api/current/bpy.types.Object.html)`)`: Object to add pattern to.
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided. 


---
