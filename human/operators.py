import bpy

from .human import Human


class HG_START_CREATION(bpy.types.Operator):
    """Imports human, setting the correct custom properties.

    Operator type:
        Object importer
        Prop setter
        Material

    Prereq:
        Starting human selected in humans preview collection
    """

    bl_idname = "hg3d.startcreation"
    bl_label = "Generate New Human"
    bl_description = "Generate a new human"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.scene.HG3D.pcoll.humans != "none"
            or context.scene.HG3D.ui.active_tab == "BATCH"
        )

    def execute(self, context):
        sett = context.scene.HG3D
        sett.ui.phase = "closed"

        human = Human.from_preset(sett.pcoll.humans, context)
        hg_rig = human.rig_obj
        hg_rig.select_set(True)
        context.view_layer.objects.active = hg_rig

        self.report({"INFO"}, "You've created: {}".format(human.name))

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
