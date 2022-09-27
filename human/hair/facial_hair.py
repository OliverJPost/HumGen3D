import bpy
from HumGen3D.backend import preview_collections
from HumGen3D.human.base.decorators import injected_context
from HumGen3D.human.hair.basehair import ImportableHair


class FacialHairSettings(ImportableHair):
    _pcoll_name = "face_hair"
    _pcoll_gender_split = False

    def __init__(self, _human):
        if _human.gender == "female":
            raise NotImplementedError(
                "Facial hair is currently not implemented for female humans"
            )

        self._human = _human
        self._startswith = "ff_"
        self._pcoll_name = "facial_hair"
        self._pcoll_gender_split = False
