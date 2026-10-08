"""Implements functions for saving hair to content library."""

import contextlib
import json
import os
from typing import TYPE_CHECKING, Iterable, Literal, Optional

import bpy
import numpy as np
from mathutils import Matrix
from HumGen3D.human.hair.compatibility import get_children_percent

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.backend.content.content_saving import save_objects_optimized, save_thumb
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.common.memory_management import hg_delete

HAIR_OBJ_NAME = "HG_Body"


def save_hair(  # noqa CCR001
    human: "Human",
    name: str,
    category: str,
    particle_systems: Iterable[str],
    hair_type: Literal["face_hair", "hair"],
    context: bpy.types.Context,
    for_male: bool = True,
    for_female: bool = True,
    thumb: Optional[bpy.types.Image] = None,
) -> None:
    """Save hair to content library.

    Args:
        human (Human): Human instance the hair is on.
        name (str): Name to save hairstyle as
        category (str): Category to save hairstyle in. If it doesn't exist already a
            folder will be created.
        particle_systems (Iterable[str]): Names of particle systems to save
        hair_type (Literal[&quot;face_hair&quot;, &quot;hair&quot;]): Type to make hair
            available under for the user
        context (bpy.types.Context): Blender context
        for_male (bool): Make hair available for male humans. Defaults to True.
        for_female (bool): Make hair available for female humans. Defaults to True.
        thumb (Optional[bpy.types.Image]): Blender image to save as thumbnail for this
            hair. Defaults to None.
    """
    pref = get_prefs()

    # The object in the saved file has to have this exact name, which is usually
    # already taken by the body of the human
    name_holder = next(
        (
            obj
            for obj in bpy.data.objects
            if obj.name == HAIR_OBJ_NAME and not obj.library
        ),
        None,
    )
    if name_holder:
        name_holder.name = f"{HAIR_OBJ_NAME}_original"

    hair_obj = human.objects.body.copy()
    hair_obj.data = hair_obj.data.copy()
    hair_obj.name = HAIR_OBJ_NAME

    try:
        context.collection.objects.link(hair_obj)
        _remove_references_to_human(hair_obj)

        context.view_layer.objects.active = hair_obj
        hair_obj.select_set(True)
        _remove_other_systems(hair_obj, particle_systems)

        keep_vgs = _find_vgs_used_by_hair(hair_obj)
        for vg in [vg for vg in hair_obj.vertex_groups if vg.name not in keep_vgs]:
            hair_obj.vertex_groups.remove(vg)
        hair_obj.show_instancer_for_viewport = False
        _bake_shape(context, hair_obj)

        if hair_type == "hair":
            blend_folder = os.path.join(pref.filepath, "hair", "head")
            json_folders = [
                os.path.join(blend_folder, gender, category)
                for gender, enabled in (("male", for_male), ("female", for_female))
                if enabled
            ]
        else:
            # Face hair is not split by gender
            blend_folder = os.path.join(pref.filepath, "hair", "face_hair")
            json_folders = [os.path.join(blend_folder, category)]

        for json_folder in json_folders:
            if not os.path.exists(json_folder):
                os.makedirs(json_folder)
            if thumb:
                save_thumb(json_folder, thumb.name, name)

            _make_hair_json(hair_obj, json_folder, name)

        save_objects_optimized(
            context,
            [
                hair_obj,
            ],
            blend_folder,
            name,
            clear_sk=False,
            clear_ps=False,
            clear_vg=False,
        )
    finally:
        hg_delete(hair_obj)
        if name_holder:
            name_holder.name = HAIR_OBJ_NAME

    human.hair.regular_hair.refresh_pcoll(context)
    with contextlib.suppress(NotImplementedError):
        human.hair.face_hair.refresh_pcoll(context)


