# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Operators of the Process tab."""

import os
import time
from typing import List, Optional

import bpy
from HumGen3D.backend import hg_log
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.backend.properties.process_props import (
    add_script,
    ensure_initialized,
    get_script_items,
    props_to_settings,
    refresh_clips,
    refresh_key_lists,
    select_list,
    settings_to_props,
)
from HumGen3D.common import find_multiple_in_list, find_original_rig
from HumGen3D.common.documentation import EARLY_ACCESS, feedback_url
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.progress import Steps, phase, run
from HumGen3D.human.human import Human
from HumGen3D.human.process import scripts as script_tools
from HumGen3D.human.process.pipeline import ExportResult, output_folder
from HumGen3D.human.process.settings import (
    RECIPE_EXTENSION,
    USER_RECIPE_FOLDER,
    ExportSettings,
)


class HG_OT_PROCESS(bpy.types.Operator):
    """Process the selected humans by the settings of the Process tab.

    The work is done in short steps on a timer, in between Blender keeps
    responding and redraws the progress bar in the status bar. Esc cancels and
    removes the copies made so far, the original humans are never changed.
    """

    bl_idname = "hg3d.process"
    bl_label = "Process"
    bl_description = "Process the selected humans with these settings"
    bl_options = {"UNDO"}

    # Work per timer tick. Long enough to get work done, short enough to keep
    # the interface fluid.
    _budget = 0.05

    def invoke(self, context, event):
        if not self._prepare(context):
            return {"CANCELLED"}
        operator = self

        def draw_status(header, context):
            operator._draw_status(header.layout)

        self._draw_fn = draw_status
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.02, window=context.window)
        wm.modal_handler_add(self)
        context.workspace.status_text_set(self._draw_fn)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        """Runs in one go, for scripts and tests."""
        if not self._prepare(context):
            return {"CANCELLED"}
        try:
            results = run(self._steps)
        except Exception as e:  # noqa: BLE001
            self._restore_handlers()
            self.report({"ERROR"}, f"Processing failed: {e}")
            return {"CANCELLED"}
        self._restore_handlers()
        self._report(context, results)
        return {"FINISHED"}

    def _prepare(self, context) -> bool:
        props = context.scene.HG3D.process
        ensure_initialized(props)
        self._settings = props_to_settings(props)
        rigs = find_multiple_in_list(context.selected_objects)
        self._humans = [Human.from_existing(rig) for rig in rigs]
        if not self._humans:
            self.report({"ERROR"}, "No humans selected")
            return False

        errors = []
        for human in self._humans:
            check = human.process.preflight(self._settings, context)
            errors.extend(f"{human.name}: {error}" for error in check.errors)
        if errors:
            self.report({"ERROR"}, "\n".join(errors))
            return False

        # The depsgraph handlers of Human Generator would react to the half
        # made copies, which crashed Blender (issue #69)
        self._handlers = list(bpy.app.handlers.depsgraph_update_post)
        bpy.app.handlers.depsgraph_update_post.clear()
        self._steps = self._all_steps(context)
        self._fraction = 0.0
        self._current = self._humans[0].name
        self._started = time.monotonic()
        return True

    def _all_steps(self, context) -> Steps[List[ExportResult]]:
        results = []
        count = len(self._humans)
        for index, human in enumerate(self._humans):
            self._current = human.name
            result = yield from phase(
                human.process.run_steps(self._settings, context),
                index / count,
                (index + 1) / count,
            )
            results.append(result)
        return results

    def modal(self, context, event):
        if event.type == "ESC":
            self._finish(context)
            self.report({"INFO"}, "Processing cancelled")
            return {"CANCELLED"}
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        deadline = time.monotonic() + self._budget
        try:
            while time.monotonic() < deadline:
                self._fraction = max(self._fraction, next(self._steps))
        except StopIteration as finished:
            self._finish(context)
            self._report(context, finished.value)
            return {"FINISHED"}
        except Exception as e:  # noqa: BLE001
            self._finish(context)
            hg_log(f"Processing failed: {e}", level="ERROR")
            self.report({"ERROR"}, f"Processing failed: {e}")
            return {"CANCELLED"}
        context.workspace.status_text_set(self._draw_fn)
        return {"RUNNING_MODAL"}

    def _draw_status(self, layout):
        layout.separator_spacer()
        row = layout.row(align=True)
        row.ui_units_x = 18
        row.progress(
            text=f"Processing {self._current}: {self._fraction:.0%}",
            factor=self._fraction,
            type="BAR",
        )
        layout.label(text="Esc to cancel")
        layout.separator_spacer()

    def _finish(self, context):
        # Closing the generator removes the copies of an unfinished human
        self._steps.close()
        context.window_manager.event_timer_remove(self._timer)
        context.workspace.status_text_set(None)
        self._restore_handlers()

    def _restore_handlers(self):
        handlers = getattr(self, "_handlers", None)
        if handlers is None:
            return
        for handler in handlers:
            if handler not in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.append(handler)
        self._handlers = None

    def _report(self, context, results: List[ExportResult]) -> None:
        seconds = time.monotonic() - self._started
        hg_log(f"Processed {len(results)} human(s) in {seconds:.1f}s", level="DEBUG")
        humans = [human for result in results for human in result.humans]
        if humans:
            for obj in context.selected_objects:
                obj.select_set(False)
            for human in humans:
                human.objects.rig.select_set(True)
            context.view_layer.objects.active = humans[0].objects.rig

        files = [path for result in results for path in result.files]
        lines = []
        for result in results:
            if len(results) > 1:
                lines.append(result.name)
            lines.extend(result.summary().splitlines())
        folder = os.path.dirname(files[0]) if files else None
        title = "Export completed" if files else "Processing completed"
        settings = results[0].settings if results else None
        feedback = None
        if EARLY_ACCESS and settings:
            feedback = feedback_url(
                {"from": "result"}, recipe=settings.recipe or None, output=settings.output.format
            )
        _show_report(title, lines, folder, feedback)
        self.report({"INFO"}, title)


