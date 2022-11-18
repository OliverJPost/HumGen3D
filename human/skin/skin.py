# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements class for changing the skin material of the human."""

from __future__ import annotations

import os
import random
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional, Union, cast

import bpy
from bpy.types import Material, ShaderNode, bpy_prop_collection  # type:ignore
from HumGen3D.backend import get_prefs
from HumGen3D.common.shadernode import NodeInput
from HumGen3D.common.type_aliases import C
from HumGen3D.human.common_baseclasses.pcoll_content import PreviewCollectionContent
from HumGen3D.user_interface.documentation.feedback_func import ShowMessageBox
from PIL import Image

from ...common.decorators import injected_context

if TYPE_CHECKING:

    from ..human import Human


class MaleSkin:
    """Subclass of human.skin for exposing controls for male specific skin settings."""

    def __init__(self, nodes: bpy_prop_collection) -> None:
        self.nodes = nodes
        self.mustache_shadow = NodeInput(self, "Gender_Group", 2)
        self.beard_shadow = NodeInput(self, "Gender_Group", 3)


class FemaleSkin:
    """Subclass of human.skin exposing controls for female specific skin settings."""

    def __init__(self, nodes: bpy_prop_collection) -> None:
        self.nodes = nodes

        self.foundation_amount = NodeInput(self, "Gender_Group", "Foundation Amount")
        self.foundation_color = NodeInput(self, "Gender_Group", "Foundation Color")
        self.blush_opacity = NodeInput(self, "Gender_Group", "Blush Opacity")
        self.blush_color = NodeInput(self, "Gender_Group", "Blush Color")
        self.eyebrows_opacity = NodeInput(self, "Gender_Group", "Eyebrows Opacity")
        self.eyebrows_color = NodeInput(self, "Gender_Group", "Eyebrows Color")
        self.lipstick_color = NodeInput(self, "Gender_Group", "Lipstick Color")
        self.lipstick_opacity = NodeInput(self, "Gender_Group", "Lipstick Opacity")
        self.eyeliner_opacity = NodeInput(self, "Gender_Group", "Eyeliner Opacity")
        self.eyeliner_color = NodeInput(self, "Gender_Group", "Eyeliner Color")


