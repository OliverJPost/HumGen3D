import bpy
from bpy.props import EnumProperty
from HumGen3D.human.clothing.add_obj_to_clothing import get_human_from_distance


class HG_OT_ADD_OBJ_TO_OUTFIT(bpy.types.Operator):
    bl_idname = "hg3d.add_obj_to_outfit"
    bl_label = "Add object to outfit"
    bl_description = "Add object to outfit"
    bl_options = {"UNDO"}

    cloth_type: EnumProperty(
        items=[
            ("torso", "Torso", "", 0),
            ("pants", "Pants", "", 1),
            ("full", "Full Body", "", 2),
            ("footwear", "Footwear", "", 3),
        ],
        default="torso",
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        col = self.layout
        col.label(text="What type of clothing is this?")

        col = col.column()
        col.scale_y = 1.5
        col.prop(self, "cloth_type", expand=True)

    def execute(self, context):
        cloth_obj = context.object
        human = get_human_from_distance(cloth_obj)

        if self.cloth_type == "footwear":
            human.footwear.add_obj(cloth_obj, context)
        else:
            human.outfit.add_obj(cloth_obj, self.cloth_type, context)
