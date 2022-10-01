import bpy
from HumGen3D.human.human import Human


class HG_PT_LEGACYINSTALL(bpy.types.Panel):
    bl_idname = "HG_PT_LEGACYINSTALL"
    bl_label = "HumGen"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"

    @classmethod
    def poll(cls, context):
        is_legacy = Human.is_legacy(context.object)
        legacy_addon_not_installed = True

        return is_legacy and legacy_addon_not_installed

    def draw(self, context):
        self.layout.alert = True
        self.layout.label(text="Legacy human")
