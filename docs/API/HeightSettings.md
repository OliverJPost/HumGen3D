> Class for changing height of human.

Accessible from: `human.height`


### Properties
---
##### Centimeters:
```py
human.height.centimeters
>>> int
```
*Read-only*
Height of human in centimeters.   
`Returns int `

---
##### Meters:
```py
human.height.meters
>>> float
```
*Read-only*
Height of human in meters.   
`Returns float `

---
### Methods
---
##### As Dict
```py
human.height.as_dict()
>>> dict
```
*Inherited from [[Could not find source]]*
Returns height of human as dictionary.   


**Returns:**
- `returns (dict)`: dict[str, float]

---
##### Randomize
```py
human.height.randomize(context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[Could not find source]]*
Randomize human height.   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided. 


---
##### Set
```py
human.height.set(value_cm: float, context: Optional[bpy_types.Context], realtime: bool)
>>> NoneType
```
*Inherited from [[Could not find source]]*
Sets height of human.   

**Arguments:**
- `value_cm (float)`: Height of human in centimeters.
- `context (Optional[bpy_types.Context])`: Blender context. Defaults to None.
- `realtime (bool)`: Whether to update the human in realtime. Only needed for sliders in the UI. Defaults to False. 


---
##### Set From Dict
```py
human.height.set_from_dict(data: dict, context: Optional[bpy_types.Context])
>>> list
```
*Inherited from [[Could not find source]]*
Sets height of human from dictionary.   

**Arguments:**
- `data (dict)`: Dictionary with height of human.
- `context (Optional[bpy_types.Context])`: Blender context. Defaults to None.  

**Returns:**
- `returns (list)`: list[str]

---
