# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, List, Tuple, cast

import bpy
from bpy.types import bpy_prop_collection  # type:ignore
from HumGen3D.backend import get_prefs
from HumGen3D.common.type_aliases import C
from HumGen3D.human.common_baseclasses.pcoll_content import PreviewCollectionContent
from HumGen3D.user_interface.documentation.feedback_func import ShowMessageBox

from ...common.decorators import injected_context

if TYPE_CHECKING:
    from bpy.types import FloatVectorProperty, Material, ShaderNode  # type:ignore

    from ..human import Human


def create_node_property(node_name: str, input_name: str | int) -> Callable[..., Any]:
    @property  # type:ignore[misc]
    def _property_function(  # type:ignore[no-untyped-def]
        self,
    ) -> float | FloatVectorProperty | Tuple[float]:
        tone_node = self.nodes[node_name]
        return tone_node.inputs[input_name].default_value

    @_property_function.setter
    def _property_function(  # type:ignore[no-untyped-def]
        self, value: float | FloatVectorProperty | Tuple[float]
    ) -> None:
        tone_node = self.nodes[node_name]
        tone_node.inputs[input_name].default_value = value

    return _property_function


class MaleSkin:
    mustache_shadows: float = create_node_property("Gender_Group", 2)  # type:ignore
    beard_shadow: float = create_node_property("Gender_Group", 3)  # type:ignore

    def __init__(self, nodes: bpy_prop_collection) -> None:
        self.nodes = nodes


class FemaleSkin:
    foundation_amount: float = create_node_property(
        "Gender_Group", "Foundation Amount"
    )  # type:ignore
    foundation_color: FloatVectorProperty = create_node_property(
        "Gender_Group", "Foundation Color"
    )
    blush_opacity: float = create_node_property(
        "Gender_Group", "Blush Opacity"
    )  # type:ignore
    blush_color: FloatVectorProperty = create_node_property(
        "Gender_Group", "Blush Color"
    )
    eyebrows_opacity: float = create_node_property(
        "Gender_Group", "Eyebrows Opacity"
    )  # type:ignore
    eyebrows_color: FloatVectorProperty = create_node_property(
        "Gender_Group", "Eyebrows Color"
    )
    lipstick_color: FloatVectorProperty = create_node_property(
        "Gender_Group", "Lipstick Color"
    )
    lipstick_opacity: float = create_node_property(
        "Gender_Group", "Lipstick Opacity"
    )  # type:ignore
    eyeliner_opacity: float = create_node_property(
        "Gender_Group", "Eyeliner Opacity"
    )  # type:ignore
    eyeliner_color: FloatVectorProperty = create_node_property(
        "Gender_Group", "Eyeliner Color"
    )

    def __init__(self, nodes: bpy_prop_collection) -> None:
        self.nodes = nodes


