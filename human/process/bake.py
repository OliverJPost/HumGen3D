# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Literal, Optional

import bpy
from bpy.types import Material, Object  # type:ignore
from HumGen3D.backend import get_prefs
from HumGen3D.backend.properties.bake_props import BakeProps
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.type_aliases import C
from HumGen3D.user_interface.documentation.feedback_func import ShowMessageBox

if TYPE_CHECKING:
    from ..human import Human


def follow_links(
    target_node: bpy.types.ShaderNode, target_socket: bpy.types.NodeSocket
) -> Optional[bpy.types.NodeSocket]:
    """Finds out what node is connected to a certain socket."""

    return next(
        (
            node_links.from_socket
            for node_links in target_node.inputs[target_socket].links  # type:ignore
        ),
        None,
    )


@dataclass
class BakeTexture:
    human_name: str
    texture_name: str
    bake_object: Object
    material_slot: int
    texture_type: str

    @property
    def output_image_name(self) -> str:
        return f"{self.human_name}_{self.texture_name}_{self.texture_type}_{self.texture_type.lower()}"  # noqa

    @property
    def material(self) -> Material:
        return self.bake_object.material_slots[
            self.material_slot  # type:ignore[index]
        ].material

    def get_resolution(self, bake_sett: BakeProps) -> int:
        if self.texture_name == "body":
            return int(bake_sett.res_body)
        elif self.texture_name == "eyes":
            return int(bake_sett.res_eyes)
        else:
            return int(bake_sett.res_clothes)


