# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import contextlib
import os
import re
import subprocess
from typing import Iterable

import bpy
from HumGen3D.backend.logging import hg_log
from HumGen3D.backend.memory_management import hg_delete
from HumGen3D.backend.preferences.preference_func import get_addon_root


class SavableContent:
    def save_to_library(self) -> None:
        raise NotImplementedError

    @staticmethod
    def save_objects_optimized(
        context: bpy.types.Context,
        objs: Iterable[bpy.types.Object],
        folder: str,
        filename: str,
        clear_sk: bool = True,
        clear_materials: bool = True,
        clear_vg: bool = True,
        clear_ps: bool = True,
        run_in_background: bool = True,
        clear_drivers: bool = True,
    ) -> None:
        """Saves the passed objects as a new blend file, opening the file in the
        background to make it as small as possible

        Args:
            objs              (list)          : List of objects to save
            folder            (Path)          : Folder to save the file in
            filename          (str)           : Name to save the file as
            clear_sk          (bool, optional): Remove all shapekeys from objs.
                                                Defaults to True.
            clear_materials   (bool, optional): Remove all materials from objs.
                                                Defaults to True.
            clear_vg          (bool, optional): Remove all vertex groups from
                                                objs. Defaults to True.
            clear_ps          (bool, optional): Remove all particle systems from
                                                objs. Defaults to True.
            run_in_background (bool, optional): Open the new subprocess in the
                                                background. Defaults to True.
        """
        for obj in objs:
            if obj.type != "MESH":
                continue
            if clear_materials:
                obj.data.materials.clear()
            if clear_vg:
                obj.vertex_groups.clear()
            if clear_sk:
                SavableContent._remove_shapekeys(obj)
            if clear_ps:
                SavableContent._remove_particle_systems(context, obj)
            if clear_drivers:
                SavableContent._remove_obj_drivers(obj)

        if clear_drivers:
            SavableContent._clear_sk_drivers()

        new_scene = bpy.data.scenes.new(name="test_scene")
        new_col = bpy.data.collections.new(name="HG")
        new_scene.collection.children.link(new_col)
        for obj in objs:
            new_col.objects.link(obj)

        if not os.path.exists(folder):
            os.makedirs(folder)

        blend_filepath = os.path.join(folder, f"{filename}.blend")
        bpy.data.libraries.write(blend_filepath, {new_scene})

        python_file = os.path.join(get_addon_root(), "scripts", "hg_purge.py")
        if run_in_background:
            hg_log("STARTING HumGen background process", level="BACKGROUND")
            subprocess.Popen(
                [
                    bpy.app.binary_path,
                    blend_filepath,
                    "--background",
                    "--python",
                    python_file,
                ],
                stdout=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                [bpy.app.binary_path, blend_filepath, "--python", python_file]
            )

        bpy.data.scenes.remove(new_scene)
        for obj in objs:
            hg_delete(obj)

    @staticmethod
    def _clear_sk_drivers() -> None:
        for key in bpy.data.shape_keys:
            try:
                fcurves = key.animation_data.drivers
                for _ in fcurves:
                    fcurves.remove(fcurves[0])  # type:ignore[index]
            except AttributeError:
                pass

    @staticmethod
    def _remove_obj_drivers(obj: bpy.types.Object) -> None:
        with contextlib.suppress(AttributeError):
            drivers_data = obj.animation_data.drivers

            for dr in drivers_data:
                obj.driver_remove(dr.data_path, -1)

    @staticmethod
    def _remove_particle_systems(
        context: bpy.types.Context, obj: bpy.types.Object
    ) -> None:
        """Remove particle systems from the passed object

        Args:
            obj (Object): obj to remove particle systems from
        """
        context.view_layer.objects.active = obj
        # TODO low level
        for i, _ in enumerate(obj.particle_systems):  # type:ignore[arg-type]
            obj.particle_systems.active_index = i
            bpy.ops.object.particle_system_remove()

    @staticmethod
    def _remove_shapekeys(obj: bpy.types.Object) -> None:
        """Remove shapekeys from the passed object

        Args:
            obj (Object): obj to remove shapekeys from
        """
        for sk in [sk for sk in obj.data.shape_keys.key_blocks if sk.name != "Basis"]:
            obj.shape_key_remove(sk)
        if obj.data.shape_keys:
            obj.shape_key_remove(obj.data.shape_keys.key_blocks["Basis"])

    @staticmethod
    def remove_number_suffix(name: str) -> str:
        """Remove the number suffix from the passed name
        (i.e. Box.004 becomes Box)

        Args:
            name (str): name to remove suffix from

        Returns:
            str: name without suffix
        """
        re_suffix = re.search(r".\d\d\d", name)
        if not re_suffix or not name.endswith(re_suffix.group(0)):
            return name
        else:
            return name.replace(re_suffix.group(0), "")
