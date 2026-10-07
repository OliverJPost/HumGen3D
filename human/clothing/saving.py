"""Contains functions for saving clothing to the content folder."""

import os
import shutil
import subprocess
from typing import TYPE_CHECKING, Iterable, Optional

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

# Extension to save images with that have no file yet, per Blender file format
_FORMAT_EXTENSIONS = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "JPEG2000": ".jp2",
    "TARGA": ".tga",
    "TARGA_RAW": ".tga",
    "BMP": ".bmp",
    "IRIS": ".rgb",
    "TIFF": ".tif",
    "OPEN_EXR": ".exr",
    "OPEN_EXR_MULTILAYER": ".exr",
    "HDR": ".hdr",
    "WEBP": ".webp",
}


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
) -> list[subprocess.Popen]:
    """Save clothing objects as one library item for each of the genders.

    Returns:
        The background processes that shrink the written files, see
        `save_objects_optimized`.
    """
    if not objs:
        raise ValueError("No clothing objects to save.")
    for gender in genders:
        gender_folder = os.path.join(folder, gender, category)
        os.makedirs(gender_folder, exist_ok=True)
        if thumbnail:
            save_thumb(gender_folder, thumbnail.name, name)

    texture_folder = os.path.join(folder, "textures")
    _save_material_textures(objs, texture_folder)
    processes = []
    for gender in genders:
        gender_folder = os.path.join(folder, gender, category)
        process = _export_for_gender(
            human,
            name,
            gender_folder,
            context,
            objs,
            open_when_finished,
            gender,
        )
        if process:
            processes.append(process)

    human.clothing.outfit.refresh_pcoll(context)
    human.clothing.footwear.refresh_pcoll(context)
    return processes


def _export_for_gender(
    human: "Human",
    name: str,
    folder: str,
    context: bpy.types.Context,
    objs: Iterable[bpy.types.Object],
    open_when_finished: bool,
    gender: str,
) -> Optional[subprocess.Popen]:
    export_list = []
    # The copies get the names of the originals, so the library item does not
    # end up with .001 suffixes. The originals get their names back afterwards.
    renamed: list[tuple[bpy.types.ID, str]] = []
    try:
        for obj in objs:
            obj_copy = obj.copy()
            obj_copy.data = obj_copy.data.copy()
            for original, copy in ((obj, obj_copy), (obj.data, obj_copy.data)):
                original_name = original.name
                renamed.append((original, original_name))
                original.name = original_name + ".hg_export"
                copy.name = original_name
            for tag in ("cloth", "shoe"):
                if tag in obj_copy:
                    del obj_copy[tag]
            context.collection.objects.link(obj_copy)
            _refit_to_gender(human, obj_copy, gender)
            export_list.append(obj_copy)

        process = save_objects_optimized(
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
    finally:
        for obj in export_list:
            hg_delete(obj)
        for original, original_name in reversed(renamed):
            original.name = original_name
    return process


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


def _save_material_textures(
    objs: Iterable[bpy.types.Object], texture_folder: str
) -> None:
    """Store the textures of the objects in the library and use those instead.

    The materials of the passed objects are changed to use the library copies,
    so the saved files reference images inside the content folder.
    """
    saved_images: dict[str, str] = {}

    for obj in objs:
        for mat in obj.data.materials:
            if not mat or not mat.node_tree:
                continue
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
    img_path = _save_img(img, saved_images, texture_folder)
    if not img_path:
        return
    if os.path.normpath(bpy.path.abspath(img.filepath_raw)) == os.path.normpath(
        img_path
    ):
        return  # Already the library image, for example when saving again
    new_img = bpy.data.images.load(img_path, check_existing=True)
    img_node.image = new_img
    new_img.colorspace_settings.name = colorspace


def _save_img(
    img: bpy.types.Image, saved_images: dict[str, str], folder: str
) -> Optional[str]:
    """Save image to content folder.

    Images that exist on disk are copied as they are. Generated, packed or
    edited images that were never saved are written from their pixels.

    Args:
        img (bpy.types.Image): Image to save.
        saved_images (dict[str, str]): Paths of images saved before, by name.
            Updated with this image.
        folder (str): Folder to save image to.

    Returns:
        Path the image was saved to, None if that failed.
    """
    img_name = remove_number_suffix(img.name)
    if img_name in saved_images:
        return saved_images[img_name]

    source = bpy.path.abspath(img.filepath_raw) if img.filepath_raw else ""
    has_file = bool(source) and os.path.isfile(source)
    if not os.path.splitext(img_name)[1]:
        extension = os.path.splitext(source)[1] if has_file else ""
        if not extension:
            if img.file_format not in _FORMAT_EXTENSIONS:
                img.file_format = "PNG"
            extension = _FORMAT_EXTENSIONS[img.file_format]
        img_name += extension
    full_path = os.path.join(folder, img_name)
    os.makedirs(folder, exist_ok=True)

    try:
        if has_file and not img.is_dirty:
            shutil.copy(source, full_path)
        else:
            img.save(filepath=full_path)
    except shutil.SameFileError:
        pass
    except (OSError, RuntimeError) as e:
        hg_log(f"failed to save {img.name} with error {e}", level="WARNING")
        return None
    saved_images[img_name] = full_path
    return full_path
