import bpy
from bpy.props import BoolProperty

TAG = "Lock Category"
DESCRIPTION = "Locks this category from being randomized by the Random button"


def get_prop():
    return BoolProperty(name=TAG, description=DESCRIPTION, default=False)


class RandomizeLockProps(bpy.types.PropertyGroup):
    _register_priority = 3

    l_skull: get_prop()
    jaw: get_prop()
    u_skull: get_prop()
    eyes: get_prop()
    ears: get_prop()
    nose: get_prop()
    mouth: get_prop()
    cheeks: get_prop()
    chin: get_prop()
    custom: get_prop()

    Torso: get_prop()
    Arms: get_prop()
    Legs: get_prop()
    Muscles: get_prop()
    Head: get_prop()
