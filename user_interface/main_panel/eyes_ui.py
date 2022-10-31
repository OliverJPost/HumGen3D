# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy

from ..panel_functions import prettify
from ..ui_baseclasses import MainPanelPart, subpanel_draw


class HG_PT_EYES(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_EYES"
    phase_name = "eyes"

    @subpanel_draw
    def draw(self, context):
        """Options for changing eyebrows and eye shader."""
        col = self.layout.column()

        if "hg_baked" in self.human.rig_obj:
            col.label(text="Textures are baked", icon="INFO")
            self._draw_eyebrow_switch(col)
            return

        hg_eyes = self.human.eye_obj

        mat = hg_eyes.data.materials[1]
        nodes = mat.node_tree.nodes

        row = col.row()
        row.alignment = "CENTER"
        row.label(text="Color:", icon="RESTRICT_COLOR_OFF")

        col = col.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False
        row = col.row(align=True)
        row.prop(nodes["HG_Eye_Color"].inputs[2], "default_value", text="Iris Color")
        row.operator(
            "hg3d.random_value", text="", icon="FILE_REFRESH"
        ).random_type = "eyes"
        col.prop(
            nodes["HG_Scelera_Color"].inputs[2],
            "value",
            text="Sclera Color",
        )

        for key in self.human.eyes.keys:
            bpy_key = key.as_bpy()
            row = col.row()
            row.prop(bpy_key, "value_limited", text=prettify(key.name), slider=True)

        col.separator()

        eye_systems = self._get_eye_systems(self.human.body_obj)

        self._draw_hair_length_ui(eye_systems, col)

    def _get_eye_systems(self, body_obj) -> list:
        """Get a list of all particle systems belojnging to eyeborws and eyelashes.

        Args:
            body_obj (Object): HumGen body object

        Returns:
            list: list of modifiers belonging to eyebrow and eyelash systems
        """
        eye_systems = []

        for mod in body_obj.modifiers:
            if (
                mod.type == "PARTICLE_SYSTEM"
                and mod.particle_system.name.startswith(("Eyebrows", "Eyelashes"))
                and (mod.show_viewport or mod.show_render)
            ):
                eye_systems.append(mod.particle_system)

        return eye_systems