def _show_report(
    title: str, lines: List[str], folder: Optional[str], feedback: Optional[str] = None
) -> None:
    """A popup with the result lines, a button to the folder of the files and,
    in early access, one to give feedback."""
    if bpy.app.background:
        hg_log(title + "\n" + "\n".join(lines))
        return

    def draw(self, context):
        for line in lines:
            self.layout.label(text=line)
        if folder:
            self.layout.separator()
            self.layout.operator("wm.path_open", text="Open folder", icon="FILE_FOLDER").filepath = folder
        if feedback:
            self.layout.separator()
            row = self.layout.row()
            row.label(text="Early access: is this what you expected?")
            row.operator("wm.url_open", text="Give feedback", icon="COMMUNITY").url = feedback

    bpy.context.window_manager.popup_menu(draw, title=title, icon="INFO")


def _existing_groups(self, context):
    path = os.path.join(get_prefs().filepath, USER_RECIPE_FOLDER)
    if not os.path.isdir(path):
        return [("Saved", "Saved", "")]
    groups = [
        (f.name, f.name, "")
        for f in os.scandir(path)
        if f.is_dir() and not f.name.startswith(".")
    ]
    return groups or [("Saved", "Saved", "")]


def recipe_exists(group: str, name: str) -> bool:
    """Whether the user has a recipe of this name in this group.

    Built-in recipes don't count, they can't be overwritten.
    """
    name = name.strip()
    if not name:
        return False
    return os.path.isfile(os.path.join(get_prefs().filepath, USER_RECIPE_FOLDER, group, name + RECIPE_EXTENSION))


class HG_OT_SAVE_RECIPE(bpy.types.Operator):
    bl_idname = "hg3d.save_process_template"
    bl_label = "Save recipe"
    bl_description = "Save the current settings as a recipe"

    name: bpy.props.StringProperty(name="Recipe name")
    new_or_existing: bpy.props.EnumProperty(
        items=[
            ("existing", "Existing", "Add to an existing group.", 0),
            ("new", "New", "Create a new group.", 1),
        ]
    )
    existing_groups: bpy.props.EnumProperty(items=_existing_groups)
    new_group_name: bpy.props.StringProperty(name="New group name")

    def invoke(self, context, event):
        props = context.scene.HG3D.process
        if props.loaded_recipe and "/" in props.loaded_recipe.replace("\\", "/"):
            self.name = os.path.splitext(os.path.basename(props.loaded_recipe))[0]
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        col = self.layout.column()
        col.label(text="Give a name to your recipe:")

        subcol = col.column()
        subcol.scale_y = 1.5
        subcol.alert = self._exists()
        subcol.prop(self, "name", text="")
        if subcol.alert:
            subcol.label(text="Will override existing.", icon="ERROR")

        col = self.layout.column()
        col.label(text="Group:")
        col.scale_y = 1.5
        row = col.row()
        row.prop(self, "new_or_existing", expand=True)
        if self.new_or_existing == "existing":
            col.prop(self, "existing_groups", text="")
        else:
            col.prop(self, "new_group_name", text="Name")

    def _group(self) -> str:
        """The group folder the recipe goes to."""
        if self.new_or_existing == "existing":
            return str(self.existing_groups)
        return self.new_group_name.strip() or "Saved"

    def _exists(self) -> bool:
        """Whether saving would overwrite a recipe of the user in the chosen group."""
        return recipe_exists(self._group(), self.name)

    def execute(self, context):
        if not self.name.strip():
            self.report({"ERROR"}, "Give the recipe a name")
            return {"CANCELLED"}
        group = self._group()
        props = context.scene.HG3D.process
        settings = props_to_settings(props)
        path = settings.save_recipe(group, self.name.strip())
        relpath = os.path.relpath(path, os.path.join(get_prefs().filepath, USER_RECIPE_FOLDER))
        settings.recipe = relpath
        settings_to_props(props, settings)
        self.report({"INFO"}, f"Saved recipe {self.name}")
        return {"FINISHED"}


