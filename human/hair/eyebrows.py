# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy
from bpy.types import Context  # type:ignore
from HumGen3D.human.hair.basehair import BaseHair
from HumGen3D.user_interface.documentation.feedback_func import ShowMessageBox

from ..base.prop_collection import PropCollection


class EyebrowSettings(BaseHair):
    def __init__(self, human):
        self._human = human
        self._startswith = "Eyebrow"

    def _set_from_preset(self, preset_eyebrow):
        """Sets the eyebrow named in preset_data as the only visible eyebrow
        system

        Args:
            hg_body (Object): humgen body obj
            preset_data (dict): preset data dict
        """
        for mod in self.modifiers:
            mod.show_viewport = mod.show_render = False

        preset_eyebrows = next(
            (
                mod
                for mod in self.modifiers
                if mod.particle_system.name == preset_eyebrow
            ),
            None,
        )

        if not preset_eyebrows:
            ShowMessageBox(message=("Could not find eyebrows named " + preset_eyebrow))
        else:
            preset_eyebrows.show_viewport = preset_eyebrows.show_render = True

    def remove_unused(self, context: Context = None, _internal: bool = False):
        if not context:
            context = bpy.context

        remove_list = [
            mod.particle_system.name for mod in self.modifiers if not mod.show_render
        ]

        if _internal and len(self.modifiers) == len(remove_list):
            ShowMessageBox(
                message="""All eyebrow systems are hidden (render),
                        please manually remove particle systems you aren't using
                        """
            )
            return

        # TODO without bpy.ops
        old_active = context.view_layer.objects.active
        context.view_layer.objects.active = self._human.body_obj
        for remove_name in remove_list:
            ps_idx = self._human.hair.particle_systems.find(remove_name)
            self.particle_systems.active_index = ps_idx
            bpy.ops.object.particle_system_remove()
        context.view_layer.objects.active = old_active

    def _switch_eyebrows(self, forward=True, report=False):
        eyebrows = self.modifiers
        if not eyebrows:
            if report:
                self.report({"WARNING"}, "No eyebrow particle systems found")
            return
        if len(eyebrows) == 1:
            if report:
                self.report({"WARNING"}, "Only one eyebrow system found")
            return

        idx, current_ps = next(
            (
                (i, mod)
                for i, mod in enumerate(eyebrows)
                if mod.show_viewport or mod.show_render
            ),
            0,
        )

        next_idx = idx + 1 if forward else idx - 1
        if next_idx >= len(eyebrows) or next_idx < 0:
            next_idx = 0

        next_ps = eyebrows[next_idx]
        next_ps.show_viewport = next_ps.show_render = True

        for ps in eyebrows:
            if ps != next_ps:
                ps.show_viewport = ps.show_render = False
