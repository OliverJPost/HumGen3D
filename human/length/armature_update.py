import bpy
from HumGen3D.human.human import Human


class HG3D_OT_SLIDER_SUBSCRIBE(bpy.types.Operator):
    bl_idname = "hg3d.slider_subscribe"
    bl_label = ""
    stop: bpy.props.BoolProperty()
    bl_options = {"UNDO"}

    def modal(self, context, event):
        if self.stop:
            context.scene.HG3D.slider_is_dragging = False
            self.human.hide_set(False)
            self.human.length.correct_armature(context)
            return {"FINISHED"}
        if event.value == "RELEASE":
            self.stop = True

        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        self.stop = False
        self.human = Human.from_existing(context.object)
        self.human.hide_set(True)
        self.human.body_obj.hide_set(False)
        self.human.body_obj.hide_viewport = False
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}
