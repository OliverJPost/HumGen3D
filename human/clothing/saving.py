"""Contains functions for saving clothing to the content folder."""

import os
import shutil
from typing import TYPE_CHECKING, Any, Iterable, Literal, Optional
from pathlib import Path

import bpy
import numpy as np
from bpy.types import Context, Image, Object
from HumGen3D.common.memory_management import hg_delete

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.backend.content.content_saving import (
    remove_number_suffix,
    save_objects_optimized,
    save_thumb,
)
from HumGen3D.backend.logging import hg_log
from HumGen3D.common.geometry import world_coords_from_obj
from HumGen3D.human.clothing.garment_fit import (
    base_shape_co,
    other_gender_base,
    to_rig_space,
    triangles,
)


def is_valid_clothing_object(obj: bpy.types.Object) -> bool:
    if "shoe" not in obj and "cloth" not in obj:
        return False

    if not obj.data.shape_keys:
        return False

    if not obj.parent or not obj.parent.type == "ARMATURE":
        return False

    corrective_sks = []
    for key in obj.data.shape_keys.key_blocks:
        if key.name.startswith("cor_"):
            corrective_sks.append(key.name)

    # Check if all corrective sks have a driver
    animation_data = obj.data.shape_keys.animation_data
    for driver in animation_data.drivers if animation_data else []:
        if not driver.data_path.split('"')[1] in corrective_sks:
            return False

    bones = obj.parent.data.bones
    return any(group.name in bones for group in obj.vertex_groups)


def has_deform_weights(obj: bpy.types.Object, rig: bpy.types.Object) -> bool:
    """Check if every vertex of the object is weighted to a deform bone of the rig.

    Args:
        obj (bpy.types.Object): Mesh object to check.
        rig (bpy.types.Object): Armature object of the human.

    Returns:
        bool: True if the object can be deformed by the rig as it is.
    """
    deform_groups = {
        group.index
        for group in obj.vertex_groups
        if group.name in rig.data.bones and rig.data.bones[group.name].use_deform
    }
    if not deform_groups:
        return False
    return all(
        any(element.group in deform_groups for element in vertex.groups)
        for vertex in obj.data.vertices
    )


def _save_clothing(
    human: "Human",
    folder: str,
    category: str,
    name: str,
    context: Context,
    objs: list[Object],
    genders: list[str],
    open_when_finished: bool = False,
    thumbnail: Optional[Image] = None,
) -> None:
    for gender in genders:
        gender_folder = os.path.join(folder, gender, category)
        if not os.path.isdir(gender_folder):
            os.mkdir(gender_folder)
        if thumbnail:
            save_thumb(gender_folder, thumbnail.name, name)

    texture_folder = os.path.join(folder, "textures")
    _save_material_textures(objs, texture_folder)
    for gender in genders:
        gender_folder = os.path.join(folder, gender, category)
        _export_for_gender(
            human,
            name,
            gender_folder,
            context,
            objs,
            open_when_finished,
            gender,
        )

    human.clothing.outfit.refresh_pcoll(context)
    human.clothing.footwear.refresh_pcoll(context)


def _export_for_gender(
    human: "Human",
    name: str,
    folder: str,
    context: bpy.types.Context,
    objs: Iterable[bpy.types.Object],
    open_when_finished: bool,
    gender: str,
) -> None:
    export_list = []
    for obj in objs:
        obj_copy = obj.copy()
        obj_copy.data = obj_copy.data.copy()
        if "cloth" in obj_copy:
            del obj_copy["cloth"]
        context.collection.objects.link(obj_copy)
        _refit_to_gender(human, obj_copy, gender)
        export_list.append(obj_copy)

    save_objects_optimized(
        context,
        export_list,
        folder,
        name,
        clear_sk=False,
        clear_materials=False,
        clear_vg=False,
        clear_drivers=False,
        run_in_background=not open_when_finished,
    )

    for obj in export_list:
        hg_delete(obj)


def _refit_to_gender(
    human: "Human", obj_copy: bpy.types.Object, gender: str
) -> None:
    """Make the base shape of a clothing object fit the base body of a gender.

    The base shape of clothing on a human fits the unmodified body of that
    human's gender. For the other gender it is refitted, and all shape keys are
    moved along so they keep meaning the same.
    """
    if gender == human.gender:
        return
    rig = human.objects.rig
    base = base_shape_co(obj_copy, rig)
    new_base = other_gender_base(human, base, triangles(obj_copy), gender)
    to_local = np.linalg.inv(to_rig_space(obj_copy, rig))[:3, :3]
    shift = (new_base - base) @ to_local.T

    mesh = obj_copy.data
    key_blocks = mesh.shape_keys.key_blocks if mesh.shape_keys else []
    for data in [key.data for key in key_blocks] + [mesh.vertices]:
        co = world_coords_from_obj(obj_copy, data=data, local=True) + shift
        data.foreach_set("co", co.ravel())
    mesh.update()


# CHECK naming adds .004 to file names, creating duplicates
def _save_material_textures(
    objs: Iterable[bpy.types.Object], texture_folder: str
) -> None:
    saved_images: dict[str, str] = {}

    for obj in objs:
        for mat in obj.data.materials:
            nodes = mat.node_tree.nodes
            for img_node in [n for n in nodes if n.bl_idname == "ShaderNodeTexImage"]:
                _process_image(saved_images, img_node, texture_folder)


def _process_image(
    saved_images: dict[str, str], img_node: bpy.types.ShaderNode, texture_folder: str
) -> None:
    img = img_node.image
    if not img:
        return
    colorspace = img.colorspace_settings.name
    if not img:
        return
    img_path, saved_images = _save_img(img, saved_images, texture_folder)
    if img_path:
        new_img = bpy.data.images.load(img_path)
        img_node.image = new_img
        new_img.colorspace_settings.name = colorspace


def _save_img(
    img: bpy.types.Image, saved_images: dict[str, str], folder: str
) -> tuple[Optional[str], dict[str, str]]:
    """Save image to content folder.

    Args:
        img (bpy.types.Image): Image to save.
        saved_images (dict[str, str]): Dictionary of saved images.
        folder (str): Folder to save image to.

    Returns:
        tuple[str, dict]:
            str: path the image was saved to
            dict[str: str]:
                str: name of the image
                str: path the image was saved to
    """
    img_name = remove_number_suffix(img.name)
    if img_name in saved_images:
        return saved_images[img_name], saved_images

    if not os.path.exists(folder):
        os.makedirs(folder)

    full_path = os.path.join(folder, img_name)
    if not Path(bpy.path.abspath(img.filepath_raw)).exists():
        img.save(filepath=full_path)
        saved_images[img_name] = full_path
        return full_path, saved_images
    try:
        shutil.copy(
            bpy.path.abspath(img.filepath_raw),
            os.path.join(folder, img_name),
        )
        saved_images[img_name] = full_path
    except RuntimeError as e:
        hg_log(f"failed to save {img.name} with error {e}", level="WARNING")
        return None, saved_images
    except shutil.SameFileError:
        saved_images[img_name] = full_path
        return full_path, saved_images

    return full_path, saved_images
