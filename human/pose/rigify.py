from typing import TYPE_CHECKING, Literal

import bpy
from HumGen3D.common.collections import add_to_collection
from HumGen3D.common.context import context_override
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.drivers import build_driver_dict
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.type_aliases import C

if TYPE_CHECKING:
    from human.human import Human


class RigifySettings:
    def __init__(self, human: "Human") -> None:
        self._human = human

    @property
    def is_rigify(self) -> bool:
        return "hg_rigify" in self._human.objects.rig

    @injected_context
    def generate(self, context: C = None) -> None:
        try:
            import rigify
        except ImportError:
            raise HumGenException(
                "Rigify is not enabled! Enable it in the addons panel of the Blender preferences."
            )
        human = self._human
        human.pose.reset()

        driver_dict = build_driver_dict(human.objects.body, remove=True)

        old_rig = human.objects.rig
        with context_override(context, old_rig, [old_rig], False):
            rigify.generate.generate_rig(context, human.objects.rig)

        rigify_rig = self._find_created_rigify_rig(context)
        rigify_rig.data["hg_rigify"] = 1
        rigify_rig.name = human.name + "_RIGIFY"
        add_to_collection(context, rigify_rig)

        self._rename_vertex_groups(human.objects.body)
        self._add_original_name_bone_tags(rigify_rig)
        self._iterate_children(human.objects.rig, rigify_rig)
        self._set_HG_props(human.objects.rig, rigify_rig)

        armature_mod = next(
            mod for mod in human.objects.body.modifiers if mod.type == "ARMATURE"
        )
        armature_mod.object = rigify_rig

        sks = human.objects.body.data.shape_keys.key_blocks
        for target_sk_name, sett_dict in driver_dict.items():
            human.keys._add_driver(sks[target_sk_name], sett_dict)

        for child in rigify_rig.children:
            self._correct_drivers(child, rigify_rig)

        human._rig_obj = rigify_rig

        if human.expression.has_facial_rig:
            for bone in human.pose_bones:
                self._relink_constraints(bone, rigify_rig)

    def _rename_vertex_groups(self, obj: bpy.types.Object) -> None:
        """Renames vertex groups to match the rigify naming convention"""
        for vg in obj.vertex_groups:
            prefix_list = ("mask", "pin", "def-", "hair", "fh", "sim", "lip")
            if not vg.name.lower().startswith(prefix_list):
                vg.name = "DEF-" + vg.name

    def _add_original_name_bone_tags(self, rigify_rig: bpy.types.Object) -> None:
        """Adds the original name of the bone as a bone tag on deformation bones

        Args:
            rigify_rig (Object): Rigify HumGen armature
        """
        deformation_bones = [
            bone for bone in rigify_rig.pose.bones if bone.name.startswith("DEF-")
        ]
        for bone in deformation_bones:
            bone["hg_original_name"] = bone.name.replace("DEF-", "")

    def _set_HG_props(
        self, hg_rig: bpy.types.Object, rigify_rig: bpy.types.Object
    ) -> None:
        """Sets the HG props on the new rig to be the same as the old rig

        Args:
            hg_rig (Object): standard HumGen armature
            rigify_rig (Object): Rigify HumGen armature
        """
        new_HG = rigify_rig.HG
        old_HG = hg_rig.HG

        new_HG.ishuman = True
        new_HG.phase = old_HG.phase
        new_HG.gender = old_HG.gender
        new_HG.body_obj = old_HG.body_obj
        new_HG.length = old_HG.length
        new_HG.version = old_HG.version
        if "pytest_human" in hg_rig:
            rigify_rig["pytest_human"] = True

    def _iterate_children(
        self, hg_rig: bpy.types.Object, rigify_rig: bpy.types.Object
    ) -> None:
        """Iterates over the children of the rig (clothes, eyes etc.) and
        sets their vertex groups, drivers and armature

        Args:
            hg_rig (Object): old HumGen armature
            rigify_rig (Object): new Rigify humgen armature
        """
        for child in hg_rig.children:
            child.parent = rigify_rig
            child_armature = [mod for mod in child.modifiers if mod.type == "ARMATURE"]
            if child_armature:
                child_armature[0].object = rigify_rig
                self._rename_vertex_groups(child)

    def _find_created_rigify_rig(self, context: bpy.types.Context) -> bpy.types.Object:
        """Finds the newly created Rigify rig
        Returns:
            bpy.types.Object: new Rigify rig
        """
        unused_rigify_rigs = [
            obj
            for obj in bpy.data.objects
            if obj.type == "ARMATURE"
            and "rig_id" in obj.data
            and not obj.children
            and "hg_rigify" not in obj.data
        ]

        for rig in unused_rigify_rigs:
            if rig in context.selected_objects:
                return rig

        raise HumGenException("Could not find the newly created Rigify rig")

    def _correct_drivers(
        self, obj: bpy.types.Object, rigify_rig: bpy.types.Object
    ) -> None:
        """Correct the drivers to fit the new bone names

        Args:
            obj (Object): HumGen body object?
            rigify_rig (Object): new Rigify rig
        """
        if not obj.data.shape_keys or not obj.data.shape_keys.animation_data:
            return

        for driver in obj.data.shape_keys.animation_data.drivers:
            var = driver.driver.variables[0]
            target = var.targets[0]
            target.id = rigify_rig
            if target.bone_target.startswith(("forearm", "upper_arm", "thigh", "foot")):
                target.bone_target = "DEF-" + target.bone_target

    def _relink_constraints(
        self, bone: bpy.types.Object, rigify_rig: bpy.types.Object
    ) -> None:
        """Relinks the limit_location constraints, currently used on the facial rig.

        Args:
            bone (PoseBone): Bone on the old rig that may have a loc constraints
            rigify_rig (Armature): New rig, which to add constraints on
        """
        new_bone = rigify_rig.pose.bones.get(bone.name)
        if not new_bone or not bone.constraints:
            return

        old_loc_constraint = next(
            (c for c in bone.constraints if c.type == "LIMIT_LOCATION")
        )
        if not old_loc_constraint:
            return

        new_loc_constraint = new_bone.constraints.new("LIMIT_LOCATION")
        new_loc_constraint.owner_space = "LOCAL"

        for limit in ["min", "max"]:
            for axis in ["x", "y", "z"]:
                self._match_constraint_settings(
                    old_loc_constraint, new_loc_constraint, limit, axis
                )

    def _match_constraint_settings(
        self,
        old_loc_constraint: bpy.types.Constraint,
        new_loc_constraint: bpy.types.Constraint,
        limit: str,
        axis: str,
    ) -> None:
        """Matches the settings between two limit location constraints

        Args:
            old_loc_constraint (Constraint): Constraint on old rig
            new_loc_constraint (Constraint): Constraint on new rigify rig
            limit (str): Min or max location to limiat
            axis (str): Axis to limit locaiton on
        """
        if getattr(old_loc_constraint, f"use_{limit}_{axis}"):
            setattr(new_loc_constraint, f"use_{limit}_{axis}", True)
            setattr(
                new_loc_constraint,
                f"{limit}_{axis}",
                getattr(old_loc_constraint, f"{limit}_{axis}"),
            )
