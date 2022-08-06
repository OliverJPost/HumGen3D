"""
Contains operators and functions for the callback HG3D gets whenever
    the active object changes.
This callback has the following usages:
-Update the choices for all preview collections, for example loading female
    hairstyles when a female human is selected
-Update the subsurface scattering toggle in the UI
-Makes sure the hg_rig.HG.body_object is updated to the correct body object when
    a human is duplicated by the user
"""

import bpy
from HumGen3D.backend.logging import hg_log
from HumGen3D.utility_section.utility_functions import (
    refresh_hair_ul,
    refresh_modapply,
    refresh_outfit_ul,
    refresh_shapekeys_ul,
)

from ..human.human import Human  # , bl_info  # type: ignore
from ..user_interface.batch_ui_lists import batch_uilist_refresh  # type: ignore
from ..user_interface.tips_suggestions_ui import update_tips_from_context  # type:ignore
from .preview_collections import refresh_pcoll


class HG_ACTIVATE(bpy.types.Operator):
    """Activates the HumGen msgbus, also populates human pcoll"""

    bl_idname = "hg3d.activate"
    bl_label = "Activate"
    bl_description = "Activate HumGen"

    def execute(self, context):
        from HumGen3D import bl_info

        sett = bpy.context.scene.HG3D
        sett.subscribed = False  # TODO is this even used?

        msgbus(self, context)
        refresh_pcoll(self, context, "humans")
        hg_log(f"Activating HumGen, version {bl_info['version']}")
        return {"FINISHED"}


def msgbus(self, context):
    """Activates the subscribtion to changes to the active object"""
    sett = context.scene.HG3D

    if sett.subscribed:
        return

    subscribe_to = bpy.types.LayerObjects, "active"
    bpy.msgbus.subscribe_rna(
        key=subscribe_to,
        owner=self,
        args=(self,),
        notify=hg_callback,
    )
    sett.subscribed = True


def hg_callback(self):
    """
    Runs every time the active object changes
    """

    human = Human.from_existing(bpy.context.object, strict_check=False)
    if not human:
        return  # return immediately when the active object is not part of a human

    human._verify_body_object()

    sett = bpy.context.scene.HG3D
    ui_phase = sett.ui.phase

    _set_shader_switches(human, sett)
    update_tips_from_context(bpy.context, sett, human.rig_obj)
    _context_specific_updates(self, sett, human, ui_phase)


def _set_shader_switches(human, sett):
    """Sets the subsurface toggle to the correct position. Update_exception is
    used to prevent an endless loop of setting the toggle

    Args:
        hg_rig (Object): HumGen armature
        sett (PropertyGroup): HumGen props
    """
    sett.update_exception = True
    body_obj = human.body_obj
    nodes = body_obj.data.materials[0].node_tree.nodes
    if not body_obj:
        return

    # body_obj.data.materials[0].node_tree.nodes
    principled_bsdf = next(
        node for node in nodes if node.type == "BSDF_PRINCIPLED"
    )
    sett.skin_sss = (
        "off"
        if principled_bsdf.inputs["Subsurface"].default_value == 0
        else "on"
    )

    uw_node = nodes.get("Underwear_Opacity")
    if uw_node:
        sett.underwear_toggle = (
            "on" if uw_node.inputs[1].default_value == 1 else "off"
        )

    _hair_shader_type_update(sett, body_obj)

    sett.update_exception = False


def _context_specific_updates(self, sett, human, ui_phase):
    """Does all updates that are only necessary for a certain UI context. I.e.
    updating the preview collection of clothing when in the clothing section

    Args:
        sett (PropertyGroup): HumGen props
        hg_rig (Ojbect): HumGen armature
        ui_phase (str): Currently open ui tab
    """
    sett.update_exception = False
    context = bpy.context
    if sett.active_ui_tab == "TOOLS":
        refresh_modapply(self, context)
        try:
            refresh_shapekeys_ul(self, context)
            refresh_hair_ul(self, context)
            refresh_outfit_ul(self, context)
        except AttributeError:
            pass
        return
    elif ui_phase == "body":
        _refresh_body_scaling(self, sett, human)
    elif ui_phase == "skin":
        refresh_pcoll(self, context, "textures")
        return
    elif ui_phase == "clothing":
        refresh_pcoll(self, context, "outfit")
        return
    elif ui_phase == "hair":
        refresh_pcoll(self, context, "hair")
        if human.gender == "male":
            refresh_pcoll(self, context, "face_hair")
        return
    elif ui_phase == "expression":
        refresh_pcoll(self, context, "expressions")
        return


def _refresh_body_scaling(self, sett, human: Human):
    """This callback makes sure the sliders of scaling the bones are at the
    correct values of the selected human

    Args:
        sett (PropertyGroup): HumGen props
        hg_rig (Object): Armature object of HumGen human
    """
    bones = human.pose_bones
    sd = human.creation_phase.body._get_scaling_data(
        1, "head", return_whole_dict=True
    ).items()

    bone_groups = {
        group_name: scaling_data["bones"] for group_name, scaling_data in sd
    }

    for group_name, bone_group in bone_groups.items():
        if "head" in bone_group:
            slider_value = (bones["head"].scale[0] - 0.9) * 5
        else:
            slider_value = bones[bone_group[0]].scale[0] * 3 - 2.5

        setattr(sett, f"{group_name}_size", slider_value)


def tab_change_update(self, context):
    """Update function for when the user switches between the main tabs (Main UI,
    Batch tab and Utility tab)"""

    refresh_modapply(self, context)

    update_tips_from_context(
        context,
        context.scene.HG3D,
        Human.from_existing(context.object).rig_obj,
    )

    batch_uilist_refresh(self, context, "outfits")
    batch_uilist_refresh(self, context, "expressions")


def _hair_shader_type_update(sett, hg_body):
    mat = hg_body.data.materials[1]
    hair_node = mat.node_tree.nodes.get("HG_Hair_V3")

    if not hair_node:
        return

    switch_value = hair_node.inputs["Fast/Accurate"].default_value

    sett.hair_shader_type = "fast" if switch_value == 0.0 else "accurate"
