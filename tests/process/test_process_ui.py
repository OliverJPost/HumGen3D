# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

"""The Process tab: its properties, its operators and the drawing of its panels.

The properties are a view on `ExportSettings`, so every recipe and every
setting has to survive the way through them. The panels are drawn into a
recording layout that checks every property, operator and icon they name, as
a typo there only shows up as a broken panel in Blender.
"""

import inspect
import json
import os
from types import SimpleNamespace

import bpy
import pytest
from HumGen3D.backend.properties import process_props
from HumGen3D.backend.properties.process_props import (
    NEXT_TIERS,
    ensure_initialized,
    is_modified,
    props_to_settings,
    refresh_clips,
    settings_to_props,
)
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.human.human import Human
from HumGen3D.human.process import operators as process_operators
from HumGen3D.human.process import pipeline
from HumGen3D.human.process import scripts as script_tools
from HumGen3D.human.process import settings as settings_module
from HumGen3D.human.process.pipeline import EXPORT_KEY, _effective_settings
from HumGen3D.human.process.process import ProcessSettings
from HumGen3D.human.process.quality import quality_of_tier, resolution_of_tier, tier_of
from HumGen3D.human.process.settings import (
    OUTPUT_FORMATS,
    TEXTURE_SETS,
    AnimationSettings,
    ExportSettings,
    QualitySettings,
)
from HumGen3D.tests.process.process_helpers import *
from HumGen3D.tests.process.test_process_settings import SHIPPED_RECIPES, exotic_settings
from HumGen3D.tests.test_fixtures import *
from HumGen3D.user_interface import special_case_panels
from HumGen3D.user_interface.process_panel import process_panel

SHIPPED_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "scripts",
    "preset_scripts",
    "write_export_info.py",
)


@pytest.fixture(scope="module")
def source():
    human = make_source_human("male")
    yield human
    human.delete()


@pytest.fixture
def props():
    props = bpy.context.scene.HG3D.process
    ensure_initialized(props)
    yield props
    # The next test starts from a recipe, with nothing ticked away
    settings_to_props(props, ExportSettings.from_recipe("unity"))
    props.scripts.items.clear()
    props.animations.clips.clear()
    for group in ("face_rig", "expressions", "correctives", "body", "face", "age"):
        getattr(props.shape_keys, f"items_{group}").clear()


@pytest.fixture
def content_folder(tmp_path, monkeypatch):
    """A content folder of its own for the recipes and scripts the tests save."""
    prefs = SimpleNamespace(filepath=str(tmp_path), is_trial=False)
    for module in (settings_module, process_operators, script_tools, pipeline):
        monkeypatch.setattr(module, "get_prefs", lambda: prefs)
    return tmp_path


def _results_of(before):
    return [obj for obj in bpy.data.objects if obj not in before and obj.type == "ARMATURE"]


def _delete_results(rigs):
    for rig in rigs:
        try:
            Human.from_existing(rig).delete()
        except ReferenceError:
            pass


# Properties and settings


@pytest.mark.parametrize("recipe", SHIPPED_RECIPES)
def test_recipe_survives_the_properties(props, recipe):
    settings = ExportSettings.from_recipe(recipe)
    settings_to_props(props, settings)
    assert props_to_settings(props).to_dict() == settings.to_dict()
    assert not is_modified(props)
    assert props.loaded_recipe == recipe
    assert props.recipe == recipe


def test_every_setting_survives_the_properties(props):
    """Every field of the schema has a property, see exotic_settings."""
    settings = exotic_settings()
    settings.scripts.items[0].path = SHIPPED_SCRIPT
    settings.scripts.items[0].args = {"file_name": "info_x"}
    settings_to_props(props, settings)
    again = props_to_settings(props)
    assert again.to_dict() == settings.to_dict()


def test_empty_key_selection_survives_the_properties(props):
    """Keeping none of a group is not the same as keeping all of it."""
    settings = ExportSettings.from_recipe("unity")
    settings.shape_keys.keep = {"expressions": []}
    settings_to_props(props, settings)
    assert props_to_settings(props).shape_keys.keep == {"expressions": []}
    assert not is_modified(props)


