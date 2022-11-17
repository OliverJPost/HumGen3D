from typing import Optional

from HumGen3D.user_interface.panel_functions import lines_from_text


class Operator:
    pass


class URLOperator(Operator):
    bl_idname = "wm.url_open"
    icon = "URL"
    parameter_name = "url"

    def __init__(self, text, url):
        self.parameter_value = url
        self.text = text


class VideoURLOperator(URLOperator):
    def __init__(self, text, url):
        super().__init__(text, url)
        self.icon = "FILE_MOVIE"


class TutorialOperator(Operator):
    bl_idname = "hg3d.draw_tutorial"
    icon = "WINDOW"
    parameter_name = "tutorial_name"

    def __init__(self, text, tutorial_name):
        self.parameter_value = tutorial_name
        self.text = text


class Tip:
    def __init__(
        self,
        title: str,
        text: str,
        icon: str = "HELP",
        operator: Optional[Operator] = None,
    ) -> None:
        self.title = title
        self.text = text
        self.icon = icon
        self.operator = operator

    @property
    def text_wrapped(self) -> str:
        lines = [
            " ".join(l) for l in lines_from_text(self.text, 100) if l != "WHITESPACE"
        ]
        return "\n".join(lines)