class SkinSettings:
    tone = create_node_property("Skin_tone", 1)
    redness = create_node_property("Skin_tone", 2)
    saturation = create_node_property("Skin_tone", 3)
    normal_strength = create_node_property("Normal Map", 0)
    roughness_multiplier = create_node_property("R_Multiply", 1)
    light_areas = create_node_property("Lighten_hsv", "Value")
    dark_areas = create_node_property("Darken_hsv", "Value")
    skin_sagging = create_node_property("HG_Age", 1)
    freckles = create_node_property("Freckles_control", "Pos2")
    splotches = create_node_property("Splotches_control", "Pos2")
    beautyspots_amount = create_node_property("BS_Control", 2)
    beautyspots_opacity = create_node_property("BS_Opacity", 1)
    beautyspots_seed = create_node_property("BS_Control", 1)

    def __init__(self, human: "Human"):
        self._human = human

    @property  # TODO make cached
    def texture(self) -> TextureSettings:
        return TextureSettings(self._human)

    @property
    def nodes(self) -> SkinNodes:
        return SkinNodes(self._human)

    @property
    def links(self) -> SkinLinks:
        return SkinLinks(self._human)

    @property
    def material(self) -> "Material":
        return cast("Material", self._human.body_obj.data.materials[0])

    @property  # TODO make cached
    def gender_specific(self) -> MaleSkin | FemaleSkin:
        if self._human.gender == "male":
            gender_specific_class = MaleSkin
        else:
            gender_specific_class = FemaleSkin  # type:ignore[assignment]
        return gender_specific_class(self.nodes)

    def randomize(self) -> None:
        mat = self.material
        nodes = self.nodes

        # Tone, redness, saturation
        for input_idx in [1, 2, 3]:
            if f"skin_tone_default_{input_idx}" in mat:  # type:ignore[operator]
                default_value = mat[f"skin_tone_default_{input_idx}"]  # type:ignore
            else:
                default_value = (
                    nodes["Skin_tone"].inputs[input_idx].default_value  # type:ignore
                )
                mat[f"skin_tone_default_{input_idx}"] = default_value  # type:ignore

            new_value = random.uniform(default_value * 0.8, default_value * 1.2)
            nodes["Skin_tone"].inputs[  # type:ignore
                input_idx
            ].default_value = new_value

        probability_list = [0, 0, 0, 0, 0, 0, 0.2, 0.3, 0.5]

        # Freckles and splotches
        nodes["Freckles_control"].inputs[  # type:ignore
            3
        ].default_value = random.choice(probability_list)
        nodes["Splotches_control"].inputs[  # type:ignore
            3
        ].default_value = random.choice(  # type:ignore
            probability_list
        )

        age_value = random.choice([0, 0, 0, 0, 0, 0, 0, 0, 0, 0.2, 0.5]) * 2

        self._human.keys["age_old.Transferred"].value = age_value
        nodes["HG_Age"].inputs[1].default_value = age_value * 6  # type:ignore[index]

        if self._human.gender == "male":
            beard_shadow_value = random.choice(probability_list) * 2
            nodes["Gender_Group"].inputs[  # type:ignore[index]
                2
            ].default_value = beard_shadow_value
            nodes["Gender_Group"].inputs[  # type:ignore[index]
                3
            ].default_value = beard_shadow_value

    @injected_context
    def set_subsurface_scattering(self, turn_on: bool, context: C = None) -> None:
        if context.scene.HG3D.update_exception:
            return

        principled_bsdf = next(
            node for node in self.nodes if node.type == "BSDF_PRINCIPLED"
        )

        principled_bsdf.inputs["Subsurface"].default_value = 0.015 if turn_on else 0

    @injected_context
    def set_underwear(self, turn_on: bool, context: C = None) -> None:

        if context.scene.HG3D.update_exception:
            return

        underwear_node = self.nodes.get(
            "Underwear_Opacity"
        )  # type:ignore[func-returns-value]

        underwear_node.inputs[1].default_value = 1 if turn_on else 0

    def _set_gender_specific(self) -> None:
        """Male and female humans of HumGen use the same shader, but one node
        group is different. This function ensures the right nodegroup is connected
        """
        gender = self._human.gender
        uw_node = self.nodes.get("Underwear_Switch")  # type:ignore[func-returns-value]

        if uw_node:
            uw_node.inputs[0].default_value = 1 if gender == "female" else 0

        if gender == "male":
            gender_specific_node = self.nodes["Gender_Group"]  # type:ignore[index]
            male_node_group = next(
                ng for ng in bpy.data.node_groups if ".HG_Beard_Shadow" in ng.name
            )
            gender_specific_node.node_tree = male_node_group

    def _remove_opposite_gender_specific(self) -> None:
        self.nodes.remove(
            self.nodes.get("Delete_node")  # type:ignore[func-returns-value]
        )

    def _set_from_preset(self, preset_data: dict[str, dict[str, float]]) -> None:
        for node_name, input_dict in preset_data.items():
            node = self.nodes.get(node_name)  # type:ignore[func-returns-value]

            for input_name, value in input_dict.items():
                if input_name.isnumeric():
                    input_name = int(input_name)  # type:ignore[assignment]
                node.inputs[input_name].default_value = value


