import bpy #type: ignore

class HG_OT_INFO(bpy.types.Operator):
    """
    Operator for showing a popup message when the questionmark icon is pressed.
    
    Credits to DB3D for inventing this way of showing information popups
    """
    bl_idname      = "hg3d.showinfo"
    bl_label       = ""
    bl_description = "Info about these options"

    info : bpy.props.StringProperty()

    def execute(self, context):
        message_title = self.info
        
        self.ShowMessageBox(message_title)

        return {'FINISHED'}

    def ShowMessageBox(self, message_txt_key):
        """Draw a message popup

        Args:
            message_txt_key (str): key to the message txts stored in this file
        """
        def draw(self, context):
            nonlocal message_txt_key
            layout = self.layout
            eval(message_txt_key +'(layout)')

        bpy.context.window_manager.popup_menu(
            draw,
            title='Info',
            icon='QUESTION'
        )


hair_children_txt = '''Enabling hair children, especially at render density can really slow down
viewport performance. Therefore HumGen keeps them hidden by default,
this includes viewport rendering. In your final renders the hair will
be visible at full density. 
'''

def hair_children(layout):
    for i, line in enumerate(hair_children_txt.splitlines()):
        layout.label(text=line)


subsurface_txt = '''Subsurface scattering simulates light bouncing inside the skin instead of just on
top of the skin. This produces very realistic results, but it also drastically
increases the render time and introduces color noise. It's recommended to turn
this setting off until you do your final render if you don't have powerful 
render hardware.
'''

def subsurface(layout):
    for i, line in enumerate(subsurface_txt.splitlines()):
        layout.label(text=line)



completed_txt = '''This model has been completed, meaning it's no longer in the editing
phase. Below you'll find the settings that are still accessible for
completed models. 
'''


def completed(layout):
    for i, line in enumerate(completed_txt.splitlines()):
        layout.label(text=line)



hairsim_type_txt = '''Choose what result you want from the simulation:

Static:
If you are making still renders. Use this mode when the default
hair grooming looks unrealistic for your chosen pose. For example
when the human is bending forward, when one would expect the hair 
to hang down.

Animated:
If you are making an animation. Fill in your start and end keyframe,
the simulation will try to calculate the way the hair should move based
on the movements of your charachter. For some hairstyles this will result
in a very different looking style, since the simulation will make hairs fall
down to calculate gravity.

'''

def hairsim_type(layout):
    for i, line in enumerate(hairsim_type_txt.splitlines()):
        layout.label(text=line)



clothsim_type_txt = '''Choose what result you want from the simulation:

Static:
If you are making still renders. Use this mode when you want the clothing to
look more acurate and detailed for your current pose. Not all clothing items
are simulatable.

Animated:
If you are making an animation. Fill in your start and end keyframe,
the simulation will try to calculate the way the clothing should move based
on the movements of your charachter. 

'''

def clothsim_type(layout):
    for i, line in enumerate(clothsim_type_txt.splitlines()):
        layout.label(text=line)



rigify_library_txt = '''The pose library does not work with Rigify rigs.

If you want to get the non-rigify rig back, there are two options:

- Undo to before the point the rigify rig was generated

- Revert to the creation phase with the button in the Creation Phase panel
'''

def rigify_library(layout):
    for i, line in enumerate(rigify_library_txt.splitlines()):
        layout.label(text=line)



length_hair_change_txt = '''Changing the hairstyle is only possible
when the character is at the default length of 1.83m.
When you change the length to something else, the hair
tab will be greyed out. To be able to change the style
again, change the length of the character to 1.83m agian.
'''

def length_hair_change(layout):
    for i, line in enumerate(length_hair_change_txt.splitlines()):
        layout.label(text=line)



autohide_hair_txt = '''Hair children were hidden to improve performance.
You can turn them back on in the hair tab, next to 'Children are hidden'.

You can also hold CTRL when clicking on the tab you want to go to
to keep the hair children turned on.

Auto-hide can be turned off in the HumGen preferences. 
You can also turn off this popup in the preferences'''

def autohide_hair(layout):
    for i, line in enumerate(autohide_hair_txt.splitlines()):
        layout.label(text=line)

starting_human_txt = '''Saving the starting human saves a list of all
values you've entered for things like body shapes, face
deformations, skin settings and length. It does not save 
the actual shapekeys, textures or edits. If you've made a
CUSTOM shapekey, save that in the 'Save shapekeys' menu first,
same goes for CUSTOM textures.

Hairstyles and hair material settings are not saved in starting
humans.
'''

def starting_human(layout):
    for i, line in enumerate(starting_human_txt.splitlines()):
        layout.label(text=line)
        
experimental_txt = '''This human is now experimental.

Experimental humans have sliders that can be pushed beyond
their normal limits, allowing for further customization.

Because these sliders now go further than they were designed
for, some strange effects might occur. For example the button
for randomizing the face will produce very extreme results.

Experimental humans will still work with the clothing, hair,
posing and other systems of Human Generator.
'''

def experimental(layout):
    for i, line in enumerate(experimental_txt.splitlines()):
        layout.label(text=line)
