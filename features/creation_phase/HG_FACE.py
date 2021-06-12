import bpy #type: ignore
from ... features.common.HG_COMMON_FUNC import find_human

class HG_RESET_FACE(bpy.types.Operator):
    """
    Resets all face deformation values to 0
    """
    bl_idname      = "hg3d.resetface"
    bl_label       = "Reset face"
    bl_description = "Resets all face deformation values to 0"
    bl_options     = {"UNDO"}

    def execute(self,context):
        hg_rig = find_human(context.object)
        hg_body = hg_rig.HG.body_obj

        face_sk = [sk for sk in hg_body.data.shape_keys.key_blocks if sk.name.startswith('ff_')]

        for sk in face_sk:
            sk.value = 0

        return {'FINISHED'}