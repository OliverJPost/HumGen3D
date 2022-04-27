import bpy
from ...old.blender_operators.common.random import set_random_active_in_pcoll
from ...old.blender_operators.creation_phase.material import (
    randomize_iris_color,
    randomize_skin_shader,
)
from ...old.blender_operators.common.common_functions import find_human
from ..human import Human


class HG_RANDOM(bpy.types.Operator):
    """randomizes this specific property, may it be a slider or a pcoll

    API: True

    Operator type:
        Prop setter
        Pcoll manipulation

    Prereq:
        Passed random_type
        Active object is part of HumGen human

    Args:
        random_type (str): internal name of property to randomize
    """

    bl_idname = "hg3d.random"
    bl_label = "Redraw Random"
    bl_description = "Randomize this property"
    bl_options = {"UNDO", "INTERNAL"}

    random_type: bpy.props.StringProperty()

    def execute(self, context):
        random_type = self.random_type
        sett = context.scene.HG3D
        hg_rig = find_human(context.active_object)
        human = Human.from_existing(context.active_object)

        if random_type == "body_type":
            human.creation_phase.body.randomize()
        elif random_type in (
            "poses",
            "expressions",
            "outfit",
            "patterns",
            "footwear",
            "hair",
        ):
            set_random_active_in_pcoll(context, sett, random_type)
        elif random_type == "skin":
            randomize_skin_shader(hg_rig.HG.body_obj, hg_rig.HG.gender)
        elif random_type.startswith("face"):
            ff_subcateg = random_type[
                5:
            ]  # facial subcategories follow the pattern face_{category}
            # where face_all does all facial features
            human.creation_phase.face.randomize(ff_subcateg)
        elif random_type == "iris_color":
            randomize_iris_color(hg_rig)

        return {"FINISHED"}


class HG_TOGGLE_HAIR_CHILDREN(bpy.types.Operator):
    """Turn hair children to 1 or back to render amount

    Operator type:
        Particle system

    Prereq:
        Active object is part of HumGen human
    """

    bl_idname = "hg3d.togglechildren"
    bl_label = "Toggle hair children"
    bl_description = "Toggle between hidden and visible hair children"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        human = Human.from_existing(context.object)
        current_state = human.hair.children_ishidden
        human.hair.set_children_hide_state(not current_state)

        return {"FINISHED"}
