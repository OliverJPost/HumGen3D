# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Human Generator 3D (HumGen3D)** is a Blender add-on for generating photorealistic humans with customizable features including body proportions, clothing, hair, expressions, and poses. The add-on provides both a GUI interface within Blender and a Python API for programmatic human generation.

- **Version**: 4.0.27
- **License**: GPL 3.0
- **Blender Compatibility**: 4.2+ (on 4.0/4.1 the add-on only shows a "needs Blender 4.2 or newer" notice)
- **Store**: https://blendermarket.com/products/humgen3d

## Development Commands

### Testing
```bash
# Run all tests (must be run from within Blender's Python environment)
pytest

# Run specific test file
pytest tests/human/test_body.py

# Run with coverage
pytest --cov=HumGen3D --cov-config=tests/.coveragerc
```

### Linting
```bash
# Run flake8
flake8

# Run mypy type checking
mypy .

# Run pylint
pylint <file>
```

### Pre-commit Hooks
The project uses pre-commit hooks for code quality:
- flake8 (with extensive plugins)
- mypy (strict mode with some exclusions)
- pylint

Run manually with: `pre-commit run --all-files`

## Architecture

### Core Structure

The codebase follows a modular architecture organized by functionality:

**`Human` Class (`human/human.py`)**: The central API entry point. All human generation and modification goes through this class. Two main constructors:
- `Human.from_preset(preset_name)`: Creates a new human from a preset
- `Human.from_existing(blender_object)`: Gets a Human instance from an existing Blender human object

**Settings Classes**: The `Human` class exposes sub-settings through properties that return specialized classes:
- `human.body` → `BodySettings`: Body proportions
- `human.face` → `FaceSettings`: Facial features
- `human.skin` → `SkinSettings`: Skin materials and textures
- `human.hair` → `HairSettings`: Hair systems (regular, facial, eyebrows, eyelashes)
- `human.clothing` → `ClothingSettings`: Outfit and footwear
- `human.pose` → `PoseSettings`: Armature poses
- `human.expression` → `ExpressionSettings`: Facial expressions
- `human.height` → `HeightSettings`: Height adjustment
- `human.keys` → `KeySettings`: Shape keys
- `human.eyes` → `EyeSettings`: Eye materials
- `human.materials` → `MaterialSettings`: Material access
- `human.process` → `ProcessSettings`: Processing operations (baking, LOD, etc.)

### Key Subsystems

**Preview Collections (`backend/preview_collections.py`)**: Manages Blender preview collections for browsing presets (humans, clothing, hair, etc.). Uses lazy loading and caching.

**Content Packs (`backend/content/`)**: Manages external content packs that users can install. Handles JSON manifests and file operations for custom content.

**Process System (`human/process/`)**: Exports humans for game engines or freezes copies in the file. `settings.py` holds the `ExportSettings` schema, which is at once the recipe file (built-in ones in `<content>/process/recipes/`, user ones in `<content>/process_templates/`), the Blender properties (`backend/properties/process_props.py`, `props_to_settings`/`settings_to_props`), the argument of `human.process.run(settings)` and the `hg_export` metadata on results. `pipeline.py` runs the steps as a progress generator (`common/progress.py`); every LOD level is a fresh duplicate of the source. The single steps are public methods of `ProcessSettings` (`process.py`) that take the matching settings section (`set_shape_keys(ShapeKeySettings)`, `bake_textures(TextureBakeSettings)`, `set_quality(QualitySettings)`, `convert_to_game_rig(settings=SkeletonSettings)`, `apply_names(OutputSettings)`, `prepare_clips(AnimationClipSettings)`, `human.export.write(path, OutputSettings)`); the pipeline calls those same methods, so a new step or option goes into the settings schema, a `ProcessSettings` method and the pipeline, in that order. Steps that change a human for good refuse to run twice (`has_*`/`was_*` properties). Engine knowledge (bone names, packing, normal map direction, clip layout) belongs in recipe JSON, not code. The data the process system runs on (built-in recipes, `game_rig_presets.json`, the LOD edge lists in `process/lod/`) is not in this public repo: it ships as the `HG_Export.hgpack` content pack from Superhive (formerly BlenderMarket), as an anti-piracy measure. Its source is the content folder, `scripts/build_export_pack.py` builds the pack, and `human/process/export_pack.py` finds it: without it the Process tab is greyed out and the API raises `ExportPackMissing`. New process data goes there, not into the add-on; raise `export_pack.REQUIRED_VERSION` when the code needs a newer pack. `t_pose.json` stays in the add-on because animation retargeting uses it. Every rigged file export gets a `<name>.humgen3d.json` manifest (`manifest.py`: files, mesh/material types, texture files, settings); the engine Companions (separate public repos humgen3d-companion-unity/-unreal/-godot) set up only what a manifest lists, so its format is a contract: bump `manifest.FORMAT` only for changes old Companions would misread.

