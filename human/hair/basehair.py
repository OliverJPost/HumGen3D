# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import contextlib
import json
import os
import random
from typing import Literal, Optional, cast

import bpy
from bpy.types import Image  # type:ignore
from HumGen3D.backend import get_prefs, hg_delete, remove_broken_drivers
from HumGen3D.backend.preferences.preferences import HG_PREF
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.math import round_vector_to_tuple
from HumGen3D.common.type_aliases import C
from HumGen3D.human import hair
from HumGen3D.human.common_baseclasses.pcoll_content import PreviewCollectionContent
from HumGen3D.human.common_baseclasses.prop_collection import PropCollection
from HumGen3D.human.common_baseclasses.savable_content import SavableContent
from HumGen3D.human.hair.haircards import HairCollection
from HumGen3D.human.hair.saving import save_hair
from HumGen3D.human.height.height import apply_armature
from HumGen3D.human.keys.keys import apply_shapekeys


class BaseHair:
    @property
    def particle_systems(self) -> PropCollection:
        particle_systems = self._human.hair.particle_systems

        psys = [ps for ps in particle_systems if self._condition(ps.name)]
        return PropCollection(psys)

    @property
    def modifiers(self) -> PropCollection:
        particle_mods = self._human.hair.modifiers

        modifiers = [
            mod for mod in particle_mods if self._condition(mod.particle_system.name)
        ]
        return PropCollection(modifiers)

    @injected_context
    def convert_to_haircards(
        self, quality: Literal["high"] = "high", context: C = None
    ) -> bpy.types.Object:
        dg = context.evaluated_depsgraph_get()

        hair_objs: list[bpy.types.Object] = []
        for mod in self.modifiers:
            if not mod.show_viewport:
                continue

            ps = mod.particle_system
            amount = 400 if quality == "high" else None  # TODO
            ps.settings.child_nbr = amount // len(ps.particles)

            body_obj = self._human.body_obj
            with context.temp_override(
                active_object=body_obj, object=body_obj, selected_objects=list(body_obj)
            ):
                bpy.ops.object.modifier_convert(modifier=mod.name)

            hair_obj = context.object  # TODO this is bound to fail
            hc = HairCollection(hair_obj, body_obj, dg)
            objs = hc.create_mesh()
            hair_objs.extend(objs)
            for obj in objs:
                obj.name += ps.name

            hc.add_uvs()
            hc.add_material()
            cap_obj = hc.add_haircap()
            hair_objs.extend(cap_obj)

        with context.temp_override(
            active_object=hair_objs[0], object=hair_objs[0], selected_objects=hair_objs
        ):
            bpy.ops.object.join()

        for mod in self.modifiers:  # noqa
            mod.show_viewport = False

        return context.object  # TODO bound to fail

    @injected_context
    def get_evaluated_particle_systems(self, context: C = None) -> PropCollection:
        dg = context.evaluated_depsgraph_get()
        eval_body = self._human.body_obj.evaluated_get(dg)
        particle_systems = eval_body.particle_systems
        psys = [ps for ps in particle_systems if self._condition(ps.name)]
        return PropCollection(psys)

    def delete_all(self) -> None:
        raise NotImplementedError  # FIXME

    def randomize_color(self) -> None:
        # TODO make system more elaborate
        hair_color_dict = {
            "blonde": (4.0, 0.8, 0.0),
            "black": (0.0, 1.0, 0.0),
            "dark_brown": (0.5, 1.0, 0.0),
            "brown": (1.0, 1.0, 0.0),
            "red": (3.0, 1.0, 0.0),
        }

        hair_color = hair_color_dict[random.choice(list(hair_color_dict))]

        for mat in self._human.body_obj.data.materials[1:]:
            nodes = mat.node_tree.nodes
            hair_node = next(n for n in nodes if n.name.startswith("HG_Hair"))
            hair_node.inputs["Hair Lightness"].default_value = hair_color[0]
            hair_node.inputs["Hair Redness"].default_value = hair_color[1]
            hair_node.inputs["Pepper & Salt"].default_value = hair_color[2]

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
    @injected_context
    def set(self, preset: str, context: C = None) -> None:  # noqa: A003, CCR001
        """Loads hair system the user selected.

        Args:
            type (str): type of hair to load ('head' or 'face_hair')
        """
        pref = get_prefs()

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

        mask_mods = [m for m in self._human.body_obj.modifiers if m.type == "MASK"]
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
        human.body_obj.select_set(True)

        # iterate over hair systems that need to be transferred

        for ps_name in json_systems:
            self._transfer_hair_system(
                context, json_systems, hair_obj, ps_name  # type:ignore
            )

        for vg in hair_obj.vertex_groups:
            if vg.name.lower().startswith(("hair", "fh")):
                self._transfer_vertexgroup(hair_obj, vg.name)

        new_hair_systems = self._get_hair_systems_dict(hair_obj)

        context.view_layer.objects.active = self._human.body_obj
        for mod in new_hair_systems:
            self._reconnect_hair(mod)
            self._add_quality_props(mod)

        self._set_correct_particle_vertexgroups(new_hair_systems, hair_obj)
        self._set_correct_hair_material(new_hair_systems, hair_type)

        for mod in self._human.hair.modifiers:
            mod.show_expanded = False

        self._move_modifiers_above_masks(new_hair_systems)
        for mod in human.body_obj.modifiers:
            # Turn on masks again
            if mod.type == "MASK":
                mod.show_viewport = True

            # Show all hair systems
            elif mod.type == "PARTICLE_SYSTEM":
                ps_sett = mod.particle_system.settings
                ps_sett.child_nbr = ps_sett.rendered_child_count

        hg_delete(hair_obj)
        remove_broken_drivers()

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

        genders = []
        if for_male:
            genders.append("male")
        if for_female:
            genders.append("female")

        # else:
        #     self._human.render_thumbnail()  # FIXME

        hair_type = self._pcoll_name
        save_hair(
            self._human,
            hairstyle_name,
            category,
            genders,
            particle_system_names,
            hair_type,
            context,
            thumbnail,
        )

    def remove_all(self) -> None:
        modifiers = self.modifiers
        for mod in modifiers:
            self._human.body_obj.modifiers.remove(mod)

    @injected_context
    def randomize(self, context: C = None) -> None:
        preset_options = self.get_options(context)
        chosen_preset = random.choice(preset_options)
        self.set(chosen_preset, context)

    def _import_hair_obj(
        self, context: bpy.types.Context, hair_type: str, pref: HG_PREF, blendfile: str
    ) -> bpy.types.Object:
        """Imports the object that contains the hair systems named in the json file.

        Args:
            context ([type]): [description]
            type (str): type of hair system ('facial hair' or 'head')
            pref (AddonPreferences): HumGen preferences
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
    ) -> None:
        """Gives the imported hair object the exact same shape as hg human.

        Args:
            hg_body (Object): body object
            hair_obj (Oject): imported hair object
        """
        body_copy = self._human.body_obj.copy()  # TODO without copying
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
            to_obj   (Object): object to transfer vertex groups to
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

        target_vg = self._human.body_obj.vertex_groups.new(name=vg_name)
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
            hg_body (Object): hg body object
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
            to_obj (Object): Object to rectify particle vertex groups on
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
            hg_body (Object):
            hair_type (str): 'head' for normal, 'face_hair' for facial hair
        """
        search_mat = ".HG_Hair_Face" if hair_type == "face" else ".HG_Hair_Head"
        # Search for current name of material to account for v1, v2 and v3
        mat_name = next(
            mat.name
            for mat in self._human.body_obj.data.materials
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
                for i, mod in enumerate(self._human.body_obj.modifiers)
                if mod.type == "MASK"
            ),
            None,
        )
        if not lowest_mask_index:
            return

        for mod in new_systems:
            # Use old method when older than 2.90
            if (2, 90, 0) > bpy.app.version:
                while self._human.body_obj.modifiers.find(mod.name) > lowest_mask_index:
                    bpy.ops.object.modifier_move_up(  # type:ignore[misc]
                        {"object": self._human.body_obj},  # type:ignore[arg-type]
                        modifier=mod.name,
                    )

            elif self._human.body_obj.modifiers.find(mod.name) > lowest_mask_index:
                bpy.ops.object.modifier_move_to_index(
                    modifier=mod.name, index=lowest_mask_index
                )
