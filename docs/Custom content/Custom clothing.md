---
permalink: customclothing
---
Want to edit our existing outfits? Or did you make an outfit of your own and want to add it to the library? This guide shows you how to.

### 1) Adding the clothing to the human
Step 1 is to make your clothing object a valid clothing item. This is very easy in Human Generator.
1. Make the clothing object the active object. Make sure it's placed correctly on the human you want to add it to, this is the position it will be saved as.
2. In the [[Custom content/Overview|Custom Content]] tab press **Add object as clothing**.
![[Screenshot_Blender_000288.webp]]
That's it! Your clothing is now added to the human! **Want to also save it to the library? See below!**

>[!info] Technical info
>Want to know what is going on behind the scenes? Pressing this button does the following:
>- Parents the clothing to the human rig
>- Adds an armature modifier to the clothing, and connects it to the rig
>- Automatically calculates vertex groups to use as weight painting
>- Adds corrective shape keys to the clothing and sets up the drivers

>[!warning] Custom weight painting
>If you have added custom weight painting, make sure ALL vertex groups are present on the clothing as are present on the body object. If any of them is missing, the add-on will overwrite your weights.
>If you want custom weight painting, we recommend letting the add-on first do automatic weight painting and customizing this to your liking. This is the more safe approach.

### 2) Go to the "Custom Content" tab
Here you'll see "Outfit" appear (or "footwear" if you added shoes). 
> [!info] Important!
> Human Generator saves outfits to the library, not individual pieces of clothing. Make sure you've added all the parts of the outfit as clothing (step 1) before going to this step.

Press **Save** (1) next to "Outfit".
![[Screenshot_Blender_000298 1.webp]]

### 3) Select thumbnail
It's best if your outfit/footwear has a thumbnail. HG offers multiple ways to add a thumbnail to your item. For an explanation of all methods, see [[Custom thumbnails]].

For now, we will use the quick and easy "Automatic render". Click the render button and the created thumbnail will be previewed. Then press next.
![[Screenshot_Blender_000296.webp]]



### 4) Gender selection
Choose if this clothing should be available for male, female, or both genders.
![[Screenshot_Blender_000300.webp]]

### 5) Category selection
Outfits/footwear are sorted into categories. Here you'll choose a category to save your clothing in.

You can choose an existing category in the "Existing" tab (1) by selecting a category from the dropdown (3). Want a category with a custom name? Go to the "Create new" tab (2) and fill in your own name. 
![[Screenshot_Blender_000214.webp]]


### 6) Choose a name
This is the name that will show in the menu and will be used as filename.

The "Open when finished" option will open new Blender windows with the exported files. This is useful if you chose to export to the opposite gender as well, as you might want to check if the automatic morph is done well.
![[Screenshot_Blender_000302.webp]]

### 7) Your clothing is now in the library!
You can now find it in the selector. Want to share it with others? See [[Exporting your content as a pack]].
![[Screenshot_Blender_000304.webp]]