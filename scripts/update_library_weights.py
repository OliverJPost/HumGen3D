# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Regenerate the skin weights of the clothing in a content library.

Run it with the oldest Blender version the library has to support, because a
.blend saved by a newer Blender can become unreadable for older versions:

    blender -b --python update_library_weights.py -- all --weights DIR

`all` does these two steps after each other, they can also be run separately:

1. compute: needs the Human Generator add-on enabled. Reads every outfit file,
   computes new weights and stores them in DIR. The library is not touched.
2. apply: needs no add-on. Writes the stored weights into the library files,
   after copying each original to DIR/backup.

`apply` refuses to save a file with a Blender newer than the one it was saved
with, unless --allow-upgrade is passed.

The add-on that Blender version has installed may be older than this script and
lack the clothing code it needs. In that case the script starts Blender again
with BLENDER_USER_SCRIPTS pointing at the scripts folder this file is in, so
the add-on it belongs to is used. The installed add-on is not changed.

Only vertex groups named after deform bones are replaced. Shape keys, drivers,
materials, modifiers and all other vertex groups stay as they are. Hand painted
fixes to the old weights are lost, the backup is the way back.
"""

import argparse
import contextlib
import csv
import json
import os
import shutil
import subprocess
import sys
import time

import bpy  # type:ignore
import numpy as np

RELAUNCHED = "HG_WEIGHTS_RELAUNCHED"
MANIFEST = "manifest.json"
REPORT = "report.csv"
# A garment whose typical distance to the base body is larger than this is not
# where it is expected, for example because the file is for the other gender
MAX_MEDIAN_DISTANCE = 0.08


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []

    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--weights", required=True, help="Folder for the weights")
    shared.add_argument("--library", help="Content folder, default from add-on")
    shared.add_argument("--only", help="Only files whose path contains this text")

    computing = argparse.ArgumentParser(add_help=False)
    computing.add_argument("--gender", choices=("male", "female"), action="append")
    computing.add_argument(
        "--footwear",
        action="store_true",
        help="Also process footwear. Off by default: shoes have rigid parts "
        "that automatic weights can bend",
    )
    computing.add_argument(
        "--keep-failed",
        action="store_true",
        help="Also store weights when the solver fell back to closest points",
    )

    applying = argparse.ArgumentParser(add_help=False)
    applying.add_argument("--backup", help="Backup folder, default <weights>/backup")
    applying.add_argument("--no-backup", action="store_true")
    applying.add_argument("--dry-run", action="store_true", help="Change no files")
    applying.add_argument(
        "--allow-upgrade",
        action="store_true",
        help="Save files even if this Blender is newer than the one they were "
        "saved with",
    )

    parser = argparse.ArgumentParser(prog="update_library_weights.py")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("compute", parents=[shared, computing], help="Compute weights")
    sub.add_parser("apply", parents=[shared, applying], help="Write to library")
    sub.add_parser("all", parents=[shared, computing, applying], help="Do both")
    return parser.parse_args(argv)


def ensure_addon_with_clothing_code():
    """Make sure the loaded add-on is recent enough, else restart with this one."""
    try:
        import HumGen3D.human.clothing.weights  # noqa: F401

        return
    except ImportError:
        pass

    addon = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    addons_dir = os.path.dirname(addon)
    usable = (
        os.path.basename(addons_dir) == "addons"
        and os.path.isfile(os.path.join(addon, "human", "clothing", "weights.py"))
        and not os.environ.get(RELAUNCHED)
    )
    if not usable:
        sys.exit(
            "The Human Generator add-on loaded by this Blender does not contain "
            "the clothing code this script needs. Start Blender with the "
            "environment variable BLENDER_USER_SCRIPTS set to the scripts "
            "folder that contains the current add-on."
        )
    scripts_dir = os.path.dirname(addons_dir)
    print(f"Installed add-on is too old, restarting with add-ons from {scripts_dir}")
    env = dict(os.environ, BLENDER_USER_SCRIPTS=scripts_dir)
    env[RELAUNCHED] = "1"
    sys.exit(subprocess.call([bpy.app.binary_path] + sys.argv[1:], env=env))


# --------------------------------------------------------------------- compute
def compute(args):
    ensure_addon_with_clothing_code()
    if "HumGen3D" not in bpy.context.preferences.addons:
        sys.exit("Enable the Human Generator add-on in this Blender version first")

    from HumGen3D import Human
    from HumGen3D.backend import get_prefs
    from HumGen3D.common.surface import closest_points, make_bvh
    from HumGen3D.human.clothing.garment_fit import (
        body_reference,
        triangles,
        weight_matrix,
    )
    from HumGen3D.human.clothing.weights import transfer_weights

    library = os.path.abspath(args.library or get_prefs().filepath)
    os.makedirs(args.weights, exist_ok=True)
    genders = args.gender or ["male", "female"]
    categories = ["outfits"] + (["footwear"] if args.footwear else [])

    rows = []
    for gender in genders:
        with _quiet():  # creating a human prints a lot
            preset = Human.get_preset_options(gender)[0]
            human = Human.from_preset(preset, bpy.context)
            body = body_reference(human)
            human.delete()
        bvh = make_bvh(body.co, body.tris)

        for path in _library_files(library, categories, gender, args.only):
            rel = os.path.relpath(path, library)
            stored = {}
            for obj in _append_mesh_objects(path):
                row = {"file": rel, "object": obj.name}
                rows.append(row)
                start = time.time()
                matrix = _rig_matrix(obj)
                co = _base_co(obj) @ matrix[:3, :3].T + matrix[:3, 3]
                tris = triangles(obj)
                if not len(tris):
                    row["status"] = "skipped: no faces"
                    continue
                distance = closest_points(co, body.co, body.tris, bvh)[3]
                if np.median(distance) > MAX_MEDIAN_DISTANCE:
                    row["status"] = "skipped: not on the base body"
                    continue

                weights, info = transfer_weights(
                    co, tris, body.co, body.tris, body.weights, bvh=bvh, maxiter=6000
                )
                old = weight_matrix(obj, body.bones)
                old /= np.maximum(old.sum(axis=1, keepdims=True), 1e-12)
                row.update(
                    vertices=len(co),
                    solver=info["solver"],
                    matched=round(info["matched"], 3),
                    changed=round(float(0.5 * np.abs(weights - old).sum(1).mean()), 4),
                    seconds=round(time.time() - start, 1),
                )
                if info["solver"] == "closest_point" and not args.keep_failed:
                    row["status"] = "skipped: solver failed"
                    continue
                used = np.where(weights.max(axis=0) > 1e-4)[0]
                index = len(stored) // 3
                stored[f"name_{index}"] = np.array(obj.name)
                stored[f"bones_{index}"] = np.array([body.bones[i] for i in used])
                stored[f"weights_{index}"] = weights[:, used].astype(np.float32)
                row["status"] = "ok"
            _remove_appended()

            if stored:
                stored["all_bones"] = np.array(body.bones)
                target = os.path.join(args.weights, rel + ".npz")
                os.makedirs(os.path.dirname(target), exist_ok=True)
                np.savez_compressed(target, **stored)
            print("COMPUTED", rel, [r["status"] for r in rows if r["file"] == rel])

    with open(os.path.join(args.weights, MANIFEST), "w") as f:
        json.dump({"library": library, "blender": bpy.app.version_string}, f)
    _write_report(os.path.join(args.weights, REPORT), rows)
    _summary("computed", rows)


@contextlib.contextmanager
def _quiet():
    """Silence everything Blender and the add-on print, errors are still raised."""
    sys.stdout.flush()
    sys.stderr.flush()
    saved = os.dup(1), os.dup(2)
    null = os.open(os.devnull, os.O_WRONLY)
    os.dup2(null, 1)
    os.dup2(null, 2)
    try:
        yield
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(saved[0], 1)
        os.dup2(saved[1], 2)
        for descriptor in saved + (null,):
            os.close(descriptor)


def _library_files(library, categories, gender, only):
    files = []
    for category in categories:
        for root, _, names in os.walk(os.path.join(library, category, gender)):
            files += [os.path.join(root, n) for n in names if n.endswith(".blend")]
    return sorted(f for f in files if not only or only in f)


def _append_mesh_objects(path):
    with bpy.data.libraries.load(path, link=False) as (data_from, data_to):
        data_to.objects = data_from.objects
    objects = [obj for obj in data_to.objects if obj is not None]
    for obj in objects:
        obj["_hg_weights_tmp"] = 1
    return [obj for obj in objects if obj.type == "MESH"]


def _remove_appended():
    for obj in [o for o in bpy.data.objects if "_hg_weights_tmp" in o]:
        bpy.data.objects.remove(obj)
    for _ in range(3):  # also the meshes, materials and images they used
        bpy.data.orphans_purge()


def _base_co(obj):
    keys = obj.data.shape_keys
    data = keys.reference_key.data if keys else obj.data.vertices
    co = np.empty(len(data) * 3, dtype=np.float64)
    data.foreach_get("co", co)
    return co.reshape(-1, 3)


def _rig_matrix(obj):
    """Local to rig space, the way the add-on parents clothing to a human."""
    basis = obj.matrix_basis.copy()
    basis.translation = (0, 0, 0)
    return np.array(obj.matrix_parent_inverse @ basis)


# ----------------------------------------------------------------------- apply
def apply(args):
    manifest_path = os.path.join(args.weights, MANIFEST)
    library = args.library
    if not library and os.path.isfile(manifest_path):
        with open(manifest_path) as f:
            library = json.load(f)["library"]
    if not library:
        sys.exit("Pass --library, no manifest found in the weights folder")
    backup = args.backup or os.path.join(args.weights, "backup")

    rows = []
    for stored_path in _stored_files(args.weights, args.only):
        rel = os.path.relpath(stored_path, args.weights)[: -len(".npz")]
        path = os.path.join(library, rel)
        row = {"file": rel}
        rows.append(row)
        if not os.path.isfile(path):
            row["status"] = "skipped: not in library"
            continue

        had_blend1 = os.path.isfile(path + "1")
        with open(path, "rb") as f:
            compressed = f.read(7) != b"BLENDER"
        bpy.ops.wm.open_mainfile(filepath=path)
        saved_with = tuple(bpy.data.version)[:2]
        row["saved_with"] = "{}.{}".format(*saved_with)
        if tuple(bpy.app.version)[:2] > saved_with and not args.allow_upgrade:
            row["status"] = "skipped: saved with older Blender, see --allow-upgrade"
            continue

        stored = np.load(stored_path)
        problems = _write_stored_weights(stored)
        if problems:
            row["status"] = "skipped: " + "; ".join(problems)
            continue
        if args.dry_run:
            row["status"] = "ok (dry run)"
            continue

        if not args.no_backup:
            target = os.path.join(backup, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if not os.path.isfile(target):  # never overwrite the first backup
                shutil.copy2(path, target)
        bpy.ops.wm.save_mainfile(compress=compressed)
        if not had_blend1 and os.path.isfile(path + "1"):
            os.remove(path + "1")
        row["status"] = "ok"
        print("APPLIED", rel)

    _summary("applied", rows)


def _stored_files(weights_dir, only):
    files = []
    for root, _, names in os.walk(weights_dir):
        files += [os.path.join(root, n) for n in names if n.endswith(".blend.npz")]
    return sorted(f for f in files if not only or only in f)


def _write_stored_weights(stored):
    """Write weights to the objects of the open file. Returns found problems."""
    all_bones = {str(name) for name in stored["all_bones"]}
    count = len([key for key in stored.files if key.startswith("name_")])
    entries = []
    for index in range(count):
        obj = bpy.data.objects.get(str(stored[f"name_{index}"]))
        weights = stored[f"weights_{index}"]
        if obj is None or obj.type != "MESH":
            return [f"object {stored[f'name_{index}']} not found"]
        if len(obj.data.vertices) != len(weights):
            return [f"vertex count of {obj.name} changed"]
        entries.append((obj, [str(b) for b in stored[f"bones_{index}"]], weights))

    for obj, bones, weights in entries:
        for group in [g for g in obj.vertex_groups if g.name in all_bones]:
            obj.vertex_groups.remove(group)
        for column, name in enumerate(bones):
            values = weights[:, column]
            group = obj.vertex_groups.new(name=name)
            for vertex in np.where(values > 1e-4)[0]:
                group.add([int(vertex)], float(values[vertex]), "REPLACE")
    return []


# ---------------------------------------------------------------------- report
def _write_report(path, rows):
    fields = ["file", "object", "status", "vertices", "solver", "matched", "changed"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields + ["seconds"])
        writer.writeheader()
        writer.writerows(rows)


def _summary(verb, rows):
    done = [row for row in rows if row.get("status", "").startswith("ok")]
    print(f"\nSUMMARY {len(done)} of {len(rows)} {verb}")
    for row in rows:
        if row not in done:
            print("  ", row["file"], row.get("object", ""), "-", row.get("status"))


if __name__ == "__main__":
    arguments = parse_args()
    if arguments.command in ("compute", "all"):
        compute(arguments)
    if arguments.command in ("apply", "all"):
        apply(arguments)
