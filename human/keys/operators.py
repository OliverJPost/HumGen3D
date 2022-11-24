# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy
from HumGen3D.human.human import Human
from HumGen3D.user_interface.documentation.feedback_func import ShowMessageBox


class HG_OT_LIVETOSHAPEKEY(bpy.types.Operator):
    bl_idname = "hg3d.livekey_to_shapekey"
    bl_label = "Convert live key to shape key"
    bl_description = "Loads the live key data onto a shape key on your model."
    bl_options = {"UNDO"}

    livekey_name: bpy.props.StringProperty()

    def execute(self, context):
        human = Human.from_existing(context.object)

        human.keys[self.livekey_name].to_shapekey()
        ShowMessageBox(
            "Live key converted to shape key. This slider is still the livekey, but the shape key is now found in Blender's shape key menu.",
            "Success",
            "INFO",
        )
        return {"FINISHED"}