class BakeSettings:
    def __init__(self, human: "Human") -> None:
        self._human = human

    @property
    def resolution_body(self) -> int:
        return bpy.context.scene.HG3D.process.baking.res_body

    @resolution_body.setter
    def resolution_body(self, value: int) -> None:  # noqa
        bpy.context.scene.HG3D.process.baking.res_body = str(value)

    @property
    def resolution_clothes(self) -> int:
        return bpy.context.scene.HG3D.process.baking.res_clothes

    @resolution_clothes.setter
    def resolution_clothes(self, value: int) -> None:  # noqa
        bpy.context.scene.HG3D.process.baking.res_clothes = str(value)

    @property
    def resolution_eyes(self) -> int:
        return bpy.context.scene.HG3D.process.baking.res_eyes

    @resolution_eyes.setter
    def resolution_eyes(self, value: int) -> None:  # noqa
        bpy.context.scene.HG3D.process.baking.res_eyes = str(value)

    @staticmethod
    def _add_image_node(
        image: bpy.types.Image,
        input_type: Literal[
            "Base Color", "Normal", "Roughness", "Metallic", "Specular"
        ],
        mat: bpy.types.Material,
    ) -> None:
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        principled = nodes["Principled BSDF"]  # type:ignore[index, call-overload]

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
            links.new(img_node.outputs[0], normal_node.inputs[1])  # type:ignore[index]
            links.new(
                normal_node.outputs[0],  # type:ignore[index]
                principled.inputs[input_type],  # type:ignore
            )
        else:
            links.new(
                img_node.outputs[0], principled.inputs[input_type]  # type:ignore
            )

    @staticmethod
    def _disable_solidify_if_enabled(obj: bpy.types.Object) -> bool:
        return_value = False
        for mod in [m for m in obj.modifiers if m.type == "SOLIDIFY"]:
            if any((mod.show_viewport, mod.show_render)):
                return_value = True

            mod.show_viewport = mod.show_render = False

        return return_value

    @staticmethod
    def _get_bake_export_path(bake_sett: BakeProps, folder_name: str) -> str:
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

    @staticmethod
    def _set_up_material_for_baking(
        baketexture: BakeTexture, image: bpy.types.Image
    ) -> None:
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
            links.new(principled.outputs[0], mat_output.inputs[0])  # type:ignore
        else:
            source_socket = follow_links(
                principled, baketexture.texture_type  # type:ignore
            )
            if not source_socket:
                raise HumGenException("Can't find node", baketexture.texture_type)
            links.new(source_socket, emit_node.inputs[0])  # type:ignore
            links.new(emit_node.outputs[0], mat_output.inputs[0])  # type:ignore

        node = nodes.new("ShaderNodeTexImage")
        node.image = image
        for node2 in nodes:
            node2.select = False
        node.select = True
        nodes.active = node

    @staticmethod
    def _check_bake_render_settings(
        context: bpy.types.Context, samples: int = 4, force_cycles: bool = False
    ) -> tuple[bool, bool, bool, bool]:
        switched_to_cuda = False
        switched_from_eevee = False
        cycles_addon = context.preferences.addons["cycles"]  # type:ignore
        if cycles_addon.preferences.compute_device_type == "OPTIX":
            switched_to_cuda = True
            cycles_addon.preferences.compute_device_type = "CUDA"
        if context.scene.render.engine != "CYCLES":
            if force_cycles:
                switched_from_eevee = True
                context.scene.render.engine = "CYCLES"
            else:
                ShowMessageBox(message="You can only bake while in Cycles")
                return True, False, False, False

        old_samples = context.scene.cycles.samples
        context.scene.cycles.samples = samples

        return False, switched_to_cuda, old_samples, switched_from_eevee

    @injected_context
    def bake_all(self, samples: int = 4, context: C = None) -> None:
        (
            _,
            was_optix,
            old_samples,
            was_eevee,
        ) = self._check_bake_render_settings(context, samples, force_cycles=True)
        baketextures = self.get_baking_list()
        for baketexture in baketextures:
            self.bake_single_texture(baketexture)

        self.set_up_new_materials(baketextures)

        if was_optix:
            context.preferences.addons[  # type:ignore[index, call-overload]
                "cycles"
            ].preferences.compute_device_type = "OPTIX"
        context.scene.cycles.samples = old_samples
        if was_eevee:
            context.scene.render.engine = "EEVEE"

    @injected_context
    def bake_single_texture(
        self, baketexture: BakeTexture, context: C = None
    ) -> bpy.types.Image:
        bake_sett = context.scene.HG3D.process.baking
        bake_obj = baketexture.bake_object
        was_solidified = self._disable_solidify_if_enabled(bake_obj)

        export_path = self._get_bake_export_path(bake_sett, bake_sett.export_folder)

        # TODO nonsquare textures?
        image = bpy.data.images.new(
            baketexture.output_image_name,
            width=baketexture.get_resolution(bake_sett),
            height=baketexture.get_resolution(bake_sett),
        )
        self._set_up_scene_for_baking(bake_obj, context)  # type:ignore
        self._set_up_material_for_baking(baketexture, image)

        bake_type = "NORMAL" if baketexture.texture_type == "Normal" else "EMIT"
        override = {
            "object": bake_obj,
            "active object": bake_obj,
            "selectect objects": [
                bake_obj,
            ],
        }
        bpy.ops.object.bake(override, type=bake_type)  # type:ignore[misc, arg-type]

        image_filename = f"{image.name}.{bake_sett.file_type}"
        image.filepath_raw = os.path.join(export_path, image_filename)
        image.file_format = bake_sett.file_type.upper()
        image.save()

        if was_solidified:
            for mod in [m for m in bake_obj.modifiers if m.type == "SOLIDIFY"]:
                mod.show_viewport = mod.show_render = False

        return image

    def set_up_new_materials(self, baketextures: List[BakeTexture]) -> None:
        object_slot_set = {
            (baketexture.bake_object, baketexture.material_slot)
            for baketexture in baketextures
        }
        for obj, slot in object_slot_set:
            org_name = obj.material_slots[slot].material.name  # type:ignore[index]
            mat = bpy.data.materials.new(f"{obj.name}_{org_name}_BAKED")
            mat.use_nodes = True

            obj.material_slots[slot].material = mat  # type:ignore[index]

        for baketexture in baketextures:
            mat = baketexture.bake_object.material_slots[
                baketexture.material_slot  # type:ignore[index]
            ].material
            image = bpy.data.images.get(baketexture.output_image_name)
            self._add_image_node(image, baketexture.texture_type, mat)  # type:ignore

    def get_baking_list(self) -> List[BakeTexture]:
        bake_list = []
        for tex_type in ["Base Color", "Specular", "Roughness", "Normal"]:
            bake_list.append(
                BakeTexture(
                    self._human.name, "body", self._human.objects.body, 0, tex_type
                )
            )

        bake_list.append(
            BakeTexture(
                self._human.name, "eyes", self._human.objects.eyes, 1, "Base Color"
            )
        )

        cloth_objs = [
            child
            for child in self._human.children
            if "cloth" in child or "shoe" in child  # type:ignore[operator]
        ]

        for cloth in cloth_objs:
            for tex_type in ["Base Color", "Roughness", "Normal"]:
                bake_list.append(
                    BakeTexture(self._human.name, cloth.name, cloth, 0, tex_type)
                )

        if self._human.proces.has_haircards:
            for tex_type in ["Base Color", "Roughness", "Normal"]:
                bake_list.append(
                    BakeTexture(
                        self._human.name,
                        "hair",
                        self._human.objects.haircards,  # type:ignore[arg-type]
                        0,
                        tex_type,
                    )
                )
                bake_list.append(
                    BakeTexture(
                        self._human.name,
                        "hair",
                        self._human.objects.haircards,  # type:ignore[arg-type]
                        1,
                        tex_type,
                    )
                )

        return bake_list

    def _set_up_scene_for_baking(
        self, bake_obj: bpy.types.Object, context: bpy.types.Context
    ) -> None:
        # TODO context override
        bake_obj.select_set(True)
        self._human.objects.rig.select_set(False)
        context.view_layer.objects.active = bake_obj
