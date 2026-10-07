> Class for manipulating skin material of human.

Accessible from: `human.skin`


### Properties
---
##### Cavity Strength:
```py
human.skin.cavity_strength
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Freckles:
```py
human.skin.freckles
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Gender Specific:
```py
human.skin.gender_specific
>>> Union[HumGen3D.human.skin.skin.MaleSkin, HumGen3D.human.skin.skin.FemaleSkin]
```
*Read-only*
Returns an instance to change node settings specifically related to gender.   
`Returns Union[HumGen3D.human.skin.skin.MaleSkin, HumGen3D.human.skin.skin.FemaleSkin] `

---
##### Links:
```py
human.skin.links
>>> SkinLinks
```
*Read-only*
All links on the human skin material.   
`Returns `[[SkinLinks]]` `

---
##### Material:
```py
human.skin.material
>>> Material
```
*Read-only*
Human skin material.   
`Returns Material `

---
##### Nodes:
```py
human.skin.nodes
>>> SkinNodes
```
*Read-only*
All nodes of the human skin material.   
`Returns `[[SkinNodes]]` `

---
##### Normal Strength:
```py
human.skin.normal_strength
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Redness:
```py
human.skin.redness
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Roughness Multiplier:
```py
human.skin.roughness_multiplier
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Saturation:
```py
human.skin.saturation
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Splotches:
```py
human.skin.splotches
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
##### Texture:
```py
human.skin.texture
>>> TextureSettings
```
*Read-only*
Gives acces to texture settings, for setting and changing textures.   
`Returns `[[TextureSettings]]` `

---
##### Tone:
```py
human.skin.tone
>>> 'NoneType' object has no attribute 'fget'
```
No docstring available.
`Returns 'NoneType' object has no attribute 'fget' `

---
### Methods
---
##### As Dict
```py
human.skin.as_dict()
>>> dict
```
*Inherited from [[Could not find source]]*
Returns a dictionary representation of the skin material.   


**Returns:**
- `returns (dict)`: dict[str, Any]

---
##### Randomize
```py
human.skin.randomize()
>>> NoneType
```
*Inherited from [[Could not find source]]*
Randomize the skin material of the human. 



---
##### Set From Dict
```py
human.skin.set_from_dict(data: dict, context: Optional[bpy_types.Context])
>>> list
```
*Inherited from [[Could not find source]]*
Set the skin material from a dictionary representation.   

**Arguments:**
- `data (dict)`: Dictionary representation of the skin material.
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided.  

**Returns:**
- `returns (list)`: list[str]

---
##### Set Subsurface Scattering
```py
human.skin.set_subsurface_scattering(turn_on: bool, context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[Could not find source]]*
Set the subsurface scattering on or off.   

**Arguments:**
- `turn_on (bool)`: True for turning on, False for turning off.
- `context (Optional[bpy_types.Context])`: Blender context. Defaults to None. 


---
##### Set Underwear
```py
human.skin.set_underwear(turn_on: bool, context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[Could not find source]]*
Turn on/off the underwear/censoring on the human skin material.   

**Arguments:**
- `turn_on (bool)`: True for showing underwear, False for hiding it
- `context (Optional[bpy_types.Context])`: Blender context. bpy.context if not provided. 


---
