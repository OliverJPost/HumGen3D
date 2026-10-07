from typing import TYPE_CHECKING, Literal

import bpy

from HumGen3D.backend import hg_log
from HumGen3D.common import os
from HumGen3D.common.context import context_override
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C
from HumGen3D.human.process.shape_keys import bake_live_keys
from HumGen3D.common.decorators import deprecated
from HumGen3D.common.exceptions import HumGenException

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
        old_location = human.location.copy()
        human.location = (0, 0, 0)

        if _bake_argument_enabled(kwargs):
            _bake_textures(human, filepath, context)

        with context_override(context, human.objects.rig, human.objects):
            old_eye_materials = _remove_eye_outer_material(human)
            try:
                bake_live_keys(human)
                # todo remove face bones if not face rig
                result = exporter_func(self, filepath, *args, **kwargs)
            finally:
                _restore_eye_materials(human, old_eye_materials)
                human.location = old_location

        return result

    def _bake_argument_enabled(kwargs):
        return "bake_textures" in kwargs and kwargs["bake_textures"]

    def _bake_textures(human, filepath, context):
        folder = os.path.dirname(filepath)
        human.process.baking.bake_all(folder, 4, context=context)

    def _check_extension(filepath):
        extension = exporter_func.__name__.replace("_separate", "").replace("_embedded", "").split("_")[-1]
        if not "." in filepath:
            filepath += "." + extension
        elif not filepath.endswith(extension):
            raise Exception(
                f"Filepath '{filepath}' does not end with extension '{extension}'. Either remove the extension or use the correct one."
            )
        return filepath

    def _remove_eye_outer_material(human):
        # Game eyes only have a single opaque material
        if human.process.has_game_eyes:
            return None

        mesh = human.objects.eyes.data
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
        # Leaf bones only exist to show the length of the last bones of a chain,
        # game engines see them as extra bones
        use_leaf_bones=False,
        # "FBX_SCALE_ALL" writes centimeters without a scale on the armature, as
        # Unreal expects
        apply_scale_options: str = "FBX_SCALE_NONE",
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
            apply_scale_options=apply_scale_options,
            # Only export the animation of this human, not of all humans in the file
            bake_anim_use_all_actions=False,
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
        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None,
    ):
        self._export_common_gltf(filepath, "GLTF_SEPARATE")

    def _export_common_gltf(
        self, filepath, format: str, img_format: Literal["AUTO", "JPEG"] = "AUTO"
    ):
        skin_materials = None
        if not self._human.process.baking.is_baked():
            hg_log(
                "Exporting GLTF without baking textures. This will result in empty textures.",
                level="WARNING",
            )
            skin_materials = self._detach_skin_shader()

        # Create an export collection, since use_selection does not work.
        collection = bpy.data.collections.new("Export")
        bpy.context.scene.collection.children.link(collection)
        for obj in self._human.objects:
            collection.objects.link(obj)
        view_layer = bpy.context.view_layer
        old_active_layer_collection = view_layer.active_layer_collection
        view_layer.active_layer_collection = view_layer.layer_collection.children[
            collection.name
        ]

        try:
            bpy.ops.export_scene.gltf(
                filepath=filepath,
                export_format=format,
                export_copyright=LICENSE_TEXT,
                export_image_format=img_format,
                use_active_collection=True,
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
    def to_glb(
        self,
        filepath: str,
        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None,
    ):
        self._export_common_gltf(filepath, "GLB")

    @exporter
    def to_abc(
        self,
        filepath: str,

        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None
    ):
        # Context override doesn't seem to work for this operator
        for obj in context.selected_objects:
            obj.select_set(False)

        for obj in self._human.objects:
            obj.select_set(True)

        bpy.ops.wm.alembic_export(
            filepath=filepath,
            selected=True
        )