import os
import shutil
from typing import TYPE_CHECKING, Any, Iterable, Optional

import bpy
import numpy as np
from bpy.types import Context, Image, Object
from HumGen3D.common.type_aliases import DistanceDict

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.backend.logging import hg_log
from HumGen3D.custom_content.content_saving import (
    remove_number_suffix,
    save_objects_optimized,
    save_thumb,
)
from HumGen3D.common.shapekey_calculator import (
    build_distance_dict,
    deform_obj_from_difference,
    world_coords_from_obj,
)


def save_clothing(
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

    # TODO disable armature modifier
    depsgraph = context.evaluated_depsgraph_get()
    body_obj_eval = human.body_obj.evaluated_get(depsgraph)
    body_eval_coords_world = world_coords_from_obj(body_obj_eval)

    texture_folder = os.path.join(folder, "textures")
    save_material_textures(objs, texture_folder)
    obj_distance_dict = {}
    for obj in objs:
        obj_world_coords = world_coords_from_obj(obj)
        distance_dict = build_distance_dict(body_eval_coords_world, obj_world_coords)
        obj_distance_dict[obj.name] = distance_dict

    body_coords_world = world_coords_from_obj(human.body_obj)
    for gender in genders:
        gender_folder = os.path.join(folder, gender, category)
        export_for_gender(
            human,
            name,
            gender_folder,
            context,
            objs,
            open_when_finished,
            gender,
            obj_distance_dict,
            body_coords_world,
        )

    human.clothing.outfit.refresh_pcoll(context)
    human.clothing.footwear.refresh_pcoll(context)


def export_for_gender(
    human: "Human",
    name: str,
    folder: str,
    context: bpy.types.Context,
    objs: Iterable[bpy.types.Object],
    open_when_finished: bool,
    gender: str,
    obj_distance_dict: DistanceDict,
    body_coords_world: np.ndarray[Any, Any],
) -> None:
    export_list = []
    if gender == "female":
        body_with_gender_coords_global = body_coords_world
    else:
        body_with_gender_coords_global = world_coords_from_obj(
            human.body_obj,
            data=human.body_obj.data.shape_keys.key_blocks["Male"].data,
        )

    for obj in objs:
        obj_copy = obj.copy()
        obj_copy.data = obj_copy.data.copy()
        if "cloth" in obj_copy:
            del obj_copy["cloth"]
        context.collection.objects.link(obj_copy)
        distance_dict = obj_distance_dict[obj.name]

        if gender != human.gender:
            sk_name = "Opposite gender"
            as_sk = True
        else:
            sk_name = ""
            as_sk = False

        deform_obj_from_difference(
            sk_name,
            distance_dict,
            body_with_gender_coords_global,
            obj_copy,
            as_shapekey=as_sk,
        )

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


# CHECK naming adds .004 to file names, creating duplicates
def save_material_textures(
    objs: Iterable[bpy.types.Object], texture_folder: str
) -> None:
    """Save the textures used by the materials of these objects to the content folder.

    Args:
        objs (list): List of objects to check for textures on
    """
    saved_images: dict[str, str] = {}

    for obj in objs:
        for mat in obj.data.materials:
            nodes = mat.node_tree.nodes
            for img_node in [n for n in nodes if n.bl_idname == "ShaderNodeTexImage"]:
                _process_image(saved_images, img_node, texture_folder)


def _process_image(
    saved_images: dict[str, str], img_node: bpy.types.ShaderNode, texture_folder: str
) -> None:
    """Prepare this image for saving and call _save_img on it.

    Args:
        saved_images (dict): Dict to keep record of what images were saved
        img_node (ShaderNode): TexImageShaderNode the image is in
    """
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
