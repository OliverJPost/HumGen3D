# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Drawing layer of the overlay: anti-aliased rounded shapes, images and text.

Everything is drawn with two small shaders built through
`GPUShaderCreateInfo`, so they run on OpenGL, Metal and Vulkan. Shapes are
signed-distance rounded rectangles, which gives smooth edges, borders and soft
shadows from one shader. Sizes are given in design units; `Canvas.px` scales
them by Blender's interface scale so the overlay looks the same on every
display.
"""
import os
from typing import Dict, List, Optional, Tuple

import blf
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

Color = Tuple[float, float, float, float]

FONT = 0  # Blender's interface font
# Titles and button labels: Inter SemiBold, the interface font one weight up.
# Characters it lacks (Chinese, Japanese, ...) come from Blender's fallback fonts.
BOLD_FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Inter-SemiBold.woff2")
_bold_font: Optional[int] = None


def bold_font() -> int:
    global _bold_font
    if _bold_font is None:
        loaded = blf.load(BOLD_FONT_PATH) if os.path.isfile(BOLD_FONT_PATH) else -1
        _bold_font = loaded if loaded != -1 else FONT
    return _bold_font

_UNIT_QUAD = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

# The viewport framebuffer is scene linear; the colours come from the theme in
# sRGB, like Blender's own interface shaders convert them.
_SDF = """
float hg_rounded_box(vec2 p, vec2 half_size, float r) {
    vec2 q = abs(p) - half_size + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}
vec3 hg_srgb_to_linear(vec3 c) {
    vec3 low = c / 12.92;
    vec3 high = pow((c + vec3(0.055)) / 1.055, vec3(2.4));
    return mix(low, high, step(vec3(0.04045), c));
}
"""

_shaders: Dict[str, gpu.types.GPUShader] = {}
_batches: Dict[str, gpu.types.GPUBatch] = {}


def _rect_shader() -> gpu.types.GPUShader:
    if "rect" not in _shaders:
        info = gpu.types.GPUShaderCreateInfo()
        info.push_constant("MAT4", "ModelViewProjectionMatrix")
        info.push_constant("VEC4", "rect")
        info.push_constant("VEC4", "color")
        info.push_constant("FLOAT", "radius")
        info.push_constant("FLOAT", "softness")
        info.push_constant("FLOAT", "pad")
        info.vertex_in(0, "VEC2", "pos")
        iface = gpu.types.GPUStageInterfaceInfo("hg_rect_iface")
        iface.smooth("VEC2", "frag_pos")
        info.vertex_out(iface)
        info.fragment_out(0, "VEC4", "fragColor")
        info.vertex_source(
            """
            void main() {
                vec2 p = rect.xy - vec2(pad) + pos * (rect.zw + vec2(2.0 * pad));
                frag_pos = p;
                gl_Position = ModelViewProjectionMatrix * vec4(p, 0.0, 1.0);
            }
            """
        )
        info.fragment_source(
            _SDF
            + """
            void main() {
                vec2 center = rect.xy + rect.zw * 0.5;
                float d = hg_rounded_box(frag_pos - center, rect.zw * 0.5, radius);
                float a = 1.0 - smoothstep(-softness, softness, d);
                fragColor = vec4(hg_srgb_to_linear(color.rgb), color.a * a);
            }
            """
        )
        _shaders["rect"] = gpu.shader.create_from_info(info)
        _batches["rect"] = batch_for_shader(_shaders["rect"], "TRIS", {"pos": _UNIT_QUAD})
    return _shaders["rect"]


def _image_shader() -> gpu.types.GPUShader:
    if "image" not in _shaders:
        info = gpu.types.GPUShaderCreateInfo()
        info.push_constant("MAT4", "ModelViewProjectionMatrix")
        info.push_constant("VEC4", "rect")
        info.push_constant("VEC4", "color")
        info.push_constant("FLOAT", "radius")
        info.push_constant("VEC4", "uv_rect")
        info.sampler(0, "FLOAT_2D", "image")
        info.vertex_in(0, "VEC2", "pos")
        iface = gpu.types.GPUStageInterfaceInfo("hg_image_iface")
        iface.smooth("VEC2", "frag_pos")
        iface.smooth("VEC2", "uv")
        info.vertex_out(iface)
        info.fragment_out(0, "VEC4", "fragColor")
        info.vertex_source(
            """
            void main() {
                vec2 p = rect.xy + pos * rect.zw;
                frag_pos = p;
                uv = uv_rect.xy + pos * uv_rect.zw;
                gl_Position = ModelViewProjectionMatrix * vec4(p, 0.0, 1.0);
            }
            """
        )
        info.fragment_source(
            _SDF
            + """
            void main() {
                vec2 center = rect.xy + rect.zw * 0.5;
                float d = hg_rounded_box(frag_pos - center, rect.zw * 0.5, radius);
                float a = 1.0 - smoothstep(-0.6, 0.6, d);
                vec4 c = texture(image, uv);
                fragColor = vec4(c.rgb * color.rgb, c.a * color.a * a);
            }
            """
        )
        _shaders["image"] = gpu.shader.create_from_info(info)
        _batches["image"] = batch_for_shader(_shaders["image"], "TRIS", {"pos": _UNIT_QUAD})
    return _shaders["image"]


def _mvp():
    return gpu.matrix.get_projection_matrix() @ gpu.matrix.get_model_view_matrix()


def hex_color(value: str, alpha: float = 1.0) -> Color:
    value = value.lstrip("#")
    return (int(value[0:2], 16) / 255, int(value[2:4], 16) / 255, int(value[4:6], 16) / 255, alpha)


class Palette:
    """The colours of humgen3d.com, the same in every Blender theme, like
    Blender's own splash screen."""

    def __init__(self, context: Optional[bpy.types.Context] = None) -> None:
        self.backdrop: Color = (0.0, 0.0, 0.0, 0.6)
        self.card: Color = hex_color("1b1b1d")
        self.inset: Color = hex_color("141416")  # fields and lists, a step below the card
        self.line: Color = hex_color("2a2a2e")  # dividers and container borders
        self.border: Color = hex_color("3a3a40")  # borders of fields and secondary buttons
        self.hover: Color = hex_color("232326")
        self.text: Color = hex_color("f3f2f0")
        self.muted: Color = hex_color("a6a6ad")
        self.faint: Color = hex_color("6c6c73")
        self.accent: Color = hex_color("8c4f70")
        self.accent_hover: Color = hex_color("9d5a7e")
        self.link: Color = hex_color("d4a5c1")
        self.on_accent: Color = (1.0, 1.0, 1.0, 1.0)
        self.success: Color = hex_color("6fbf8b")
        self.danger: Color = hex_color("e5736b")
        self.shadow: Color = (0.0, 0.0, 0.0, 0.45)

    @staticmethod
    def with_alpha(color: Color, alpha: float) -> Color:
        return (color[0], color[1], color[2], color[3] * alpha)


