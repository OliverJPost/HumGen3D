import bpy
from HumGen3D.backend.preview_collections import refresh_pcoll
from HumGen3D.human.hair.basehair import ImportableHair


class FacialHairSettings(ImportableHair):
    def __init__(self, _human):
        if _human.gender == "female":
            raise NotImplementedError(
                "Facial hair is currently not implemented for female humans"
            )

        self._human = _human
        self._startswith = "ff_"

    def get_preset_options(self, context=None):
        if not context:
            context = bpy.context
        refresh_pcoll(self, context, "face_hair", hg_rig=self._human.rig_obj)

        return context.scene.HG3D["previews_list_face_hair"]
