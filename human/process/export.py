# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Writes a human to a file, see `ExportBuilder`.

The `to_*` methods take the options of the Blender exporters. `write` takes
the `OutputSettings` of the process system instead and picks the format and
its options from them, so a recipe and a call of the API mean the same thing.
"""

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Literal

import bpy

from HumGen3D.backend import hg_log
from HumGen3D.common.context import context_override
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C
from HumGen3D.human.process.shape_keys import bake_live_keys
from HumGen3D.common.decorators import deprecated
from HumGen3D.common.exceptions import HumGenException

from . import naming
from .animations import rig_actions
from .settings import FILE_FORMATS, OutputSettings

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

Axis = Literal["X", "Y", "Z", "-X", "-Y", "-Z"]
# What of the animation of the rig goes into the file: nothing, the active
# action or the active action and the NLA strips as separate takes
Animation = Literal["none", "active", "strips"]
LICENSE_TEXT = """Made with Human Generator for Blender3D.
Licensed under the Human Generator Asset License.
Does not permit redistribution except embedded in software or in other formats that do not allow easy extraction.
See https://humgen3d.com for more information.
"""


def fbx_kwargs(output: OutputSettings, units: str = "meters") -> Dict[str, Any]:
    """The arguments of `ExportBuilder.to_fbx` for these output settings.

    Args:
        output (OutputSettings): The FBX options and the texture placement.
        units (str): "meters" or "centimeters", see `SkeletonSettings.units`.
            Centimeters apply the FBX unit scale to the objects, so Unreal
            imports the armature at scale 1.
    """
    fbx = output.fbx
    embedded = output.textures == "embedded"
    return {
        "axis_forward": fbx.axis_forward,
        "axis_up": fbx.axis_up,
        "primary_bone_axis": fbx.primary_bone_axis,
        "secondary_bone_axis": fbx.secondary_bone_axis,
        "use_leaf_bones": fbx.leaf_bones,
        "export_custom_props": fbx.custom_properties,
        "triangulate": fbx.triangulate,
        "mesh_smooth_type": fbx.smoothing,
        "apply_scale_options": "FBX_SCALE_ALL" if units == "centimeters" else "FBX_SCALE_NONE",
        "path_mode": "COPY" if embedded else "RELATIVE",
        "embed_textures": embedded,
    }


def gltf_kwargs(output: OutputSettings) -> Dict[str, Any]:
    """The arguments of `ExportBuilder.to_glb` and `to_gltf_separate` for these settings."""
    return {
        "image_format": output.gltf.image_format,
        "tangents": output.gltf.tangents,
        "draco": output.gltf.draco,
    }


@contextmanager
def selected_for_export(
    context: bpy.types.Context, objects: List[bpy.types.Object]
) -> Iterator[None]:
    """Selects exactly these objects in the view layer, the selection restored after.

    The OBJ and Alembic exporters read the selection of the view layer and
    ignore a context override.
    """
    view_layer = context.view_layer
    old_selected = [obj for obj in view_layer.objects if obj.select_get()]
    old_active = view_layer.objects.active
    for obj in old_selected:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    try:
        yield
    finally:
        for obj in objects:
            obj.select_set(False)
        for obj in old_selected:
            obj.select_set(True)
        view_layer.objects.active = old_active


def exporter(exporter_func):
    @injected_context
    def wrapper(self, filepath, *args, **kwargs):
        context = kwargs.get("context", bpy.context)
        filepath = _check_extension(filepath)
        human = self._human
        old_location = human.location.copy()
        human.location = (0, 0, 0)

        if _bake_argument_enabled(kwargs) and not human.process.was_baked:
            _bake_textures(human, filepath, context)

        objects = (
            [human.objects.rig] if kwargs.get("armature_only") else list(human.objects)
        )
        # A copy of a human has names like "Jake_Body.001" while the original is
        # in the file, the exported file gets the names without the suffix
        datablocks = naming.datablocks(human) + rig_actions(human)
        with context_override(context, human.objects.rig, objects), naming.exact_names(datablocks):
            old_eye_materials = _remove_eye_outer_material(human)
            try:
                bake_live_keys(human)
                exporter_func(self, filepath, *args, **kwargs)
            finally:
                _restore_eye_materials(human, old_eye_materials)
                human.location = old_location

        return filepath

    def _bake_argument_enabled(kwargs):
        return "bake_textures" in kwargs and kwargs["bake_textures"]

    def _bake_textures(human, filepath, context):
        folder = os.path.dirname(filepath)
        human.process.bake_textures(folder=folder, context=context)

    def _check_extension(filepath):
        extension = exporter_func.__name__.replace("_separate", "").replace("_embedded", "").split("_")[-1]
        if not filepath.lower().endswith("." + extension):
            filepath += "." + extension
        return filepath

    def _remove_eye_outer_material(human):
        # Game eyes only have a single opaque material
        if human.process.has_game_eyes:
            return None

        mesh = human.objects.eyes.data
        if len(mesh.materials) < 2:
            return None
        old_materials = list(mesh.materials)
        old_material_indices = [polygon.material_index for polygon in mesh.polygons]
        # Remove transparent outer material, not supported by most formats
        mesh.materials.pop(index=0)

        return old_materials, old_material_indices

    def _restore_eye_materials(human, old_eye_materials):
        if not old_eye_materials:
            return

        old_materials, old_material_indices = old_eye_materials
        mesh = human.objects.eyes.data
        mesh.materials.clear()
        for material in old_materials:
            mesh.materials.append(material)
        mesh.polygons.foreach_set("material_index", old_material_indices)

    return wrapper


# NOTE: Do not remove the context arguments, they are used by the decorator
class ExportBuilder:
    """Writes a human to a file. Every method returns the path that was written.

    The datablocks are written under their names without the number suffix of
    Blender, the livekeys are baked and the transparent outer layer of the eyes
    is left out, as most formats can't carry it.
    """

    def __init__(self, _human: "Human"):
        self._human = _human

    @injected_context
    def write(
        self,
        filepath: str,
        output: OutputSettings,
        units: str = "meters",
        animation: Animation = "none",
        armature_only: bool = False,
        sample_rate: int = 0,
        context: C = None,
    ) -> str:
        """Writes the human in the format of the output settings.

        Args:
            filepath (str): Path of the file, the extension of the format is
                added when missing. Its folder is made when needed.
            output (OutputSettings): Format, exporter options and texture
                placement, as in a recipe.
            units (str): "meters" or "centimeters", see `SkeletonSettings.units`.
                FBX only.
            animation (Animation): "none", "active" or "strips", what of the
                animation of the rig goes into the file. Formats with a rig only.
            armature_only (bool): Only the skeleton and its animation, for a
                file with clips.
            sample_rate (int): Frames per second the animation is sampled at,
                0 for the frame rate of the scene, see
                `AnimationClipSettings.sample_rate`. FBX only.
            context (C): Blender context. bpy.context if not provided.

        Returns:
            str: The path that was written.

        Raises:
            ValueError: If the output is not a file format.
        """
        file_format = output.format
        if file_format not in FILE_FORMATS:
            raise ValueError(f"Output format has to be one of {FILE_FORMATS}")
        folder = os.path.dirname(os.path.abspath(filepath))
        os.makedirs(folder, exist_ok=True)
        if file_format == "fbx":
            # The exporter samples every `bake_anim_step` frames of the scene
            fps = context.scene.render.fps / context.scene.render.fps_base
            return self.to_fbx(
                filepath,
                animation=animation,
                armature_only=armature_only,
                bake_anim_step=max(fps / sample_rate, 0.01) if sample_rate > 0 else 1.0,
                context=context,
                **fbx_kwargs(output, units),
            )
        if file_format == "glb":
            return self.to_glb(
                filepath,
                animation=animation,
                armature_only=armature_only,
                context=context,
                **gltf_kwargs(output),
            )
        if file_format == "gltf":
            return self.to_gltf_separate(
                filepath,
                animation=animation,
                armature_only=armature_only,
                context=context,
                **gltf_kwargs(output),
            )
        if file_format == "obj":
            return self.to_obj(filepath, context=context)
        return self.to_abc(filepath, context=context)

    @exporter
    def to_fbx(
        self,
        filepath: str,
        export_custom_props: bool = False,
        triangulate: bool = False,
        axis_forward: Axis = "-Z",
        axis_up: Axis = "Y",
        primary_bone_axis: Axis = "Y",
        secondary_bone_axis: Axis = "X",
        # Leaf bones only exist to show the length of the last bones of a chain,
        # game engines see them as extra bones
        use_leaf_bones=False,
        # "FBX_SCALE_ALL" writes centimeters without a scale on the armature, as
        # Unreal expects
        apply_scale_options: str = "FBX_SCALE_NONE",
        mesh_smooth_type: str = "FACE",
        # "COPY" with embed_textures puts the images inside the file
        path_mode: str = "AUTO",
        embed_textures: bool = False,
        animation: Animation = "active",
        # Only the skeleton and its animation, for files with clips
        armature_only: bool = False,
        # Frames of the scene between two samples of the animation
        bake_anim_step: float = 1.0,
        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None,
    ):
        bpy.ops.export_scene.fbx(
            filepath=filepath,
            use_selection=True,
            object_types={"ARMATURE"} if armature_only else {"ARMATURE", "MESH"},
            use_mesh_modifiers=False,  # To make sure shape keys are exported
            mesh_smooth_type=mesh_smooth_type,
            use_custom_props=export_custom_props,
            use_triangles=triangulate,
            primary_bone_axis=primary_bone_axis,
            secondary_bone_axis=secondary_bone_axis,
            axis_up=axis_up,
            axis_forward=axis_forward,
            add_leaf_bones=use_leaf_bones,
            apply_scale_options=apply_scale_options,
            path_mode=path_mode,
            embed_textures=embed_textures,
            bake_anim=animation != "none",
            # Only export the animation of this human, not of all humans in the file
            bake_anim_use_all_actions=False,
            bake_anim_use_nla_strips=animation == "strips",
            bake_anim_step=bake_anim_step,
        )

    @exporter
    def to_obj(
        self,
        filepath: str,
        apply_modifiers: bool = True,
        triangulate: bool = False,
        export_vertex_groups: bool = False,
        path_mode: Literal[
            "AUTO", "ABSOLUTE", "RELATIVE", "MATCH", "STRIP", "COPY"
        ] = "AUTO",
        axis_forward: Axis = "-Z",
        axis_up: Axis = "Y",
        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None,
    ):
        if bpy.app.version < (4, 0, 0):
            bpy.ops.export_scene.obj(
                filepath=filepath,
                use_selection=True,
                use_mesh_modifiers=apply_modifiers,
                use_normals=True,
                use_uvs=True,
                use_materials=True,
                use_triangles=triangulate,
                use_vertex_groups=export_vertex_groups,
                path_mode=path_mode,
                axis_forward=axis_forward,
                axis_up=axis_up,
            )
        else:
            objects = [obj for obj in self._human.objects if obj.type == "MESH"]
            with selected_for_export(context, objects):
                bpy.ops.wm.obj_export(
                    filepath=filepath,
                    export_selected_objects=True,
                    apply_modifiers=apply_modifiers,
                    export_normals=True,
                    export_uv=True,
                    export_materials=True,
                    export_triangulated_mesh=triangulate,
                    path_mode=path_mode,
                    forward_axis=axis_forward.replace("-", "NEGATIVE_"),
                    up_axis=axis_up.replace("-", "NEGATIVE_"),
                )

    @exporter
    @deprecated("Use .to_gltf_embedded or .to_gltf_separate instead.")
    def to_gltf(
        self,
        filepath: str,
        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None,
        ):
        self._export_common_gltf(filepath, "GLTF_EMBEDDED")

    @exporter
    def to_gltf_embedded(
        self,
        filepath: str,
        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None,
    ):
        self._export_common_gltf(filepath, "GLTF_EMBEDDED")

    @exporter
    def to_gltf_separate(
        self,
        filepath: str,
        image_format: Literal["AUTO", "JPEG"] = "AUTO",
        tangents: bool = False,
        draco: bool = False,
        animation: Animation = "none",
        armature_only: bool = False,
        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None,
    ):
        self._export_common_gltf(
            filepath, "GLTF_SEPARATE", image_format, tangents, draco, animation, armature_only
        )

    @exporter
    def to_glb(
        self,
        filepath: str,
        image_format: Literal["AUTO", "JPEG"] = "AUTO",
        tangents: bool = False,
        draco: bool = False,
        animation: Animation = "none",
        armature_only: bool = False,
        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None,
    ):
        self._export_common_gltf(
            filepath, "GLB", image_format, tangents, draco, animation, armature_only
        )

    def _export_common_gltf(  # noqa: CCR001
        self,
        filepath,
        format: str,
        img_format: Literal["AUTO", "JPEG"] = "AUTO",
        tangents: bool = False,
        draco: bool = False,
        animation: Animation = "none",
        armature_only: bool = False,
    ):
        skin_materials = None
        if not self._human.process.was_baked:
            hg_log(
                "Exporting GLTF without baking textures. This will result in empty textures.",
                level="WARNING",
            )
            skin_materials = self._detach_skin_shader()

        # Create an export collection, since use_selection does not work.
        collection = bpy.data.collections.new("Export")
        bpy.context.scene.collection.children.link(collection)
        objects = (
            [self._human.objects.rig] if armature_only else list(self._human.objects)
        )
        for obj in objects:
            collection.objects.link(obj)
        view_layer = bpy.context.view_layer
        old_active_layer_collection = view_layer.active_layer_collection
        view_layer.active_layer_collection = view_layer.layer_collection.children[
            collection.name
        ]

        kwargs = {}
        if animation == "none":
            kwargs["export_animations"] = False
        else:
            kwargs["export_animations"] = True
            kwargs["export_animation_mode"] = (
                "NLA_TRACKS" if animation == "strips" else "ACTIVE_ACTIONS"
            )
        if tangents:
            kwargs["export_tangents"] = True
        if draco:
            kwargs["export_draco_mesh_compression_enable"] = True

        try:
            bpy.ops.export_scene.gltf(
                filepath=filepath,
                export_format=format,
                export_copyright=LICENSE_TEXT,
                export_image_format=img_format,
                use_active_collection=True,
                **kwargs,
            )
        except TypeError as e:
            if str(e) == "Converting py args to operator properties: enum \"GLTF_EMBEDDED\" not found in ('GLB', 'GLTF_SEPARATE')":
                raise HumGenException("You need to enable glTF Embedded in the 'glTF 2.0 Format' add-on preferences.") from None
            else:
                raise
        finally:
            # Removing the active collection would leave the context without one
            view_layer.active_layer_collection = old_active_layer_collection
            bpy.context.scene.collection.children.unlink(collection)
            bpy.data.collections.remove(collection)
            if skin_materials:
                self._restore_skin_shader(*skin_materials)

    def _detach_skin_shader(self) -> tuple[bpy.types.Material, bpy.types.Material]:
        """Gives the body a copy of its skin material without the shader node.

        The glTF exporter reads the textures from the Principled BSDF, which the
        unbaked skin material feeds from a node tree it can't export. The original
        material is shared with the human this one was duplicated from, so it is
        left untouched and put back after the export.

        Returns:
            tuple[Material, Material]: The original material and the copy.
        """
        body = self._human.objects.body
        material = body.data.materials[0]
        export_material = material.copy()
        body.data.materials[0] = export_material
        shader_node = export_material.node_tree.nodes.get("Principled BSDF")
        if shader_node:
            export_material.node_tree.nodes.remove(shader_node)
        return material, export_material

    def _restore_skin_shader(
        self, material: bpy.types.Material, export_material: bpy.types.Material
    ) -> None:
        self._human.objects.body.data.materials[0] = material
        bpy.data.materials.remove(export_material)

    @exporter
    def to_abc(
        self,
        filepath: str,

        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None
    ):
        # The operator ignores the context override, it reads the view layer
        with selected_for_export(context, list(self._human.objects)):
            bpy.ops.wm.alembic_export(filepath=filepath, selected=True)
