import bpy
from HumGen3D import Human
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.backend.preview_collections import refresh_pcoll
from .documentation.tips_suggestions_ui import update_tips_from_context
from .documentation.info_popups import HG_OT_INFO


class HG_SECTION_TOGGLE(bpy.types.Operator):
    """
    Section tabs, pressing it will make that section the open/active one,
    closing any other opened sections

    Args:
        section_name (str): name of the section to toggle
    """

    bl_idname = "hg3d.section_toggle"
    bl_label = ""
    bl_description = """
        Open this menu
        CTRL+Click to keep hair children turned on
        """

    categ_dict = {
        "outfit": ("outfits",),
        "footwear": ("footwear",),
        "pose": ("poses",),
        "hair": ("hair", "face_hair"),
        "expression": ("expressions",),
    }

    section_name: bpy.props.StringProperty()
    children_hide_exception: bpy.props.BoolProperty(default=False)

    def invoke(self, context, event):
        self.children_hide_exception = event.ctrl
        return self.execute(context)

    def execute(self, context):
        human = Human.from_existing(context.object)
        sett = context.scene.HG3D
        sett.ui.phase = self.section_name

        for item in self.categ_dict.get(self.section_name):
            refresh_pcoll(self, context, item)

        pref = get_prefs()
        if (
            pref.auto_hide_hair_switch  # Turned on in preferences
            and not self.children_hide_exception  # User did not hold Ctrl
            and not self.section_name in ("hair", "eyes")  # It's not the hair tab
            and not human.hair.children_ishidden  # The children weren't already hidden
        ):
            self.hide_hair_and_show_notification(human, pref)

        return {"FINISHED"}

    def hide_hair_and_show_notification(self, human, pref):
        human.hair.children_set_hide(True)
        self.report(
            {"INFO"},
            "Hair children were hidden to improve performance.",
        )

        if pref.auto_hide_popup:
            HG_OT_INFO.ShowMessageBox(None, "autohide_hair")


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
