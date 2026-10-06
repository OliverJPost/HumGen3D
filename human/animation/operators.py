# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import os

import bpy
from bpy_extras.io_utils import ImportHelper  # type:ignore
from HumGen3D.common.exceptions import HumGenException
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


class HG_OT_IMPORT_MIXAMO(bpy.types.Operator, ImportHelper):  # type:ignore[misc]
    """Converts a Mixamo FBX animation to the library and applies it to the human.

    Operator type:
        Animation

    Prereq:
        Active object is part of HumGen human
    """

    bl_idname = "hg3d.import_mixamo"
    bl_label = "Import Mixamo Animation"
    bl_description = (
        "Converts an FBX animation downloaded from Mixamo, saves it to the "
        "animation library and applies it to this human"
    )
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".fbx"
    filter_glob: bpy.props.StringProperty(default="*.fbx", options={"HIDDEN"})
    animation_name: bpy.props.StringProperty(
        name="Name",
        description="Name in the animation library, the file name if empty",
    )
    category: bpy.props.StringProperty(
        name="Category",
        description="Folder of the animation library to save in",
        default="Mixamo",
    )
    loop: bpy.props.BoolProperty(
        name="Loop",
        description="The animation is cyclic, like a walk or idle",
        default=False,
    )
    render_thumbnail: bpy.props.BoolProperty(
        name="Render Thumbnail",
        description="Render a thumbnail of this human for the library",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "animation_name")
        layout.prop(self, "category")
        layout.prop(self, "loop")
        layout.prop(self, "render_thumbnail")

    def execute(self, context):
        human = Human.from_existing(context.active_object)
        try:
            preset = human.animation.import_mixamo(
                self.filepath,
                name=self.animation_name,
                category=self.category.strip() or "Mixamo",
                loop=self.loop,
                context=context,
                render_thumbnail=self.render_thumbnail,
                finger_curl=context.scene.HG3D.animation_finger_curl,
            )
        except HumGenException as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

        self._show_in_library(context, preset)
        self.report({"INFO"}, f"Saved animation to {preset}")
        return {"FINISHED"}

    def _show_in_library(self, context, preset):
        """Selects the category and the new animation in the preview collection."""
        pcoll_sett = context.scene.HG3D.pcoll
        pcoll_sett.animation_category = os.path.basename(os.path.dirname(preset))
        previews = list(context.scene.HG3D.get("previews_list_animation", []))
        if preset in previews:
            # Index, the first item of the enum is the "none" item. Set as raw value
            # so the update callback does not apply the animation a second time.
            context.scene.HG3D.pcoll["animation"] = previews.index(preset) + 1
