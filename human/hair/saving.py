import json
import os
from typing import TYPE_CHECKING, Iterable, Literal, Optional

import bpy
from HumGen3D.common.type_aliases import GenderStr

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.backend.content.content_saving import save_objects_optimized, save_thumb
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.common.memory_management import hg_delete


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
    pref = get_prefs()

    hair_obj = human.body_obj.copy()
    hair_obj.data = hair_obj.data.copy()
    hair_obj.name = "HG_Body"
    context.collection.objects.link(hair_obj)

    context.view_layer.objects.active = hair_obj
    hair_obj.select_set(True)
    _remove_other_systems(hair_obj, particle_systems)

    keep_vgs = _find_vgs_used_by_hair(hair_obj)
    for vg in [vg for vg in hair_obj.vertex_groups if vg.name not in keep_vgs]:
        hair_obj.vertex_groups.remove(vg)

    def create_for_gender(gender: GenderStr) -> Optional[str]:
        if hair_type == "face_hair" and gender == "female":
            return None

        if hair_type == "hair":
            blend_folder = os.path.join(pref.filepath, "hair", "head")
            json_folder = os.path.join(blend_folder, gender, category)
        else:
            blend_folder = os.path.join(pref.filepath, "hair", "face_hair")
            json_folder = os.path.join(blend_folder, category)

        if not os.path.exists(json_folder):
            os.makedirs(json_folder)
        if thumb:
            save_thumb(json_folder, thumb.name, name)

        _make_hair_json(hair_obj, json_folder, name)

        return blend_folder

    if for_male:
        blend_folder = create_for_gender("male")
    if for_female:
        blend_folder = create_for_gender("female")

    save_objects_optimized(
        context,
        [
            hair_obj,
        ],
        blend_folder,
        name,
        clear_ps=False,
        clear_vg=False,
    )

    human.hair.regular_hair.refresh_pcoll(context)
    human.hair.face_hair.refresh_pcoll(context)

    hg_delete(hair_obj)


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
        context (context): bl context
        hair_obj (bpy.types.Object): Body object the hairstyles are on
        folder (str): Folder to save json to
        style_name (str): Name of this style
    """
    ps_dict = {}
    for mod in hair_obj.modifiers:
        if mod.type == "PARTICLE_SYSTEM":
            ps = mod.particle_system
            ps_length = ps.settings.child_length
            ps_children = ps.settings.child_nbr
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
