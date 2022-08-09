from calendar import c
import bpy
from HumGen3D.backend import get_prefs, refresh_pcoll

from HumGen3D.user_interface.info_popups import HG_OT_INFO
from HumGen3D.user_interface.tips_suggestions_ui import (
    update_tips_from_context,
)

from HumGen3D.backend.preview_collections import set_random_active_in_pcoll
from ..human import Human


class HG_RANDOM(bpy.types.Operator):
    """randomizes this specific property, may it be a slider or a pcoll

    API: True

    Operator type:
        Prop setter
        Pcoll manipulation

    Prereq:
        Passed random_type
        Active object is part of HumGen human

    Args:
        random_type (str): internal name of property to randomize
    """

    bl_idname = "hg3d.random"
    bl_label = "Redraw Random"
    bl_description = "Randomize this property"
    bl_options = {"UNDO", "INTERNAL"}

    random_type: bpy.props.StringProperty()

    def execute(self, context):
        random_type = self.random_type
        sett = context.scene.HG3D
        human = Human.from_existing(context.active_object)

        if random_type == "body_type":
            human.body.randomize()
        elif random_type in (
            "poses",
            "expressions",
            "outfits",
            "patterns",
            "footwear",
            "hair",
        ):
            set_random_active_in_pcoll(context, sett, random_type)
        elif random_type == "skin":
            human.skin.randomize()
        elif random_type.startswith("face"):
            ff_subcateg = random_type[
                5:
            ]  # facial subcategories follow the pattern face_{category}
            # where face_all does all facial features
            human.face.randomize(ff_subcateg)
        elif random_type == "iris_color":
            human.eyes.randomize()

        return {"FINISHED"}


class HG_TOGGLE_HAIR_CHILDREN(bpy.types.Operator):
    """Turn hair children to 1 or back to render amount

    Operator type:
        Particle system

    Prereq:
        Active object is part of HumGen human
    """

    bl_idname = "hg3d.togglechildren"
    bl_label = "Toggle hair children"
    bl_description = "Toggle between hidden and visible hair children"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        human = Human.from_existing(context.object)
        current_state = human.hair.children_ishidden
        human.hair.children_set_hide(not current_state)

        return {"FINISHED"}


class HG_DESELECT(bpy.types.Operator):
    """
    Sets the active object as none

    Operator Type:
        Selection
        HumGen UI manipulation

    Prereq:
        -Human selected
    """

    bl_idname = "hg3d.deselect"
    bl_label = "Deselect"
    bl_description = "Deselects active object"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        for obj in bpy.context.selected_objects:
            obj.select_set(False)

        context.view_layer.objects.active = None
        return {"FINISHED"}


class HG_SECTION_TOGGLE(bpy.types.Operator):
    """
    Section tabs, pressing it will make that section the open/active one,
    closing any other opened sections

    API: False

    Operator Type:
        HumGen UI manipulation

    Args:
        section_name (str): name of the section to toggle
    """

    bl_idname = "hg3d.section_toggle"
    bl_label = ""
    bl_description = """
        Open this menu
        CTRL+Click to keep hair children turned on
        """

    section_name: bpy.props.StringProperty()
    children_hide_exception: bpy.props.BoolProperty(default=False)

    def invoke(self, context, event):
        self.children_hide_exception = event.ctrl
        return self.execute(context)

    def execute(self, context):
        human = Human.from_existing(context.object)
        sett = context.scene.HG3D
        sett.ui.phase = (
            "closed" if sett.ui.phase == self.section_name else self.section_name
        )
        # PCOLL add here
        categ_dict = {
            "clothing": ("outfits",),
            "footwear": ("footwear",),
            "pose": ("poses",),
            "hair": ("hair", "face_hair"),
            "expression": ("expressions",),
        }

        if not any(human.is_batch_result):
            if self.section_name in categ_dict:
                for item in categ_dict[self.section_name]:
                    refresh_pcoll(self, context, item)

        pref = get_prefs()
        if pref.auto_hide_hair_switch and not self.children_hide_exception:
            if not self.section_name in ("hair", "eyes"):
                on_before = not human.hair.children_ishidden
                human.hair.children_set_hide(True)
                if on_before:
                    self.report(
                        {"INFO"},
                        "Hair children were hidden to improve performance.",
                    )

                    if pref.auto_hide_popup:
                        HG_OT_INFO.ShowMessageBox(None, "autohide_hair")
        return {"FINISHED"}


class HG_NEXT_PREV_HUMAN(bpy.types.Operator):
    """Zooms in on next or previous human in the scene

    Operator Type:
        Selection
        VIEW 3D (zoom)

    Args:
        forward (bool): True if go to next, False if go to previous

    Prereq:
        Humans in scene
    """

    bl_idname = "hg3d.next_prev_human"
    bl_label = "Next/Previous"
    bl_description = "Goes to the next human"
    bl_options = {"UNDO"}

    forward: bpy.props.BoolProperty(name="", default=False)

    def execute(self, context):
        forward = self.forward

        for obj in bpy.context.selected_objects:
            obj.select_set(False)

        humans = []
        for obj in context.scene.objects:  # CHECK if works
            if obj.HG.ishuman and not "backup" in obj.name.lower():
                humans.append(obj)

        if len(humans) == 0:
            self.report({"INFO"}, "No Humans in this scene")
            return {"FINISHED"}

        hg_rig = Human.from_existing(context.active_object).rig_obj

        index = humans.index(hg_rig) if hg_rig in humans else 0

        if forward:
            if index + 1 < len(humans):
                next_index = index + 1
            else:
                next_index = 0
        else:
            if index - 1 >= 0:
                next_index = index - 1
            else:
                next_index = len(humans) - 1

        next_human = humans[next_index]

        context.view_layer.objects.active = next_human
        next_human.select_set(True)

        bpy.ops.view3d.view_selected()

        return {"FINISHED"}


