import json
import os
import random
from pathlib import Path

import bpy
from HumGen3D.backend import hg_log, hg_delete, remove_broken_drivers, get_prefs
from HumGen3D.human import hair
from HumGen3D.human.base.decorators import injected_context
from HumGen3D.human.base.exceptions import HumGenException
from HumGen3D.human.base.pcoll_content import PreviewCollectionContent
from HumGen3D.human.base.prop_collection import PropCollection
from HumGen3D.human.length.length import apply_armature
from HumGen3D.human.shape_keys.shape_keys import apply_shapekeys


class BaseHair:
    def _add_quality_props(self, mod):

        ps = mod.particle_system.settings
        ps["steps"] = ps.render_step
        ps["children"] = ps.rendered_child_count
        ps["root"] = ps.root_radius
        ps["tip"] = ps.tip_radius

    def randomize_color(self):
        # TODO make system more elaborate
        hair_color_dict = {
            "blonde": (4.0, 0.8, 0.0),
            "black": (0.0, 1.0, 0.0),
            "dark_brown": (0.5, 1.0, 0.0),
            "brown": (1.0, 1.0, 0.0),
            "red": (3.0, 1.0, 0.0),
        }

        hair_color = hair_color_dict[random.choice([name for name in hair_color_dict])]

        for mat in self._human.body_obj.data.materials[1:]:
            nodes = mat.node_tree.nodes
            hair_node = next(n for n in nodes if n.name.startswith("HG_Hair"))
            hair_node.inputs["Hair Lightness"].default_value = hair_color[0]
            hair_node.inputs["Hair Redness"].default_value = hair_color[1]
            hair_node.inputs["Pepper & Salt"].default_value = hair_color[2]

    @property
    def particle_systems(self):
        return self._get_particle_systems()

    @property
    def modifiers(self):
        return self._get_modifiers()

    def _get_modifiers(self):
        particle_mods = self._human.hair.modifiers

        modifiers = [
            mod for mod in particle_mods if self._condition(mod.particle_system.name)
        ]
        return PropCollection(modifiers)

    def _get_particle_systems(self):
        particle_systems = self._human.hair.particle_systems

        psys = [ps for ps in particle_systems if self._condition(ps.name)]
        return PropCollection(psys)

    def _condition(self, string):
        if hasattr(self, "_startswith"):
            return string.startswith(self._startswith)
        elif hasattr(self, "_notstartswith"):
            return not string.startswith(self._notstartswith)
        else:
            raise HumGenException(
                "Did not initialize hair class with _startswith or _notstartswith"
            )

    def delete_all(self):
        raise NotImplementedError


