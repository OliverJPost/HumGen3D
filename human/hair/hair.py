# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements class for accessing hair types of human."""

from operator import attrgetter
from typing import TYPE_CHECKING, Any, Literal

import bpy
from bpy.types import bpy_prop_collection  # type:ignore

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.human.common_baseclasses.prop_collection import PropCollection
from HumGen3D.human.hair.eyelashes import EyelashSettings
from HumGen3D.human.hair.face_hair import FacialHairSettings
from HumGen3D.human.hair.regular_hair import RegularHairSettings

from ..hair.eyebrows import EyebrowSettings


class HairSettings:
    """Class for accessing hair types of human and common functionality."""

    def __init__(self, human: "Human") -> None:
        self._human = human

    @property  # TODO make cached
    def eyebrows(self) -> EyebrowSettings:
        """Property for accessing eyebrow settings.

        Returns:
            EyebrowSettings: Eyebrow settings.
        """
        return EyebrowSettings(self._human)

    @property  # TODO make cached
    def eyelashes(self) -> EyelashSettings:
        """Property for accessing eyelash settings.

        Returns:
            EyelashSettings: Eyelash settings.
        """
        return EyelashSettings(self._human)

    @property  # TODO make cached
    def face_hair(self) -> FacialHairSettings:
        """Property for accessing facial hair settings.

        Returns:
            FacialHairSettings: Instance of FacialHairSettings.
        """
        return FacialHairSettings(self._human)

    @property  # TODO make cached
    def regular_hair(self) -> RegularHairSettings:
        """Property for accessing regular hair settings.

        Returns:
            RegularHairSettings: Instance of RegularHairSettings.
        """
        return RegularHairSettings(self._human)

    @property
    def children_ishidden(self) -> bool:
        """Check if hair children of systems are hidden.

        Returns:
            bool: True if children are hidden, False otherwise.
        """
        ishidden = True
        for ps in self._human.hair.particle_systems:
            if ps.settings.child_nbr > 1:
                ishidden = False

        return ishidden

    @property
    def particle_systems(self) -> bpy_prop_collection:
        """All particle systems of human body.

        Returns:
            bpy_prop_collection: Collection of particle systems on human body.
        """
        return self._human.objects.body.particle_systems

    @property
    def modifiers(self) -> PropCollection:
        """All modifiers on human body.

        Returns:
            PropCollection: Collection of ParticleSystem modifiers on human body.
        """
        return PropCollection(
            [
                mod
                for mod in self._human.objects.body.modifiers
                if mod.type == "PARTICLE_SYSTEM"
            ]
        )

    def set_connected(self, connected: bool) -> None:
        """Shortcut for using `connect_hair` and `disconnect_hair` operators.

        This should be used when modifying the body mesh (the actual mesh, not the shape
        keys).

        Args:
            connected (bool): True if hair should be connected, False otherwise.
        """
        with bpy.context.temp_override(active_object=self._human.objects.body):
            if connected:
                bpy.ops.particle.connect_hair(all=True)
            else:
                bpy.ops.particle.disconnect_hair(all=True)

    def children_set_hide(self, hide: bool) -> None:
        """Set the visibility state of the children of all hair systems.

        If you will do a heavy computation on the human body, you should hide the
            children. This is already implemented for builtin heavy operations.

        Args:
            hide (bool): True if children should be hidden, False otherwise.
        """
        for ps in self._human.hair.particle_systems:
            if hide:
                ps.settings.child_nbr = 1
            else:
                render_children = ps.settings.rendered_child_count
                ps.settings.child_nbr = render_children

    def remove_system_by_name(self, name: str) -> None:
        """Remove a certain particle system from the human by its name.

        Args:
            name (str): Name of the particle system to remove.
        """
        mod = next(m for m in self.modifiers if m.particle_system.name == name)
        self._human.objects.body.modifiers.remove(mod)

    def update_hair_shader_type(self, shader_type: Literal["fast", "accurate"]) -> None:
        """Set the shader type between accurate (Eevee comp.) and fast (Cycles only).

        Args:
            shader_type (Literal["fast", "accurate"]): Type to set the shader to.
        """
        value = 0 if shader_type == "fast" else 1

        hg_rig = self._human.objects.rig
        hg_body = hg_rig.HG.body_obj

        for mat in hg_body.data.materials[1:3]:
            hair_group = mat.node_tree.nodes.get("HG_Hair_V3")
            if not hair_group:
                continue

            hair_group.inputs["Fast/Accurate"].default_value = value

    def set_hair_quality(
        self, hair_quality: Literal["high", "medium", "low", "ultralow"]
    ) -> None:
        """Makes hairs thicker and lowers chileren amount for lower qualities.

        Args:
            hair_quality (Literal["high", "medium", "low", "ultralow"]): Quality to set
                all hair types on this human to.
        """
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

    def as_dict(self) -> dict[str, dict[str, Any]]:
        """Return a dictionary representation of the hair settings.

        Returns:
            dict[str, dict[str, Any]]: Dictionary representation of the hair settings.
        """
        return {
            "eyebrows": self.eyebrows.as_dict(),
            "regular_hair": self.regular_hair.as_dict(),
            "face_hair": self.face_hair.as_dict()
            if self._human.gender == "male"
            else {},
        }

    def set_from_dict(self, data: dict[str, dict[str, Any]]) -> None:
        """Set the hair settings from a dictionary representation.

        See `as_dict` for structure.

        Args:
            data (dict[str, dict[str, Any]]): Dictionary representation of the hair
        """
        for hair_categ, categ_data in data.items():
            for attr_name, attr_value in categ_data.items():
                if attr_name == "set":
                    if attr_value:
                        getattr(self, hair_categ).set(attr_value)
                else:
                    retreiver = attrgetter(f"{hair_categ}.{attr_name}")
                    retreiver(self).value = attr_value

    def _get_steps_amount(
        self, hair_quality: Literal["high", "medium", "low", "ultralow"], max_steps: int
    ) -> int:
        min_steps = 1 if max_steps <= 2 else 2 if max_steps <= 4 else 3
        deduction_dict = {"high": 0, "medium": 1, "low": 2, "ultralow": 3}
        new_steps = max_steps - deduction_dict[hair_quality]
        if new_steps < min_steps:
            new_steps = min_steps

        return new_steps

    def _delete_opposite_gender_specific(self) -> None:
        """Deletes the hair of the opposite gender."""
        ps_delete_dict = {
            "female": ("Eyebrows_Male", "Eyelashes_Male"),
            "male": ("Eyebrows_Female", "Eyelashes_Female"),
        }

        gender = self._human.gender

        # TODO make into common func
        for ps_name in ps_delete_dict[gender]:
            self.remove_system_by_name(ps_name)

    def _get_child_amount(
        self,
        hair_quality: Literal["high", "medium", "low", "ultralow"],
        max_children: int,
    ) -> int:
        division_dict = {"high": 1, "medium": 2, "low": 4, "ultralow": 10}
        new_children = max_children / division_dict[hair_quality]

        return int(new_children)

    def _get_root_and_tip(
        self,
        hair_quality: Literal["high", "medium", "low", "ultralow"],
        max_root: int,
        max_tip: int,
    ) -> tuple[int, int]:
        multiplication_dict = {
            "high": 1,
            "medium": 2,
            "low": 6,
            "ultralow": 12,
        }

        new_root = max_root * multiplication_dict[hair_quality]
        new_tip = max_tip * multiplication_dict[hair_quality]

        return new_root, new_tip

    def _add_quality_props(self) -> None:
        for psys in self.particle_systems:
            ps = psys.settings
            ps["steps"] = ps.render_step
            ps["children"] = ps.rendered_child_count
            ps["root"] = ps.root_radius
            ps["tip"] = ps.tip_radius
