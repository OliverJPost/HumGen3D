---
cssClass: "Overview"
---
# API Documentation

### Summary:
Human Generator V4 introduces an API first design, where almost every functionality is accessible from your own Python scripts/add-ons. This API is still in development, you can report issues and request features either via [GitHub](https://github.com/HG3D/HumGen3D) or by contacting us via one of [[Contact Us|these channels]].

&nbsp;

##### What can you do with the API?
- Create new HG humans via Python, using [[Human]]
- Edit existing HG humans via Python, using [[Human]]
- Export and process humans via Python, using [[ProcessSettings]] (`human.process`), see [[Process/Python API|Processing humans from Python]]
- Control the batch generator via Python, using [[BatchHumanGenerator]]

---

### How to import from the module?
The HumGen3D API module can only be imported on machines that run Human Generator V4.0 or above. It works by importing the code directly from the Blender add-on, like this:
```python
from HumGen3D import Human
```

###### Currently, the available imports are:
- [[Human]]
- [[BatchHumanGenerator]]
- `HumGenException`
- `common.find_hg_rig`
- `common.find_multiple_in_list`
- `common.is_legacy`
- `common.is_part_of_human`

###### What happens if someone does not have Human Generator V4?
- If someone either doesn't have Human Generator installed or has a version before V4, you will get a `ModuleNotFoundError`

--- 
### Human examples
`Human` is the Python representation of a Human Generator human. It can both be used to create new humans or edit existing ones. Below you will find some example use cases. For a full overview of the available properties and methods of `Human`, see [[Human]].

---

###### Creating a human from scratch:
New properties/methods in this example: [[Human#From Preset]]
```python
from HumGen3D import Human

# Get available starting humans. You have to provide the gender
# as a string of either "male" or "female"
human_options = Human.get_preset_options("male")

# Choose a preset option, either using the random module or directly
chosen_option = human_options[0]

# You can see what the chosen preset looks like:
print(chosen_option)
>>> '/models/male/Asian 3.json' 

# Create the human, this will also generate it in Blender
my_human = Human.from_preset(chosen_option)

#You now have a Human Generator human in your scene. The result is the exact same as if you pressed the 'Generate New Human' button in the Human Generator interface.
```

---

###### Linking an existing human:
New properties/methods in this example: [[Human#From Existing]]
```python
import bpy
from HumGen3D import Human
from HumGen3D.common import is_part_of_human

# First you have to find an object that's part of an existing human
active_object = bpy.context.active_object

# You can check if it's the correct object like this:
if is_part_of_human(active_object):
	print('Found correct object!')

# Then you create a new Python instance from this object
my_existing_human = Human.from_existing(active_object)
```

---
###### Passing context:
Some methods need the Blender context in order to work. For easy of use, the Human Generator API makes it optional for you to pass this context. If no context is passed, bpy.context is used.
*If you are making a more advanced script or using the API in an add-on of your own, it's recommended to always pass your own context.*
```python
	def execute(self, context):
		chosen_option = '/models/male/Asian 3.json'
		my_human = Human.from_preset(chosen_option, context=context)
```

To see which methods need context, see the full [[Human]] documentation.

*You might see warnings like this if you don't pass context:*
```
HG_INFO:         <FrameSummary file /Users/ole/Library/Application Support/Blender/3.3/scripts/addons/HumGen3D/human/human.py, line 219 in from_preset>
HG_WARNING:      Argument 'context' for function 'set_from_dict' substituted with bpy.context.  It's highly recommended to pass your own context!
```
These are harmless, they are just there to remind you to pass your own context.


