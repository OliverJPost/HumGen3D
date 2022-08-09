from HumGen3D.human.human import Human
import bpy


class HG_REMOVE_HAIR(bpy.types.Operator):
    """Removes the corresponding hair system

    Operator type:
        Particle systems

    Prereq:
        Hair_system passed, and hair system is present on active object
        Active object is part of a HumGen human

    """

    bl_idname = "hg3d.removehair"
    bl_label = "Remove hair system"
    bl_description = "Removes this specific hair system from your human"
    bl_options = {"UNDO"}

    hair_system: bpy.props.StringProperty()

    def execute(self, context):
        hg_rig = Human.from_existing(context.object).rig_obj
        hg_body = hg_rig.HG.body_obj

        context.view_layer.objects.active = hg_body

        ps_idx = next(
            i
            for i, ps in enumerate(hg_body.particle_systems)
            if ps.name == self.hair_system
        )
        hg_body.particle_systems.active_index = ps_idx
        bpy.ops.object.particle_system_remove()
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class HG_EYEBROW_SWITCH(bpy.types.Operator):
    """Cycle trough all eyebrow particle systems on this object

    Operator type:
        Particle system

    Prereq:
        forward passed
        Active object is part of HumGen human
        At least 2 particle systems on this object starting with 'Eyebrows'

    Args:
        forward (bool): True if go forward in list, False if go backward
    """

    bl_idname = "hg3d.eyebrowswitch"
    bl_label = "Switch eyebrows"
    bl_description = "Next or previous eyebrow style"

    forward: bpy.props.BoolProperty()

    def execute(self, context):
        human = Human.from_existing(context.object)
        human.hair.eyebrows._switch_eyebrows(forward=self.forward)

        return {"FINISHED"}
