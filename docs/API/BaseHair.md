##### As Dict
```py
human.hair.eyebrows.as_dict()
>>> dict
```
Returns dict of eyebrow settings.   


**Returns:**
- `returns (dict)`: dict[str, Any]

---
##### Convert To Haircards
```py
human.hair.eyebrows.convert_to_haircards(quality: Literal['high'], context: Optional[bpy_types.Context])
>>> Object
```
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
No description available.



---
##### Get Evaluated Particle Systems
```py
human.hair.eyebrows.get_evaluated_particle_systems(context: Optional[bpy_types.Context])
>>> PropCollection
```
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
Randomize the color of the hair of this type. 



---
