# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implement base class for classes used for manipulating human hair.

Used for the four subclasses of human.hair: regular_hair, eyebrows, eyelashes, face_hair
"""

import contextlib
import json
import os
import random
from typing import Any, Literal, Optional, cast

import bpy
from bpy.types import Image  # type:ignore
from HumGen3D.backend import get_prefs, hg_delete, remove_broken_drivers
from HumGen3D.backend.preferences.preferences import HG_PREF
from HumGen3D.common.collections import add_to_collection
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.math import round_vector_to_tuple
from HumGen3D.common.shadernode import NodeInput
from HumGen3D.common.type_aliases import C
from HumGen3D.human import hair
from HumGen3D.human.common_baseclasses.pcoll_content import PreviewCollectionContent
from HumGen3D.human.common_baseclasses.prop_collection import PropCollection
from HumGen3D.human.common_baseclasses.savable_content import SavableContent
from HumGen3D.human.hair.haircards import HairCollection
from HumGen3D.human.hair.saving import save_hair
from HumGen3D.human.height.height import apply_armature
from HumGen3D.human.keys.keys import apply_shapekeys

HAIR_NODE_NAME = "HG_Hair"


class BaseHair:
    """Base class used for all four hair subclasses.

    Contains ways to change the material of the hair, to access modifiers and particle
    systems and to generate haircards.
    """

    def __init__(self) -> None:
        self.lightness = NodeInput(self, HAIR_NODE_NAME, "Lightness")
        self.redness = NodeInput(self, HAIR_NODE_NAME, "Redness")
        self.roughness = NodeInput(self, HAIR_NODE_NAME, "Roughness")
        self.salt_and_pepper = NodeInput(self, HAIR_NODE_NAME, "Pepper & Salt")
        self.roots = NodeInput(self, HAIR_NODE_NAME, "Roots")
        self.root_lightness = NodeInput(self, HAIR_NODE_NAME, "Root Lightness")
        self.root_redness = NodeInput(self, HAIR_NODE_NAME, "Root Redness")
        self.roots_hue = NodeInput(self, HAIR_NODE_NAME, "Roots Hue")
        self.fast_or_accurate = NodeInput(self, HAIR_NODE_NAME, "Fast/Accurate")
        self.hue = NodeInput(self, HAIR_NODE_NAME, "Hue")

    @property
    def particle_systems(self) -> PropCollection:
        """Get propcollection of particle systems on the human used by this hair type.

        Returns:
            PropCollection: PropCollection of particle systems used by this hair type
        """
        particle_systems = self._human.hair.particle_systems

        psys = [ps for ps in particle_systems if self._condition(ps.name)]
        return PropCollection(psys)

    @property
    def modifiers(self) -> PropCollection:
        """Modifiers associated with the particle systems of this hair type.

        Returns:
            PropCollection: PropCollection of modifiers associated with the particle
                systems of this hair type
        """
        particle_mods = self._human.hair.modifiers

        modifiers = [
            mod for mod in particle_mods if self._condition(mod.particle_system.name)
        ]
        return PropCollection(modifiers)

    @property
    def haircard_obj(self) -> Optional[bpy.types.Object]:
        """Blender object of haircards IF generated.

        Returns:
            bpy.types.Object: Blender object of haircards IF generated else None
        """
        return next(  # type:ignore[call-overload]
            (obj for obj in self._human.children if self._haircap_tag in obj), None
        )

    @property
    def materials(self) -> list[bpy.types.Material]:
        """List of materials used for this type of hair.

        Usually singleton, but will contain multiple values if haircards are generated.

        Returns:
            list[bpy.types.Material]: List of materials used for this type of hair
        """
        if self.haircard_obj:
            return self.haircard_obj.data.materials
        else:
            return [self._human.objects.body.data.materials[self._mat_idx]]

    @property
    def nodes(self) -> PropCollection:
        """PropCollection of nodes used in the materials for this type of hair. # noqa

        Returns:
            PropCollection: PropCollection of nodes used in the materials for this type
        """
        nodes: list[bpy.types.ShaderNode] = []
        for mat in self.materials:
            nodes.extend(mat.node_tree.nodes)  # type:ignore[arg-type]
        return PropCollection(nodes)

    @injected_context
    def convert_to_haircards(
        self, quality: Literal["high"] = "high", context: C = None
    ) -> bpy.types.Object:
        """Convert the hair of this type to haircards.

        Will generate a mesh object consisting of a haircap and haircards. For eye
        systems only a haircap will be generated.

        Args:
            quality (Literal["high"]): Quality of the haircards. Defaults to
                high.
            context (C): Blender context. bpy.context if not provided.

        Returns:
            bpy.types.Object: Blender object of the haircap
        """
        hair_objs: list[bpy.types.Object] = []

        if not self.modifiers:
            raise HumGenException("No hair to convert")

        for mod in self.modifiers:
            if not mod.show_viewport:
                continue

            ps = mod.particle_system
            ps.settings.child_nbr = ps.settings.child_nbr // 10
            body_obj = self._human.objects.body
            with context.temp_override(
                active_object=body_obj,
                object=body_obj,
                selected_objects=[
                    body_obj,
                ],
            ):
                bpy.ops.object.modifier_convert(modifier=mod.name)

            hair_obj = context.object  # TODO this is bound to fail
            hc = HairCollection(hair_obj, self._human)
            if self._haircap_type == "Scalp":
                objs = hc.create_mesh(quality)
                hair_objs.extend(objs)
                for obj in objs:
                    obj.name += ps.name

                hc.add_uvs()
                hc.add_material()

        density_vertex_groups = [
            body_obj.vertex_groups[ps.vertex_group_density]
            for ps in self.particle_systems
            if ps.vertex_group_density
        ]
        if density_vertex_groups or self._haircap_type != "Scalp":
            cap_obj = hc.add_haircap(
                self._human, self._haircap_type, density_vertex_groups, context
            )
            hair_objs.append(cap_obj)
        hc.set_node_values(self._human)

        if len(hair_objs) > 1:
            join_obj_name = hair_objs[0].name
            with context.temp_override(
                active_object=hair_objs[0],
                selected_editable_objects=hair_objs,
            ):
                bpy.ops.object.join()

            joined_object = bpy.data.objects[join_obj_name]  # type:ignore[index]
            joined_object.name = "Haircards"
        else:
            joined_object = cap_obj

        for mod in self.modifiers:  # noqa
            mod.show_viewport = False

        joined_object.parent = self._human.objects.rig
        joined_object.modifiers.new("Armature", "ARMATURE")

        add_to_collection(context, joined_object, "HumGen")
        return joined_object

    @injected_context
    def get_evaluated_particle_systems(self, context: C = None) -> PropCollection:
        """Get an evaluated version of the particle systems of this hair type.

        Args:
            context (C): Blender context. bpy.context if not provided.

        Returns:
            PropCollection: PropCollection of evaluated particle systems
        """
        dg = context.evaluated_depsgraph_get()
        eval_body = self._human.objects.body.evaluated_get(dg)
        particle_systems = eval_body.particle_systems
        psys = [ps for ps in particle_systems if self._condition(ps.name)]
        return PropCollection(psys)

    def delete_all(self) -> None:  # noqa
        raise NotImplementedError  # FIXME

    def randomize_color(self) -> None:
        """Randomize the color of the hair of this type."""
        # TODO make system more elaborate
        hair_color_dict = {
            "blonde": (4.0, 0.8, 0.0),
            "black": (0.0, 1.0, 0.0),
            "dark_brown": (0.5, 1.0, 0.0),
            "brown": (1.0, 1.0, 0.0),
            "red": (3.0, 1.0, 0.0),
        }

        hair_color = hair_color_dict[random.choice(list(hair_color_dict))]

        for mat in self._human.objects.body.data.materials[1:]:
            nodes = mat.node_tree.nodes
            hair_node = next(n for n in nodes if n.name.startswith("HG_Hair"))
            hair_node.inputs["Lightness"].default_value = hair_color[0]
            hair_node.inputs["Redness"].default_value = hair_color[1]
            hair_node.inputs["Pepper & Salt"].default_value = hair_color[2]

    def as_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of this hair type.

        Contains information about material.

        Returns:
            dict[str, Any]: Dictionary representation of this hair type
        """
        return {
            "lightness": self.lightness.value,
            "redness": self.redness.value,
            "roughness": self.roughness.value,
            "salt_and_pepper": self.salt_and_pepper.value,
            "roots": self.roots.value,
            "root_lightness": self.root_lightness.value,
            "root_redness": self.root_redness.value,
            "roots_hue": self.roots_hue.value,
            "fast_or_accurate": self.fast_or_accurate.value,
            "hue": self.hue.value,
        }

    def _condition(self, string: str) -> bool:  # noqa
        if hasattr(self, "_startswith"):
            return string.startswith(self._startswith)
        elif hasattr(self, "_notstartswith"):
            return not string.startswith(self._notstartswith)
        else:
            raise HumGenException(
                "Did not initialize hair class with _startswith or _notstartswith"
            )

    def _add_quality_props(self, mod: bpy.types.Modifier) -> None:

        ps = mod.particle_system.settings
        ps["steps"] = ps.render_step
        ps["children"] = ps.rendered_child_count
        ps["root"] = ps.root_radius
        ps["tip"] = ps.tip_radius

    def __hash__(self) -> int:
        key_data = []
        for particle_system in self.particle_systems:
            for particle in particle_system.particles:
                key_data.extend(
                    [round_vector_to_tuple(k.co_local) for k in particle.hair_keys]
                )
                key_data.append(round_vector_to_tuple(particle.location, precision=8))
                key_data.append(round_vector_to_tuple(particle.rotation, precision=4))

        return hash(tuple(key_data))


