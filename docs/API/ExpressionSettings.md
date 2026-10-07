---
accessor: human.expression
---
> Class for manipulating human expression.

    Either using 1-click expressions or with the facial rig.
    

Accessible from: `human.expression`
Inherits from [[PreviewCollectionContent]]


### Properties
---
##### Keys:
```py
human.expression.keys
>>> list
```
*Read-only*
Filtered list from HumGen3D.human.keys for keys part of expressions.   
`Returns list `

---
### Methods
---
##### Get Categories
```py
human.expression.get_categories()
>>> list
```
*Inherited from [[PreviewCollectionContent]]*
Get a list of categoris this content type is organized in.  You can choose one of these categories to filter the content retreived from get_options().   


**Returns:**
- `returns (list)`: list[str]

---
##### Get Options
```py
human.expression.get_options(context: Optional[bpy_types.Context], category: str)
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
##### Load Facial Rig
```py
human.expression.load_facial_rig(context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[Could not find source]]*
Imports all necessary shape keys and unhides the bones used to control face.   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided. 


---
##### Refresh Pcoll
```py
human.expression.refresh_pcoll(context: Optional[bpy_types.Context], override_category: Optional[str], ignore_searchterm: bool)
>>> NoneType
```
*Inherited from [[PreviewCollectionContent]]*
Refresh the items of this preview collection.  This is low level functionality, you should not need to use this. It is used to refresh the list of possible content for this human. If you use get_options() this is automatically done for you.   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided.
- `override_category (Optional[str])`: Override the category to use, if not provided all items regardless of category will be shown.
- `ignore_searchterm (bool)`: If True, the searchterm set by the user will be ignored. Defaults to False. 


---
##### Remove Facial Rig
```py
human.expression.remove_facial_rig()
>>> NoneType
```
*Inherited from [[Could not find source]]*
Remove the facial rig from the human, including all it's shape keys.  Will also hide the bones again.   



---
##### Set
```py
human.expression.set(preset: str)
>>> NoneType
```
*Inherited from [[PreviewCollectionContent]]*
Loads the passed 1-click expression preset on the human.  This will import the shapekey from the .npz file and set the value to 1.0.   

**Arguments:**
- `preset (str)`: Preset to load. You can get a list of available presets with `get_options()`. 


---
##### Set Random
```py
human.expression.set_random(context: Optional[bpy_types.Context], update_ui: bool)
>>> NoneType
```
*Inherited from [[PreviewCollectionContent]]*
Set this content type to a random content item.  This will use random.choice to select a random item from the output of get_options().   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided.
- `update_ui (bool)`: Will also show the chosen item as the active thumbnail in the template_icon_view. Defaults to False. 


---
