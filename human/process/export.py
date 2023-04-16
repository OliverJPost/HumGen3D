from typing import TYPE_CHECKING, Literal

import bpy

from HumGen3D.backend import hg_log
from HumGen3D.common import os
from HumGen3D.common.context import context_override
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

Axis = Literal["X", "Y", "Z", "-X", "-Y", "-Z"]
LICENSE_TEXT = """Made with Human Generator for Blender3D.
Licensed under the Human Generator Asset License.
Does not permit redistribution except embedded in software or in other formats that do not allow easy extraction.
See https://humgen3d.com for more information.
"""


def exporter(exporter_func):
    @injected_context
    def wrapper(self, filepath, *args, **kwargs):
        context = kwargs.get("context", bpy.context)
        filepath = _check_extension(filepath)
        human = self._human
        human.location = (0, 0, 0)

        if _bake_argument_enabled(kwargs):
            _bake_textures(human, filepath, context)

        with context_override(context, human.objects.rig, human.objects):
            _remove_eye_outer_material(human)
            # todo remove face bones if not face rig
            result = exporter_func(self, filepath, *args, **kwargs)
            # todo re-add outer material

        return result

    def _bake_argument_enabled(kwargs):
        return "bake_textures" in kwargs and kwargs["bake_textures"]

    def _bake_textures(human, filepath, context):
        folder = os.path.dirname(filepath)
        human.process.baking.bake_all(folder, 4, context=context)

    def _check_extension(filepath):
        extension = exporter_func.__name__.split("_")[-1]
        if not "." in filepath:
            filepath += "." + extension
        elif not filepath.endswith(extension):
            raise Exception(
                "Filepath does not end with extension. Either remove the extension or use the correct one."
            )
        return filepath

    def _remove_eye_outer_material(human):
        eyes = human.objects.eyes
        # Remove transparent outer material, not supported by most formats
        eyes.data.materials.pop(index=0)

    return wrapper


# NOTE: Do not remove the context arguments, they are used by the decorator
class ExportBuilder:
    def __init__(self, _human: "Human"):
        self._human = _human

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
        use_leaf_bones=True,
        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None,
    ):
        bpy.ops.export_scene.fbx(
            filepath=filepath,
            use_selection=True,
            object_types={
                "ARMATURE",
                "MESH",
            },
            use_mesh_modifiers=False,  # To make sure shape keys are exported
            mesh_smooth_type="FACE",
            use_custom_props=export_custom_props,
            use_triangles=triangulate,
            primary_bone_axis=primary_bone_axis,
            secondary_bone_axis=secondary_bone_axis,
            axis_up=axis_up,
            axis_forward=axis_forward,
            add_leaf_bones=use_leaf_bones,
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

    @exporter
    def to_gltf(
        self,
        filepath: str,
        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None,
    ):
        self._export_common_gltf(filepath, "GLTF_EMBEDDED")

    def _export_common_gltf(
        self, filepath, format: str, img_format: Literal["AUTO", "JPEG"] = "AUTO"
    ):
        if not self._human.process.baking.is_baked():
            hg_log(
                "Exporting GLTF without baking textures. This will result in empty textures.",
                level="WARNING",
            )
            self._human.skin._unlink_all_textures()

        # Create an export collection, since use_selection does not work.
        collection = bpy.data.collections.new("Export")
        bpy.context.scene.collection.children.link(collection)
        for obj in self._human.objects:
            collection.objects.link(obj)
        bpy.context.view_layer.active_layer_collection = (
            bpy.context.view_layer.layer_collection.children[collection.name]
        )

        bpy.ops.export_scene.gltf(
            filepath=filepath,
            export_format=format,
            export_copyright=LICENSE_TEXT,
            export_image_format=img_format,
            use_active_collection=True,
        )

        bpy.context.scene.collection.children.unlink(collection)
        bpy.data.collections.remove(collection)

    @exporter
    def to_glb(
        self,
        filepath: str,
        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None,
    ):
        self._export_common_gltf(filepath, "GLB")
