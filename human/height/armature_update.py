# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import random

import bpy


class HG3D_OT_SLIDER_SUBSCRIBE(bpy.types.Operator):
    bl_idname = "hg3d.slider_subscribe"
    bl_label = ""
    # bl_options = {"UNDO"}

    stop: bpy.props.BoolProperty()
    hide_armature: bpy.props.BoolProperty(default=False)
    _handler = None

    @classmethod
    def is_running(cls):
        return cls._handler is not None

    def modal(self, context, event):
        if self.stop:
            self.human.hide_set(False)
            self.armature_modifier.show_viewport = True
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

            cls = self.__class__
            cls._handler = None

            return {"FINISHED"}
        if event.value == "RELEASE":
            self.stop = True

        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        # To prevent circular import
        from HumGen3D.human.human import Human

        # Set handler property for checking if the modal is running
        cls = self.__class__
        if cls._handler is not None:
            return {"CANCELLED"}

        cls._handler = self

        self.stop = False
        self.human = Human.from_existing(context.object)
        self.human.hide_set(True)
        self.human.body_obj.hide_set(False)
        self.human.body_obj.hide_viewport = False

        self.armature_modifier = next(
            mod for mod in self.human.body_obj.modifiers if mod.type == "ARMATURE"
        )
        if self.hide_armature:
            self.armature_modifier.show_viewport = False

        for mod in self.human.body_obj.modifiers:
            if mod.type == "MASK":
                mod.show_viewport = False

        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}