def test_clip_selection_survives_unrefreshed_list(props):
    """A recipe with chosen clips, loaded before the list was filled, must not
    turn into every clip."""
    settings = ExportSettings.from_recipe("unity")
    settings.animations = AnimationSettings(enabled=True, source="library", clips=["animations/a.json"])
    settings_to_props(props, settings)
    assert props_to_settings(props).animations.clips == ["animations/a.json"]


def test_recipe_selection_after_refresh(props, source, context):
    """Refreshing the lists keeps the selection of a recipe, the keys and clips
    it did not choose are not ticked."""
    clip = source.animation.actions[0].name
    settings = ExportSettings.from_recipe("unity")
    settings.shape_keys.keep = {"expressions": ["Happy"], "face_rig": []}
    settings.animations = AnimationSettings(enabled=True, clips=[clip])
    settings_to_props(props, settings)
    process_props.refresh_key_lists(props, source, context)
    refresh_clips(props, source, context)
    assert len(props.shape_keys.items_expressions) > 5
    assert len(props.animations.clips) == len(source.animation.actions) > 1
    again = props_to_settings(props)
    assert again.shape_keys.keep == {"expressions": ["Happy"], "face_rig": []}
    assert again.animations.clips == [clip]
    # Ticking everything of a refreshed list is every key again
    bpy.ops.hg3d.select_process_list(list="expressions", select=True)
    assert "expressions" not in props_to_settings(props).shape_keys.keep


def test_choosing_a_recipe_loads_it(props):
    props.recipe = "unreal"
    assert props.loaded_recipe == "unreal"
    assert props.output.naming == "unreal"
    assert props.skeleton.units == "centimeters"
    assert props.textures.workflow == "orm"
    assert not is_modified(props)
    props.recipe = "godot"
    assert props.output.format == "glb"
    assert props.output.naming == "plain"


def test_modified_and_reset(props):
    props.recipe = "unity"
    assert not is_modified(props)
    props.lods[0].body = "2"
    assert is_modified(props)
    labels = {ident: label for ident, label, *_ in process_props.get_recipe_items(props, bpy.context) if ident}
    assert labels["unity"].endswith("(modified)")
    assert bpy.ops.hg3d.reset_recipe() == {"FINISHED"}
    assert props.lods[0].body == "0"
    assert not is_modified(props)


def test_lod_count_adds_lower_levels(props):
    props.recipe = "unity"
    assert tier_of(process_props.quality_from_props(props.lods[0])) == "high"
    props.lod_count = 4
    tiers = [tier_of(process_props.quality_from_props(level)) for level in props.lods]
    assert tiers == ["high", "medium", "low", "mobile"]
    props.lod_count = 2
    assert len(props.lods) == 2
    assert len(props_to_settings(props).lods) == 2
    # A level added after a custom level is lower than it
    props.lods[1].body = "0"
    props.lod_count = 3
    assert tier_of(process_props.quality_from_props(props.lods[2])) == NEXT_TIERS["custom"]


def test_texture_tier(props):
    textures = props.textures
    textures.tier = "512"
    assert process_props._resolution_from_props(textures) == resolution_of_tier("512")
    assert textures.tier == "512"
    textures.res_body = "4096"
    assert textures.tier == "custom"
    textures.tier = "2k"
    assert props_to_settings(props).textures.resolution == resolution_of_tier("2k")


def test_quality_props_roundtrip():
    props = bpy.context.scene.HG3D.process
    ensure_initialized(props)
    level = props.lods[0]
    for tier in ("original", "ultra", "high", "medium", "low", "mobile"):
        process_props.quality_to_props(level, quality_of_tier(tier))
        assert process_props.quality_from_props(level) == quality_of_tier(tier)


def test_initialize_fresh_scene():
    scene = bpy.data.scenes.new("HG process init")
    try:
        props = scene.HG3D.process
        assert not props.lods
        ensure_initialized(props)
        assert props.loaded_recipe == SHIPPED_RECIPES[0]
        assert len(props.lods) == 1
        # Twice changes nothing
        props.lods[0].body = "2"
        ensure_initialized(props)
        assert props.lods[0].body == "2"
    finally:
        bpy.data.scenes.remove(scene)


