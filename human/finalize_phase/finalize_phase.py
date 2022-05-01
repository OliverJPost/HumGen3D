import bpy
from bpy.types import Context
from HumGen3D.backend.memory_management import hg_delete
from HumGen3D.human.base.collections import add_to_collection

from .clothing.footwear import FootwearSettings
from .clothing.outfit import OutfitSettings
from .expression.expression import ExpressionSettings
from .pose.pose import PoseSettings


class FinalizePhaseSettings:
    def __init__(self, human):
        self._human = human

    @property
    def backup_rig(self):
        return self._human.props.backup

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

        backup_rig = self.backup_rig
        assert backup_rig
        # remove current human, including all children of the current human
        for obj in self._human.objects:
            hg_delete(obj)

        # backup human: rename, make visible, add to collection
        self._human.rig_obj = backup_rig
        hg_rig = self._human.rig_obj
        hg_rig.name = hg_rig.name.replace("_Backup", "")
        self._human.hide_set(False)
        add_to_collection(context, hg_rig)

        # backup children: set correct body_obj property, add to collection, make visible
        hg_body = None
        for child in hg_rig.children:
            if "hg_body" in child:
                hg_rig.HG.body_obj = child
                hg_body = child
            add_to_collection(context, child)
            child.hide_viewport = False
            child.hide_render = False

        # point constraints to the correct rig
        p_bones = hg_rig.pose.bones
        for bone in [p_bones["jaw"], p_bones["jaw_upper"]]:
            child_constraints = [
                c
                for c in bone.constraints
                if c.type == "CHILD_OF" or c.type == "DAMPED_TRACK"
            ]
            for c in child_constraints:
                c.target = hg_body

        context.view_layer.objects.active = hg_rig
