# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

# flake8: noqa D101

"""Implements operator for updating human after user lets go of slider."""

from typing import Optional, no_type_check

import bpy


class HG3D_OT_SLIDER_SUBSCRIBE(bpy.types.Operator):
    bl_idname = "hg3d.slider_subscribe"
    bl_label = ""
    bl_options = {"UNDO"}

    stop: bpy.props.BoolProperty()
    hide_armature: bpy.props.BoolProperty(default=False)
    _handler: Optional["HG3D_OT_SLIDER_SUBSCRIBE"] = None

    @classmethod
    def is_running(cls) -> bool:
        return cls._handler is not None

    @no_type_check
    def modal(self, context, event):
        if self.stop:
            self.correct_when_done(context)

            cls = self.__class__
            cls._handler = None
            return {"FINISHED"}
        if event.value == "RELEASE":
            self.stop = True

        return {"PASS_THROUGH"}

    @no_type_check
    def correct_when_done(self, context):
        self.armature_modifier.show_viewport = True
        self.human.keys.update_human_from_key_change(context)
        if not self.children_hidden_before:
            self.human.hair.children_set_hide(False)

    @no_type_check
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
        self.human.objects.body.hide_set(False)
        self.human.objects.body.hide_viewport = False

        self.children_hidden_before = self.human.hair.children_ishidden
        self.human.hair.children_set_hide(True)

        self.armature_modifier = next(
            mod for mod in self.human.objects.body.modifiers if mod.type == "ARMATURE"
        )
        if self.hide_armature:
            self.armature_modifier.show_viewport = False

        for mod in self.human.objects.body.modifiers:
            if mod.type == "MASK":
                mod.show_viewport = False

        if event.type == "RET":
            self.correct_when_done(context)
            cls._handler = None
            return {"FINISHED"}

        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}