def test_opening_the_tab_fills_the_lists(source, context):
    props = context.scene.HG3D.process
    context.scene.HG3D.ui.active_tab = "CREATE"
    props.lods.clear()
    props.animations.clips.clear()
    props.shape_keys.items_face_rig.clear()
    select_only(context, source)
    context.scene.HG3D.ui.active_tab = "PROCESS"
    assert props.lods
    assert len(props.shape_keys.items_face_rig) > 20
    assert len(props.animations.clips) == len(source.animation.actions)


def test_init_operator():
    props = bpy.context.scene.HG3D.process
    props.lods.clear()
    assert bpy.ops.hg3d.init_process() == {"FINISHED"}
    assert props.lods


def test_absolute_folder(props):
    props.output.folder = "//exports"
    assert not props.output.folder.startswith("//")
    assert os.path.isabs(props.output.folder)


# Operators of the tab


def test_save_recipe_operator(props, content_folder):
    props.recipe = "godot"
    props.lods[0].body = "1"
    result = bpy.ops.hg3d.save_process_template(name="Hero", new_or_existing="new", new_group_name="Team")
    assert result == {"FINISHED"}
    path = content_folder / "process_templates" / "Team" / "Hero.json"
    assert path.is_file()
    assert props.loaded_recipe == os.path.join("Team", "Hero.json")
    assert not is_modified(props)
    loaded = ExportSettings.from_recipe(props.loaded_recipe)
    assert loaded.lods[0].body == 1
    assert loaded.output.format == "glb"
    # The saved recipe is in the dropdown, under its group
    items = process_props.get_recipe_items(props, None)
    assert ("", "Team", "") in items
    assert any(item[0] == props.loaded_recipe for item in items)
    # Saving into the existing group
    result = bpy.ops.hg3d.save_process_template(name="Villain", new_or_existing="existing", existing_groups="Team")
    assert result == {"FINISHED"}
    assert (content_folder / "process_templates" / "Team" / "Villain.json").is_file()


def test_save_recipe_needs_a_name(props, content_folder):
    with pytest.raises(RuntimeError, match="Give the recipe a name"):
        bpy.ops.hg3d.save_process_template(name="  ")
    assert not (content_folder / "process_templates").exists()


def test_script_operators(props, content_folder):
    props.scripts.items.clear()
    props.scripts.enabled = False
    assert SHIPPED_SCRIPT in script_tools.available_scripts()
    assert bpy.ops.hg3d.add_script(script=SHIPPED_SCRIPT) == {"FINISHED"}
    assert props.scripts.enabled, "Adding a script turns the scripts on"
    item = props.scripts.items[0]
    assert item.stage == "after_export", "The STAGE constant of the script"
    assert item.takes_files
    assert [(arg.name, arg.type, arg.value) for arg in item.args] == [("file_name", "str", "export_info")]
    item.args[0].value = "custom_info"

    # A script made from the template lands in the content folder of the user
    assert bpy.ops.hg3d.new_script(name="my_script") == {"FINISHED"}
    new_path = str(content_folder / "scripts" / "my_script.py")
    assert os.path.isfile(new_path)
    assert props.scripts.items[1].path == new_path
    assert props.scripts.items[1].stage == "after_processing"
    assert script_tools.inspect_script(new_path).args == []
    with pytest.raises(RuntimeError, match="Only letters"):
        bpy.ops.hg3d.new_script(name="bad name")

    settings = props_to_settings(props)
    assert [(s.path, s.stage, s.args) for s in settings.scripts.items] == [
        (SHIPPED_SCRIPT, "after_export", {"file_name": "custom_info"}),
        (new_path, "after_processing", {}),
    ]

    assert bpy.ops.hg3d.move_script(index=1, direction=-1) == {"FINISHED"}
    assert props.scripts.items[0].path == new_path
    assert bpy.ops.hg3d.move_script(index=0, direction=-1) == {"FINISHED"}, "Out of range is ignored"
    assert props.scripts.items[0].path == new_path
    assert bpy.ops.hg3d.remove_script(index=0) == {"FINISHED"}
    assert [item.path for item in props.scripts.items] == [SHIPPED_SCRIPT]
    assert bpy.ops.hg3d.remove_script(index=5) == {"FINISHED"}
    assert len(props.scripts.items) == 1

    text = bpy.data.texts.get("my_script.py")
    if text:
        bpy.data.texts.remove(text)


