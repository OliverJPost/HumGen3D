---
accessor: human.body
---
> Class to edit body proportions of the human.

    The body proportions are changed by changing the values of the LiveKeys stored
    in the folder `livekeys/body_proportions`. These are accessible in the API under
    `human.body.keys`.

    Note: By default Human Generator does not come with shape keys for changing body
    proportions, but either by users converting them or by new 3rd party packs adding
    them you can expect shape keys too.

    For more info on LiveKeys see [[LiveKeys]].
    

Accessible from: `human.body`


### Properties
---
##### Keys:
```py
human.body.keys
>>> list
```
*Read-only*
Access ShapeKeyItems and LiveKeyItems for changing body proportions.  Gets all LiveKeyItems and ShapeKeyItems from the global Human Generator key collection (`Human.keys.all_keys`) that belong to the body proportion category.   
`Returns list `

---
### Methods
---
##### Randomize
```py
human.body.randomize(context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[Could not find source]]*
Randomizes the values of the body keys of this human.  Uses a random value retreived from a normal distrubition with mean 0 and sigma of 0.5.   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context 


---
##### Reset Values
```py
human.body.reset_values(context: Optional[bpy_types.Context])
>>> NoneType
```
*Inherited from [[Could not find source]]*
Reset all body keys to their default values.   

**Arguments:**
- `context (Optional[bpy_types.Context])`: Blender context 


---
