# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy
from HumGen3D.backend import get_prefs
from HumGen3D.human.keys.keys import LiveKeyItem

from ..ui_baseclasses import MainPanelPart, subpanel_draw


class HG_PT_FACE(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_FACE"
    phase_name = "face"

    @subpanel_draw
    def draw(self, context):

        col = self.layout.column()
        col.scale_y = 1.5

        row = col.row(align=True)
        row.operator("hg3d.random_value", text="Randomize all").random_type = "face_all"
        row.operator("hg3d.resetface", text="", icon="LOOP_BACK")

        col = self.layout.column(align=True)

        col.label(text="Upper Face:")
        flow_u_skull = self._get_ff_col(col, "Upper Skull", "u_skull")
        flow_eyes = self._get_ff_col(col, "Eyes", "eyes")
        flow_ears = self._get_ff_col(col, "Ears", "ears")
        flow_nose = self._get_ff_col(col, "Nose", "nose")

        col.separator()
        col.label(text="Lower Face:")
        flow_l_skull = self._get_ff_col(col, "Lower Skull", "l_skull")
        flow_mouth = self._get_ff_col(col, "Mouth", "mouth")
        flow_cheeks = self._get_ff_col(col, "Cheeks", "cheeks")
        flow_jaw = self._get_ff_col(col, "Jaw", "jaw")
        flow_chin = self._get_ff_col(col, "Chin", "chin")

        col.separator()
        col.label(text="Other:")
        flow_custom = self._get_ff_col(col, "Custom", "custom")
        flow_presets = self._get_ff_col(col, "Presets", "presets")

        for key in self.human.face.keys:
            bpy_key = key.as_bpy(context)
            if getattr(self.sett.ui, bpy_key.subcategory):
                row = locals()[f"flow_{bpy_key.subcategory}"].row(align=True)
                row.prop(bpy_key, "value", text=bpy_key.name, slider=True)
                if isinstance(key, LiveKeyItem):
                    row.operator(
                        "hg3d.livekey_to_shapekey",
                        text="",
                        icon="SHAPEKEY_DATA",
                        emboss=False,
                    ).livekey_name = key.name

    def _build_sk_name(self, sk_name, prefix) -> str:
        """Builds a displayable name from internal shapekey names.

        Removes prefix->Replaces underscores with space->Removes .Transferred
        suffix from age shapekey->Title case the name

        Args:
            sk_name (str): internal name of the shapekey
            prefix (str): category prefix of the shapekey to be removed

        Returns:
            str: Display name of shapekey
        """
        for r in ((prefix, ""), ("_", " "), (".Transferred", "")):
            sk_name = sk_name.replace(*r)

        return sk_name.title()

    def _get_ff_col(self, layout, categ_name, is_open_propname) -> bpy.types.UILayout:
        """Creates a collapsable box for passed shapekey category

        Args:
            layout (bpy.types.layout): layout.box of the facial features section
            categ_name (str): Name of this shapekey category to be displayed
            is_open_propname (str): name of the settings bool that opens and
            closes the box

        Returns:
            UILayout: Column inside collapsable box
        """
        sett = self.sett
        boxbox = layout.box()
        boxbox.scale_y = 1 if get_prefs().compact_ff_ui else 1.5

        ui_bools = {
            "nose": sett.ui.nose,
            "u_skull": sett.ui.u_skull,
            "chin": sett.ui.chin,
            "mouth": sett.ui.mouth,
            "eyes": sett.ui.eyes,
            "cheeks": sett.ui.cheeks,
            "l_skull": sett.ui.l_skull,
            "jaw": sett.ui.jaw,
            "ears": sett.ui.ears,
            "other": sett.ui.other,
            "custom": sett.ui.custom,
            "presets": sett.ui.presets,
        }

        row = boxbox.row()
        row.prop(
            sett.ui,
            is_open_propname,
            text=categ_name,
            icon="TRIA_DOWN" if ui_bools[is_open_propname] else "TRIA_RIGHT",
            toggle=True,
            emboss=False,
        )
        if is_open_propname != "presets":
            row.operator(
                "hg3d.random_value", text="", icon="FILE_REFRESH", emboss=False
            ).random_type = "face_{}".format(is_open_propname)
        else:
            row.operator("hg3d.showinfo", text="", icon="BLANK1", emboss=False)

        col = layout.column(align=True)
        col.scale_y = 1 if get_prefs().compact_ff_ui else 1.5

        return col
