# Imports the Unreal-recipe FBX and reports what the docs claim about Unreal Engine.
import json, os, sys, traceback
import unreal

OUT = os.environ.get("HG_REPORT", "/tmp/unreal_report.json")
FBX = os.environ["HG_FBX"]
report = {"fbx": FBX, "engine": unreal.SystemLibrary.get_engine_version()}

def probe(name, fn):
    try:
        report[name] = fn()
    except Exception as e:
        report[name] = f"ERROR {type(e).__name__}: {e}"

def import_fbx(dest, legacy):
    task = unreal.AssetImportTask()
    task.filename = FBX
    task.destination_path = dest
    task.automated = True
    task.save = False
    task.replace_existing = True
    if legacy:
        opts = unreal.FbxImportUI()
        opts.import_mesh = True
        opts.import_as_skeletal = True
        opts.import_materials = True
        opts.import_textures = True
        opts.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
        opts.skeletal_mesh_import_data.import_morph_targets = True
        task.options = opts
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    return [str(p) for p in task.imported_object_paths]

def bones(mesh):
    sub = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    names = []
    def walk(name):
        names.append(str(name))
        for child in sub.get_bone_children(mesh, name):
            walk(child)
    for root in ("root", "Root", "Hips", "mixamorig:Hips", "pelvis"):
        try:
            if sub.get_bone_children(mesh, root) or root in ("root", "Root"):
                walk(root)
                break
        except Exception:
            continue
    return names

def inspect(dest):
    r = {}
    assets = unreal.EditorAssetLibrary.list_assets(dest, recursive=True)
    r["assets"] = sorted(a.split("/")[-1].split(".")[0] for a in assets)
    r["textures"] = []
    r["materials"] = []
    mesh = None
    for a in assets:
        obj = unreal.EditorAssetLibrary.load_asset(a)
        if isinstance(obj, unreal.Texture2D):
            r["textures"].append({"name": obj.get_name(), "srgb": obj.get_editor_property("srgb"), "compression": str(obj.get_editor_property("compression_settings")).split(".")[-1].split(":")[0]})
        elif isinstance(obj, unreal.MaterialInstanceConstant):
            m = {"name": obj.get_name(), "parent": obj.get_editor_property("parent").get_name() if obj.get_editor_property("parent") else None}
            try:
                ov = obj.get_editor_property("base_property_overrides")
                m["override_blend_mode"] = ov.get_editor_property("override_blend_mode")
                m["blend_mode"] = str(ov.get_editor_property("blend_mode")).split(".")[-1].split(":")[0]
                m["two_sided"] = ov.get_editor_property("two_sided")
            except Exception as e:
                m["props"] = str(e)
            try:
                m["texture_params"] = {str(t.parameter_info.name): (t.parameter_value.get_name() if t.parameter_value else None) for t in obj.get_editor_property("texture_parameter_values")}
            except Exception as e:
                m["texture_params"] = str(e)
            r["materials"].append(m)
        elif isinstance(obj, unreal.Material):
            r["materials"].append({"name": obj.get_name(), "blend_mode": str(obj.get_editor_property("blend_mode")), "two_sided": obj.get_editor_property("two_sided")})
        elif isinstance(obj, unreal.SkeletalMesh):
            mesh = obj
    if mesh is None:
        r["skeletal_mesh"] = None
        return r
    r["skeletal_mesh"] = mesh.get_name()
    b = mesh.get_bounds()
    r["height_cm"] = float(b.box_extent.z) * 2
    for name, fn in [
        ("morph_count", lambda: len(mesh.get_all_morph_target_names())),
        ("morph_targets_sample", lambda: [str(n) for n in mesh.get_all_morph_target_names()][:12]),
        ("lod_count", lambda: unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem).get_lod_count(mesh)),
        ("materials_on_mesh", lambda: [str(sm.material_interface.get_name()) if sm.material_interface else None for sm in mesh.materials]),
        ("skeleton", lambda: mesh.skeleton.get_name()),
        ("bones", lambda: bones(mesh)),
    ]:
        try:
            r[name] = fn()
        except Exception as e:
            r[name] = f"ERROR {type(e).__name__}: {e}"
    return r

try:
    # UE 5.8 imports skeletal meshes through Interchange by default; the legacy
    # FbxImportUI path no longer carries the morph target option in Python
    probe("interchange_import_paths", lambda: import_fbx("/Game/HumGenInterchange", False))
    probe("interchange", lambda: inspect("/Game/HumGenInterchange"))
except Exception:
    report["fatal"] = traceback.format_exc()
with open(OUT, "w") as f:
    json.dump(report, f, indent=2, default=str)
unreal.log("REPORT WRITTEN " + OUT)
