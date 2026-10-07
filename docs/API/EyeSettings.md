---
accessor: human.eyes
---
> Class for manipulating the eyes of the human.

    Also contains properties for changing the material values.
    

Accessible from: `human.eyes`


### Properties
---
##### Eye Obj:
```py
human.eyes.eye_obj
>>> Object
```
*Read-only*
Blender object of the eyes of the human.   
`Returns `[bpy.types.Object](https://docs.blender.org/api/current/bpy.types.Object.html)` `

---
##### Inner Material:
```py
human.eyes.inner_material
>>> Material
```
*Read-only*
The material used for the inner part of the eyes (The colored part).   
`Returns Material `

---
##### Iris Color:
```py
human.eyes.iris_color
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Nodes:
```py
human.eyes.nodes
>>> PropCollection
```
*Read-only*
Nodes of the inner eye material.   
`Returns `[[PropCollection]]` `

---
##### Outer Material:
```py
human.eyes.outer_material
>>> Material
```
*Read-only*
The material used for the outer layer of the eyes (The transparent part).   
`Returns Material `

---
##### Sclera Color:
```py
human.eyes.sclera_color
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
### Methods
---
##### As Dict
```py
human.eyes.as_dict()
>>> dict
```
*Inherited from [[Could not find source]]*
Returns the current eye settings as a dictionary.   


**Returns:**
- `returns (dict)`: dict

---
##### Randomize
```py
human.eyes.randomize()
>>> NoneType
```
*Inherited from [[Could not find source]]*
Randomizes the color of the pupils based on worlwide statistics. 



---
##### Set From Dict
```py
human.eyes.set_from_dict(data: dict)
>>> list
```
*Inherited from [[Could not find source]]*
Sets the eye settings from a dictionary.  This dict can be derived from the as_dict method.   

**Arguments:**
- `data (dict)`: Dictionary to set the eye settings from.  

**Returns:**
- `returns (list)`: list[str]

---
