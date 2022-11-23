# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE


import bpy
from HumGen3D.human.human import Human
from HumGen3D.user_interface.documentation.feedback_func import show_message


class HG_REMOVE_SHAPEKEY(bpy.types.Operator):
    """Removes the corresponding shapekey."""

    bl_idname = "hg3d.removesk"
    bl_label = "Remove this shapekey"
    bl_description = "Remove this shapekey"
    bl_options = {"UNDO"}

    shapekey: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        hg_rig = Human.from_existing(context.active_object).objects.rig
        hg_body = hg_rig.HG.body_obj

        sk_delete = hg_body.data.shape_keys.key_blocks[self.shapekey]
        hg_body.shape_key_remove(sk_delete)

        return {"FINISHED"}


class HG_ADD_FRIG(bpy.types.Operator):
    """Adds the facial rig to this human, importing the necessary shapekeys."""

    bl_idname = "hg3d.addfrig"
    bl_label = "Add facial rig"
    bl_description = "Adds facial rig"
    bl_options = {"UNDO"}

    def execute(self, context):
        human = Human.from_existing(context.object)
        human.expression.load_facial_rig()
        return {"FINISHED"}


class HG_REMOVE_FRIG(bpy.types.Operator):
    """Removes the facial rig, including its shapekeys."""

    bl_idname = "hg3d.removefrig"
    bl_label = "Remove facial rig"
    bl_description = "Remove facial rig"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        human = Human.from_existing(context.object)
        human.expression.remove_facial_rig()
        return {"FINISHED"}


class HG_OT_PREPARE_FOR_ARKIT(bpy.types.Operator):
    bl_idname = "hg3d.prepare_for_arkit"
    bl_label = "Prepare for ARKit"
    bl_description = "Removes drivers and adds single keyframe to all FACS shapekeys"
    bl_options = {"UNDO"}

    suffix: bpy.props.EnumProperty(
        name="Shapekey suffix",
        items=[
            ("long", "Left and Right (Default ARKit)", "", 0),
            ("short", "_L and _R (FaceApp)", "", 1),
        ],
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "suffix", text="Suffix")

    def execute(self, context):  # FIXME
        import bpy
        from HumGen3D import Human

        human = Human.from_existing(bpy.context.object)

        for key in human.keys.all_added_shapekeys:
            sk = key.as_bpy()
            if sk.name == "Basis" or sk.name.startswith("cor_"):
                continue
            sk.driver_remove("value")
            sk.keyframe_insert("value", frame=0)
            if self.suffix == "long" and sk.name.endswith(("_L", "_R")):
                sk.name = sk.name.replace("_L", "Left").replace("_R", "Right")

        show_message(self, "Succesfully removed drivers and added keyframes")
        return {"FINISHED"}
