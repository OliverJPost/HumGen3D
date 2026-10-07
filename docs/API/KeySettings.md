---
accessor: human.keys
---
> Class for changing the shape keys and  LiveKeys of this human.

Accessible from: `human.keys`


### Properties
---
##### All Added Shapekeys:
```py
human.keys.all_added_shapekeys
>>> List[HumGen3D.human.keys.keys.ShapeKeyItem]
```
*Read-only*
A list of all ShapeKeyItems that were added by the user or converted from lk.   
`Returns List[HumGen3D.human.keys.keys.ShapeKeyItem] `

---
##### All Deformation Shapekeys:
```py
human.keys.all_deformation_shapekeys
>>> List[HumGen3D.human.keys.keys.ShapeKeyItem]
```
*Read-only*
A list of ShapeKeyItems that are used for deformation.  This means they are not used for animation, but for changing the base shape of the human. It leaves out the Basis key, the corrective keys, the eye look keys, and the expression keys.   
`Returns List[HumGen3D.human.keys.keys.ShapeKeyItem] `

---
##### All Keys:
```py
human.keys.all_keys
>>> List[Union[HumGen3D.human.keys.keys.LiveKeyItem, HumGen3D.human.keys.keys.ShapeKeyItem]]
```
*Read-only*
A list of all ShapeKeyItems and LiveKeyItems of this human.   
`Returns List[Union[HumGen3D.human.keys.keys.LiveKeyItem, HumGen3D.human.keys.keys.ShapeKeyItem]] `

---
##### All Livekeys:
```py
human.keys.all_livekeys
>>> List[HumGen3D.human.keys.keys.LiveKeyItem]
```
*Read-only*
A list of all LiveKeyItems of this human.   
`Returns List[HumGen3D.human.keys.keys.LiveKeyItem] `

---
##### All Shapekeys:
```py
human.keys.all_shapekeys
>>> List[HumGen3D.human.keys.keys.ShapeKeyItem]
```
*Read-only*
A list of all ShapeKeyItems of this human.   
`Returns List[HumGen3D.human.keys.keys.ShapeKeyItem] `

---
##### Permanent Key:
```py
human.keys.permanent_key
>>> ShapeKey
```
*Read-only*
The permanent shape key used for livekeying. Points to the Blender key.   
`Returns ShapeKey `

---
##### Temp Key:
```py
human.keys.temp_key
>>> ShapeKey
```
*Read-only*
The temporary shape key used for livekeying. Points to the Blender key.   
`Returns ShapeKey `

---
### Methods
---
##### As Dict
```py
human.keys.as_dict()
>>> dict
```
*Inherited from [[Could not find source]]*
Get the current shape key and live key values as a dictionary.   


**Returns:**
- `returns (dict)`: dict[str, float]

---
##### Filtered
```py
human.keys.filtered(category: str, subcategory: Optional[str])
>>> List[Union[HumGen3D.human.keys.keys.LiveKeyItem, HumGen3D.human.keys.keys.ShapeKeyItem]]
```
*Inherited from [[Could not find source]]*
Get all keys that match the given category and subcategory.   

**Arguments:**
- `category (str)`: The category to filter for.
- `subcategory (Optional[str])`: The subcategory to filter for.  

**Returns:**
- `returns (List[Union[HumGen3D.human.keys.keys.LiveKeyItem, HumGen3D.human.keys.keys.ShapeKeyItem]])`: List[Union[LiveKeyItem, ShapeKeyItem]]

---
##### Get
```py
human.keys.get(name: str)
>>> Union[HumGen3D.human.keys.keys.ShapeKeyItem, HumGen3D.human.keys.keys.LiveKeyItem, NoneType]
```
*Inherited from [[Could not find source]]*
No description available.

**Arguments:**
- `name (str)`: 

**Returns:**
- `returns (Union[HumGen3D.human.keys.keys.ShapeKeyItem, HumGen3D.human.keys.keys.LiveKeyItem, NoneType])`: 

---
##### Load From Npz
```py
human.keys.load_from_npz(npz_filepath: str, obj_override: Optional[bpy_types.Object])
>>> ShapeKey
```
*Inherited from [[Could not find source]]*
Creates new shapekey on the body or the passed obj_override from a npz file.  This .npy file contains a one dimensional array with coordinates of the shape key, RELATIVE to the base coordinates of the body.   

**Arguments:**
- `npz_filepath (str)`: Path to the .npz file
- `obj_override (Optional[bpy_types.Object])`: Add the shape key to this object instead of to the body object. Defaults to None.  

**Returns:**
- `returns (ShapeKey)`: bpy.types.ShapeKey

---
##### Set From Dict
```py
human.keys.set_from_dict(key_dict: dict, context: Optional[bpy_types.Context])
>>> list
```
*Inherited from [[Could not find source]]*
Set the shape key and live key values from a dictionary.   

**Arguments:**
- `key_dict (dict)`: Dictionary of shape key and live key values
- `context (Optional[bpy_types.Context])`: Blender context. Defaults to None.  

**Returns:**
- `returns (list)`: list[str]

---
##### Update Human From Key Change
```py
human.keys.update_human_from_key_change(context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[Could not find source]]*
Update the human mesh from the current live key values.  This is used when updating a live key directly or after changing multiple livekeys with their `set_without_update` method.   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. Defaults to None. 


---
