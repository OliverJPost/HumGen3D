---
accessor: human.process.lod
---
> Has methods for setting LODs for the meshes of a human.

Accessible from: `human.process.lod`


### Methods
---
##### Set Body Lod
```py
human.process.lod.set_body_lod(lod: Literal[0, 1, 2])
>>> NoneType
```
*Inherited from [[Could not find source]]*
Set the LOD of the body mesh.   

**Arguments:**
- `lod (Literal[0, 1, 2])`: LOD to set the body mesh to. 0 means no difference, 1 means lower polycount in the face and 2 means lower polycount in the whole body.  


---
##### Set Clothing Lod
```py
human.process.lod.set_clothing_lod(decimate_ratio: float, remove_subdiv: bool, remove_solidify: bool)
>>> NoneType
```
*Inherited from [[Could not find source]]*
Set the LOD of the clothing meshes by decimating them.   

**Arguments:**
- `decimate_ratio (float)`: Ratio of decimation. Defaults to 0.15.
- `remove_subdiv (bool)`: Whether to remove subdivision modifiers.
- `remove_solidify (bool)`: Whether to remove solidify modifiers. 


---
