---
accessor: human
---
> Python representation of a Human Generator human.

    This class with its subclasses can be used to modify the
    Human Generator human inside Blender.
    

Accessible from: `human`


### Properties
---
##### Age:
```py
human.age
>>> AgeSettings
```
*Read-only*
Points to the age settings of the human.   
`Returns `[[AgeSettings]]` `

---
##### Body:
```py
human.body
>>> BodySettings
```
*Read-only*
Points to the body settings of the human.   
`Returns `[[BodySettings]]` `

---
##### Children:
```py
human.children
>>> Iterable[bpy_types.Object]
```
*Read-only*
A generator of all children of the rig object of the human.  Does NOT yield subchildren.  Yields: Object: A Blender object that is a child of the rig object of the human  
`Returns Iterable[bpy_types.Object] `

---
##### Clothing:
```py
human.clothing
>>> ClothingSettings
```
*Read-only*
Points to the clothing settings of the human.   
`Returns `[[ClothingSettings]]` `

---
##### Expression:
```py
human.expression
>>> ExpressionSettings
```
*Read-only*
Points to the expression settings of the human.   
`Returns `[[ExpressionSettings]]` `

---
##### Eyes:
```py
human.eyes
>>> EyeSettings
```
*Read-only*
Subclass used to access and change the eye object and material.   
`Returns `[[EyeSettings]]` `

---
##### Face:
```py
human.face
>>> FaceSettings
```
*Read-only*
Points to the face settings of the human.   
`Returns `[[FaceSettings]]` `

---
##### Gender:
```py
human.gender
>>> Literal['male', 'female']
```
*Read-only*
Gender of this human in ("male", "female").   
`Returns Literal['male', 'female'] `

---
##### Get Categories:
```py
human.get_categories
>>> 'function' object has no attribute 'fget'
```
Get a list of categories the human presets are divided into.   
`Returns 'function' object has no attribute 'fget' `

---
##### Get Preset Options:
```py
human.get_preset_options
>>> 'function' object has no attribute 'fget'
```
 Return a list of human possible presets for the given gender.  Choose one of the options to pass to Human.from_preset() constructor.   
`Returns 'function' object has no attribute 'fget' `

---
##### Hair:
```py
human.hair
>>> HairSettings
```
*Read-only*
Subclass used to access and change the hair systems and materials.   
`Returns `[[HairSettings]]` `

---
##### Height:
```py
human.height
>>> HeightSettings
```
*Read-only*
Points to the height settings of the human.   
`Returns `[[HeightSettings]]` `

---
##### Keys:
```py
human.keys
>>> KeySettings
```
*Read-only*
Subclass used to access and change the shape keys of the body object.  Iterating yields key_blocks.   
`Returns `[[KeySettings]]` `

---
##### Location:
```py
human.location
>>> FloatVectorProperty
```
Location of the human in Blender global space.  Retrieved from rig_obj.location   
`Returns FloatVectorProperty `

---
##### Materials:
```py
human.materials
>>> MaterialSettings
```
*Read-only*
Points to the class giving access to different materials of human.   
`Returns `[[MaterialSettings]]` `

---
##### Name:
```py
human.name
>>> str
```
Name of this human. Takes name of rig object and removes HG_ prefix.   
`Returns str `

---
##### Objects:
```py
human.objects
>>> ObjectCollection
```
*Read-only*
Get a collection of all objects that are part of the human.   
`Returns `[[ObjectCollection]]` `

---
##### Pose:
```py
human.pose
>>> PoseSettings
```
*Read-only*
Points to the pose settings of the human.   
`Returns `[[PoseSettings]]` `

---
##### Pose Bones:
```py
human.pose_bones
>>> bpy_prop_collection
```
*Read-only*
Pose bones of the human rig.   
`Returns bpy_prop_collection `

---
##### Process:
```py
human.process
>>> ProcessSettings
```
*Read-only*
Points to the class used by the process tab of HumGen.   
`Returns `[[ProcessSettings]]` `

---
##### Props:
```py
human.props
>>> HG_OBJECT_PROPS
```
*Read-only*
Custom object properties of the human.  Used by the add-on for storing metadata like gender, backup_human pointer, current phase, body_obj pointer. Points to rig_obj.HG   
`Returns `[[HG_OBJECT_PROPS]]` `

---
##### Rotation Euler:
```py
human.rotation_euler
>>> FloatVectorProperty
```
Euler rotation of the human in Blender global space.  Retrieved from rig_obj.rotation_euler   
`Returns FloatVectorProperty `

---
##### Skin:
```py
human.skin
>>> SkinSettings
```
*Read-only*
Subclass used to change the skin material of the human body.   
`Returns `[[SkinSettings]]` `

