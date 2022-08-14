import functools
from tokenize import Triple

import bpy
from HumGen3D.human.human import Human

from ...backend.preview_collections import get_hg_icon
from ..tips_suggestions_ui import draw_tips_suggestions_ui


def subpanel_draw(draw_method):
    @functools.wraps(draw_method)
    def wrapper(self, context):
        self.human = Human.from_existing(context.object)
        self.sett = context.scene.HG3D
        self.draw_top_widget(self.human)
        self.draw_bold_title(self.layout, self.phase_name.capitalize(), self.phase_name)

        draw_method(self, context)

        draw_tips_suggestions_ui(self.layout, context)

    return wrapper


class MainPanelPart:
    bl_idname = "MainPanelPart"
    bl_label = "HumGen"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"
    phase_name = None

    def draw(self, context):
        self.layout.label(text="Fu")
        pass  # raise NotImplementedError

    def draw_header(self, context):
        layout = self.layout
        row = layout.row()
        row.alert = True
        row.operator(
            "hg3d.section_toggle", text="Back", depress=True, icon="BACK"
        ).section_name = "closed"

    def draw_bold_title(self, layout, text: str, icon=None):
        row = layout.box().row()
        row.scale_x = 0.3
        row.alignment = "CENTER"
        if icon:
            if icon_value := get_hg_icon(icon):
                row.label(icon_value=icon_value)
            else:
                row.label(icon=icon)
            row.separator()

        for char in text:
            if char.islower():
                char = f"{char}_lower"
            row.label(icon_value=get_hg_icon(char))

        separators = 1 + bool(icon)
        for _ in range(separators):
            row.separator()

    def draw_panel_switch_header(self, layout, sett):
        """Draws a enum prop that switches between main humgen panel and extras panel
        Args:
            layout (UILayout): header layout to draw the switch in
            sett (PropertyGroup): HumGen props
        """
        row = layout.row()
        row.scale_x = 1.5
        row.alignment = "EXPAND"
        row.prop(sett.ui, "active_tab", expand=True, icon_only=True)

    def draw_top_widget(self, human):
        col = self.layout.column(align=True)

        row = col.row(align=True)
        row.scale_y = 1.5
        row.scale_x = 0.9
        row.operator(
            "hg3d.next_prev_human", text="", icon="TRIA_LEFT", depress=True
        ).forward = False
        row.operator(
            "hg3d.next_prev_human", text="", icon="TRIA_RIGHT", depress=True
        ).forward = True
        # button showing name and gender of human
        row.operator(
            "view3d.view_selected",
            text=self._get_header_label(human),
            depress=bool(human),
        )
        subrow = row.row(align=True)
        subrow.alert = True
        subrow.scale_x = 1.2
        subrow.operator("hg3d.delete", text="", icon="TRASH")  # , depress=True)

        if human:
            box = col.box()
            hair_systems = self._get_hair_systems(human.body_obj, eyesystems=True)
            self._draw_hair_children_switch(hair_systems, box)

        if self.phase_name != "closed":
            pass  # self.draw_back_button(self.layout)

    @classmethod
    def poll(cls, context):
        sett = context.scene.HG3D
        if not sett.ui.active_tab == "CREATE":
            return False
        elif not sett.ui.phase == cls.phase_name:
            return False
        elif sett.custom_content.content_saving_ui:
            return False
        human = Human.from_existing(context.object, strict_check=False)
        if not human:
            return False
        if human.is_batch_result[0]:
            return False

    def draw_back_button(self, layout):
        row = layout.column(align=True).row()
        row.scale_y = 1.5
        subrow = row.row()
        subrow.alert = True
        subrow.operator(
            "hg3d.section_toggle", text="", depress=True, icon="BACK"
        ).section_name = "closed"
        box = row.box()
        box.label(text="yay")

    def get_flow(self, layout, animation=False) -> bpy.types.UILayout:
        """Returns a property split enabled UILayout

        Args:
            sett (PropertyGroup): HumGen props
            layout (UILayout): layout to draw flor in
            animation (bool, optional): show keyframe dot on row. Defaults to False.

        Returns:
            UILayout: flow layout
        """

        col_2 = layout.column(align=True)
        col_2.use_property_split = True
        col_2.use_property_decorate = animation

        flow = col_2.grid_flow(
            row_major=False,
            columns=1,
            even_columns=True,
            even_rows=False,
            align=True,
        )  # TODO is this even necessary now property split is used?
        return flow

    def draw_sub_spoiler(
        self, layout, sett, prop_name, label
    ) -> "tuple[bool, bpy.types.UILayout]":
        """Draws a ciollapsable box, with title and arrow symbol

        Args:
            layout (UILayout): Layout to draw spoiler in
            sett (PropertyGroup): HumGen Props
            prop_name (str): Name of the BoolProperty that opens/closes spoiler
            label (str): Label to display in the ui

        Returns:
            tuple[bool, bpy.types.UILayout]:
                bool: True means the box will open in the UI
                UILayout: layout.box to draw items inside the openable box
        """
        boxbox = layout.box()
        boxbox.prop(
            sett.ui,
            prop_name,
            icon="TRIA_DOWN" if getattr(sett.ui, prop_name) else "TRIA_RIGHT",
            text=label,
            emboss=False,
            toggle=True,
        )

        spoiler_open = getattr(sett.ui, prop_name)

        return spoiler_open, boxbox

    def _get_hair_systems(self, body_obj, eyesystems=False) -> list:
        """get a list of hair systems on this object

        Args:
            body_obj (Object): HumGen body object, can be any mesh object

        Returns:
            list: list of hair particle systems
        """

        hair_systems = []
        for mod in body_obj.modifiers:
            if mod.type == "PARTICLE_SYSTEM" and (
                eyesystems
                or not mod.particle_system.name.startswith(("Eyebrows", "Eyelashes"))
            ):
                hair_systems.append(mod.particle_system)

        return hair_systems

    def _draw_hair_children_switch(self, hair_systems, layout):
        """Draws a switch for turning children to render amount or back to 1

        Args:
            hair_systems (list): List of hair particle systems
            layout (UILayout): layout to draw switch in
        """

        row = layout.row(align=True)
        if not hair_systems:
            row.label(text="No hair systems found")
            return

        row.label(
            text=(
                "Hair children are hidden"
                if self.human.hair.children_ishidden
                else "Hair children are visible"
            )
        )
        row.operator(
            "hg3d.togglechildren",
            text="",
            icon=("HIDE_ON" if hair_systems[0].settings.child_nbr <= 1 else "HIDE_OFF"),
        )

    def _get_header_label(self, human):
        if not human:
            label = "No Human selected"
        else:
            name = human.name.replace("HG_", "").replace("_RIGIFY", "")
            gender = human.gender.capitalize()
            label = f"This is {name}"
        return label

    def _draw_hair_length_ui(self, hair_systems, box):
        """shows a collapsable list of hair systems, with a slider for length

        Args:
            hair_systems (list): list of particle hair systems
            box (UILayout): layout.box of hair section
        """
        boxbox = box.box()
        boxbox.prop(
            self.sett.ui,
            "hair_length",
            icon="TRIA_DOWN" if self.sett.ui.hair_length else "TRIA_RIGHT",
            emboss=False,
            toggle=True,
        )
        if not self.sett.ui.hair_length:
            return

        if not hair_systems:
            box.label(text="No hairstyles loaded")
            return

        flow = self.get_flow(box)
        for ps in hair_systems:
            ps_name = ps.name.replace("fh_", "").replace("_", " ").title()

            row = flow.row()
            row.prop(ps.settings, "child_length", text=ps_name)
            row.operator("hg3d.removehair", text="", icon="TRASH").hair_system = ps.name

    def searchbox(self, sett, name, layout):
        """draws a searchbox of the given preview collection

        Args:
            sett (PropertyGroup): HumGen props
            name (str): name of the preview collection to search
            layout (UILayout): layout to draw search box in
        """
        row = layout.row(align=True)
        row.prop(sett.pcoll, "search_term_{}".format(name), text="", icon="VIEWZOOM")

        if hasattr(sett.pcoll, f"search_term_{name}"):
            row.operator(
                "hg3d.clear_searchbox", text="", icon="X"
            ).searchbox_name = name
