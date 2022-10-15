import json
import os

import bpy
from HumGen3D.backend.logging import hg_log
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.human.human import Human
from HumGen3D.user_interface.documentation.feedback_func import show_message
from HumGen3D.user_interface.documentation.tips_suggestions_ui import (
    update_tips_from_context,
)


def refresh_shapekeys_ul(self, context):
    sett = context.scene.HG3D  # type:ignore[attr-defined]
    pref = get_prefs()
    col = context.scene.shapekeys_col

    previously_enabled_items = [i.sk_name for i in col if i.enabled]

    col.clear()

    existing_sks = find_existing_shapekeys(sett.custom_content, pref)

    human = Human.from_existing(context.object)
    if not human:
        return

    for sk in human.keys:
        if sk.name in existing_sks:
            continue

        item = col.add()
        item.sk_name = sk.name

        if sk.name in previously_enabled_items:
            item.enabled = True

        item.on = True if not sk.mute else False
        if not item.on:
            item.enabled = False


def find_existing_shapekeys(cc_sett, pref):
    existing_sks = [
        "Basis",
    ]
    if not cc_sett.show_saved_sks:
        walker = os.walk(os.path.join(pref.filepath, "models", "shapekeys"))
        for root, _, filenames in walker:
            for fn in filenames:
                if not os.path.splitext(fn)[1] == ".json":
                    continue
                with open(os.path.join(root, fn)) as f:
                    data = json.load(f)

                existing_sks.extend(data)
    return existing_sks


def refresh_hair_ul(self, context):
    cc_sett = context.scene.HG3D.custom_content
    col = context.scene.savehair_col

    previously_enabled_items = [i.ps_name for i in col if i.enabled]

    col.clear()

    hg_rig = cc_sett.content_saving_active_human
    if not hg_rig:
        return

    for ps in hg_rig.HG.body_obj.particle_systems:
        if ps.name.startswith("Eye") and not cc_sett.hair.show_eyesystems:
            continue
        item = col.add()
        item.ps_name = ps.name

        if ps.name in previously_enabled_items:
            item.enabled = True


# TODO if old list, make cloth_types the same again
def refresh_outfit_ul(self, context):
    sett = context.scene.HG3D  # type:ignore[attr-defined]
    col = context.scene.saveoutfit_col

    previously_enabled_items = [i.obj_name for i in col if i.enabled]

    col.clear()

    hg_rig = sett.content_saving_active_human

    for obj in [
        o
        for o in hg_rig.children
        if o.type == "MESH"
        and not "hg_body" in o
        and not "hg_eyes" in o
        and not "hg_teeth" in o
    ]:

        item = col.add()
        item.obj_name = obj.name

        if obj.data.shape_keys:
            item.cor_sks_present = next(
                (
                    True
                    for sk in obj.data.shape_keys.key_blocks
                    if sk.name.startswith("cor")
                ),
                False,
            )

        item.weight_paint_present = "spine" in [vg.name for vg in obj.vertex_groups]

        if obj.name in previously_enabled_items:
            item.enabled = True


class HG_OT_OPEN_CONTENT_SAVING_TAB(bpy.types.Operator):
    """Opens the Content Saving UI, hiding the regular UI.

    Prereq:
    Active object is part of a HumGen human

    Arguments:
    content_type (str): String that indicated what content type to show the
    saving UI for. ('shapekeys', 'clothing', 'hair', 'starting_human', 'pose')

    """

    bl_idname = "hg3d.open_content_saving_tab"
    bl_label = "Save custom content"
    bl_description = "Opens the screen to save custom content"

    content_type: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return context.object

    def execute(self, context):
        cc_sett = context.scene.HG3D.custom_content

        hg_rig = Human.from_existing(context.object).rig_obj

        cc_sett.content_saving_ui = True
        cc_sett.content_saving_type = self.content_type
        cc_sett.content_saving_tab_index = 0
        cc_sett.content_saving_active_human = hg_rig
        cc_sett.content_saving_object = context.object

        hg_log(self.content_type)
        if self.content_type == "shapekeys":
            refresh_shapekeys_ul(self, context)
        elif self.content_type == "hair":
            refresh_hair_ul(self, context)
        elif self.content_type == "clothing":
            refresh_outfit_ul(self, context)

        if self.content_type == "starting_human":
            unsaved_sks = self._check_if_human_uses_unsaved_shapekeys(cc_sett)
            if unsaved_sks:
                message = self._build_sk_warning_message(unsaved_sks)
                show_message(self, message)

                cc_sett.content_saving_ui = False
                return {"CANCELLED"}
        if self.content_type == "mesh_to_cloth":
            if context.object.type != "MESH":
                show_message(self, "Active object is not a mesh")
                cc_sett.content_saving_ui = False
                return {"CANCELLED"}
            elif "cloth" in context.object:
                show_message(
                    self,
                    "This object is already HG clothing, are you sure you want to redo this process?",
                )

        update_tips_from_context(context, cc_sett, cc_sett.content_saving_active_human)
        return {"FINISHED"}

    def _check_if_human_uses_unsaved_shapekeys(self, cc_sett) -> list:
        """Check with the list of already saved shapekeys to see if this human
        uses (value above 0) any shapekeys that are not already saved.

        Args:
            sett (PropertyGroup): Add-on props

        Returns:
            list: list of names of shapekeys that are not saved
        """
        existing_sks = find_existing_shapekeys(cc_sett, get_prefs())
        hg_log("existing sks", existing_sks)
        hg_body = cc_sett.content_saving_active_human.HG.body_obj
        unsaved_sks = []
        for sk in hg_body.data.shape_keys.key_blocks:
            if sk.name not in existing_sks and sk.value > 0:
                unsaved_sks.append(sk.name)

    def _build_sk_warning_message(self, unsaved_sks):
        """Builds a string with newline characters to display which shapekeys
        are not saved yet.

        Args:
            unsaved_sks (list): list of unsaved shapekey names

        Returns:
            str: Message string to display to the user
        """
        message = "This human uses custom shape keys that are not saved yet! \nPlease save these shapekeys using our 'Save custom shapekeys' button:\n"
        for sk_name in unsaved_sks:
            message += f"- {sk_name}\n"
        return message