def test_add_unreadable_script(props, tmp_path):
    path = write_script(tmp_path, "broken", "def main(context, human, x):\n    pass\n")
    assert not process_props.add_script(props, path), "x has no type annotation"
    count = len(props.scripts.items)
    assert count == 0 or props.scripts.items[-1].path != path


def test_refresh_keys_and_select_list(props, source, context):
    select_only(context, source)
    assert bpy.ops.hg3d.refresh_key_lists() == {"FINISHED"}
    keys = props.shape_keys
    options = source.process.shape_key_options(context)
    for group, names in options.items():
        assert [item.name for item in getattr(keys, f"items_{group}")] == names
    assert len(keys.items_face_rig) > 20, "The FACS keys of the library"
    assert len(keys.items_expressions) > 5

    assert bpy.ops.hg3d.select_process_list(list="expressions", select=False) == {"FINISHED"}
    assert props_to_settings(props).shape_keys.keep["expressions"] == []
    keys.items_expressions[0].enabled = True
    assert props_to_settings(props).shape_keys.keep["expressions"] == [keys.items_expressions[0].name]
    # Refreshing keeps what was unticked
    assert bpy.ops.hg3d.refresh_key_lists() == {"FINISHED"}
    assert sum(item.enabled for item in keys.items_expressions) == 1
    assert bpy.ops.hg3d.select_process_list(list="expressions", select=True) == {"FINISHED"}
    assert "expressions" not in props_to_settings(props).shape_keys.keep, "All ticked is all"
    assert bpy.ops.hg3d.select_process_list(list="nonsense") == {"CANCELLED"}


def test_refresh_clips(props, source, context):
    select_only(context, source)
    props.animations.source = "human"
    assert bpy.ops.hg3d.refresh_clips() == {"FINISHED"}
    clips = props.animations.clips
    names = [action.name for action in source.animation.actions]
    assert sorted(clip.identifier for clip in clips) == sorted(names)
    assert all(clip.is_hg for clip in clips)
    clips[0].enabled = False
    assert props_to_settings(props).animations.clips == [clip.identifier for clip in clips[1:]]
    assert bpy.ops.hg3d.select_process_list(list="clips", select=True) == {"FINISHED"}
    assert props_to_settings(props).animations.clips is None

    # Switching the source lists the library, its clips are preset paths
    props.animations.source = "library"
    refresh_clips(props, source, context)
    assert len(clips) > 2
    assert all(clip.identifier.endswith(".json") for clip in clips)


# The process operator, as the button runs it


def test_process_operator_in_file(props, source, context):
    settings_to_props(props, cheap_settings("blender"))
    select_only(context, source)
    before = set(bpy.data.objects)
    original = snapshot(source)
    handlers = list(bpy.app.handlers.depsgraph_update_post)

    assert bpy.ops.hg3d.process() == {"FINISHED"}
    rigs = _results_of(before)
    try:
        assert len(rigs) == 1
        result = Human.from_existing(rigs[0])
        assert result.process.is_processed
        assert result.objects.rig.select_get()
        assert context.view_layer.objects.active == result.objects.rig
        assert result.process.settings.to_dict() == _effective_settings(props_to_settings(props)).to_dict()
        assert snapshot(source) == original
        # The handlers set aside during processing are back, see issue #69
        assert list(bpy.app.handlers.depsgraph_update_post) == handlers
        # The processed human is no editable human, the tab shows no sections
        select_only(context, result)
        assert not process_panel.HG_PT_MESHES.poll(context)
        assert special_case_panels.HG_PT_PROCESSED.poll(context)
    finally:
        _delete_results(rigs)