class TextureSettings(PreviewCollectionContent):
    def __init__(self, human: "Human") -> None:
        self._human = human
        self._pcoll_name = "texture"
        self._pcoll_gender_split = True

    @injected_context
    def set(self, textureset_path: str, context: C = None) -> None:  # noqa A001
        diffuse_texture = textureset_path
        library = "Default 4K"  # TODO

        if diffuse_texture == "none":
            return
        if diffuse_texture.startswith(os.sep):
            diffuse_texture = diffuse_texture[1:]

        nodes = self._human.skin.nodes
        gender = self._human.gender

        self._add_texture_to_node(
            nodes.get("Color"),  # type:ignore[func-returns-value]
            diffuse_texture,
            "Color",
        )
        for node in nodes.get_image_nodes():
            for tx_type in ["skin_rough_spec", "Normal"]:
                if tx_type in node.name:
                    pbr_path = os.path.join("textures", gender, library, "PBR")
                    self._add_texture_to_node(node, pbr_path, tx_type)

        if library in ["Default 1K", "Default 512px"]:
            resolution_folder = "MEDIUM_RES" if library == "Default 1K" else "LOW_RES"
            self._change_peripheral_texture_resolution(resolution_folder)

        self._human.skin.material["texture_category"] = library  # type:ignore[index]

    @injected_context
    def _set_from_preset(
        self, mat_preset_data: dict[str, str], context: C = None
    ) -> None:

        self.refresh_pcoll(context)
        texture_name = mat_preset_data["diffuse"]
        texture_category = mat_preset_data["texture_category"]
        gender = self._human.gender

        self.set(os.path.join("textures", gender, texture_category, texture_name))

    def _change_peripheral_texture_resolution(self, resolution_folder: str) -> None:
        # TODO cleanup
        for obj in self._human.children:
            for mat in obj.data.materials:
                for node in [
                    node
                    for node in mat.node_tree.nodes
                    if node.bl_idname == "ShaderNodeTexImage"
                ]:
                    if (
                        node.name.startswith(("skin_rough_spec", "Normal", "Color"))
                        and obj == self._human.body_obj
                    ):
                        continue
                    current_image = node.image
                    current_path = current_image.filepath

                    if "MEDIUM_RES" in current_path or "LOW_RES" in current_path:
                        current_dir = Path(os.path.dirname(current_path)).parent
                    else:
                        current_dir = os.path.dirname(current_path)

                    directory = os.path.join(current_dir, resolution_folder)
                    fn, ext = os.path.splitext(os.path.basename(current_path))
                    resolution_tag = resolution_folder.replace("_RES", "")
                    corrected_fn = (
                        fn.replace("_4K", "")
                        .replace("_MEDIUM", "")
                        .replace("_LOW", "")
                        .replace("_2K", "")
                    )
                    new_fn = corrected_fn + f"_{resolution_tag}" + ext
                    new_path = os.path.join(directory, new_fn)

                    old_color_mode = current_image.colorspace_settings.name
                    node.image = bpy.data.images.load(new_path, check_existing=True)
                    node.image.colorspace_settings.name = old_color_mode

    def _add_texture_to_node(
        self, node: ShaderNode, sub_path: Path | str, tx_type: str
    ) -> None:
        """Adds correct image to the teximage node

        Args:
            node      (ShaderNode): TexImage node to add image to
            sub_path  (Path)      : Path relative to HumGen folder where the texture
                                is located
            tx_type   (str)       : what kind of texture it is (Diffuse, Roughness etc.)
        """
        pref = get_prefs()

        filepath = os.path.join(pref.filepath, sub_path)

        # TODO cleanup

        if tx_type == "Color":
            image_path = filepath
        else:
            if tx_type == "Normal":
                tx_type = "norm"
            for fn in os.listdir(filepath):
                if tx_type.lower() in fn.lower():
                    image_path = os.path.join(filepath, fn)

        image = bpy.data.images.load(image_path, check_existing=True)
        node.image = image
        if tx_type != "Color":
            if pref.nc_colorspace_name:
                image.colorspace_settings.name = pref.nc_colorspace_name
                return
            found = False
            for color_space in [
                "Non-Color",
                "Non-Colour Data",
                "Utility - Raw",
            ]:
                try:
                    image.colorspace_settings.name = color_space
                    found = True
                    break
                except TypeError:
                    pass
            if not found:
                # TODO raise
                ShowMessageBox(
                    message="Could not find colorspace alternative for non-color data, default colorspace used"  # noqa
                )


class SkinNodes(bpy_prop_collection):
    def __new__(cls, human: "Human") -> "SkinNodes":
        skin_mat = human.body_obj.data.materials[0]
        nodes = skin_mat.node_tree.nodes
        return super().__new__(cls, nodes)  # type:ignore[call-arg]

    def get_image_nodes(self) -> List[ShaderNode]:
        return [node for node in self if node.bl_idname == "ShaderNodeTexImage"]


class SkinLinks(bpy_prop_collection):
    def __new__(cls, human: "Human") -> "SkinLinks":
        skin_mat = human.body_obj.data.materials[0]
        links = skin_mat.node_tree.links
        return super().__new__(cls, links)  # type:ignore[call-arg]
