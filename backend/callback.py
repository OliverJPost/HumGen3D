# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

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

import os

import bpy
from HumGen3D.backend import hg_log, preview_collections
from HumGen3D.human.keys.keys import update_livekey_collection
from HumGen3D.utility_section.utility_functions import (
    refresh_hair_ul,
    refresh_modapply,
    refresh_outfit_ul,
    refresh_shapekeys_ul,
)

from ..backend.preferences.preference_func import get_prefs
from ..human.human import Human  # , bl_info  # type: ignore
from ..user_interface.batch_panel.batch_ui_lists import (
    batch_uilist_refresh,  # type: ignore
)
from ..user_interface.documentation.tips_suggestions_ui import (  # type:ignore
    update_tips_from_context,
)


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
        preview_collections["humans"].refresh(context, gender=sett.gender)
        hg_log(f"Activating HumGen, version {bl_info['version']}")

        update_livekey_collection()

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
    principled_bsdf = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
    sett.skin_sss = (
        "off" if principled_bsdf.inputs["Subsurface"].default_value == 0 else "on"
    )

    uw_node = nodes.get("Underwear_Opacity")
    if uw_node:
        sett.underwear_toggle = "on" if uw_node.inputs[1].default_value == 1 else "off"

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
    if sett.ui.active_tab == "TOOLS":
        try:
            refresh_shapekeys_ul(self, context)
            refresh_hair_ul(self, context)
            refresh_outfit_ul(self, context)
        except AttributeError:
            pass
        return
    elif ui_phase == "apply":
        refresh_modapply(self, context)
    elif ui_phase == "hair":
        preview_collections["hair"].refresh(context, human.gender)
        if human.gender == "male":
            preview_collections["face_hair"].refresh(context)
    else:
        try:
            getattr(human, ui_phase).refresh_pcoll(context)
        except (AttributeError, RecursionError):
            pass


def tab_change_update(self, context):
    """Update function for when the user switches between the main tabs (Main UI,
    Batch tab and Utility tab)"""

    refresh_modapply(self, context)

    human = Human.from_existing(context.object, strict_check=False)
    if not human:
        return

    update_tips_from_context(
        context,
        context.scene.HG3D,
        human.rig_obj,
    )

    batch_uilist_refresh(self, context, "outfit")
    batch_uilist_refresh(self, context, "expression")


def _hair_shader_type_update(sett, hg_body):
    mat = hg_body.data.materials[1]
    hair_node = mat.node_tree.nodes.get("HG_Hair_V3")

    if not hair_node:
        return

    switch_value = hair_node.inputs["Fast/Accurate"].default_value

    sett.hair_shader_type = "fast" if switch_value == 0.0 else "accurate"
