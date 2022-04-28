from HumGen3D.backend.memory_management import hg_delete
from bpy.types import Context

import bpy
from HumGen3D.human.base.collections import add_to_collection
from .expression.expression import ExpressionSettings

from .pose.pose import PoseSettings
from .clothing.footwear import FootwearSettings
from .clothing.outfit import OutfitSettings


class FinalizePhaseSettings:
    def __init__(self, human):
        self._human = human

    @property
    def pose(self) -> PoseSettings:
        if not hasattr(self, "_pose"):
            self._pose = PoseSettings(self._human)
        return self._pose

    @property
    def outfit(self) -> OutfitSettings:
        if not hasattr(self, "_outfit"):
            self._outfit = OutfitSettings(self._human)
        return self._outfit

    @property
    def footwear(self) -> FootwearSettings:
        if not hasattr(self, "_footwear"):
            self._footwear = FootwearSettings(self._human)
        return self._footwear

    @property
    def expression(self) -> ExpressionSettings:
        if not hasattr(self, "_expression"):
            self._expression = ExpressionSettings(self._human)
        return self._expression

    def revert(self, context: Context = None) -> None:
        if not context:
            context = bpy.context

        # remove current human, including all children of the current human
        for obj in self.objects:
            hg_delete(obj)

        # backup human: rename, make visible, add to collection
        self.backup_rig.name = self.backup_rig.name.replace("_Backup", "")
        self.backup_rig.hide_viewport = False
        self.backup_rig.hide_render = False
        add_to_collection(context, self.backup_rig)

        # backup children: set correct body_obj property, add to collection, make visible
        hg_body = None
        for child in self.backup_rig.children:
            if "hg_body" in child:
                self.backup_rig.HG.body_obj = child
                hg_body = child
            add_to_collection(context, child)
            child.hide_viewport = False
            child.hide_render = False

        # point constraints to the correct rig
        p_bones = self.backup_rig.pose.bones
        for bone in [p_bones["jaw"], p_bones["jaw_upper"]]:
            child_constraints = [
                c
                for c in bone.constraints
                if c.type == "CHILD_OF" or c.type == "DAMPED_TRACK"
            ]
            for c in child_constraints:
                c.target = hg_body

        context.view_layer.objects.active = self.backup_rig
