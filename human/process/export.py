from typing import TYPE_CHECKING, Literal

import bpy

from HumGen3D.common import os
from HumGen3D.common.context import context_override
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

Axis = Literal["X", "Y", "Z", "-X", "-Y", "-Z"]

# Template for decorator
def exporter(func):
    @injected_context
    def wrapper(self, filepath, *args, **kwargs):
        # Get name of function
        extension = func.__name__.split("_")[-1]
        if not "." in filepath:
            filepath += "." + extension
        elif not filepath.endswith(extension):
            raise Exception(
                "Filepath does not end with extension. Either remove the extension or use the correct one."
            )
        args = (self, filepath, *args)
        context = kwargs.get("context", bpy.context)
        bake_textures = kwargs.get("bake_textures", False)

        if bake_textures:
            folder = os.path.dirname(filepath)
            self._human.process.baking.bake_all(folder, 4, context=context)

        with context_override(context, self._human.objects[0], self._human.objects):
            result = func(*args, **kwargs)

        return result

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
        self.remove_eye_outer_material()
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
        self.remove_eye_outer_material()
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

    def remove_eye_outer_material(self):
        eyes = self._human.objects.eyes
        # Remove transparent outer material, not supported by obj
        eyes.data.materials.pop(index=0)

    @exporter
    def to_gltf(
        self,
        filepath: str,
        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None,
    ):
        bpy.ops.export_scene.gltf(
            filepath=filepath,
            export_format="GLTF_SEPARATE",
            export_image_format="AUTO",
            export_texcoords=True,
            export_normals=True,
            export_draco_mesh_compression_enable=False,
            export_draco_mesh_compression_level=7,
            export_draco_position_quantization=14,
            export_draco_normal_quantization=10,
            export_draco_texcoord_quantization=12,
            export_draco_generic_quantization=12,
            export_tangents=False,
            export_materials="EXPORT",
            export_colors=True,
            export_cameras=False,
            use_selection=True,
            export_extras=False,
            export_yup=False,
            export_apply=False,
            export_animations=True,
            export_frame_range=True,
            export_frame_step=1,
            export_force_sampling=False,
            export_nla_strips=False,
            export_def_bones=False,
            export_current_frame=False,
            export_skins=True,
            export_morph=True,
            export_morph_normal=True,
            export_morph_tangent=False,
            export_lights=False,
        )

    @exporter
    def to_glb(
        self,
        filepath: str,
        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None,
    ):
        bpy.ops.export_scene.gltf(
            filepath=filepath,
            export_format="GLB",
            export_image_format="AUTO",
            export_texcoords=True,
            export_normals=True,
            export_draco_mesh_compression_enable=False,
            export_draco_mesh_compression_level=7,
            export_draco_position_quantization=14,
            export_draco_normal_quantization=10,
            export_draco_texcoord_quantization=12,
            export_draco_generic_quantization=12,
            export_tangents=False,
            export_materials="EXPORT",
            export_colors=True,
            export_cameras=False,
            use_selection=True,
            export_extras=False,
            export_yup=False,
            export_apply=False,
            export_animations=True,
            export_frame_range=True,
            export_frame_step=1,
            export_force_sampling=False,
            export_nla_strips=False,
            export_def_bones=False,
            export_current_frame=False,
            export_skins=True,
            export_morph=True,
            export_morph_normal=True,
            export_morph_tangent=False,
            export_lights=False,
        )
