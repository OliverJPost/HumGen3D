import bpy
from bpy.types import Material, Object

class BakingSettings:
    def __init__(self, _human):
        self._human = _human
        self.resolution_body =
        self.resolution_eyes =
        self.resolution_clothing =
        self.file_extension = ".PNG"
        self.export_path =

    def bake_all(self):
        pass

    def bake_texture(self, object: Object, material: Material, texture_type: str, override_resolution=None):

        solidify_is_visible = self._get_solidify_visibility(object)
        if solidify_is_visible:
            self._hide_set_solidify(object, True)

        human_name = self._human.name

        img_name = f"{human_name}_{material.name}_{texture_type}"

        if override_resolution:
            resolution = override_resolution
        elif object == self._human.body_obj:
            resolution = self.resolution_body
        elif object == self._human.eyes.eye_obj:
            resolution = self.resolution_eyes
        else:
            resolution = self.resolution_clothing

        img = bpy.data.images.new(
            img_name, width=resolution, height=resolution
        )

        nodes = material.node_tree.nodes
        links = material.node_tree.links

        principled = next(n for n in nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
        mat_output = next(n for n in nodes if n.bl_idname == "ShaderNodeOutputMaterial")

        emit_node = nodes.new("ShaderNodeEmission")

        if texture_type == "Normal":
            links.new(principled.outputs[0], mat_output.inputs[0])
        else:
            source_socket = self._follow_links(principled, texture_type)
            if not source_socket:
                raise HumGenException("Can't find node", bake_type)
            links.new(source_socket, emit_node.inputs[0])
            links.new(emit_node.outputs[0], mat_output.inputs[0])


    def _get_solidify_visibility(self, object: Object) -> bool:
        for mod in [m for m in object.modifiers if m.type == "SOLIDIFY"]:
            if any((mod.show_viewport, mod.show_render)):
                return True
        return False

    def _hide_set_solidify(self, object: Object, state: bool):
        for mod in [m for m in object.modifiers if m.type == "SOLIDIFY"]:
            mod.show_viewport = mod.show_render = state

    def _follow_links(self, node, texture_type):
        try:
            source_socket = next(
                node_links.from_socket
                for node_links in node.inputs[texture_type].links
            )
        except Exception:
            source_socket = None

        return source_socket