from typing import TYPE_CHECKING, Literal

import bpy

from HumGen3D.common import os
from HumGen3D.common.context import context_override
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C

if TYPE_CHECKING:
    from HumGen3D.human.human import Human


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
        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None,
    ):
        bpy.ops.export_scene.fbx(
            filepath=filepath,
            use_selection=False,
            use_active_collection=False,
            object_types={"ARMATURE", "MESH", "EMPTY"},
            add_leaf_bones=False,
            use_mesh_modifiers=True,
            use_mesh_modifiers_render=True,
            mesh_smooth_type="FACE",
            use_tspace=False,
            use_custom_props=True,
            bake_anim=True,
            bake_anim_use_all_bones=True,
            bake_anim_use_nla_strips=True,
            bake_anim_use_all_actions=True,
            bake_anim_force_startend_keying=True,
            bake_anim_step=1.0,
            bake_anim_simplify_factor=1.0,
            path_mode="AUTO",
            embed_textures=False,
            batch_mode="OFF",
            use_batch_own_dir=True,
            use_metadata=True,
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
        axis_forward: Literal["X", "Y", "Z", "-X", "-Y", "-Z"] = "-Z",
        axis_up: Literal["X", "Y", "Z", "-X", "-Y", "-Z"] = "Y",
        # DON'T REMOVE, used by decorator
        bake_textures: bool = False,
        context: C = None,
    ):
        eyes = self._human.objects.eyes
        # Remove transparent outer material, not supported by obj
        eyes.data.materials.pop(index=0)
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
