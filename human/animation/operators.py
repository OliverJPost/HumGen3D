# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy
from HumGen3D.human.human import Human


class HG_OT_REMOVE_ANIMATION(bpy.types.Operator):
    """Removes the Human Generator animation from the human.

    Operator type:
        Animation

    Prereq:
        Active object is part of HumGen human
    """

    bl_idname = "hg3d.remove_animation"
    bl_label = "Remove Animation"
    bl_description = "Removes the animation, the human returns to its rest pose"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        human = Human.from_existing(context.active_object)
        human.animation.remove()
        return {"FINISHED"}


class HG_OT_ANIMATION_FRAME_RANGE(bpy.types.Operator):
    """Sets the frame range of the scene to the animation of the human.

    Operator type:
        Animation

    Prereq:
        Active object is part of HumGen human with an animation
    """

    bl_idname = "hg3d.animation_frame_range"
    bl_label = "Set Frame Range"
    bl_description = "Sets the frame range of the scene to one cycle of the animation"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        human = Human.from_existing(context.active_object)
        human.animation.set_scene_frame_range(context)
        return {"FINISHED"}
