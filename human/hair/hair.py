import bpy

from ..hair.eyebrows import EyebrowSettings


class HairSettings:
    def __init__(self, human):
        self._human = human

    @property
    def eyebrows(self) -> EyebrowSettings:
        if not hasattr(self, "_eyebrows"):
            self._eyebrows = EyebrowSettings(self._human)
        return self._eyebrows

    def _delete_opposite_gender_specific(self):
        """Deletes the hair of the opposite gender

        Args:
            hg_body (Object): hg body object
            gender (str): gender of this human
        """
        ps_delete_dict = {
            "female": ("Eyebrows_Male", "Eyelashes_Male"),
            "male": ("Eyebrows_Female", "Eyelashes_Female"),
        }

        gender = self._human.gender
        hg_body = self._human.body_obj

        # TODO make into common func
        for ps_name in ps_delete_dict[gender]:
            ps_idx = next(
                i
                for i, ps in enumerate(hg_body.particle_systems)
                if ps.name == ps_name
            )
            hg_body.particle_systems.active_index = ps_idx

            bpy.ops.object.particle_system_remove()

    @property
    def particle_systems(self):
        return self._human.body_obj.particle_systems

    def _add_quality_props(self):
        for psys in self.particle_systems:
            ps = psys.settings
            ps["steps"] = ps.render_step
            ps["children"] = ps.rendered_child_count
            ps["root"] = ps.root_radius
            ps["tip"] = ps.tip_radius
