# Engine checks

Scripts that import a processed character into a game engine from the command
line and write a JSON report of what arrived: bones, morph targets, materials,
textures, scale. They back the claims of the engine pages in `docs/Process/`
and were last run on 2026-10-10 with Blender 5.1, Unity 6000.6, Unreal Engine
5.8 and Godot 4.7.

1. `blender -b characters.blend --python blender_export_characters.py` writes the
   character (edit the recipe and folder at the top).
2. Unity: create an empty project (`Unity -batchmode -nographics -createProject <dir> -quit`),
   copy `unity_HumGenCheck.cs` to `Assets/Editor/` and the export to `Assets/HumGen/`, then
   `Unity -batchmode -nographics -projectPath <dir> -executeMethod HumGenCheck.Run -quit`.
   The report is `<dir>/report.json`.
3. Godot: a folder with a `project.godot`, the `.glb` and `godot_check.gd`, then
   `Godot --headless --path <dir> --import` and `Godot --headless --path <dir> --script check.gd`.
   The report is `<dir>/report.json`.
4. Unreal: a `.uproject` with `PythonScriptPlugin` enabled, then
   `HG_FBX=<file.fbx> HG_REPORT=<report.json> UnrealEditor-Cmd <project.uproject> -run=pythonscript -script=unreal_check.py -unattended -nopause -nosplash`.