**Batch Generator (`batch_generator/generator.py`)**: `BatchHumanGenerator` class for generating multiple humans with randomized features. Used both programmatically and by the GUI batch panel.

**Auto Class Registration (`backend/auto_classes.py`)**: Automatically discovers and registers all Blender operator, panel, and property classes by walking the directory tree. Classes can set `_register_priority` attribute to control registration order.

**Common Utilities (`common/`)**: Shared functionality:
- Object finding and management
- Material operations
- Driver handling
- Math utilities
- Type aliases for Blender types

### Data Flow

1. **Human Creation**: Imports base rig and body objects from `models/HG_HUMAN.blend`
2. **Preset Loading**: Reads JSON files containing shape keys, material settings, and content references
3. **Settings Application**: Each settings class has `set_from_dict()` and `as_dict()` methods for serialization
4. **Content Application**: References external .blend files for clothing, hair, poses via append/link operations
5. **Custom Properties**: Stores metadata on Blender objects via `HG_OBJECT_PROPS` (accessed as `obj.HG`)

### Important Patterns

**Context Injection**: Many methods use `@injected_context` decorator to automatically provide Blender context if not passed.

**Gender-Specific Logic**: Most content and features are gender-specific. Gender is stored as `"male"` or `"female"` strings.

**Legacy Compatibility**: Code includes checks for legacy humans (pre-4.0) via `is_legacy()` function.

**Backup Humans**: The add-on creates backup copies of humans before major modifications.

**Object Hierarchy**:
- Root: Armature object (the "rig")
- Children: Body mesh, eyes, teeth, clothing items, hair objects
- Custom properties on rig identify it as HumGen human (`ishuman=True`)

## Documentation (`docs/`)

User documentation lives in `docs/` as an Obsidian vault (open the folder in Obsidian to edit) and is rendered at humgen3d.com/docs. Licence, install, refund and contact pages live in the website repo instead.

- When a change affects what users see or do (UI, options, workflow, API), update the matching pages in `docs/Guide`, `docs/Process`, `docs/Batch` or `docs/Custom content` in the same commit.
- The API reference (`docs/API/api.json`) is generated by `python scripts/api_docs.py` from docstrings and type hints (needs `griffe`, no Blender): change the docstring or annotation, then rerun it. A pre-commit hook (`--check`) fails when it is stale. `docs/API/Overview.md` is hand-written.
- Give public attributes set in `__init__` a type annotation and a docstring line below them, so they show up documented.
- Obsidian syntax is fine: `[[Page]]`, `[[Page#Heading|label]]`, `![[image.webp]]`, `> [!info]` callouts (`> [!tip]-` folds). Put new media in `docs/attachments/` as WebP (screenshots) or MP4 (recordings), not PNG/GIF.
- Docs on `dev` describe unreleased behaviour; they go live when they reach the public `main`.

## Blender-Specific Considerations

- **Operators**: All Blender operators must inherit from `bpy.types.Operator` and be registered
- **Properties**: Use Blender's property types (`bpy.props.StringProperty`, etc.) not standard Python properties
- **Type Hints**: Blender property annotations use special syntax (e.g., `prop: StringProperty`) that conflicts with standard type checking
- **Module System**: Blender caches imports; uses `importlib.reload()` pattern for development
- **Handlers**: Load handlers (`bpy.app.handlers.load_post`) run startup procedures

## File Organization