def test_process_operator_several_humans(props, source, context):
    second = make_source_human("female", outfit=False, clips=0)
    settings_to_props(props, cheap_settings("blender"))
    select_only(context, source, second)
    before = set(bpy.data.objects)
    try:
        assert bpy.ops.hg3d.process() == {"FINISHED"}
        rigs = _results_of(before)
        assert len(rigs) == 2
        originals = {Human.from_existing(rig).process.settings is not None for rig in rigs}
        assert originals == {True}
        assert {rig.select_get() for rig in rigs} == {True}
        _delete_results(rigs)
    finally:
        second.delete()


def test_process_operator_refuses_bad_settings(props, source, context):
    settings_to_props(props, cheap_settings("unity", "/hg_no_such_root/out"))
    select_only(context, source)
    before = set(bpy.data.objects)
    handlers = list(bpy.app.handlers.depsgraph_update_post)
    with pytest.raises(RuntimeError, match="Can't write to"):
        bpy.ops.hg3d.process()
    assert set(bpy.data.objects) == before
    assert list(bpy.app.handlers.depsgraph_update_post) == handlers


def test_process_operator_without_humans(props, context):
    select_only(context)
    with pytest.raises(RuntimeError, match="No humans selected"):
        bpy.ops.hg3d.process()


def test_process_operator_failure_cleans_up(props, source, context, monkeypatch):
    settings = cheap_settings("blender")
    settings.skeleton.enabled = True
    settings_to_props(props, settings)
    select_only(context, source)

    def fail(*args, **kwargs):
        raise RuntimeError("Simulated failure")

    monkeypatch.setattr(ProcessSettings, "convert_to_game_rig", fail)
    before = set(bpy.data.objects)
    counts = datablock_counts()
    handlers = list(bpy.app.handlers.depsgraph_update_post)
    original = snapshot(source)
    with pytest.raises(RuntimeError, match="Simulated failure"):
        bpy.ops.hg3d.process()
    assert set(bpy.data.objects) == before
    assert datablock_counts()["armatures"] == counts["armatures"]
    assert list(bpy.app.handlers.depsgraph_update_post) == handlers
    assert snapshot(source) == original


def test_result_operators(props, source, context):
    """The buttons of the panel of a processed human."""
    settings = cheap_settings("blender")
    settings.lods[0].teeth = 2
    result = source.process.run(settings, context).humans[0]
    try:
        settings_to_props(props, ExportSettings.from_recipe("unity"))
        select_only(context, result)
        context.scene.HG3D.ui.active_tab = "CREATE"
        assert bpy.ops.hg3d.load_result_settings() == {"FINISHED"}
        assert context.scene.HG3D.ui.active_tab == "PROCESS"
        assert props.output.format == "in_file"
        assert props.lods[0].teeth == "2"

        assert bpy.ops.hg3d.select_original_human() == {"FINISHED"}
        assert context.view_layer.objects.active == source.objects.rig
        assert result.objects.rig not in context.selected_objects

        select_only(context, source)
        assert bpy.ops.hg3d.load_result_settings() == {"CANCELLED"}, "No settings on an original"
    finally:
        result.delete()


# Drawing the panels


ICONS = set(bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items.keys())


def _operator_type(idname):
    module, name = idname.split(".")
    return getattr(getattr(bpy.ops, module), name).get_rna_type()


class OperatorRecorder:
    def __init__(self, idname):
        object.__setattr__(self, "_rna", _operator_type(idname))
        object.__setattr__(self, "_idname", idname)

    def __setattr__(self, name, value):
        assert name in self._rna.properties, f"{self._idname} has no property {name}"


