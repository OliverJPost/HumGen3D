# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""
Callback HG3D gets whenever the active object changes.

This callback has the following usages:
-Update the choices for all preview collections, for example loading female
    hairstyles when a female human is selected
-Update the subsurface scattering toggle in the UI
-Makes sure the hg_rig.HG.body_object is updated to the correct body object when
    a human is duplicated by the user
"""

import contextlib
from typing import no_type_check

import bpy
from bpy.types import Context  # type:ignore[import]
from HumGen3D.backend import hg_log, preview_collections
from HumGen3D.backend.content.possible_content import find_possible_content
from HumGen3D.backend.properties.batch_props import BatchProps
from HumGen3D.human.keys.keys import update_livekey_collection
from HumGen3D.human.process.apply_modifiers import refresh_modapply
from HumGen3D.user_interface.content_panel.operators import (
    refresh_hair_ul,
    refresh_outfit_ul,
    refresh_shapekeys_ul,
)

from ..human.human import Human
from ..user_interface.documentation.tips_suggestions_ui import update_tips_from_context


class HG_ACTIVATE(bpy.types.Operator):  # noqa
    """Activates the HumGen msgbus, also populates human pcoll."""

    bl_idname = "hg3d.activate"
    bl_label = "Activate"
    bl_description = "Activate HumGen"

    @no_type_check
    def execute(self, context):  # noqa
        from HumGen3D import bl_info

        sett = bpy.context.scene.HG3D

        sett.subscribed = False  # TODO is this even used?

        msgbus(self, context)
        preview_collections["humans"].refresh(context, gender=sett.gender)
        hg_log(f"Activating HumGen, version {bl_info['version']}")

        update_livekey_collection()

        return {"FINISHED"}


def msgbus(self: bpy.types.Operator, context: Context) -> None:
    """Activates the subscribtion to changes to the active object.

    Args:
        self: Operator to make owner of this subscription
        context: Bpy context
    """
    sett = context.scene.HG3D  # type:ignore[attr-defined]

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


@no_type_check
def hg_callback() -> None:
    """Runs every time the active object changes."""
    human = Human.from_existing(bpy.context.object, strict_check=False)
    if not human:
        return  # return immediately when the active object is not part of a human

    human._verify_body_object()

    sett = bpy.context.scene.HG3D  # type: ignore[attr-defined]
    ui_phase = sett.ui.phase

    _set_shader_switches(human, sett)
    update_tips_from_context(bpy.context, sett, human)
    _context_specific_updates(sett, human, ui_phase)


@no_type_check
def _set_shader_switches(human, sett):
    """Sets the subsurface toggle to the correct position. Update_exception is
    used to prevent an endless loop of setting the toggle
    """  # noqa
    sett.update_exception = True
    body_obj = human.objects.body
    nodes = body_obj.data.materials[0].node_tree.nodes
    if not body_obj:
        return

    principled_bsdf = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
    sett.skin_sss = (
        "off" if principled_bsdf.inputs["Subsurface"].default_value == 0 else "on"
    )

    uw_node = nodes.get("Underwear_Opacity")
    if uw_node:
        sett.underwear_toggle = "on" if uw_node.inputs[1].default_value == 1 else "off"

    _hair_shader_type_update(sett, body_obj)

    sett.update_exception = False


@no_type_check
def _context_specific_updates(sett, human, ui_phase):
    """Does all updates that are only necessary for a certain UI context. I.e.
    updating the preview collection of clothing when in the clothing section
    """  # noqa
    sett.update_exception = False
    context = bpy.context

    if ui_phase == "apply":
        refresh_modapply(None, context)
    elif ui_phase == "hair":
        human.hair.regular_hair.refresh_pcoll(context, human.gender)
        if human.gender == "male":
            human.hair.face_hair.refresh_pcoll(context)
    elif ui_phase == "clothing":
        human.clothing.outfit.refresh_pcoll(context)
        human.clothing.footwear.refresh_pcoll(context)
    elif ui_phase == "skin":
        human.skin.texture.refresh_pcoll(context)
    else:
        with contextlib.suppress(AttributeError, RecursionError):
            getattr(human, ui_phase).refresh_pcoll(context)


@no_type_check
def tab_change_update(self, context):
    """Update function for when the user switches between the main tabs (Main UI,
    Batch tab and Utility tab)"""  # noqa

    refresh_modapply(self, context)

    human = Human.from_existing(context.object, strict_check=False)
    set_human_categ_props()
    if not human:
        return

    update_tips_from_context(
        context,
        context.scene.HG3D,
        human,
    )

    find_possible_content(context)
    refresh_outfit_ul(None, context)


def set_human_categ_props() -> None:
    """Create properties for the batch generator to choose human categories."""
    all_folders = set(Human.get_categories("male") + Human.get_categories("female"))
    all_folders.remove("All")
    for category in all_folders:
        setattr(
            BatchProps,
            f"{category}_chance",
            bpy.props.IntProperty(
                name=category, default=100, min=0, max=100, subtype="PERCENTAGE"
            ),  # type:ignore[func-returns-value]
        )


@no_type_check
def _hair_shader_type_update(sett, hg_body):
    mat = hg_body.data.materials[1]
    hair_node = mat.node_tree.nodes.get("HG_Hair_V3")

    if not hair_node:
        return

    switch_value = hair_node.inputs["Fast/Accurate"].default_value

    sett.hair_shader_type = "fast" if switch_value == 0.0 else "accurate"
