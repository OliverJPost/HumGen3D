import bpy
from HumGen3D.human.human import Human

from ...backend.preview_collections import get_hg_icon
from .main_panel_baseclass import MainPanelPart, subpanel_draw


class HG_PT_BODY(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_Body"
    phase_name = "body"

    """First section shown to the user after adding a human

    Shows sliders for body proportion shapekeys, including a randomize
    button for these sliders
    Also shows a collapsable menu for changing individual body part size
    """

    @subpanel_draw
    def draw(self, context):

        # row.alignment = "CENTER"
        # row.label(text="Body Proportions", icon="COMMUNITY")
        # row = self.layout.row()
        # row.scale_y = 0.2
        # row.alignment = "CENTER"
        # for i in range(8):
        #     row.label(text="", icon="KEYTYPE_KEYFRAME_VEC")

        col = self.layout.column()
        col.scale_y = 1.25

        col_h = col.column()
        col_h.scale_y = 1.5
        col_h.operator(
            "hg3d.random", text="Random", icon="FILE_REFRESH"
        ).random_type = "body_type"

        col.separator()
        flow = self.get_flow(col)

        for sk in self.human.body.shape_keys:
            flow.prop(
                sk,
                "value",
                text=sk.name.replace("bp_", "").capitalize(),
                expand=True,
            )

        col.separator()

        self._individual_scale_ui(col, sett)

    def _individual_scale_ui(self, box, sett):
        """Collapsable menu showing sliders to change bone scale of different
        body parts of the HumGen human

        Args:
            box (UILayout): Box layout of body section
            sett (Scene.HG3D): Humgen properties
        """
        is_open, boxbox = self.draw_sub_spoiler(
            box, sett, "indiv_scale", "Individual scaling"
        )
        if not is_open:
            return

        col = boxbox.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False

        col.prop(sett, "head_size", text="Head", slider=True)
        col.prop(sett, "neck_size", text="Neck", slider=True)
        col.separator()
        col.prop(sett, "chest_size", text="Chest", slider=True)
        col.prop(sett, "shoulder_size", text="Shoulders", slider=True)
        col.prop(sett, "breast_size", text="Breasts", slider=True)
        col.prop(sett, "hips_size", text="Hips", slider=True)
        col.separator()
        col.prop(sett, "upper_arm_size", text="Upper Arm", slider=True)
        col.prop(sett, "forearm_size", text="Forearm", slider=True)
        col.prop(sett, "hand_size", text="Hands", slider=True)
        col.separator()
        col.prop(sett, "thigh_size", text="Thighs", slider=True)
        col.prop(sett, "shin_size", text="Shins", slider=True)
        col.separator()

        col.label(text="Type number for stronger values", icon="INFO")
