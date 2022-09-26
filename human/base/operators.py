import random
from calendar import c

import bpy
from HumGen3D.backend import get_prefs, refresh_pcoll
from HumGen3D.user_interface.documentation.info_popups import HG_OT_INFO
from HumGen3D.user_interface.documentation.tips_suggestions_ui import (
    update_tips_from_context,
)

from ..human import Human


class HG_RANDOM_CHOICE(bpy.types.Operator):
    """Picks a random item to be active in this preview collection. For all pcolls
    except "humans" it will also load the item onto the humna.
    """

    bl_idname = "hg3d.random_choice"
    bl_label = "Random Choice"
    bl_description = "Pick a random choice for this category"
    bl_options = {"UNDO", "INTERNAL"}

    pcoll_name: bpy.props.StringProperty()

    def execute(self, context):
        random_type = self.random_type
        sett = context.scene.HG3D
        human = Human.from_existing(context.active_object, strict_check=False)

        if random_type in (
            "poses",
            "expressions",
            "outfits",
            "patterns",
            "footwear",
            "hair",
        ):
            getattr(human, random_type).set_random(update_ui=True)
        elif random_type == "humans":
            sett.gender = random.choice(["male", "female"])
            current = sett.pcoll.humans
            options = human.get_preset_options(sett.gender, context)
            chosen = random.choice([o for o in options if o != current])
            sett.pcoll.humans = chosen

        return {"FINISHED"}


class HG_RANDOM_VALUE(bpy.types.Operator):
    """randomizes this specific property"""

    bl_idname = "hg3d.random_value"
    bl_label = "Randomize"
    bl_description = "Randomize this value"
    bl_options = {"UNDO", "INTERNAL"}

    random_type: bpy.props.StringProperty()

    def execute(self, context):
        random_type = self.random_type
        human = Human.from_existing(context.active_object, strict_check=False)

        if random_type.startswith("face"):
            # facial subcategories follow the pattern face_{category}
            ff_subcateg = random_type[5:]
            # where face_all does all facial features
            human.face.randomize(ff_subcateg)
        else:
            getattr(human, random_type).randomize()
        return {"FINISHED"}


class HG_TOGGLE_HAIR_CHILDREN(bpy.types.Operator):
    """Turn hair children to 1 or back to render amount"""

    bl_idname = "hg3d.togglechildren"
    bl_label = "Toggle hair children"
    bl_description = "Toggle between hidden and visible hair children"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        human = Human.from_existing(context.object)
        current_state = human.hair.children_ishidden
        human.hair.children_set_hide(not current_state)

        return {"FINISHED"}
