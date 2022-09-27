# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, List

import bpy
from bpy.types import Material, Object
from HumGen3D.backend import get_prefs
from HumGen3D.human.base.decorators import injected_context
from HumGen3D.human.base.exceptions import HumGenException
from HumGen3D.user_interface.documentation.feedback_func import ShowMessageBox

if TYPE_CHECKING:
    from ..human import Human


def follow_links(target_node, target_socket):
    """
    finds out what node is connected to a certain socket
    """

    try:
        source_socket = next(
            node_links.from_socket
            for node_links in target_node.inputs[target_socket].links
        )
    except:
        source_socket = None

    return source_socket


@dataclass
class BakeTexture:
    human_name: str
    texture_name: str
    bake_object: Object
    material_slot: int
    texture_type: str

    def get_resolution(self, bake_sett) -> int:
        if self.texture_name == "body":
            return int(bake_sett.res_body)
        elif self.texture_name == "eyes":
            return int(bake_sett.res_eyes)
        else:
            return int(bake_sett.res_clothes)

    @property
    def output_image_name(self) -> str:
        return f"{self.human_name}_{self.texture_name}_{self.texture_type}_{self.texture_type.lower()}"

    @property
    def material(self) -> Material:
        return self.bake_object.material_slots[self.material_slot].material


