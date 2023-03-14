from enum import Enum
from typing import Optional

import bpy


class TabState(str, Enum):
    CREATE = "CREATE"
    BATCH = "BATCH"
    CONTENT = "CONTENT"
    PROCESS = "PROCESS"

    def section_from_context(self, context: bpy.types.Context):
        if self == self.CREATE:
            return CreateSectionState.from_prop(context.scene.HG3D.ui.active_section)
        # todo content
        else:
            return None

    def update_tips(self, context: bpy.types.Context):
        # todo
        pass


class SectionState(str, Enum):
    def subsection_from_context(self, context: bpy.types.Context):
        return None


class CreateSectionState(SectionState):
    CLOSED = "closed"
    BODY = "body"
    FACE = "face"
    AGE = "age"
    HEIGHT = "height"
    SKIN = "skin"
    HAIR = "hair"
    CLOTHING = "clothing"
    POSE = "pose"
    EXPRESSION = "expression"

    @classmethod
    def from_prop(cls, prop: str):
        return cls(prop) if prop in cls.__members__ else cls.CLOSED

    def subsection_from_context(self, context: bpy.types.Context):
        if self == self.HAIR:
            return context.scene.HG3D.ui.hair_ui_tab
        elif self == self.CLOTHING:
            return context.scene.HG3D.ui.clothing_tab
        elif self == self.POSE:
            return context.scene.HG3D.ui.pose_tab_switch
        elif self == self.EXPRESSION:
            return context.scene.HG3D.ui.expression_type
        else:
            return None


class UserInterfaceState:
    active_tab: TabState
    active_section: Optional[SectionState]
    active_subsection: Optional[str]

    def __init__(self, context: bpy.types.Context):
        self.update(context)

    def update(self, context: bpy.types.Context):
        self.active_tab = TabState(context.scene.HG3D.ui.active_tab)
        self.active_section = self.active_tab.section_from_context(context)
        self.active_subsection = self.active_section.subsection_from_context(context)
