"""
Operators and functions to be used by the developer and content pack creators
"""

import bpy
from HumGen3D.human.human import Human
from mathutils import Matrix

from ..common.common_functions import find_human


# REMOVE
class HG_TESTOP(bpy.types.Operator):
    """Operator for testing bits of code"""

    bl_idname = "hg3d.testop"
    bl_label = "Test"
    bl_description = "Empty operator used for internal testing"
    bl_options = {"UNDO"}

    def execute(self, context):
        return {"FINISHED"}


class HG_RESET_BATCH_OPERATOR(bpy.types.Operator):
    """Operator for testing bits of code"""

    bl_idname = "hg3d.reset_batch_operator"
    bl_label = "Reset batch operator"
    bl_description = "If an error occured during batch creation, use this to get the purple button back"
    bl_options = {"UNDO"}

    def execute(self, context):
        context.scene.HG3D.batch_idx = 0
        return {"FINISHED"}


class HG_CONVERT_HAIR_SHADER(bpy.types.Operator):
    """Operator for testing bits of code"""

    bl_idname = "hg3d.convert_hair_shader"
    bl_label = "Convert to new hair shader"
    bl_description = (
        "Convert human that still uses old hair to the new hair shader"
    )
    bl_options = {"UNDO"}

    def execute(self, context):
        human = Human.from_existing(context.object)
        if human.materials.get("HG_Hair_V3"):
            self.report({"INFO"}, "This human already has the new hair shader")
            return {"FINISHED"}

        human.hair.convert_to_new_hair_shader()
        self.report({"INFO"}, "Converted hair to new hair shader")
        return {"FINISHED"}


# keep
class HG_MASK_PROP(bpy.types.Operator):
    """
    Adds a custom property to the object indicating what mesh mask should be added to the human for this cloth
    """

    bl_idname = "hg3d.maskprop"
    bl_label = "Add"
    bl_description = "Adds a custom prop with the name of the mask"
    bl_options = {"UNDO"}

    def execute(self, context):
        obj = context.object
        mask_name = context.scene.HG3D.dev_mask_name
        for i in range(10):
            try:
                mask = obj["mask_{}".format(i)]
                continue
            except:
                obj["mask_{}".format(i)] = "mask_{}".format(mask_name)
                break

        return {"FINISHED"}


# keep
class HG_DELETE_STRETCH(bpy.types.Operator):
    """
    Deletes stretch bones from this human
    """

    bl_idname = "hg3d.delstretch"
    bl_label = "Remove stretch bones"
    bl_description = "Removes all stretch bones"
    bl_options = {"UNDO"}

    def execute(self, context):
        human = Human.from_existing(context.object)
        if not human:
            self.report({"WARNING"}, "No human selected")
            return {"FINISHED"}

        hg_body = human.body_obj

        remove_list = [
            driver for driver in hg_body.data.shape_keys.animation_data.drivers
        ]

        for driver in remove_list:
            hg_body.data.shape_keys.animation_data.drivers.remove(driver)

        human.creation_phase.delete_stretch_bones()

        return {"FINISHED"}
