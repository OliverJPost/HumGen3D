> Class for manipulating human eyebrows.

Accessible from: `human.hair.eyebrows`
Inherits from [[BaseHair]]


### Properties
---
##### Fast Or Accurate:
```py
human.hair.eyebrows.fast_or_accurate
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Haircard Obj:
```py
human.hair.eyebrows.haircard_obj
>>> Optional[bpy_types.Object]
```
*Read-only*
Blender object of haircards IF generated.   
`Returns Optional[bpy_types.Object] `

---
##### Hue:
```py
human.hair.eyebrows.hue
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Lightness:
```py
human.hair.eyebrows.lightness
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Materials:
```py
human.hair.eyebrows.materials
>>> list
```
*Read-only*
List of materials used for this type of hair.  Usually singleton, but will contain multiple values if haircards are generated.   
`Returns list `

---
##### Modifiers:
```py
human.hair.eyebrows.modifiers
>>> PropCollection
```
*Read-only*
Modifiers associated with the particle systems of this hair type.   
`Returns `[[PropCollection]]` `

---
##### Nodes:
```py
human.hair.eyebrows.nodes
>>> PropCollection
```
*Read-only*
PropCollection of nodes used in the materials for this type of hair. # noqa   
`Returns `[[PropCollection]]` `

---
##### Particle Systems:
```py
human.hair.eyebrows.particle_systems
>>> PropCollection
```
*Read-only*
Get propcollection of particle systems on the human used by this hair type.   
`Returns `[[PropCollection]]` `

---
##### Redness:
```py
human.hair.eyebrows.redness
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Root Lightness:
```py
human.hair.eyebrows.root_lightness
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Root Redness:
```py
human.hair.eyebrows.root_redness
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Roots:
```py
human.hair.eyebrows.roots
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Roots Hue:
```py
human.hair.eyebrows.roots_hue
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Roughness:
```py
human.hair.eyebrows.roughness
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Salt And Pepper:
```py
human.hair.eyebrows.salt_and_pepper
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
### Methods
---
##### As Dict
```py
human.hair.eyebrows.as_dict()
>>> dict
```
*Inherited from [[BaseHair]]*
Returns dict of eyebrow settings.   


**Returns:**
- `returns (dict)`: dict[str, Any]

---
##### Convert To Haircards
```py
human.hair.eyebrows.convert_to_haircards(quality: Literal['high'], context: Optional[bpy_types.Context])
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
human.hair.eyebrows.delete_all()
>>> NoneType
```
*Inherited from [[BaseHair]]*
No description available.



---
##### Get Evaluated Particle Systems
```py
human.hair.eyebrows.get_evaluated_particle_systems(context: Optional[bpy_types.Context])
>>> PropCollection
```
*Inherited from [[BaseHair]]*
Get an evaluated version of the particle systems of this hair type.   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided.  

**Returns:**
- `returns (`[[PropCollection]]`)`: PropCollection

---
##### Randomize Color
```py
human.hair.eyebrows.randomize_color()
>>> NoneType
```
*Inherited from [[BaseHair]]*
Randomize the color of the hair of this type. 



---
##### Remove Unused
```py
human.hair.eyebrows.remove_unused(context: Optional[bpy_types.Context], _internal: bool)
>>> NoneType
```
*Inherited from [[Could not find source]]*
Remove unused eyebrow systems.   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context. Defaults to None. 
- `_internal (bool)`: No description


---
##### Set
```py
human.hair.eyebrows.set(preset_eyebrow: str)
>>> NoneType
```
*Inherited from [[Could not find source]]*
Sets the eyebrow named in preset_data as the only visible eyebrow system.   

**Arguments:**
- `preset_eyebrow (str)`: Name of eyebrows to set as active 


---
