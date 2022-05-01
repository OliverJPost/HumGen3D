from HumGen3D.human.hair.basehair import ImportableHair

from HumGen3D.backend.preview_collections import refresh_pcoll
import bpy


class RegularHairSettings(ImportableHair):
    def __init__(self, _human):
        self._human = _human
        self._notstartswith = ("Eye", "ff_")

    def get_preset_options(self, context=None):
        if not context:
            context = bpy.context
        refresh_pcoll(self, context, "hair", hg_rig=self._human.rig_obj)

        return context.scene.HG3D["previews_list_hair"]
