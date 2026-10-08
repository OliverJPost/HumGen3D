# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Human Generator 3D (HumGen3D)** is a Blender add-on for generating photorealistic humans with customizable features including body proportions, clothing, hair, expressions, and poses. The add-on provides both a GUI interface within Blender and a Python API for programmatic human generation.

- **Version**: 4.0.27
- **License**: GPL 3.0
- **Blender Compatibility**: 3.2.0+
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

**Process System (`human/process/`)**: Exports humans for game engines or freezes copies in the file. `settings.py` holds the `ExportSettings` schema, which is at once the recipe file (`recipes/*.json` shipped, `<content>/process_templates/` user), the Blender properties (`backend/properties/process_props.py`, `props_to_settings`/`settings_to_props`), the argument of `human.process.run(settings)` and the `hg_export` metadata on results. `pipeline.py` runs the steps as a progress generator (`common/progress.py`); every LOD level is a fresh duplicate of the source. The single steps are public methods of `ProcessSettings` (`process.py`) that take the matching settings section (`set_shape_keys(ShapeKeySettings)`, `bake_textures(TextureSettings)`, `set_quality(QualitySettings)`, `convert_to_game_rig(settings=SkeletonSettings)`, `apply_names(OutputSettings)`, `prepare_clips(AnimationSettings)`, `human.export.write(path, OutputSettings)`); the pipeline calls those same methods, so a new step or option goes into the settings schema, a `ProcessSettings` method and the pipeline, in that order. Steps that change a human for good refuse to run twice (`has_*`/`was_*` properties). Engine knowledge (bone names, packing, normal map direction, clip layout) belongs in recipe JSON, not code.

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

## Version Management

Version is stored in two places (keep in sync):
- `__init__.py`: `__version__` tuple and `bl_info["version"]`
- Both must be updated together for releases