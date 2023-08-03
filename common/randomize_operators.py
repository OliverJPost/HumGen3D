# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Contains Blender operators for randomizing within pcolls and slider values."""

import random

import bpy

from ..human.human import Human


class HG_RANDOM_CHOICE(bpy.types.Operator):
    """Picks a random item to be active in this preview collection.

    For all pcolls except "humans" it will also load the item onto the human.
    """

    bl_idname = "hg3d.random_choice"
    bl_label = "Random Choice"
    bl_description = "Pick a random choice for this category"
    bl_options = {"UNDO", "INTERNAL"}

    pcoll_name: bpy.props.StringProperty()

    def execute(self, context):
        pcoll_name = self.pcoll_name
        sett = context.scene.HG3D  # type:ignore[attr-defined]
        human = Human.from_existing(context.active_object, strict_check=False)

        if pcoll_name in (
            "pose",
            "expression",
            "hair",
        ):
            getattr(human, pcoll_name).set_random(update_ui=True)
        elif pcoll_name in ("outfit", "footwear"):
            getattr(human.clothing, pcoll_name).set_random(
                update_ui=True, context=context
            )
        elif pcoll_name == "humans":
            current = sett.pcoll.humans
            options = Human.get_preset_options(sett.gender, context=context)
            chosen = random.choice([o for o in options if o != current])
            sett.pcoll.humans = chosen
        elif pcoll_name == "pattern":
            human.clothing.outfit.pattern.set_random(context.object, context=context)
        return {"FINISHED"}


class HG_RESET_VALUES(bpy.types.Operator):
    """randomizes this specific property."""

    bl_idname = "hg3d.reset_values"
    bl_label = "Reset"
    bl_description = "Reset values"
    bl_options = {"UNDO", "INTERNAL"}

    categ: bpy.props.StringProperty()

    def execute(self, context):
        human = Human.from_existing(context.active_object, strict_check=False)
        getattr(human, self.categ).reset_values()
        return {"FINISHED"}


class HG_RANDOM_VALUE(bpy.types.Operator):
    """randomizes this specific property."""

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
            human.face.randomize(ff_subcateg, use_bell_curve=True, use_locks=True)
        elif random_type.startswith("body_"):
            subcategory = random_type[5:]
            human.body.randomize(category=subcategory, use_locks=True)
        else:
            try:
                getattr(human, random_type).randomize(use_locks=True)
            except TypeError:
                getattr(human, random_type).randomize()
        return {"FINISHED"}
