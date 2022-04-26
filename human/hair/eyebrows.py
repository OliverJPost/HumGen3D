import bpy

from ...old.blender_operators.common.common_functions import ShowMessageBox
from ..base.prop_collection import PropCollection


class EyebrowSettings:
    def __init__(self, human):
        self._human = human

    @property
    def particle_systems(self):
        if not hasattr(self, "_particle_systems"):
            particle_systems = self._human.body_obj.particle_systems
            eyebrows = [
                ps for ps in particle_systems if ps.name.startswith("Eyebrows")
            ]
            self._particle_systems = PropCollection(eyebrows)
        return self._particle_systems

    @property
    def modifiers(self):
        if not hasattr(self, "_modifiers"):
            particle_mods = [
                mod
                for mod in self._human.body_obj.modifiers
                if mod.type == "PARTICLE_SYSTEM"
            ]
            eyebrows = [
                mod
                for mod in particle_mods
                if mod.particle_system.name.startswith("Eyebrows")
            ]
            self._modifiers = PropCollection(eyebrows)
        return self._modifiers

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
            ShowMessageBox(
                message=("Could not find eyebrows named " + preset_eyebrow)
            )
        else:
            preset_eyebrows.show_viewport = preset_eyebrows.show_render = True
