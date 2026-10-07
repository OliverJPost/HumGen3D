> [!info] Part of the [[Guide/Overview|Human Generator Guide]]

*How to use Human Generator's expression features*

The expression section consists of two tabs:
- The [[#The 1-click expression library:|1-click expression library tab]]
- The [[#The face rig|face rig tab]]

![[CleanShot 2023-03-07 at 11.21.53@2x.webp]]


---


## The 1-click expression library:
Human Generator includes a library of ready to use expressions. For a full list with pictures, see [Human Generator Base Content](https://www.humgen3d.com/base-content).

To add a **new expression** to your human, click on the selection square and a grid of options will show up. Click one of the icons to load this expression.
![[CleanShot 2023-03-07 at 11.19.56.mp4]]
> [!tip]- Python API - Adding expressions
> You can get a list of all available 1-click expressions like this:
> ```python
> options = human.expression.get_options()
> ```
> You can set the active expression of this human like this::
> ```python
> chosen_option = options[0] # Select specific one, or randomly
> human.expression.set(chosen_option)
> ```
> ---
> For all API options, see [[ExpressionSettings]].

>[!example] Add your own expressions
>Want to add your own 1-click expressions to the library? See [[Custom shape keys]].

To **change the strength** of an expression, open the "Strength" dropdown. An overview of all expressions loaded on the human is visible here. The slider changes how strong the expression is. Here, you can also **delete** the expression.

![[CleanShot 2023-03-07 at 11.29.38.mp4]]

If you want to **combine** expressions, for example "Blink Left" with "Blink Right" for fully closed eyes, just turn up the slider of both these expressions.
The dot next to the delete button is for **animating the expression**. This allows you to add keyframes to make the expression change over time. For more advanced animations, we recommend using the [[#The face rig|Face Rig]].

> [!tip]- Python API - Expression Strength
> To change the strength of an expression with Python, you can use our `ShapeKeyItem` class. To get a list of the active expression keys on this human, use this code:
> ```python
> keys = human.expression.keys
> ```
> This gives you a list of `ShapeKeyItem`s (Expressions are never `LiveKeyItem`s)
> To change the value of the key, use this code:
> ```python
> key = keys[0] # Randomly chosen key for example
> key.value = 0.5
> ```
> ---
> For all API options, see [[ExpressionSettings]].


---


## The face rig

Human Generator includes a face rig based on the [FACS](https://en.wikipedia.org/wiki/Facial_Action_Coding_System) system. This is a set of 52 shape keys that together can create a wide range of facial expressions. To add the face rig, click the **add facial rig** button in the Face Rig tab of the expression menu.

![[CleanShot 2023-03-07 at 11.32.24.mp4]]
> [!tip]- Python API - Face rig
> To load the facial rig
> ```python
> human.expression.load_facial_rig()
> ```
> To remove the facial rig
> ```python
> human.expression.remove_facial_rig()
> ```
> >[!warning]
> >The face rig shape keys are loaded with drivers on them. To change their values using the Python API you will need to remove the drivers.
> ---
> For all API options, see [[ExpressionSettings]].

This will load the required shape keys onto the model and add bones to easily control/animate them. 

#### How to use the face rig:
First, select the armature/rig object of the human and go into "Pose Mode" (Shortcut: `ctrl + tab`). This will show the color coding of the bones and allow you to move them.

- *Green bones* are for eye movement
- *Purple bones* are for mouth movement
- *Yellow bones* are for all other movements.

> [!info]
> The bones are limited in the direction and amount they can move. Most bones can only be moved on one axis, others in multiple directions. We recommend selecting them and pressing the `g` key to move them in any direction.

>[!note]
>Once you've added the face rig, you can no longer use 1-click expressions. These two systems interfere with eachother. If you want to revert to using 1-click expressions again you can use the "Remove face rig" button.

#### How to animate the face rig:
###### Manual animation:
You can add animation manually by using Blender's [Keyframes](https://docs.blender.org/manual/en/latest/animation/keyframes/introduction.html). While in "Pose mode" move one of the face bones to the position you like and add a *Location* keyframe using the `i` shortcut. Make sure your timeline is at the moment in time you want this keyframe at. 
![[CleanShot 2023-03-07 at 12.09.22.mp4]]
>[!warning]
>If a bone has keyframes on it, moving it to another position **without** adding a keyframe will cause it to revert to it's previous position. Either remove all keyframes from the bone or add a new keyframe at the position you want the bone to be at.



###### ARKit face capture animation.
The face rig of Human Generator works with the Apple ARKit. This is a way to add animations to the face rig using a motion capture on a FaceID equipped iPhone.

**NOTE:** You need both a FaceID equipped iPhone for this and a third party app. Some examples are "Face Cap" and "iFacialMocap" (these are just examples, they are not tested or endorsed by us).

1. Record the animation using one of the available facial mocap apps.
2. Export the animation as FBX.
3. A file conversion is required for Blender to read the FBX ASCII file (it's a different FBX format than Blender supports). You can download a free converter from [AutoDesk](https://www.autodesk.com/developer-network/platform-technologies/fbx-converter-archives) or search for "FBX converter" on the web to find other possibilities.
4. Once the FBX is imported in Blender, it should look like a human face.
5. Make sure you have the facial rig loaded on the human.
6. Use the "Prepare for ARKit" button in Human Generator's face rig tab to prepare the model for the animation transfer. This removes the drivers from the shape keys and inserts keyframes. **NOTE 1:** This will break the controls of the face rig. **NOTE 2:** If you used FaceApp, you should select the alternate naming method in the popup.
7. Select the source mesh (from the imported FBX), go to the "Timeline" animation editor and select all keyframes. Once selected, right-click and copy.
![[CleanShot 2023-03-07 at 12.16.38@2x.webp]]
8. Now select the Human Generator body object and in the animation timeline right-click and paste the copied animation keyframes. Make sure the start keyframe is 0.
**Now your animation is transferred!**

