##### Save To Library
```py
human.pose.save_to_library(name: str, category: str, thumbnail: Optional[bpy.types.Image], context: Optional[bpy_types.Context])
>>> NoneType
```
Save current pose to the Human Generator pose library.   

**Arguments:**
- `name (str)`: Name to save the pose as.
- `category (str)`: Category to save the pose in. If the category does not exist, a new folder is created. Defaults to "Custom".
- `thumbnail (Optional[bpy.types.Image])`: Thumbnail to use for the pose. If None, no thumbnail is saved. Defaults to None.
- `context (Optional[bpy_types.Context])`: Context to use. Defaults to None. 


---