class SkinSettings:
    """Class for manipulating skin material of human."""

    def __init__(self, human: "Human"):
        self._human = human

        self.cavity_strength = NodeInput(self, "Cavity_Multiply", "Fac")
        self.tone = NodeInput(self, "Skin_tone", 1)
        self.redness = NodeInput(self, "Skin_tone", 2)
        self.saturation = NodeInput(self, "Skin_tone", 3)
        self.normal_strength = NodeInput(self, "Normal Map", 0)
        self.roughness_multiplier = NodeInput(self, "R_Multiply", 1)
        self.freckles = NodeInput(self, "Freckles_control", "Pos2")
        self.splotches = NodeInput(self, "Splotches_control", "Pos2")

    @property  # TODO make cached
    def texture(self) -> TextureSettings:
        """Gives acces to texture settings, for setting and changing textures.

        Returns:
            TextureSettings: Texture settings object.
        """
        return TextureSettings(self._human)

    @property
    def nodes(self) -> SkinNodes:
        """All nodes of the human skin material.

        Returns:
            SkinNodes: All nodes of the human skin material. Basically a
                bpy_prop_collection with one extra method.
        """
        return SkinNodes(self._human)

    @property
    def links(self) -> SkinLinks:
        """All links on the human skin material.

        Returns:
            SkinLinks: All links on the human skin material. Basically a
                bpy_prop_collection.
        """
        return SkinLinks(self._human)

    @property
    def material(self) -> "Material":
        """Human skin material.

        Returns:
            Material: Human skin Blender material.
        """
        return cast("Material", self._human.objects.body.data.materials[0])

    @property  # TODO make cached
    def gender_specific(self) -> Union[MaleSkin, FemaleSkin]:
        """Returns an instance to change node settings specifically related to gender.

        Returns:
            Union[MaleSkin, FemaleSkin]: Instance to change node settings regarding
                the specific gender of this human.
        """
        if self._human.gender == "male":
            gender_specific_class = MaleSkin
        else:
            gender_specific_class = FemaleSkin  # type:ignore[assignment]
        return gender_specific_class(self.nodes)

    def randomize(self) -> None:
        """Randomize the skin material of the human."""
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
        """Set the subsurface scattering on or off.

        Args:
            turn_on (bool): True for turning on, False for turning off.
            context (C): Blender context. Defaults to None.
        """
        if context.scene.HG3D.update_exception:
            return

        principled_bsdf = next(
            node for node in self.nodes if node.type == "BSDF_PRINCIPLED"
        )

        principled_bsdf.inputs["Subsurface"].default_value = 0.015 if turn_on else 0

    @injected_context
    def set_underwear(self, turn_on: bool, context: C = None) -> None:
        """Turn on/off the underwear/censoring on the human skin material.

        Args:
            turn_on (bool): True for showing underwear, False for hiding it
            context (C): Blender context. bpy.context if not provided.
        """
        if context.scene.HG3D.update_exception:
            return

        underwear_node = self.nodes.get(
            "Underwear_Opacity"
        )  # type:ignore[func-returns-value]

        underwear_node.inputs[1].default_value = 1 if turn_on else 0

    def as_dict(self) -> dict[str, Any]:
        """Returns a dictionary representation of the skin material.

        Returns:
            dict[str, Any]: Dictionary representation of the skin material.
        """
        return {
            "tone": self.tone.value,
            "redness": self.redness.value,
            "saturation": self.saturation.value,
            "normal_strength": self.normal_strength.value,
            "roughness_multiplier": self.roughness_multiplier.value,
            "freckles": self.freckles.value,
            "splotches": self.splotches.value,
            "texture.set": self.texture._active,
            "cavity_strength": self.cavity_strength.value,
            "gender_specific": {
                attr_name + "": attr_value.value
                for attr_name, attr_value in vars(self.gender_specific).items()
                if attr_name != "nodes"
            },
        }

    @injected_context
    def set_from_dict(self, data: dict[str, Any], context: C = None) -> list[str]:
        """Set the skin material from a dictionary representation.

        Args:
            data (dict[str, Any]): Dictionary representation of the skin material.
            context (C): Blender context. bpy.context if not provided.

        Returns:
            list[str]: List of occurred errors.
        """
        errors = []
        for attr_name, attr_value in data.items():
            if attr_name == "gender_specific":
                for gs_attr_name, gs_attr_value in attr_value.items():
                    setattr(self.gender_specific, gs_attr_name, gs_attr_value)
            elif "texture.set" in attr_name:
                if attr_value is not None:
                    try:
                        self.texture.set(attr_value)
                    except RuntimeError:
                        errors.append("Texture error:")
                        errors.append(f"'{attr_value}' not found.")

            else:
                getattr(self, attr_name).value = attr_value

        return errors

    def _set_gender_specific(self) -> None:
        """Male and female humans of HumGen use the same shader, but one node # noqa
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


class TextureSettings(PreviewCollectionContent):
    """Class for changing the skin texture of the human."""

    def __init__(self, human: "Human") -> None:
        self._human = human
        self._pcoll_name = "texture"
        self._pcoll_gender_split = True

    def set(self, textureset_path: str) -> None:  # noqa A001
        """Set the skin texture from a textureset from the HumGen library.

        Args:
            textureset_path (str): Relative path to the textureset. Can be found from
                the `get_options` method.
        """
        diffuse_texture = textureset_path
        library = "Default 4K"  # TODO

        if diffuse_texture == "none":
            return

        self._active = textureset_path

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

    def save_to_library(
        self,
        save_name: str,
        category="Default",
        thumbnail: Optional[bpy.types.Image] = None,
    ) -> None:
        category = category.strip()
        nodes = self._human.materials.body.node_tree.nodes
        image = nodes.get("Color").image
        filepath = image.filepath
        if not filepath:
            raise NotImplementedError("Can only save textures that are saved to disk.")

        texture_folder = os.path.join(
            get_prefs().filepath, "textures", self._human.gender
        )
        ext = os.path.splitext(filepath)[-1]
        if ext.lower() not in (".png", ".tiff"):
            raise NotImplementedError("Can only save png and tiff textures.")

        categ_folder = f"{category} 4K"
        shutil.copy(
            filepath, os.path.join(texture_folder, categ_folder, save_name + ext)
        )
        self.save_thumb(save_name, thumbnail, texture_folder, categ_folder)

        image = Image.open(filepath)
        for res_name, res in (("1K", 1024), ("512px", 512)):
            new_image = image.resize((res, res))
            categ_folder = f"{category} {res_name}"
            new_image.save(os.path.join(texture_folder, categ_folder, save_name + ext))
            self.save_thumb(save_name, thumbnail, texture_folder, categ_folder)

    def save_thumb(self, save_name, thumbnail, texture_folder, categ_folder):
        thumnbail_dest = os.path.join(texture_folder, categ_folder, save_name + ".jpg")
        if thumbnail.filepath:
            shutil.copyfile(thumbnail.filepath, thumnbail_dest)
        else:
            thumbnail.filepath = thumnbail_dest
            thumbnail.save()

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
                        and obj == self._human.objects.body
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
        self, node: ShaderNode, sub_path: Union[Path, str], tx_type: str
    ) -> None:
        """Adds correct image to the teximage node.

        Args:
            node (ShaderNode): TexImage node to add image to
            sub_path (Path): Path relative to HumGen folder where the texture
                is located
            tx_type (str): what kind of texture it is (Diffuse, Roughness etc.)
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
    """Inherits from bpy_prop_collection to add custom methods to the collection."""

    def __new__(cls, human: "Human") -> "SkinNodes":  # noqa D102
        skin_mat = human.objects.body.data.materials[0]
        nodes = skin_mat.node_tree.nodes
        return super().__new__(cls, nodes)  # type:ignore[call-arg]

    def get_image_nodes(self) -> List[ShaderNode]:
        """Get all nodes that are ShaderNodeTexImage.

        Returns:
            List[ShaderNode]: List of ShaderNodeTexImage nodes
        """
        return [node for node in self if node.bl_idname == "ShaderNodeTexImage"]


class SkinLinks(bpy_prop_collection):
    """Inherits from bpy_prop_collection to add custom methods to the collection."""

    def __new__(cls, human: "Human") -> "SkinLinks":  # noqa D102
        skin_mat = human.objects.body.data.materials[0]
        links = skin_mat.node_tree.links
        return super().__new__(cls, links)  # type:ignore[call-arg]
