---
accessor: human.hair
---
> Class for accessing hair types of human and common functionality.

Accessible from: `human.hair`


### Properties
---
##### Children Ishidden:
```py
human.hair.children_ishidden
>>> bool
```
*Read-only*
Check if hair children of systems are hidden.   
`Returns bool `

---
##### Eyebrows:
```py
human.hair.eyebrows
>>> EyebrowSettings
```
*Read-only*
Property for accessing eyebrow settings.   
`Returns `[[EyebrowSettings]]` `

---
##### Eyelashes:
```py
human.hair.eyelashes
>>> EyelashSettings
```
*Read-only*
Property for accessing eyelash settings.   
`Returns `[[EyelashSettings]]` `

---
##### Face Hair:
```py
human.hair.face_hair
>>> FacialHairSettings
```
*Read-only*
Property for accessing facial hair settings.   
`Returns `[[FacialHairSettings]]` `

---
##### Modifiers:
```py
human.hair.modifiers
>>> PropCollection
```
*Read-only*
All modifiers on human body.   
`Returns `[[PropCollection]]` `

---
##### Particle Systems:
```py
human.hair.particle_systems
>>> bpy_prop_collection
```
*Read-only*
All particle systems of human body.   
`Returns bpy_prop_collection `

---
##### Regular Hair:
```py
human.hair.regular_hair
>>> RegularHairSettings
```
*Read-only*
Property for accessing regular hair settings.   
`Returns `[[RegularHairSettings]]` `

---
### Methods
---
##### As Dict
```py
human.hair.as_dict()
>>> dict
```
*Inherited from [[Could not find source]]*
Return a dictionary representation of the hair settings.   


**Returns:**
- `returns (dict)`: dict[str, dict[str, Any]]

---
##### Children Set Hide
```py
human.hair.children_set_hide(hide: bool)
>>> NoneType
```
*Inherited from [[Could not find source]]*
Set the visibility state of the children of all hair systems.  If you will do a heavy computation on the human body, you should hide the children. This is already implemented for builtin heavy operations.   

**Arguments:**
- `hide (bool)`: True if children should be hidden, False otherwise. 


---
##### Remove System By Name
```py
human.hair.remove_system_by_name(name: str)
>>> NoneType
```
*Inherited from [[Could not find source]]*
Remove a certain particle system from the human by its name.   

**Arguments:**
- `name (str)`: Name of the particle system to remove. 


---
##### Set Connected
```py
human.hair.set_connected(connected: bool)
>>> NoneType
```
*Inherited from [[Could not find source]]*
Shortcut for using `connect_hair` and `disconnect_hair` operators.  This should be used when modifying the body mesh (the actual mesh, not the shape keys).   

**Arguments:**
- `connected (bool)`: True if hair should be connected, False otherwise. 


---
##### Set From Dict
```py
human.hair.set_from_dict(data: dict)
>>> list
```
*Inherited from [[Could not find source]]*
Set the hair settings from a dictionary representation.  See `as_dict` for structure.   

**Arguments:**
- `data (dict)`: Dictionary representation of the hair  

**Returns:**
- `returns (list)`: list[str]

---
##### Set Hair Quality
```py
human.hair.set_hair_quality(hair_quality: Literal['high', 'medium', 'low', 'ultralow'])
>>> NoneType
```
*Inherited from [[Could not find source]]*
Makes hairs thicker and lowers chileren amount for lower qualities.   

**Arguments:**
- `hair_quality (Literal['high', 'medium', 'low', 'ultralow'])`: Quality to set all hair types on this human to. 


---
##### Update Hair Shader Type
```py
human.hair.update_hair_shader_type(shader_type: Literal['fast', 'accurate'])
>>> NoneType
```
*Inherited from [[Could not find source]]*
Set the shader type between accurate (Eevee comp.) and fast (Cycles only).   

**Arguments:**
- `shader_type (Literal['fast', 'accurate'])`: Type to set the shader to. 


---
