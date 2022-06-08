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
        mat = context.object.active_material
        self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links

        # finds the nodes, adding them if they don't exist
        img_node = self._create_node_if_doesnt_exist("HG_Pattern")
        mapping_node = self._create_node_if_doesnt_exist("HG_Pattern_Mapping")
        coord_node = self._create_node_if_doesnt_exist(
            "HG_Pattern_Coordinates"
        )

        # deletes the nodes
        if not self.add:
            mat.node_tree.nodes.remove(img_node)
            mat.node_tree.nodes.remove(mapping_node)
            mat.node_tree.nodes.remove(coord_node)
            self.nodes["HG_Control"].inputs["Pattern"].default_value = (
                0,
                0,
                0,
                1,
            )
            return {"FINISHED"}

        set_random_active_in_pcoll(context, context.scene.HG3D, "patterns")
        return {"FINISHED"}

    def _create_node_if_doesnt_exist(self, name) -> bpy.types.ShaderNode:
        """Returns the node, creating it if it doesn't exist

        Args:
            name (str): name of node to check

        Return
            node (ShaderNode): node that was being searched for
        """
        # try to find the node, returns it if it already exists
        for node in self.nodes:
            if node.name == name:
                return node

        # adds the node, because it doesn't exist yet
        type_dict = {
            "HG_Pattern": "ShaderNodeTexImage",
            "HG_Pattern_Mapping": "ShaderNodeMapping",
            "HG_Pattern_Coordinates": "ShaderNodeTexCoord",
        }

        node = self.nodes.new(type_dict[name])
        node.name = name

        link_dict = {
            "HG_Pattern": (0, "HG_Control", 9),
            "HG_Pattern_Mapping": (0, "HG_Pattern", 0),
            "HG_Pattern_Coordinates": (2, "HG_Pattern_Mapping", 0),
        }
        target_node = self.nodes[link_dict[name][1]]
        self.links.new(
            node.outputs[link_dict[name][0]],
            target_node.inputs[link_dict[name][2]],
        )

        return node

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