# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import os

import bpy
from HumGen3D.backend import get_addon_root
from HumGen3D.human.base.prop_collection import PropCollection
from HumGen3D.human.hair.eyelashes import EyelashSettings
from HumGen3D.human.hair.face_hair import FacialHairSettings
from HumGen3D.human.hair.regular_hair import RegularHairSettings

from ..base.decorators import injected_context
from ..hair.eyebrows import EyebrowSettings


class HairSettings:
    def __init__(self, human):
        self._human = human

    @property  # TODO make cached
    def eyebrows(self) -> EyebrowSettings:
        return EyebrowSettings(self._human)

    @property  # TODO make cached
    def eyelashes(self) -> EyelashSettings:
        return EyelashSettings(self._human)

    @property  # TODO make cached
    def face_hair(self) -> FacialHairSettings:
        return FacialHairSettings(self._human)

    @property  # TODO make cached
    def regular_hair(self) -> RegularHairSettings:
        return RegularHairSettings(self._human)

    @property
    def children_ishidden(self) -> bool:
        ishidden = True
        for ps in self._human.hair.particle_systems:
            if ps.settings.child_nbr > 1:
                ishidden = False

        return ishidden

    def children_set_hide(self, hide: bool):
        for ps in self._human.hair.particle_systems:
            if hide:
                ps.settings.child_nbr = 1
            else:
                render_children = ps.settings.rendered_child_count
                ps.settings.child_nbr = render_children

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
            self.remove_system_by_name(ps_name)

    @property
    def particle_systems(self):
        return self._human.body_obj.particle_systems

    @property
    def modifiers(self):
        return PropCollection(
            [
                mod
                for mod in self._human.body_obj.modifiers
                if mod.type == "PARTICLE_SYSTEM"
            ]
        )

    def remove_system_by_name(self, name):
        mod = next(m for m in self.modifiers if m.particle_system.name == name)
        self._human.body_obj.modifiers.remove(mod)

    def _add_quality_props(self):
        for psys in self.particle_systems:
            ps = psys.settings
            ps["steps"] = ps.render_step
            ps["children"] = ps.rendered_child_count
            ps["root"] = ps.root_radius
            ps["tip"] = ps.tip_radius

    def convert_to_new_hair_shader(self, hg_body):
        hair_mats = hg_body.data.materials[1:3]

        group_nodes = []
        for mat in hair_mats:
            group_nodes.append(
                next(
                    (n for n in mat.node_tree.nodes if n.name == "HG_Hair"),
                    None,
                )
            )

        # check if there is at least one
        if not any(group_nodes):
            return

        addon_folder = get_addon_root()
        blendfile = os.path.join(addon_folder, "human", "hair", "hair_shader_v3.blend")

        if "HG_Hair_V3" in [ng.name for ng in bpy.data.node_groups]:
            new_hair_group = bpy.data.node_groups["HG_Hair_V3"]
        else:
            with bpy.data.libraries.load(blendfile, link=False) as (
                data_from,
                data_to,
            ):
                data_to.node_groups = data_from.node_groups

            new_hair_group = data_to.node_groups[0]

        for node in group_nodes:
            node.node_tree = new_hair_group
            node.name = "HG_Hair_V3"

    def update_hair_shader_type(self, shader_type):
        value = 0 if shader_type == "fast" else 1

        hg_rig = self._human.rig_obj
        hg_body = hg_rig.HG.body_obj

        for mat in hg_body.data.materials[1:3]:
            hair_group = mat.node_tree.nodes.get("HG_Hair_V3")
            if not hair_group:
                continue

            hair_group.inputs["Fast/Accurate"].default_value = value

    def set_hair_quality(self, hair_quality):
        for psys in self._human.hair.particle_systems:
            ps = psys.settings
            max_steps = ps["steps"]
            max_children = ps["children"]
            max_root = ps["root"]
            max_tip = ps["tip"]

            ps.render_step = ps.display_step = self._get_steps_amount(
                hair_quality, max_steps
            )
            ps.rendered_child_count = ps.child_nbr = self._get_child_amount(
                hair_quality, max_children
            )
            ps.root_radius, ps.tip_radius = self._get_root_and_tip(
                hair_quality, max_root, max_tip
            )

    def _get_steps_amount(self, hair_quality, max_steps):
        min_steps = 1 if max_steps <= 2 else 2 if max_steps <= 4 else 3
        deduction_dict = {"high": 0, "medium": 1, "low": 2, "ultralow": 3}
        new_steps = max_steps - deduction_dict[hair_quality]
        if new_steps < min_steps:
            new_steps = min_steps

        return new_steps

    def _get_child_amount(self, hair_quality, max_children):
        division_dict = {"high": 1, "medium": 2, "low": 4, "ultralow": 10}
        new_children = max_children / division_dict[hair_quality]

        return int(new_children)

    def _get_root_and_tip(self, hair_quality, max_root, max_tip):
        multiplication_dict = {
            "high": 1,
            "medium": 2,
            "low": 6,
            "ultralow": 12,
        }

        new_root = max_root * multiplication_dict[hair_quality]
        new_tip = max_tip * multiplication_dict[hair_quality]

        return new_root, new_tip
