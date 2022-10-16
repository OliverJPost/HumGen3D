# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy

from ...backend import hg_log


def show_message(self, msg):
    hg_log(msg)
    self.report({"WARNING"}, msg)
    ShowMessageBox(message=msg)


def ShowConfirmationBox(message=""):
    """Shows a confirmation box to the user with the given text."""

    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.invoke_props_dialog(draw)


def ShowMessageBox(message="", title="Human Generator - Alert", icon="INFO"):
    """Shows a message popup with the passed text.

    Args:
        message (str, optional): Message to display. Defaults to "".
        title (str, optional): Title for popup. Defaults to "Human Generator - Alert".
        icon (str, optional): Icon code. Defaults to 'INFO'.
    """

    def draw(self, context):
        for line in message.splitlines():
            self.layout.label(text=line)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)
