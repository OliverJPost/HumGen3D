import bpy
from HumGen3D.backend import refresh_pcoll
from HumGen3D.human.hair.basehair import ImportableHair

from HumGen3D.human.base.decorators import injected_context


class FacialHairSettings(ImportableHair):
    def __init__(self, _human):
        if _human.gender == "female":
            raise NotImplementedError(
                "Facial hair is currently not implemented for female humans"
            )

        self._human = _human
        self._startswith = "ff_"
        self._pcoll_name = "facial_hair"
        self._pcoll_gender_split = False

    @injected_context
    def get_preset_options(self, context=None):
        refresh_pcoll(self, context, "face_hair", hg_rig=self._human.rig_obj)

        return context.scene.HG3D["previews_list_face_hair"]