---
### Classmethods
---
##### From Existing
```py
human.from_existing(existing_human: Object, strict_check: bool)
>>> HumGen3D.human.human.Human | None
```
*Inherited from [[Could not find source]]*
New instance from a passed Blender object that is part of an existing human.   

**Arguments:**
- `existing_human (`[bpy.types.Object](https://docs.blender.org/api/current/bpy.types.Object.html)`)`: Object that is part of the human you want to get.
- `strict_check (bool)`: If True, the method will raise an exception if the passed object is not part of a human. If False, it will return None instead. Defaults to True  

**Returns:**
- `returns (HumGen3D.human.human.Human | None)`: A Human instance or None

---
##### From Preset
```py
human.from_preset(preset: str, context: Optional[bpy_types.Context], prettify_eevee: bool, from_batch_generator: bool)
>>> Human
```
*Inherited from [[Could not find source]]*
Creates human in Blender based on passed preset and returns Human instance.   

**Arguments:**
- `preset (str)`: The name of the preset, as retrieved from Human.get_preset_options()
- `context (Optional[bpy_types.Context])`: The Blender context. Defaults to bpy.context if None
- `prettify_eevee (bool)`: If True, the AO and Strip settings will be set to settings that look nicer. Defaults to True
- `from_batch_generator (bool)`: If True, some settings will be skipped as they are defined in the batch generator. Defaults to False  

**Returns:**
- `returns (`[[Human]]`)`: Human

---
### Methods
---
##### As Dict
```py
human.as_dict()
>>> dict
```
*Inherited from [[Could not find source]]*
Returns a dictionary representation of this human.  This is used for saving the human to a JSON file.   


**Returns:**
- `returns (dict)`: A dictionary representation of this human.

---
##### Delete
```py
human.delete()
>>> NoneType
```
*Inherited from [[Could not find source]]*
Delete the human from Blender.  Will delete all meshes and objects that this human consists of, including the backup human.  



---
##### Duplicate
```py
human.duplicate(context: Optional[bpy_types.Context])
>>> Human
```
*Inherited from [[Could not find source]]*
Make a copy of this human. Will both duplicate in Blender and Python.  All relations will be corrected:   

**Arguments:**
- `context (Optional[bpy_types.Context])`: The context of the current scene.  

**Returns:**
- `returns (`[[Human]]`)`: The duplicated human as Python instance.

---
##### Hide Set
```py
human.hide_set(state: bool)
>>> NoneType
```
*Inherited from [[Could not find source]]*
Switch between visible and hidden state for all objects of this human.   

**Arguments:**
- `state (bool)`: Use True for hidden, False for visible 


---
##### Make Camera Look At Human
```py
human.make_camera_look_at_human(obj_camera: Object, look_at_correction: float)
>>> NoneType
```
*Inherited from [[Could not find source]]*
Makes the passed camera point towards a preset point on the human.   

**Arguments:**
- `obj_camera (`[bpy.types.Object](https://docs.blender.org/api/current/bpy.types.Object.html)`)`: Camera object
- `look_at_correction (float)`: Correction based on how much lower to point the camera compared to the top of the armature 


---
##### Render Thumbnail
```py
human.render_thumbnail(folder: Optional[str], name: str, focus: str, context: Optional[bpy_types.Context], resolution: int, white_material: bool)
>>> str
```
*Inherited from [[Could not find source]]*
Render a thumbnail of this human.   

**Arguments:**
- `folder (Optional[str])`: Folder to save the thumbnail to. If None the default folder will be used.
- `name (str)`: Name of the thumbnail. Will be used as filename.
- `focus (str)`: Focus of the thumbnail. Can be one of: "full_body_front", "full_body_side", "head_front", "head_side".
- `context (Optional[bpy_types.Context])`: The context of the current scene.
- `resolution (int)`: Resolution of the thumbnail. Defaults to 256.
- `white_material (bool)`: Use a white material for the human. Defaults to False.  

**Returns:**
- `returns (str)`: Path to the rendered thumbnail.

---
##### Save To Library
```py
human.save_to_library(name: str, category: str, thumbnail: Optional[bpy.types.Image], context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[Could not find source]]*
Save the human with it's current settings as a starting human preset.  Will add it to the content library.   

**Arguments:**
- `name (str)`: Name of the preset
- `category (str)`: Category of the preset, defaults to "Custom". Creates new category if it doesn't exist yet.
- `thumbnail (Optional[bpy.types.Image])`: Image to use as thumbnail for the preset. If None no thumbnail will be added.
- `context (Optional[bpy_types.Context])`: The context of the current scene. 


---