class LayoutRecorder:
    """A UILayout that checks what is drawn into it and records the labels."""

    def __init__(self, log):
        self.__dict__["_log"] = log

    def __setattr__(self, name, value):
        assert name in bpy.types.UILayout.bl_rna.properties, f"UILayout has no {name}"
        self.__dict__[name] = value

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        assert name in bpy.types.UILayout.bl_rna.functions, f"UILayout has no {name}()"

        def method(*args, **kwargs):
            self._log.append((name, args, kwargs))
            self._check(name, args, kwargs)
            if name in ("operator",):
                return OperatorRecorder(args[0] if args else kwargs["operator"])
            return LayoutRecorder(self._log)

        return method

    @staticmethod
    def _check(name, args, kwargs):
        icon = kwargs.get("icon")
        if icon:
            assert icon in ICONS, f"Unknown icon {icon}"
        if name in ("prop", "prop_enum", "template_icon_view", "template_list"):
            data, prop_name = args[0], args[1]
            assert prop_name in data.bl_rna.properties, f"{data} has no property {prop_name}"
            if name == "prop_enum":
                items = data.bl_rna.properties[prop_name].enum_items
                assert args[2] in items.keys(), f"{prop_name} has no item {args[2]}"
        elif name == "operator_menu_enum":
            rna = _operator_type(args[0])
            assert args[1] in rna.properties

    def labels(self):
        return [
            kwargs.get("text", args[0] if args else "")
            for name, args, kwargs in self._log
            if name == "label"
        ]


class ContextProxy:
    """The context with the selection and region the panel is drawn for."""

    def __init__(self, obj, selected):
        self.object = self.active_object = obj
        self.selected_objects = selected
        self.region = SimpleNamespace(width=400)
        # Without a window the scale of the interface is 0
        self.preferences = SimpleNamespace(
            system=SimpleNamespace(ui_scale=1.0), addons=bpy.context.preferences.addons
        )

    def __getattr__(self, name):
        return getattr(bpy.context, name)


def _bound(cls, panel, name):
    """A method of a panel class bound to a stand-in panel instance."""
    raw = inspect.getattr_static(cls, name)
    if isinstance(raw, staticmethod):
        return raw.__func__
    if isinstance(raw, classmethod):
        return raw.__func__.__get__(cls)
    if not callable(raw):
        return raw
    return raw.__get__(panel)


class PanelStandIn:
    def __init__(self, cls, layout):
        self._cls = cls
        self.layout = layout

    def __getattr__(self, name):
        return _bound(self._cls, self, name)


PROCESS_PANELS = [
    cls
    for _, cls in inspect.getmembers(process_panel, inspect.isclass)
    if issubclass(cls, bpy.types.Panel) and cls.__module__ == process_panel.__name__
]


def _draw_all(context, panels=PROCESS_PANELS):
    """Polls and draws the panels as Blender would, returns the labels drawn."""
    log = []
    drawn = []
    for cls in sorted(panels, key=lambda c: getattr(c, "bl_order", 0)):
        if not cls.poll(context):
            continue
        drawn.append(cls.__name__)
        for method in ("draw_header", "draw_header_preset", "draw"):
            if hasattr(cls, method):
                panel = PanelStandIn(cls, LayoutRecorder(log))
                _bound(cls, panel, method)(context)
    labels = LayoutRecorder(log).labels()
    return drawn, labels


def test_every_panel_is_found():
    names = {cls.__name__ for cls in PROCESS_PANELS}
    assert {"HG_PT_PROCESS", "HG_PT_MESHES", "HG_PT_HAIRCARDS", "HG_PT_SKELETON", "HG_PT_SHAPEKEYS", "HG_PT_TEXTURES", "HG_PT_ANIMATIONS", "HG_PT_SCRIPTS", "HG_PT_Z_PROCESS_LOWER"} <= names


def test_panels_without_selection(props, context):
    context.scene.HG3D.ui.active_tab = "PROCESS"
    drawn, labels = _draw_all(ContextProxy(None, []))
    assert drawn == ["HG_PT_PROCESS"]
    assert "No humans selected!" in labels


def test_panels_before_initialized(source, context):
    props = context.scene.HG3D.process
    # Switching to the tab loads the recipes, so the props are cleared after
    context.scene.HG3D.ui.active_tab = "PROCESS"
    props.lods.clear()
    try:
        drawn, _ = _draw_all(ContextProxy(source.objects.rig, [source.objects.rig]))
        assert drawn == ["HG_PT_PROCESS"], "Only the load button before the recipes are loaded"
    finally:
        ensure_initialized(props)