class ImportableHair(BaseHair, PreviewCollectionContent, SavableContent):
    """Further specialization of BaseHair for hair that can be imported from a pcoll."""

    @injected_context
    def set(self, preset: str, context: C = None) -> None:  # noqa: A003, CCR001
        """Loads hair system the user selected.

        Args:
            preset (str): Name of the preset to load. Must be in the preview collection.
                Options can be retreived from `get_options()`.
            context (C): Blender context. bpy.context if not provided.
        """
        pref = get_prefs()

        self._active = preset

        full_path = str(pref.filepath) + preset
        with open(full_path) as f:
            hair_data = json.load(f)

        blendfile = hair_data["blend_file"]
        json_systems = hair_data["hair_systems"]

        hair_type = (
            "face_hair"
            if isinstance(self, hair.face_hair.FacialHairSettings)
            else "head"
        )

        hair_obj = self._import_hair_obj(
            context, hair_type, pref, blendfile  # type:ignore
        )

        human = self._human
        human.hide_set(False)

        if hair_type == "face_hair":
            human.hair.face_hair.remove_all()
        else:
            human.hair.regular_hair.remove_all()
        remove_broken_drivers()

        mask_mods = [m for m in self._human.objects.body.modifiers if m.type == "MASK"]
        for mod in mask_mods:
            mod.show_viewport = False

        # IMPORTANT: Hair systems do not transfer correctly if they are hidden in the
        # viewport
        for mod in hair_obj.modifiers:
            if mod.type == "PARTICLE_SYSTEM":
                mod.show_viewport = True

        context.view_layer.objects.active = hair_obj
        self._morph_hair_obj_to_body_obj(context, hair_obj)  # type:ignore

        context.view_layer.objects.active = hair_obj
        bpy.ops.particle.disconnect_hair(all=True)

        for obj in context.selected_objects:
            obj.select_set(False)
        context.view_layer.objects.active = hair_obj
        human.objects.body.select_set(True)

        # iterate over hair systems that need to be transferred

        for ps_name in json_systems:
            self._transfer_hair_system(
                context, json_systems, hair_obj, ps_name  # type:ignore
            )

        for vg in hair_obj.vertex_groups:
            if vg.name.lower().startswith(("hair", "fh")):
                self._transfer_vertexgroup(hair_obj, vg.name)

        new_hair_systems = self._get_hair_systems_dict(hair_obj)

        context.view_layer.objects.active = self._human.objects.body
        for mod in new_hair_systems:
            self._reconnect_hair(mod)
            self._add_quality_props(mod)

        self._set_correct_particle_vertexgroups(new_hair_systems, hair_obj)
        self._set_correct_hair_material(new_hair_systems, hair_type)

        for mod in self._human.hair.modifiers:
            mod.show_expanded = False

        self._move_modifiers_above_masks(new_hair_systems)
        for mod in human.objects.body.modifiers:
            # Turn on masks again
            if mod.type == "MASK":
                mod.show_viewport = True

            # Show all hair systems
            elif mod.type == "PARTICLE_SYSTEM":
                ps_sett = mod.particle_system.settings
                ps_sett.child_nbr = ps_sett.rendered_child_count

        hg_delete(hair_obj)
        remove_broken_drivers()
        human.hair._add_quality_props()
        human.props.hashes[f"${self._pcoll_name}"] = str(hash(self))

    @injected_context
    def save_to_library(
        self,
        particle_system_names: list[str],
        hairstyle_name: str,
        category: str,
        for_male: bool = True,
        for_female: bool = True,
        thumbnail: Optional[Image] = None,
        context: C = None,
    ) -> None:
        """Save the currently active hair system of this type to the HG library.

        Args:
            particle_system_names (list[str]): Names of the particle systems to save.
            hairstyle_name (str): Name to save this hairstyle as.
            category (str): Category to save this hairstyle in. If this category does
                not already exist, a new folder will be created.
            for_male (bool): Whether this hairstyle is available for male humans.
            for_female (bool): Whether this hairstyle is available for female humans.
            thumbnail (Optional[Image]): Thumbnail to save with this hairstyle. Pass
                a Blender Image object here. If None, no thumbnail will be used.
            context (C): Blender context. bpy.context if not provided.
        """

        hair_type = self._pcoll_name
        save_hair(
            self._human,
            hairstyle_name,
            category,
            particle_system_names,
            hair_type,
            context,
            for_male=for_male,
            for_female=for_female,
            thumb=thumbnail,
        )

    def remove_all(self) -> None:
        """Remove all modifiers of this hair type from the human."""
        modifiers = self.modifiers
        for mod in modifiers:
            self._human.objects.body.modifiers.remove(mod)

    @injected_context
    def randomize(self, context: C = None) -> None:
        """Pick a random hairstyle from the library and apply it to the human.

        Args:
            context (C): Blender context. bpy.context if not provided.
        """
        preset_options = self.get_options(context)
        chosen_preset = random.choice(preset_options)
        self.set(chosen_preset, context)

    def _import_hair_obj(
        self, context: bpy.types.Context, hair_type: str, pref: HG_PREF, blendfile: str
    ) -> bpy.types.Object:
        """Imports the object that contains the hair systems named in the json file.

        Args:
            context (Context): Blender context
            hair_type (str): type of hair system ('facial hair' or 'head')
            pref (HG_PREF): HumGen preferences
            blendfile (str): name of blendfile to open

        Returns:
            Object: body object that contains the hair systems
        """
        # import hair object, linking it to the scene and collection
        subfolder = "head" if hair_type == "head" else "face_hair"
        blendpath = os.path.join(pref.filepath, "hair", subfolder, blendfile)

        with bpy.data.libraries.load(blendpath, link=False) as (_, data_to):
            data_to.objects = ["HG_Body"]

        hair_obj = data_to.objects[0]
        scene = context.scene
        scene.collection.objects.link(hair_obj)

        return cast(bpy.types.Object, hair_obj)

    def _morph_hair_obj_to_body_obj(
        self, context: bpy.types.Context, hair_obj: bpy.types.Object
    ) -> None:  # noqa
        """Gives the imported hair object the exact same shape as hg human."""  # noqa
        body_copy = self._human.objects.body.copy()  # TODO without copying
        body_copy.data = body_copy.data.copy()
        context.scene.collection.objects.link(body_copy)

        apply_shapekeys(body_copy)
        remove_broken_drivers()
        apply_armature(body_copy)

        for obj in context.selected_objects:
            obj.select_set(False)

        hair_obj.select_set(True)
        body_copy.select_set(True)
        context.view_layer.objects.active = hair_obj
        bpy.ops.object.join_shapes()

        sk = hair_obj.data.shape_keys.key_blocks
        sk[body_copy.name].value = 1

        hg_delete(body_copy)

    def _transfer_hair_system(
        self,
        context: bpy.types.Context,
        json_systems: dict[str, dict[str, float]],
        hair_obj: bpy.types.Object,
        ps_name: str,
    ) -> None:
        ps_mods = [mod for mod in hair_obj.modifiers if mod.type == "PARTICLE_SYSTEM"]
        for mod in ps_mods:
            if mod.particle_system.name == ps_name:
                self._set_particle_settings(json_systems, mod, ps_name)  # type:ignore
                break

        override = context.copy()  # type:ignore[func-returns-value]
        override["particle_system"] = hair_obj.particle_systems[ps_name]  # type:ignore
        bpy.ops.particle.copy_particle_systems(
            override, remove_target_particles=False, use_active=True
        )

    def _set_particle_settings(
        self,
        json_systems: dict[str, dict[str, float]],
        mod: bpy.types.Modifier,
        ps_name: str,
    ) -> None:
        """Sets the settings of this particle settings according to the json dict.

        Args:
            json_systems (dict):
                key (str): name of hair system
                value (dict):
                    key (str): name of setting
                    value (Anytype): value to set that setting to
            mod (bpy.types.modifier): modifier of this particle system
            ps_name (str): name of the particle system
        """
        psys = mod.particle_system.settings
        json_sett = json_systems[ps_name]
        if "length" in json_sett:
            psys.child_length = json_sett["length"]
        if "children_amount" in json_sett:
            psys.child_nbr = json_sett["children_amount"]
            psys.rendered_child_count = json_sett["children_amount"]
        if "path_steps" in json_sett:
            psys.display_step = json_sett["path_steps"]
            psys.render_step = json_sett["path_steps"]

    def _transfer_vertexgroup(self, from_obj: bpy.types.Object, vg_name: str) -> None:
        """Copies vertex groups from one object to the other.

        Args:
            from_obj (Object): object to transfer vertex group from
            vg_name  (str)   : name of vertex group to transfer
        """
        vert_dict = {}
        for vert_idx, _ in enumerate(from_obj.data.vertices):
            with contextlib.suppress(Exception):
                vg = from_obj.vertex_groups[
                    vg_name
                ]  # type:ignore[index, call-overload]
                vert_dict[vert_idx] = vg.weight(vert_idx)

        target_vg = self._human.objects.body.vertex_groups.new(name=vg_name)
        # fmt: off
        for v in vert_dict:
            target_vg.add([v, ], vert_dict[v], "ADD")
        # fmt: on

    def _get_hair_systems_dict(
        self, hair_obj: bpy.types.Object
    ) -> dict[bpy.types.Modifier, str]:
        """Gets hair particle systems on passed object, including modifiers.

        Args:
            hair_obj (Object): imported hair obj

        Returns:
            dict:
                key   (bpy.types.modifier)       : Modifier of a particle system
                value (bpy.types.particle_system): Particle hair system
        """
        system_names = []

        for mod in [mod for mod in hair_obj.modifiers if mod.type == "PARTICLE_SYSTEM"]:
            system_names.append(mod.particle_system.name)

        new_mod_dict = {}
        for mod in self._human.hair.modifiers:
            if mod.particle_system.name in system_names:
                new_mod_dict[mod] = mod.particle_system.name

        return new_mod_dict

    def _reconnect_hair(self, mod: bpy.types.Modifier) -> None:
        """Reconnects the transferred hair systems to the skull.

        Args:
            mod (bpy.types.modifier): Modifier of type particle system to reconnect
        """
        particle_systems = self._human.hair.particle_systems
        for i, ps in enumerate(particle_systems):
            if ps.name == mod.particle_system.name:
                ps_idx = i
        particle_systems.active_index = ps_idx
        bpy.ops.particle.connect_hair(all=False)

    def _set_correct_particle_vertexgroups(
        self, new_systems: dict[bpy.types.Modifier, str], from_obj: bpy.types.Object
    ) -> None:
        """Corrects particle system errors caused bytransfering systems.

        Args:
            new_systems (dict): modifiers and particle_systems to correct vgs for
            from_obj (Object): Object to check correct particle vertex group on
        """
        for ps_name in new_systems.values():

            vg_attributes = [
                "vertex_group_clump",
                "vertex_group_density",
                "vertex_group_field",
                "vertex_group_kink",
                "vertex_group_length",
                "vertex_group_rotation",
                "vertex_group_roughness_1",
                "vertex_group_roughness_2",
                "vertex_group_roughness_end",
                "vertex_group_size",
                "vertex_group_tangent",
                "vertex_group_twist",
                "vertex_group_velocity",
            ]

            old_ps_sett = from_obj.particle_systems[ps_name]  # type:ignore
            new_ps_sett = self._human.hair.particle_systems[ps_name]

            for vg_attr in vg_attributes:
                setattr(new_ps_sett, vg_attr, getattr(old_ps_sett, vg_attr))

    def _set_correct_hair_material(
        self, new_systems: dict[bpy.types.Modifier, str], hair_type: str
    ) -> None:
        """Sets face hair material for fh systems and head head material for head hair.

        Args:
            new_systems (dict): Dict of modifiers and particle_systems of hair systems
            hair_type (str): 'head' for normal, 'face_hair' for facial hair
        """
        search_mat = ".HG_Hair_Face" if hair_type == "face_hair" else ".HG_Hair_Head"
        # Search for current name of material to account for v1, v2 and v3
        body_obj = self._human.objects.body
        mat_name = next(
            mat.name
            for mat in body_obj.data.materials
            if mat.name.startswith(search_mat)
        )

        for ps in new_systems:
            ps.particle_system.settings.material_slot = mat_name

    def _move_modifiers_above_masks(
        self, new_systems: dict[bpy.types.Modifier, str]
    ) -> None:
        lowest_mask_index = next(
            (
                i
                for i, mod in enumerate(self._human.objects.body.modifiers)
                if mod.type == "MASK"
            ),
            None,
        )
        if not lowest_mask_index:
            return

        for mod in new_systems:
            # Use old method when older than 2.90
            if (2, 90, 0) > bpy.app.version:
                while (
                    self._human.objects.body.modifiers.find(mod.name)
                    > lowest_mask_index
                ):
                    bpy.ops.object.modifier_move_up(  # type:ignore[misc]
                        {"object": self._human.objects.body},  # type:ignore[arg-type]
                        modifier=mod.name,
                    )

            elif self._human.objects.body.modifiers.find(mod.name) > lowest_mask_index:
                bpy.ops.object.modifier_move_to_index(
                    modifier=mod.name, index=lowest_mask_index
                )
