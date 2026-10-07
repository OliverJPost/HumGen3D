---
cssclasses:
  - overview
permalink: guide
---

# The Human Generator Guide

*This guide goes step by step through the process of creating a human in Human Generator!*

> [!info] Besides the Human Generator Guide, we also have:
> - The [[Batch/Overview|Batch Generator Guide]]
> - The [[Process/Overview|Process System Guide]]
> - The [[Custom content/Overview|Custom Content Guide]]
> - The [[API/Overview|Python API Guide]]



## Creating a new human:
When no other human is selected, the Human Generator interface will show the options for creating a **new human**. Select one of the available genders and click the selection square to see the available starting humans. If needed, you can use the categories dropdown to narrow down the selection.

Press **Generate new human** to generate the selected preset at the location of the 3D cursor (you place the 3D cursor in Blender with `shift + right click`).

![[CleanShot 2023-04-06 at 00.18.29.mp4]]

> [!info]
> If you've already generated a human, and want to **generate another one**, but the creation panel is not showing:
> - Select an object in the scene that is not part of a human, (i.e. the camera).
> - OR use the `deselect` button in the header of the Human Generator panel
> 
> ![[CleanShot 2023-04-06 at 00.24.42@2x.webp]]

> [!hint]- Python API - Creating new humans
> To get a list of possible starting humans, use this code:
> ```python
> from HumGen3D import Human
> gender = "female" # or "male"
> starting_human_options = Human.get_preset_options(gender)
> ```
> To create the human in the Blender scene:
> ```python
> chosen_preset = starting_human_options[0]
> human = Human.from_preset(chosen_preset)
> ```
> 
> For more info, see the [[API/Overview]]

>[!example] Save your edits as a starting human
>You can also add your own starting humans. See [[Custom starting humans]].


## Editing the human:
Once a new human has been created, you will see the section overview panel:

![[CleanShot 2023-04-06 at 00.27.28@2x.webp]]

Editing the human is divided into these sections. Click on these links to see the guide for each section.
1. [[Body]] - Change the body proportions of the human, including muscle and cartoon effects
2. [[Age]] - Make the human look younger or older
3. [[Face]] - Change the facial proportions of this human
4. [[Height]] - Make the human shorter or taller
5. [[Skin]] - Change the skin material of the human, including eye color
6. [[Hair]] - Use hairstyles from our library, including eyebrows and facial hair
7. [[Guide/Clothing]] - Add outfits and footwear to the human
8. [[Pose]] - Posing your human from our library, or with a Rigify rig
9. [[Expression]] - Options for adding facial expressions, a facial rig, and facial motion capture



## Finalising your human
Once you're finished editing, you might want to have a look at these tutorials:
- [[How do I export to another software|Exporting the human]]
- etc.