def _open_everything(props):
    for group in (props.meshes, props.skeleton, props.textures, props.animations, props.output):
        group.show_advanced = True
    for group in ("face_rig", "expressions", "correctives", "body", "face", "age"):
        setattr(props.shape_keys, f"open_{group}", True)
    props.animations.clips_open = True
    props.human_list_isopen = True
    for item in props.scripts.items:
        item.menu_open = True


@pytest.mark.parametrize("recipe", SHIPPED_RECIPES)
@pytest.mark.parametrize("lods", [1, 3])
def test_panels_draw_for_every_recipe(props, source, context, recipe, lods):
    context.scene.HG3D.ui.active_tab = "PROCESS"
    props.recipe = recipe
    props.lod_count = lods
    process_props.add_script(props, SHIPPED_SCRIPT)
    refresh_clips(props, source, context)
    process_props.refresh_key_lists(props, source, context)
    _open_everything(props)
    rig = source.objects.rig
    drawn, labels = _draw_all(ContextProxy(rig, [rig]))
    expected = {cls.__name__ for cls in PROCESS_PANELS}
    if props.output.format not in ("in_file", "fbx", "glb", "gltf"):
        expected.discard("HG_PT_ANIMATIONS")
    assert set(drawn) == expected
    if lods > 1:
        assert {"0", "1", "2"} <= set(labels), "A numbered row per level"


@pytest.mark.parametrize("output_format", [ident for ident, *_ in OUTPUT_FORMATS])
def test_panels_draw_for_every_format(props, source, context, output_format):
    context.scene.HG3D.ui.active_tab = "PROCESS"
    props.recipe = "unity"
    props.output.format = output_format
    props.output.naming = "custom"
    props.skeleton.names = "custom"
    props.textures.file_format = "jpeg"
    _open_everything(props)
    rig = source.objects.rig
    drawn, labels = _draw_all(ContextProxy(rig, [rig]))
    assert ("HG_PT_ANIMATIONS" in drawn) == (output_format in ("in_file", "fbx", "glb", "gltf"))
    assert "JPEG drops the hair alpha" in labels
    # The preflight is shown under the button
    assert any("bone names file" in label.lower() for label in labels)


def test_panels_with_everything_off(props, source, context):
    context.scene.HG3D.ui.active_tab = "PROCESS"
    props.recipe = "blender"
    for group in (props.meshes, props.haircards, props.skeleton, props.shape_keys, props.textures, props.animations, props.scripts):
        group.enabled = False
    rig = source.objects.rig
    drawn, _ = _draw_all(ContextProxy(rig, [rig]))
    assert "HG_PT_Z_PROCESS_LOWER" in drawn


def test_button_text(props, source, context):
    second = make_source_human("female", outfit=False, clips=0)
    context.scene.HG3D.ui.active_tab = "PROCESS"
    try:
        rigs = [source.objects.rig, second.objects.rig]
        props.recipe = "unity"
        log = []
        panel = PanelStandIn(process_panel.HG_PT_Z_PROCESS_LOWER, LayoutRecorder(log))
        panel.draw(ContextProxy(rigs[0], rigs))
        texts = [kwargs.get("text") for name, _, kwargs in log if name == "operator"]
        assert "Export 2 humans to FBX" in texts
        props.output.format = "in_file"
        log.clear()
        panel.draw(ContextProxy(rigs[0], rigs[:1]))
        texts = [kwargs.get("text") for name, _, kwargs in log if name == "operator"]
        assert "Make processed copy" in texts
    finally:
        second.delete()


def test_processed_panel(props, source, context):
    result = source.process.run(cheap_settings("blender"), context).humans[0]
    try:
        rig = result.objects.rig
        proxy = ContextProxy(rig, [rig])
        assert special_case_panels.HG_PT_PROCESSED.poll(proxy)
        assert not process_panel.HG_PT_PROCESS.poll(proxy)
        log = []
        PanelStandIn(special_case_panels.HG_PT_PROCESSED, LayoutRecorder(log)).draw(proxy)
        operators = [args[0] for name, args, _ in log if name == "operator"]
        assert operators == ["hg3d.select_original_human", "hg3d.process_again", "hg3d.load_result_settings"]
    finally:
        result.delete()