class ImportableHair(BaseHair, PreviewCollectionContent):
    @injected_context
    def set(self, preset, context=None):
        """Loads hair system the user selected by reading the json that belongs to
        the selected hairstyle

        Args:
            type (str): type of hair to load ('head' or 'facial_hair')
        """
        pref = get_prefs()

        full_path = str(pref.filepath) + preset
        with open(full_path) as f:
            hair_data = json.load(f)

        blendfile = hair_data["blend_file"]
        json_systems = hair_data["hair_systems"]

        hair_type = (
            "facial_hair"
            if isinstance(self, hair.facial_hair.FacialHairSettings)
            else "head"
        )

        hair_obj = self._import_hair_obj(context, hair_type, pref, blendfile)

        human = self._human
        human.hide_set(False)

        if hair_type == "facial_hair":
            human.hair.facial_hair.remove_all()
        else:
            human.hair.regular_hair.remove_all()
        remove_broken_drivers()

        mask_mods = [m for m in self._human.body_obj.modifiers if m.type == "MASK"]
        for mod in mask_mods:
            mod.show_viewport = False

        # IMPORTANT: Hair systems do not transfer correctly if they are hidden in the viewport
        for mod in hair_obj.modifiers:
            if mod.type == "PARTICLE_SYSTEM":
                mod.show_viewport = True

        context.view_layer.objects.active = hair_obj
        self._morph_hair_obj_to_body_obj(context, hair_obj)

        context.view_layer.objects.active = hair_obj
        bpy.ops.particle.disconnect_hair(all=True)

        for obj in context.selected_objects:
            obj.select_set(False)
        context.view_layer.objects.active = hair_obj
        human.body_obj.select_set(True)

        # iterate over hair systems that need to be transferred

        for ps_name in json_systems:
            self._transfer_hair_system(context, json_systems, hair_obj, ps_name)

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

    def _import_hair_obj(self, context, hair_type, pref, blendfile) -> bpy.types.Object:
        """Imports the object that contains the hair systems named in the json file

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

        return hair_obj

    def _morph_hair_obj_to_body_obj(self, context, hair_obj):
        """Gives the imported hair object the exact same shape as hg, to make sure
        the hair systems get transferred correctly

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

    def _transfer_hair_system(self, context, json_systems, hair_obj, ps):
        ps_mods = [mod for mod in hair_obj.modifiers if mod.type == "PARTICLE_SYSTEM"]
        for mod in ps_mods:
            if mod.particle_system.name == ps:
                self._set_particle_settings(json_systems, mod, ps)
                break

        override = context.copy()
        override["particle_system"] = hair_obj.particle_systems[ps]
        bpy.ops.particle.copy_particle_systems(
            override, remove_target_particles=False, use_active=True
        )

    def _set_particle_settings(self, json_systems, mod, ps_name):
        """Sets the settings of this particle settings according to the json dict

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

    def _transfer_vertexgroup(self, from_obj, vg_name):
        """Copies vertex groups from one object to the other

        Args:
            to_obj   (Object): object to transfer vertex groups to
            from_obj (Object): object to transfer vertex group from
            vg_name  (str)   : name of vertex group to transfer
        """

        vert_dict = {}
        for vert_idx, _ in enumerate(from_obj.data.vertices):
            try:
                vert_dict[vert_idx] = from_obj.vertex_groups[vg_name].weight(vert_idx)
            except:
                pass

        target_vg = self._human.body_obj.vertex_groups.new(name=vg_name)
        # fmt: off
        for v in vert_dict:
            target_vg.add([v,],vert_dict[v],"ADD")
        # fmt: on

    def _get_hair_systems_dict(self, hair_obj) -> dict:
        """Gets hair particle systems on passed object, including modifiers

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

    def _reconnect_hair(self, mod):
        """Reconnects the transferred hair systems to the skull

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

    def _set_correct_particle_vertexgroups(self, new_systems, from_obj):
        """Transferring particle systems results in the wrong vertex group being set,
        this corrects that

        Args:
            new_systems (dict): modifiers and particle_systems to correct vgs for
            from_obj (Object): Object to check correct particle vertex group on
            to_obj (Object): Object to rectify particle vertex groups on
        """
        for ps_name in [new_systems[mod] for mod in new_systems]:

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

            old_ps_sett = from_obj.particle_systems[ps_name]
            new_ps_sett = self._human.hair.particle_systems[ps_name]

            for vg_attr in vg_attributes:
                setattr(new_ps_sett, vg_attr, getattr(old_ps_sett, vg_attr))

    def _set_correct_hair_material(self, new_systems, hair_type):
        """Sets face hair material for face hair systems and head head material for
        head hair

        Args:
            new_systems (dict): Dict of modifiers and particle_systems of hair systems
            hg_body (Object):
            hair_type (str): 'head' for normal, 'facial_hair' for facial hair
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

    def _move_modifiers_above_masks(self, new_systems):
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
                    bpy.ops.object.modifier_move_up(
                        {"object": self._human.body_obj}, modifier=mod.name
                    )

            elif self._human.body_obj.modifiers.find(mod.name) > lowest_mask_index:
                bpy.ops.object.modifier_move_to_index(
                    modifier=mod.name, index=lowest_mask_index
                )

    def remove_all(self):
        modifiers = self.modifiers
        for mod in modifiers:
            self._human.body_obj.modifiers.remove(mod)

    @injected_context
    def randomize(self, context=None):
        preset_options = self.get_preset_options()
        chosen_preset = random.choice(preset_options)
        self.set(chosen_preset, context)
