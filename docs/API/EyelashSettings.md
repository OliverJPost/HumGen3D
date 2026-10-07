---
accessor: human.hair.eyelashes
---
> Class for manipulating eyelashes of human.

Accessible from: `human.hair.eyelashes`
Inherits from [[BaseHair]]


### Properties
---
##### Fast Or Accurate:
```py
human.hair.eyelashes.fast_or_accurate
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Haircard Obj:
```py
human.hair.eyelashes.haircard_obj
>>> Optional[bpy_types.Object]
```
*Read-only*
Blender object of haircards IF generated.   
`Returns Optional[bpy_types.Object] `

---
##### Hue:
```py
human.hair.eyelashes.hue
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Lightness:
```py
human.hair.eyelashes.lightness
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Materials:
```py
human.hair.eyelashes.materials
>>> list
```
*Read-only*
List of materials used for this type of hair.  Usually singleton, but will contain multiple values if haircards are generated.   
`Returns list `

---
##### Modifiers:
```py
human.hair.eyelashes.modifiers
>>> PropCollection
```
*Read-only*
Modifiers associated with the particle systems of this hair type.   
`Returns `[[PropCollection]]` `

---
##### Nodes:
```py
human.hair.eyelashes.nodes
>>> PropCollection
```
*Read-only*
PropCollection of nodes used in the materials for this type of hair. # noqa   
`Returns `[[PropCollection]]` `

---
##### Particle Systems:
```py
human.hair.eyelashes.particle_systems
>>> PropCollection
```
*Read-only*
Get propcollection of particle systems on the human used by this hair type.   
`Returns `[[PropCollection]]` `

---
##### Redness:
```py
human.hair.eyelashes.redness
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Root Lightness:
```py
human.hair.eyelashes.root_lightness
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Root Redness:
```py
human.hair.eyelashes.root_redness
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Roots:
```py
human.hair.eyelashes.roots
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Roots Hue:
```py
human.hair.eyelashes.roots_hue
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Roughness:
```py
human.hair.eyelashes.roughness
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Salt And Pepper:
```py
human.hair.eyelashes.salt_and_pepper
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
### Methods
---
##### As Dict
```py
human.hair.eyelashes.as_dict()
>>> dict
```
*Inherited from [[BaseHair]]*
Return a dictionary representation of this hair type.  Contains information about material.   


**Returns:**
- `returns (dict)`: dict[str, Any]

---
##### Convert To Haircards
```py
human.hair.eyelashes.convert_to_haircards(quality: Literal['high'], context: Optional[bpy_types.Context])
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
human.hair.eyelashes.delete_all()
>>> NoneType
```
*Inherited from [[BaseHair]]*
No description available.



---
##### Get Evaluated Particle Systems
```py
human.hair.eyelashes.get_evaluated_particle_systems(context: Optional[bpy_types.Context])
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
human.hair.eyelashes.randomize_color()
>>> NoneType
```
*Inherited from [[BaseHair]]*
Randomize the color of the hair of this type. 



---
