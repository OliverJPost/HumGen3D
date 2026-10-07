> Class for accessing methods and subclasses for processing the human.

Accessible from: `human.process`


### Properties
---
##### Add Props From Dict:
```py
human.process.add_props_from_dict
>>> 'function' object has no attribute 'fget'
```
No docstring available.
`Returns 'function' object has no attribute 'fget' `

---
##### Baking:
```py
human.process.baking
>>> BakeSettings
```
*Read-only*
Gives access to the baking settings.   
`Returns `[[BakeSettings]]` `

---
##### Has Haircards:
```py
human.process.has_haircards
>>> bool
```
*Read-only*
Checks if haircards are present.   
`Returns bool `

---
##### Is Lod:
```py
human.process.is_lod
>>> bool
```
*Read-only*
Checks if the human is an LOD.   
`Returns bool `

---
##### Lod:
```py
human.process.lod
>>> LodSettings
```
*Read-only*
Gives access to the LOD settings.   
`Returns `[[LodSettings]]` `

---
##### Parts Were Renamed:
```py
human.process.parts_were_renamed
>>> bool
```
*Read-only*
Checks if the parts were renamed.   
`Returns bool `

---
##### Rig Renamed:
```py
human.process.rig_renamed
>>> bool
```
*Read-only*
Checks if the rig was renamed.   
`Returns bool `

---
##### Save Settings To Template:
```py
human.process.save_settings_to_template
>>> 'function' object has no attribute 'fget'
```
Saves the current settings to a template file.   
`Returns 'function' object has no attribute 'fget' `

---
##### Set Settings From Template:
```py
human.process.set_settings_from_template
>>> 'function' object has no attribute 'fget'
```
Sets the process settings from a template file.   
`Returns 'function' object has no attribute 'fget' `

---
##### Was Baked:
```py
human.process.was_baked
>>> bool
```
*Read-only*
Checks if materials were baked.   
`Returns bool `

---
### Methods
---
##### Rename Bones From Json
```py
human.process.rename_bones_from_json(json_string: Optional[str], json_path: Optional[str])
>>> NoneType
```
*Inherited from [[Could not find source]]*
Renames the bones of the human according to the provided json str or file.   

**Arguments:**
- `json_string (Optional[str])`: The json string. Defaults to None. ONLY ONE OF json_string and json_path may be provided.
- `json_path (Optional[str])`: The path to the json file. Defaults to None.  


---
##### Rename Materials From Json
```py
human.process.rename_materials_from_json(json_string: Optional[str], json_path: Optional[str], custom_token: str, suffix: str)
>>> NoneType
```
*Inherited from [[Could not find source]]*
Renames materials of the human according to the provided json str or file.   

**Arguments:**
- `json_string (Optional[str])`: The json string. Defaults to None.
- `json_path (Optional[str])`: The path to the json file. Defaults to None.
- `custom_token (str)`: A custom token that can be inserted into name templates.
- `suffix (str)`: A suffix that will be appended to the new names.  


---
##### Rename Objects From Json
```py
human.process.rename_objects_from_json(json_string: Optional[str], json_path: Optional[str], custom_token: str, suffix: str)
>>> NoneType
```
*Inherited from [[Could not find source]]*
Renames the objects of the human according to the provided json str or file.   

**Arguments:**
- `json_string (Optional[str])`: The json string. Defaults to None.
- `json_path (Optional[str])`: The path to the json file. Defaults to None.
- `custom_token (str)`: A custom token that can be inserted into name templates.
- `suffix (str)`: A suffix that will be appended to the new names.  


---