class HG_OPENPREF(bpy.types.Operator):
    """Opens the preferences.

    API: False

    Operator type:
        Blender UI manipulation

    Prereq:
        None
    """

    bl_idname = "hg3d.openpref"
    bl_label = ""
    bl_description = "Opens the preferences window"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        old_area = bpy.context.area
        old_ui_type = old_area.ui_type

        bpy.context.area.ui_type = "PREFERENCES"
        bpy.context.preferences.active_section = "ADDONS"
        bpy.context.window_manager.addon_support = {"COMMUNITY"}
        bpy.context.window_manager.addon_search = "Human Generator 3D"

        bpy.ops.screen.area_dupli("INVOKE_DEFAULT")
        old_area.ui_type = old_ui_type
        return {"FINISHED"}


class HG_DELETE(bpy.types.Operator):
    """
    Deletes the active human, including it's backup human if it's not in use by
    any other humans

    Operator type:
        Object deletion

    Prereq:
        Active object is part of HumGen human
    """

    bl_idname = "hg3d.delete"
    bl_label = "Delete Human"
    bl_description = "Deletes human and all objects associated with the human"
    bl_options = {"UNDO"}

    obj_override: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        if self.obj_override:
            obj = bpy.data.objects.get(self.obj_override)
            human = Human.from_existing(obj)
        else:
            human = Human.from_existing(context.object, strict_check=False)
        if not human:
            self.report({"INFO"}, "No human selected")
            return {"FINISHED"}

        human.delete()

        return {"FINISHED"}


class HG_CLEAR_SEARCH(bpy.types.Operator):
    """Clears the passed searchfield

    API: False

    Operator type:
        Preview collection manipulation

    Prereq:
        None

    Args:
        pcoll_type (str): Name of preview collection to clear the searchbox for
    """

    bl_idname = "hg3d.clear_searchbox"
    bl_label = "Clear search"
    bl_description = "Clears the searchbox"

    searchbox_name: bpy.props.StringProperty()

    def execute(self, context):
        sett = context.scene.HG3D
        if self.searchbox_name == "cpack_creator":
            get_prefs().cpack_content_search = ""
        else:
            sett.pcoll["search_term_{}".format(self.searchbox_name)] = ""
            refresh_pcoll(self, context, self.searchbox_name)

        return {"FINISHED"}


class HG_NEXTPREV_CONTENT_SAVING_TAB(bpy.types.Operator):

    bl_idname = "hg3d.nextprev_content_saving_tab"
    bl_label = "Next/previous"
    bl_description = "Next/previous tab"

    next: bpy.props.BoolProperty()

    def execute(self, context):
        sett = context.scene.HG3D

        if self.next and sett.content_saving_type == "mesh_to_cloth":
            not_in_a_pose = self.check_if_in_A_pose(context, sett)

            if not_in_a_pose:
                sett.mtc_not_in_a_pose = True

        sett.content_saving_tab_index += 1 if self.next else -1

        update_tips_from_context(context, sett, sett.content_saving_active_human)

        return {"FINISHED"}

    def check_if_in_A_pose(self, context, sett):
        hg_rig = sett.content_saving_active_human
        context.view_layer.objects.active = hg_rig
        hg_rig.select_set(True)
        bpy.ops.object.mode_set(mode="POSE")

        important_bone_suffixes = (
            "forearm",
            "upper",
            "spine",
            "shoulder",
            "neck",
            "head",
            "thigh",
            "shin",
            "foot",
            "toe",
            "hand",
            "breast",
        )

        not_in_a_pose = False
        for bone in hg_rig.pose.bones:
            if not bone.name.startswith(important_bone_suffixes):
                continue
            for i in range(1, 4):
                if bone.rotation_quaternion[i]:
                    not_in_a_pose = True

        bpy.ops.object.mode_set(mode="OBJECT")

        return not_in_a_pose


class HG_REVERT_TO_CREATION(bpy.types.Operator):
    """
    Reverts to creation phase by deleting the current human and making the
    corresponding backup human the active human

    Operator Type:
        HumGen phase change
        Object deletion

    Prereq:
        Active object is part of finalize phase
    """

    bl_idname = "hg3d.revert"
    bl_label = "Revert: ALL changes made after creation phase will be discarded. This may break copied version of this human"
    bl_description = "Revert to the creation phase. This discards any changes made after the creation phase"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        # confirmation checkbox
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        Human.from_existing(context.object).finalize_phase.revert(context)
        return {"FINISHED"}