class HG_OT_RESET_RECIPE(bpy.types.Operator):
    bl_idname = "hg3d.reset_recipe"
    bl_label = "Reset to recipe"
    bl_description = "Set the settings back to those of the recipe"
    bl_options = {"UNDO"}

    def execute(self, context):
        props = context.scene.HG3D.process
        if not props.loaded_recipe:
            return {"CANCELLED"}
        try:
            settings_to_props(props, ExportSettings.from_recipe(props.loaded_recipe))
        except (OSError, ValueError) as e:
            self.report({"ERROR"}, f"Could not load recipe: {e}")
            return {"CANCELLED"}
        return {"FINISHED"}


class HG_OT_INIT_PROCESS(bpy.types.Operator):
    bl_idname = "hg3d.init_process"
    bl_label = "Start"
    bl_description = "Load the first recipe into the Process tab"

    def execute(self, context):
        ensure_initialized(context.scene.HG3D.process)
        return {"FINISHED"}


class HG_OT_SELECT_ORIGINAL_HUMAN(bpy.types.Operator):
    bl_idname = "hg3d.select_original_human"
    bl_label = "Select original human"
    bl_description = "Select the editable human this processed human was made from."
    bl_options = {"UNDO"}

    def execute(self, context):
        original_rig = find_original_rig(context.object, context.view_layer.objects)
        if not original_rig:
            self.report({"WARNING"}, "The original human is not in this scene anymore.")
            return {"CANCELLED"}

        for obj in context.selected_objects:
            obj.select_set(False)
        original_rig.hide_set(False)
        original_rig.select_set(True)
        context.view_layer.objects.active = original_rig

        return {"FINISHED"}


class HG_OT_LOAD_RESULT_SETTINGS(bpy.types.Operator):
    bl_idname = "hg3d.load_result_settings"
    bl_label = "Load these settings"
    bl_description = "Put the settings this human was processed with in the Process tab"
    bl_options = {"UNDO"}

    def execute(self, context):
        human = Human.from_existing(context.object)
        settings = human.process.settings if human else None
        if not settings:
            self.report({"WARNING"}, "This human has no process settings stored")
            return {"CANCELLED"}
        settings_to_props(context.scene.HG3D.process, settings)
        context.scene.HG3D.ui.active_tab = "PROCESS"
        return {"FINISHED"}


class HG_OT_PROCESS_AGAIN(bpy.types.Operator):
    bl_idname = "hg3d.process_again"
    bl_label = "Process again"
    bl_description = "Process the original human again with the settings this one was made with"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        human = Human.from_existing(context.object)
        settings = human.process.settings if human else None
        original_rig = find_original_rig(context.object, context.view_layer.objects)
        if not settings or not original_rig:
            self.report({"WARNING"}, "The original human or the settings are not available")
            return {"CANCELLED"}
        settings_to_props(context.scene.HG3D.process, settings)
        for obj in context.selected_objects:
            obj.select_set(False)
        original_rig.hide_set(False)
        original_rig.select_set(True)
        context.view_layer.objects.active = original_rig
        return bpy.ops.hg3d.process("INVOKE_DEFAULT")


class HG_OT_REFRESH_CLIPS(bpy.types.Operator):
    bl_idname = "hg3d.refresh_clips"
    bl_label = "Refresh clips"
    bl_description = "List the animations on the selected human"

    def execute(self, context):
        human = Human.from_existing(context.object)
        if not human:
            return {"CANCELLED"}
        refresh_clips(context.scene.HG3D.process, human, context)
        return {"FINISHED"}


class HG_OT_REFRESH_KEYS(bpy.types.Operator):
    bl_idname = "hg3d.refresh_key_lists"
    bl_label = "Refresh keys"
    bl_description = "List the shape keys of the selected human and the library"

    def execute(self, context):
        human = Human.from_existing(context.object)
        if not human:
            return {"CANCELLED"}
        refresh_key_lists(context.scene.HG3D.process, human, context)
        return {"FINISHED"}


