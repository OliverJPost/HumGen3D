import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from HumGen3D.human.clothing.add_obj_to_clothing import get_human_from_distance
from HumGen3D.human.human import Human


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


class HG_OT_SAVE_SK(bpy.types.Operator):
    bl_idname = "hg3d.save_sk_to_library"
    bl_label = "Save shapekey to library"
    bl_description = "Saves this shape key to the library as a LiveKey"
    bl_options = {"UNDO"}

    save_type: EnumProperty(
        items=[
            ("shapekey", "Shape key by default", "", 0),
            ("livekey", "LiveKey", "", 1),
        ],
        default="livekey",
    )
    delete_original = BoolProperty(default=False, name="Delete original")

    sk_name: StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout

        layout.label(text="How do you want to save this key?")
        col = layout.column(align=True)
        col.prop(self, "save_type", expand=True)

        if self.save_type == "livekey":
            col.prop(self, "delete_original")

    def execute(self, context):
        human = Human.from_existing(context.object)
        bpy_key = human.body_obj.data.shape_keys.key_blocks[self.sk_name]

        key = next(key for key in human.keys if key.as_bpy() == bpy_key)

        delete_original = (
            True if self.save_type == "livekey" and self.delete_original else False
        )
        key.save_to_library(
            as_livekey=self.save_type == "livekey", delete_original=delete_original
        )
