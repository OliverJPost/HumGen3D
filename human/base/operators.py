import random
from calendar import c

import bpy
from HumGen3D.backend import get_prefs, refresh_pcoll
from HumGen3D.user_interface.documentation.info_popups import HG_OT_INFO
from HumGen3D.user_interface.documentation.tips_suggestions_ui import (
    update_tips_from_context,
)

from ..human import Human


class HG_RANDOM_CHOICE(bpy.types.Operator):
    """Picks a random item to be active in this preview collection. For all pcolls
    except "humans" it will also load the item onto the humna.
    """

    bl_idname = "hg3d.random_choice"
    bl_label = "Random Choice"
    bl_description = "Pick a random choice for this category"
    bl_options = {"UNDO", "INTERNAL"}

    pcoll_name: bpy.props.StringProperty()

    def execute(self, context):
        random_type = self.random_type
        sett = context.scene.HG3D
        human = Human.from_existing(context.active_object, strict_check=False)

        if random_type in (
            "poses",
            "expressions",
            "outfits",
            "patterns",
            "footwear",
            "hair",
        ):
            getattr(human, random_type).set_random(update_ui=True)
        elif random_type == "humans":
            sett.gender = random.choice(["male", "female"])
            current = sett.pcoll.humans
            options = human.get_preset_options(sett.gender, context)
            chosen = random.choice([o for o in options if o != current])
            sett.pcoll.humans = chosen

        return {"FINISHED"}


class HG_RANDOM_VALUE(bpy.types.Operator):
    """randomizes this specific property"""

    bl_idname = "hg3d.random_value"
    bl_label = "Randomize"
    bl_description = "Randomize this value"
    bl_options = {"UNDO", "INTERNAL"}

    random_type: bpy.props.StringProperty()

    def execute(self, context):
        random_type = self.random_type
        human = Human.from_existing(context.active_object, strict_check=False)

        if random_type.startswith("face"):
            # facial subcategories follow the pattern face_{category}
            ff_subcateg = random_type[5:]
            # where face_all does all facial features
            human.face.randomize(ff_subcateg)
        else:
            getattr(human, random_type).randomize()
        return {"FINISHED"}


class HG_TOGGLE_HAIR_CHILDREN(bpy.types.Operator):
    """Turn hair children to 1 or back to render amount"""

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


class HG_NEXT_PREV_HUMAN(bpy.types.Operator):
    """Zooms in on next or previous human in the scene"""

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