class HG_OT_SELECT_LIST(bpy.types.Operator):
    """The All and None buttons of the clip and shape key lists."""

    bl_idname = "hg3d.select_process_list"
    bl_label = "Select"
    bl_description = "Tick or untick every entry of the list"

    # "clips" or a group of KEY_GROUPS
    list: bpy.props.StringProperty()  # noqa: A003
    select: bpy.props.BoolProperty(default=True)

    @classmethod
    def description(cls, context, properties):
        return "Tick every entry" if properties.select else "Untick every entry"

    def execute(self, context):
        props = context.scene.HG3D.process
        if self.list == "clips":
            items = props.animations.clips
        else:
            items = getattr(props.shape_keys, f"items_{self.list}", None)
            if items is None:
                return {"CANCELLED"}
        select_list(items, self.select)
        return {"FINISHED"}


class HG_OT_ADD_SCRIPT(bpy.types.Operator):
    bl_idname = "hg3d.add_script"
    bl_label = "Add script"
    bl_description = "Add a script of the content folder or a shipped one to the list"

    script: bpy.props.EnumProperty(items=get_script_items)

    def execute(self, context):
        if not add_script(context.scene.HG3D.process, self.script):
            self.report({"ERROR"}, f"Could not read {self.script}, see the console")
            return {"CANCELLED"}
        return {"FINISHED"}


class HG_OT_REMOVE_SCRIPT(bpy.types.Operator):
    bl_idname = "hg3d.remove_script"
    bl_label = "Remove script"
    bl_description = "Remove the script from the list"

    index: bpy.props.IntProperty()

    def execute(self, context):
        scripts = context.scene.HG3D.process.scripts.items
        if 0 <= self.index < len(scripts):
            scripts.remove(self.index)
        return {"FINISHED"}


class HG_OT_MOVE_SCRIPT(bpy.types.Operator):
    bl_idname = "hg3d.move_script"
    bl_label = "Move script"
    bl_description = "Move the script up or down in the list"

    index: bpy.props.IntProperty()
    direction: bpy.props.IntProperty(default=1)

    def execute(self, context):
        scripts = context.scene.HG3D.process.scripts.items
        target = self.index + self.direction
        if 0 <= self.index < len(scripts) and 0 <= target < len(scripts):
            scripts.move(self.index, target)
        return {"FINISHED"}


class HG_OT_NEW_SCRIPT(bpy.types.Operator):
    bl_idname = "hg3d.new_script"
    bl_label = "New script"
    bl_description = "Create a script from the template, add it to the list and open it in the text editor"

    name: bpy.props.StringProperty(name="Name")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        col = self.layout.column()
        col.label(text="Give a name to your script:")
        subcol = col.column()
        subcol.scale_y = 1.5
        non_valid = not self.name or any(char in self.name for char in r"\/:*?<>| .")
        subcol.alert = non_valid
        subcol.prop(self, "name", text="")
        if non_valid:
            subcol.label(text="Only letters, numbers and underscores.", icon="ERROR")

    def execute(self, context):
        if not self.name or any(char in self.name for char in r"\/:*?<>| ."):
            self.report({"ERROR"}, "Only letters, numbers and underscores")
            return {"CANCELLED"}
        path = script_tools.create_script(self.name)
        add_script(context.scene.HG3D.process, path)

        textblock = bpy.data.texts.load(path)
        scripting_workspace = bpy.data.workspaces.get("Scripting")
        if scripting_workspace:
            context.window.workspace = scripting_workspace
            for screen in scripting_workspace.screens:
                for area in screen.areas:
                    if area.type == "TEXT_EDITOR":
                        for space in area.spaces:
                            if space.type == "TEXT_EDITOR":
                                space.text = textblock
                                break
                        break
        else:
            self.report({"INFO"}, f"Script saved to {path}, open it in a text editor")
        return {"FINISHED"}


def process_with_settings(
    humans: List[Human], settings: ExportSettings, context: bpy.types.Context
) -> List[ExportResult]:
    """Processes humans in one go, what the operator does without the interface.

    Args:
        humans (List[Human]): Humans to process.
        settings (ExportSettings): What to make.
        context (bpy.types.Context): Blender context.

    Returns:
        List[ExportResult]: One result per human.

    Raises:
        HumGenException: If the preflight of a human finds an error.
    """
    results = []
    for human in humans:
        check = human.process.preflight(settings, context)
        if not check.ok:
            raise HumGenException(f"{human.name}: " + "; ".join(check.errors))
        results.append(human.process.run(settings, context))
    return results


__all__ = ["output_folder", "process_with_settings"]