class BakeSettings:
    def __init__(self, human: Human) -> None:
        self._human = human

    def get_baking_list(self) -> List[BakeTexture]:
        bake_list = []
        for tex_type in ["Base Color", "Specular", "Roughness", "Normal"]:
            bake_list.append(
                BakeTexture(self._human.name, "body", self._human.body_obj, 0, tex_type)
            )

        bake_list.append(
            BakeTexture(self._human.name, "eyes", self._human.eye_obj, 1, "Base Color")
        )

        cloth_objs = [
            child
            for child in self._human.children
            if "cloth" in child or "shoe" in child
        ]

        for cloth in cloth_objs:
            for tex_type in ["Base Color", "Roughness", "Normal"]:
                bake_list.append(
                    BakeTexture(self._human.name, cloth.name, cloth, 0, tex_type)
                )

        return bake_list

    @injected_context
    def bake_all(self, samples=4, context=None) -> None:
        (
            _,
            was_optix,
            old_samples,
            was_eevee,
        ) = self.check_bake_render_settings(context, samples, force_cycles=True)
        baketextures = self.get_baking_list()
        for baketexture in baketextures:
            self.bake_single_texture(baketexture)

        self.set_up_new_materials(baketextures)

        if was_optix:
            context.preferences.addons[
                "cycles"
            ].preferences.compute_device_type = "OPTIX"
        context.scene.cycles.samples = old_samples
        if was_eevee:
            context.scene.render.engine = "EEVEE"

    @injected_context
    def bake_single_texture(self, baketexture: BakeTexture, context=None) -> None:
        bake_sett = context.scene.HG3D.bake
        bake_obj = baketexture.bake_object
        was_solidified = self._disable_solidify_if_enabled(bake_obj)

        export_path = self._get_bake_export_path(bake_sett, bake_sett.export_folder)

        # TODO nonsquare textures?
        image = bpy.data.images.new(
            baketexture.output_image_name,
            width=baketexture.get_resolution(bake_sett),
            height=baketexture.get_resolution(bake_sett),
        )
        self._set_up_scene_for_baking(bake_obj, context)
        self._set_up_material_for_baking(baketexture, image)

        bake_type = "NORMAL" if baketexture.texture_type == "Normal" else "EMIT"
        override = {
            "object": bake_obj,
            "active object": bake_obj,
            "selectect objects": [
                bake_obj,
            ],
        }
        bpy.ops.object.bake(override, type=bake_type)  # , pass_filter={'COLOR'}

        image_filename = f"{image.name}.{bake_sett.file_type}"
        image.filepath_raw = os.path.join(export_path, image_filename)
        image.file_format = bake_sett.file_type.upper()
        image.save()

        if was_solidified:
            for mod in [m for m in bake_obj.modifiers if m.type == "SOLIDIFY"]:
                mod.show_viewport = mod.show_render = False

        return image

    def set_up_new_materials(self, baketextures: List[BakeTexture]) -> None:
        object_slot_set = set(
            [
                (baketexture.bake_object, baketexture.material_slot)
                for baketexture in baketextures
            ]
        )
        for obj, slot in object_slot_set:
            org_name = obj.material_slots[slot].material.name
            mat = bpy.data.materials.new(f"{obj.name}_{org_name}_BAKED")
            mat.use_nodes = True

            obj.material_slots[slot].material = mat

        for baketexture in baketextures:
            mat = baketexture.bake_object.material_slots[
                baketexture.material_slot
            ].material
            image = bpy.data.images.get(baketexture.output_image_name)
            self._add_image_node(image, baketexture.texture_type, mat)

    @staticmethod
    def _add_image_node(image, input_type, mat):
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        principled = nodes["Principled BSDF"]

        img_node = nodes.new("ShaderNodeTexImage")
        img_node.image = image
        img_node.name = input_type

        node_locs = {
            "Base Color": (-600, 400),
            "Normal": (-600, -200),
            "Roughness": (-600, 100),
            "Metallic": (-1000, 300),
            "Specular": (-1000, -100),
        }
        img_node.location = node_locs[input_type]

        if input_type in ["Normal"]:
            image.colorspace_settings.name = "Non-Color"
            normal_node = nodes.new("ShaderNodeNormalMap")
            normal_node.location = (-300, -200)
            links.new(img_node.outputs[0], normal_node.inputs[1])
            links.new(normal_node.outputs[0], principled.inputs[input_type])
        else:
            links.new(img_node.outputs[0], principled.inputs[input_type])

    @staticmethod
    def _disable_solidify_if_enabled(obj) -> bool:
        return_value = False
        for mod in [m for m in obj.modifiers if m.type == "SOLIDIFY"]:
            if any((mod.show_viewport, mod.show_render)):
                return_value = True

            mod.show_viewport = mod.show_render = False

        return return_value

    @staticmethod
    def _get_bake_export_path(bake_sett, folder_name) -> str:
        if bake_sett.export_folder:
            export_path = os.path.join(
                bake_sett.export_folder, "bake_results", folder_name
            )
        else:
            export_path = os.path.join(
                get_prefs().filepath, "bake_results", folder_name
            )

        if not os.path.exists(export_path):
            os.makedirs(export_path)

        return export_path

    def _set_up_scene_for_baking(self, bake_obj, context):
        # TODO context override
        bake_obj.select_set(True)
        self._human.rig_obj.select_set(False)
        context.view_layer.objects.active = bake_obj

    @staticmethod
    def _set_up_material_for_baking(baketexture, image) -> None:
        nodes = baketexture.material.node_tree.nodes
        links = baketexture.material.node_tree.links

        principled = next(
            node for node in nodes if node.bl_idname == "ShaderNodeBsdfPrincipled"
        )
        mat_output = next(
            node for node in nodes if node.bl_idname == "ShaderNodeOutputMaterial"
        )
        emit_node = nodes.new("ShaderNodeEmission")
        if baketexture.texture_type == "Normal":
            links.new(principled.outputs[0], mat_output.inputs[0])
        else:
            source_socket = follow_links(principled, baketexture.texture_type)
            if not source_socket:
                raise HumGenException("Can't find node", baketexture.texture_type)
            links.new(source_socket, emit_node.inputs[0])
            links.new(emit_node.outputs[0], mat_output.inputs[0])

        node = nodes.new("ShaderNodeTexImage")
        node.image = image
        for node2 in nodes:
            node2.select = False
        node.select = True
        nodes.active = node

    @staticmethod
    def _check_bake_render_settings(context, samples=4, force_cycles=False):
        switched_to_cuda = False
        switched_from_eevee = False
        if (
            context.preferences.addons["cycles"].preferences.compute_device_type
            == "OPTIX"
        ):
            switched_to_cuda = True
            context.preferences.addons[
                "cycles"
            ].preferences.compute_device_type = "CUDA"
        if context.scene.render.engine != "CYCLES":
            if force_cycles:
                switched_from_eevee = True
                context.scene.render.engine = "CYCLES"
            else:
                ShowMessageBox(message="You can only bake while in Cycles")
                return True, None, None, None

        old_samples = context.scene.cycles.samples
        context.scene.cycles.samples = samples

        return False, switched_to_cuda, old_samples, switched_from_eevee