def _bake_shape(context: bpy.types.Context, hair_obj: bpy.types.Object) -> None:
    """Bake the evaluated (deformed) mesh shape into the vertex positions.

    The shape keys are stripped afterwards, so without this the mesh would revert
    to basis while the particle co_local values stay authored for the deformed
    shape, distorting the hair.

    Args:
        hair_obj (bpy.types.Object): Copy of the body object the hair is saved on
    """
    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = hair_obj.evaluated_get(depsgraph)
    eval_coords = np.empty(len(hair_obj.data.vertices) * 3, dtype=np.float32)
    eval_obj.data.vertices.foreach_get("co", eval_coords)

    if hair_obj.data.shape_keys:
        for sk in [
            sk for sk in hair_obj.data.shape_keys.key_blocks if sk.name != "Basis"
        ]:
            hair_obj.shape_key_remove(sk)
        hair_obj.shape_key_remove(hair_obj.data.shape_keys.key_blocks["Basis"])

    hair_obj.data.vertices.foreach_set("co", eval_coords)
    hair_obj.data.update()


def _remove_references_to_human(hair_obj: bpy.types.Object) -> None:
    """Remove everything that would make Blender save the human with the hair.

    Args:
        hair_obj (bpy.types.Object): Copy of the body object the hair is saved on
    """
    hair_obj.parent = None
    hair_obj.matrix_world = Matrix()
    for mod in [mod for mod in hair_obj.modifiers if mod.type != "PARTICLE_SYSTEM"]:
        hair_obj.modifiers.remove(mod)


def _find_vgs_used_by_hair(hair_obj: bpy.types.Object) -> list[str]:
    """Get a list of all vertex groups used by the hair systems.

    Args:
        hair_obj (bpy.types.Object): Human body the hair is on

    Returns:
        list: list of vertex groups that are used by hairsystems
    """
    all_vgs = [vg.name for vg in hair_obj.vertex_groups]
    keep_vgs = []
    for ps in hair_obj.particle_systems:  # TODO only iterate selected # type:ignore
        vg_types = [
            ps.vertex_group_clump,
            ps.vertex_group_density,
            ps.vertex_group_field,
            ps.vertex_group_kink,
            ps.vertex_group_length,
            ps.vertex_group_rotation,
            ps.vertex_group_roughness_1,
            ps.vertex_group_roughness_2,
            ps.vertex_group_roughness_end,
            ps.vertex_group_size,
            ps.vertex_group_tangent,
            ps.vertex_group_twist,
            ps.vertex_group_velocity,
        ]
        for used_vg in vg_types:
            if used_vg in all_vgs:
                keep_vgs.append(used_vg)

    return keep_vgs


def _remove_other_systems(obj: bpy.types.Object, keep_list: Iterable[str]) -> None:
    """Remove particle systems that are nog going to be saved.

    Args:
        obj (bpy.types.Object): Human body object to remove systems from
        keep_list (list): List of names of particle systems to keep
    """
    remove_list = [ps.name for ps in obj.particle_systems if ps.name not in keep_list]

    for ps_name in remove_list:
        ps_idx = [
            i
            for i, ps in enumerate(obj.particle_systems)  # type:ignore[arg-type]
            if ps.name == ps_name
        ]
        obj.particle_systems.active_index = ps_idx[0]
        bpy.ops.object.particle_system_remove()


def _make_hair_json(hair_obj: bpy.types.Object, folder: str, style_name: str) -> None:
    """Make a json that contains the settings for this hairstyle and save it.

    Args:
        hair_obj (bpy.types.Object): Body object the hairstyles are on
        folder (str): Folder to save json to
        style_name (str): Name of this style
    """
    ps_dict = {}
    for mod in hair_obj.modifiers:
        if mod.type == "PARTICLE_SYSTEM":
            ps = mod.particle_system
            ps_length = ps.settings.child_length
            ps_children = get_children_percent(ps.settings)
            ps_steps = ps.settings.display_step
            ps_dict[ps.name] = {
                "length": ps_length,
                "children_amount": ps_children,
                "path_steps": ps_steps,
            }

    json_data = {
        "blend_file": f"{style_name}.blend",
        "hair_systems": ps_dict,
    }

    full_path = os.path.join(folder, f"{style_name}.json")

    with open(full_path, "w") as f:
        json.dump(json_data, f, indent=4)