- `__init__.py`: Add-on entry point, handles registration
- `human/`: Core human generation and modification logic
- `backend/`: Infrastructure (properties, preferences, updates, content management)
- `batch_generator/`: Batch human generation system
- `user_interface/`: Blender UI panels and operators
- `common/`: Shared utilities
- `tests/`: Pytest test suite
- `scripts/`: Development and utility scripts
- `extern/`: Third-party code

## Testing Notes

Tests must be run within Blender's Python environment, not standard Python. Test fixtures are defined in `tests/test_fixtures.py`. Tests use pytest with lazy fixtures for Blender objects.

Most process tests make a human, convert hair to cards and bake textures, so `tests/process` (345 tests) runs well over an hour and `test_haircards.py` alone takes about 8 minutes. Don't run a whole folder to check a change: run the test files that cover the code you touched (for example `test_baked_materials.py`, `test_process_settings.py` and `test_process_ui.py` for a bake option), and add `-x`. Don't filter the output down to the summary line; keep the progress visible so a long run can be judged.

## Documentation

- `docs/` holds the user documentation as Obsidian-style markdown (`[[Page]]`, `![[file.webp|520]]`, `> [!info]` callouts); the website repo renders it at `humgen3d.com/docs/<folder>/<file>` with lower-case, dash-separated slugs (`docs/Process/Bake Textures.md` → `/docs/process/bake-textures`, a folder's `Overview.md` is the folder URL). Every page starts with a `description:` frontmatter (the meta description) and one `# Heading`; pages are listed in the sidebar in the order their folder's Overview links them. Media goes in `docs/attachments/`.
- `docs/API/api.json` is generated by `python scripts/api_docs.py` (griffe) from the docstrings; API pages are keyed by class name, so two public classes must not share a name.
- A before/after image slider is a fenced `compare` block (Obsidian shows it as code): three lines, `before: file.webp | Label`, `after: file.webp | Label` and an optional `width: 640`; both images need the same size. The site renders it with `components/docs/image-compare.tsx` in the website repo.
- Buttons in the interface link to pages through `common/documentation.py` (`docs_url("process/skeleton")`, `draw_docs_button`); `DOCS_URL` is the only place the site address lives.

## Setup, content packs and updates (`backend/setup/`)

The content packs are installed and updated by the add-on itself. `backend/setup/` is the engine, `user_interface/setup_overlay/` the gpu-drawn window plus the sidebar `HG_PT_SETUP` panel (same steps as plain widgets, for when the overlay cannot show), and the preferences show the pack list with per-pack updates.
- `catalogue.py`: the server's catalogue (`GET humgen3d.com/api/addon/catalogue`, one entry per pack with versions, sizes, sha256, `min_addon`) against `installed_packs(folder)` (the `content_packs/*.json` manifests) gives a `PackStatus` per pack: missing, update_required, update_available, up_to_date, needs_newer_addon, locked. `REQUIRED` in that file is the only place the add-on says which pack versions it needs; raise it there when the code needs newer data (HG Export has its own in `export_pack.REQUIRED_VERSION`).
- `api_client.py`: the three requests (catalogue, `activate` with order GUID + email, `content` for download URLs). `HUMGEN_API_URL` points it at another server for tests. The website side lives in the website repo (`lib/addon/*`, `app/api/addon/*`, `app/ext/*`, docs/addon-setup.md there).
- `downloader.py`: resumable download with checksum, install = unzip over the content folder + record the file list in the pack JSON; an update removes only the old pack's files that the new one lacks, and `remove()`/the stale step never delete a path another installed pack lists (old pack JSONs don't list every file they installed, so the trial cleanup also only deletes files with "trial" in the name). The pack JSON is written last, so an interrupted install keeps the old version recorded. Nothing here imports bpy.
- `user_settings.py`: a JSON file outside Blender (`~/Library/Application Support/HumGen3D/settings.json` on macOS, `%APPDATA%` / `~/.config` elsewhere) with the content folder and the order the user activated with. It survives Blender versions and the legacy→extension switch; `migration.resolve_content_folder()` reads it (and the legacy package's preferences) at load. **Any run of the setup code outside normal use writes to that real file unless `HUMGEN_SETTINGS_FILE` points elsewhere**: activating writes the order, a rejected order is marked `credential_status: rejected` (never deleted), an install writes the folder. `tests/conftest.py` sets the variable for every pytest run and `scripts/ci/run_in_blender.py` sets it too; set it yourself for any ad-hoc Blender run, screenshot harness or one-off script (`HUMGEN_SETTINGS_FILE=/tmp/x.json Blender ...`), or your own content folder and order get overwritten.
- `update_check.py`: the once-a-day background check, started from a timer after load, never on the main thread, silent when `bpy.app.online_access` is off (`online.py`; the UI offers an "Allow online access" button instead of sending people to the preferences). `backend/updates/update.py::check_update` only applies the cached result now.
- `repository.py`: the extension repository `https://humgen3d.com/ext/index.json`; a trial lead's install link uses `/ext/t/<rid>/index.json`, from which `trial_rid()` reads the request id. Releasing: bump the manifest version, merge to main, push the tag `v<version>`; `.github/workflows/release.yml` builds the zip and `index.json` (`scripts/release_extension.py`) and attaches both to a GitHub release, which the website serves as the repository (`humgen3d.com/ext/`). GitHub's "latest release" is what Blender sees, so every version tag must become a release, not a bare tag.
- Rules the setup UI follows: content on disk is never locked or removed because of licensing (content notices are a banner, never a replacement of the panel); find existing content before asking anything (`migration.find_existing_content`, `content_state`: unset / unreachable / empty / installed); never show a step whose answer is known (the `begin_*` entry points on `SetupState` route by what is installed and stored); the order is asked only when licensed packs are about to download; there is no install-from-file route for our own packs. The licence tier comes from the server on every activate/content call (`user_settings.update_license`) and drives the "Upgrade to Commercial" button. The catalogue's `addon.notices` / `addon.setup` / `schema` are the server's kill switches.
- The state machine is `user_interface/setup_overlay/state.py` (`SetupState`, one `state` instance). Everything external goes through `Services`; `FakeServices` (env `HUMGEN_FAKE_SETUP=1` or the dev-tools preference "Fake setup downloads") counts bytes instead of downloading, which the tests and the GUI screenshot harness use. Tests: `tests/test_setup_*.py` (local HTTP servers, no network). CI: `.github/workflows/tests.yml` runs them inside downloaded Blenders on Linux and Windows for pushes to main.

## Version Management

The version lives in `blender_manifest.toml` (`version = "x.y.z"`); `__version__` in `__init__.py` is read from it at import (`package.manifest_version`). `bl_info["version"]` in `__init__.py` must be a literal for the legacy loader, so update it together with the manifest; `tests/test_extension.py` fails when they differ.

## Extension and legacy add-on

The same folder loads as a legacy add-on (`bl_info`, package `HumGen3D`, from `scripts/addons`) and as a Blender extension (`blender_manifest.toml`, package `bl_ext.<repository>.humgen3d`). Blender below 4.2 is not supported: there `register()` registers only a notice (`user_interface/install_notices.py`), which is why `bl_info` still says 4.0. When both copies are switched on, the extension registers only the "installed twice" notice with `hg3d.use_new_version` (copies the legacy preferences, switches the legacy copy off, registers in-session), and the legacy copy steps aside; `tests/extension_probe.py` covers both. Rules that follow from this:
- Only relative imports inside the package, never `from HumGen3D...`. `package.py` gives the real package name (`addon_package()`, `is_extension()`, `addon_root()`, `addon_version()`); use it for the preferences lookup and the `bl_idname` of the preferences.
- `alias.py` keeps `from HumGen3D import Human` (and the old `HG3D`) working for scripts when the package has another name: a `sys.meta_path` finder hands out the real modules, so there is never a second copy of a class. Installed at import and in `register()`, removed in `unregister()`.
- No runtime `pip`, no bundled wheels: image work goes through `common/images.py` (Blender's image API) instead of Pillow.
- The CG Cookie self-updater is skipped as an extension (`is_extension()`); Blender's repository delivers updates there.
- Build the extension zip with `"/Applications/Blender 5.1.app/Contents/MacOS/Blender" --command extension build --source-dir . --output-dir <folder>` (the `[build]` excludes in the manifest keep tests, docs, scripts and venvs out); `--command extension validate .` checks the manifest. `tests/test_extension_mode.py` loads the folder as an extension in a separate Blender Python.