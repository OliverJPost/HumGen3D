import json
import random

from HumGen3D.backend.memory_management import hg_delete
import bpy
from HumGen3D.backend.preview_collections import set_random_active_in_pcoll
from HumGen3D.human.human import Human

from .base_clothing import find_masks


class HG_BACK_TO_HUMAN(bpy.types.Operator):
    """Makes the rig the active object, changing the ui back to the default state

    API: False

    Operator type:
        Selection
        HumGen UI manipulation

    Prereq:
        Cloth object was active
    """

    bl_idname = "hg3d.backhuman"
    bl_label = "Back to Human"
    bl_description = "Makes the human the active object"

    def execute(self, context):
        hg_rig = Human.from_existing(context.object).rig_obj
        context.view_layer.objects.active = hg_rig
        return {"FINISHED"}


class HG_DELETE_CLOTH(bpy.types.Operator):
    """Deletes the selected cloth object, also removes any mask modifiers this
    cloth was using

    Operator type:
        Object deletion

    Prereq:
        Active object is a HumGen clothing object
    """

    bl_idname = "hg3d.deletecloth"
    bl_label = "Delete cloth"
    bl_description = "Deletes this clothing object"

    def execute(self, context):
        hg_rig = Human.from_existing(context.object).rig_obj
        hg_body = hg_rig.HG.body_obj

        cloth_obj = context.object
        remove_masks = find_masks(cloth_obj)
        hg_delete(cloth_obj)

        remove_mods = [
            mod
            for mod in hg_body.modifiers
            if mod.type == "MASK" and mod.name in remove_masks
        ]

        for mod in remove_mods:
            hg_body.modifiers.remove(mod)

        context.view_layer.objects.active = hg_rig
        return {"FINISHED"}


class HG_OT_PATTERN(bpy.types.Operator):
    """
    Adds a pattern to the selected cloth material, adding the necessary nodes. Also used for removing the pattern
    """

    bl_idname = "hg3d.pattern"
    bl_label = "Cloth Pattern"
    bl_description = "Toggles pattern on and off"

    add: bpy.props.BoolProperty()  # True means the pattern is added, False means the pattern will be removed

    def execute(self, context):
        obj = context.object

        human = Human.from_existing(obj)

        if self.add:
            human.finalize_phase.outfit.pattern.set_random(obj, context)
        else:
            human.finalize_phase.outfit.pattern.remove(obj)

        return {"FINISHED"}


class HG_COLOR_RANDOM(bpy.types.Operator):
    """
    Sets the color slot to a random color from the color dicts from HG_COLORS

    Operator type:
        Material

    Prereq:
        Passed arguments
        Active material of active object is a HumGen clothing material

    Args:
        input_name (str): Name of HG_Control node input to randomize the color for
        color_group (str):  Name of the color groups stored in HG_COLOR to pick
            colors from
    """

    bl_idname = "hg3d.color_random"
    bl_label = "Random Color"
    bl_description = "Randomize this property"
    bl_options = {"UNDO", "INTERNAL"}

    input_name: bpy.props.StringProperty()
    color_group: bpy.props.StringProperty()

    def execute(self, context):
        colorgroups_json = "colorgroups.json"
        with open(colorgroups_json) as f:
            color_dict = json.load(f)

        color_hex = random.choice(color_dict[self.color_group])
        color_rgba = self._hex_to_rgba(color_hex)

        nodes = context.object.active_material.node_tree.nodes
        input_socket = nodes["HG_Control"].inputs[self.input_name]

        input_socket.default_value = tuple(color_rgba)

        return {"FINISHED"}

    def _hex_to_rgba(self, color_hex) -> "tuple[float, float, float, 1]":
        """Build rgb color from this hex code

        Args:
            color_hex (str): Hexadecimal color code, withhout # in front

        Returns:
            tuple[float, float, float, 1]: rgba color
        """
        color_rgb = [int(color_hex[i : i + 2], 16) for i in (0, 2, 4)]
        float_color_rgb = [x / 255.0 for x in color_rgb]
        float_color_rgb.append(1)

        return float_color_rgb