class Canvas:
    """Draws in region pixels. Sizes passed to the methods are design units."""

    def __init__(self, context: bpy.types.Context, alpha: float = 1.0) -> None:
        self.context = context
        self.scale = context.preferences.system.ui_scale
        self.alpha = alpha
        self.palette = Palette(context)
        self.width = context.region.width
        self.height = context.region.height

    def px(self, value: float) -> float:
        return value * self.scale

    def _fade(self, color: Color) -> Color:
        return (color[0], color[1], color[2], color[3] * self.alpha)

    # Shapes

    def rect(self, x: float, y: float, w: float, h: float, color: Color, radius: float = 0.0) -> None:
        if w <= 0 or h <= 0 or color[3] <= 0:
            return
        gpu.state.blend_set("ALPHA")  # blf resets the blend state
        shader = _rect_shader()
        shader.bind()
        shader.uniform_float("ModelViewProjectionMatrix", _mvp())
        shader.uniform_float("rect", (x, y, w, h))
        shader.uniform_float("color", self._fade(color))
        shader.uniform_float("radius", min(radius, w / 2, h / 2))
        shader.uniform_float("softness", 0.6)
        shader.uniform_float("pad", 1.0)
        _batches["rect"].draw(shader)

    def shadow(self, x: float, y: float, w: float, h: float, radius: float, blur: float, color: Color, offset_y: float = 0.0) -> None:
        gpu.state.blend_set("ALPHA")
        shader = _rect_shader()
        shader.bind()
        shader.uniform_float("ModelViewProjectionMatrix", _mvp())
        shader.uniform_float("rect", (x, y + offset_y, w, h))
        shader.uniform_float("color", self._fade(color))
        shader.uniform_float("radius", min(radius, w / 2, h / 2))
        shader.uniform_float("softness", blur)
        shader.uniform_float("pad", blur)
        _batches["rect"].draw(shader)

    def outline(self, x: float, y: float, w: float, h: float, color: Color, radius: float, thickness: float, inner: Color) -> None:
        self.rect(x, y, w, h, color, radius)
        self.rect(x + thickness, y + thickness, w - 2 * thickness, h - 2 * thickness, inner, max(radius - thickness, 0))

    def hline(self, x: float, y: float, w: float, color: Color) -> None:
        """A one-pixel divider, snapped to the pixel grid."""
        self.rect(round(x), round(y), w, max(1.0, round(self.scale)), color)

    def image(self, texture: gpu.types.GPUTexture, x: float, y: float, w: float, h: float, radius: float = 0.0, alpha: float = 1.0, cover: bool = True) -> None:
        """Draw a texture in a rounded rectangle, cropped to fill it (`cover`)."""
        gpu.state.blend_set("ALPHA")
        shader = _image_shader()
        shader.bind()
        shader.uniform_float("ModelViewProjectionMatrix", _mvp())
        shader.uniform_float("rect", (x, y, w, h))
        shader.uniform_float("color", (1.0, 1.0, 1.0, alpha * self.alpha))
        shader.uniform_float("radius", min(radius, w / 2, h / 2))
        uv = (0.0, 0.0, 1.0, 1.0)
        if cover and texture.width and texture.height:
            image_aspect = texture.width / texture.height
            box_aspect = w / h
            if image_aspect > box_aspect:
                span = box_aspect / image_aspect
                uv = ((1 - span) / 2, 0.0, span, 1.0)
            else:
                span = image_aspect / box_aspect
                uv = (0.0, (1 - span) / 2, 1.0, span)
        shader.uniform_float("uv_rect", uv)
        shader.uniform_sampler("image", texture)
        _batches["image"].draw(shader)

    def clip(self, x: float, y: float, w: float, h: float) -> None:
        """Clip what is drawn next to a rectangle, until `unclip`."""
        gpu.state.scissor_test_set(True)
        gpu.state.scissor_set(int(x), int(y), int(max(w, 0)), int(max(h, 0)))

    def unclip(self) -> None:
        gpu.state.scissor_test_set(False)

    # Text

    def _font(self, size: float, bold: bool = False) -> int:
        font = bold_font() if bold else FONT
        blf.size(font, self.px(size))
        return font

    def text_width(self, text: str, size: float, bold: bool = False) -> float:
        font = self._font(size, bold)
        return blf.dimensions(font, text)[0]

    def text(self, text: str, x: float, y: float, size: float, color: Color, align: str = "LEFT", bold: bool = False) -> float:
        """Draw one line with its baseline at `y`. Returns the width in pixels."""
        font = self._font(size, bold)
        width = blf.dimensions(font, text)[0]
        if align == "CENTER":
            x -= width / 2
        elif align == "RIGHT":
            x -= width
        blf.position(font, round(x), round(y), 0)
        blf.color(font, *self._fade(color))
        blf.draw(font, text)
        return width

    def ellipsize(self, text: str, size: float, max_width: float, bold: bool = False) -> str:
        if self.text_width(text, size, bold) <= max_width:
            return text
        while text and self.text_width(text + "…", size, bold) > max_width:
            text = text[:-1]
        return text + "…"

    def wrap(self, text: str, size: float, max_width: float, bold: bool = False) -> List[str]:
        font = self._font(size, bold)
        lines: List[str] = []
        for paragraph in text.split("\n"):
            line = ""
            for word in paragraph.split(" "):
                candidate = word if not line else line + " " + word
                if blf.dimensions(font, candidate)[0] <= max_width or not line:
                    line = candidate
                else:
                    lines.append(line)
                    line = word
            lines.append(line)
        return lines

    def paragraph(self, text: str, x: float, top: float, size: float, color: Color, max_width: float, leading: float = 1.45, align: str = "LEFT", bold: bool = False) -> float:
        """Draw wrapped text below `top`. Returns the height used, in pixels."""
        line_height = self.px(size) * leading
        y = top - self.px(size)
        for line in self.wrap(text, size, max_width, bold):
            self.text(line, x, y, size, color, align, bold)
            y -= line_height
        return top - y - line_height


class TextureCache:
    """Images loaded for the overlay, released when it closes."""

    def __init__(self) -> None:
        self._textures: Dict[str, gpu.types.GPUTexture] = {}
        self._images: List[bpy.types.Image] = []

    def get(self, path: str) -> Optional[gpu.types.GPUTexture]:
        if path in self._textures:
            return self._textures[path]
        if not os.path.isfile(path):
            return None
        image = bpy.data.images.load(path, check_existing=False)
        image.name = "HG_overlay_" + os.path.basename(path)
        try:
            texture = gpu.texture.from_image(image)
        except Exception:  # noqa: BLE001
            bpy.data.images.remove(image)
            return None
        self._images.append(image)
        self._textures[path] = texture
        return texture

    def release(self) -> None:
        self._textures.clear()
        for image in self._images:
            try:
                bpy.data.images.remove(image)
            except Exception:  # noqa: BLE001
                pass
        self._images.clear()


def ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
