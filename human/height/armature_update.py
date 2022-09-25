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
            self.human.height.correct_armature(context)
            self.human.height.correct_eyes()
            self.human.height.correct_teeth()

            for mod in self.human.body_obj.modifiers:
                if mod.type == "MASK":
                    mod.show_viewport = True

            for cloth_obj in self.human.outfit.objects:
                self.human.outfit.deform_cloth_to_human(context, cloth_obj)
            for shoe_obj in self.human.footwear.objects:
                self.human.footwear.deform_cloth_to_human(context, shoe_obj)

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

        for mod in self.human.body_obj.modifiers:
            if mod.type == "MASK":
                mod.show_viewport = False

        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}
