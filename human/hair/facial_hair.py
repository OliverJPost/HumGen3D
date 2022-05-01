

from HumGen3D.human.hair.basehair import ImportableHair


class FacialHairSettings(ImportableHair):
    def __init__(self, _human):
        if _human.gender == 'female':
            raise NotImplementedError("Facial hair is currently not implemented for female humans")

        self._human = _human
        self._startswith = "ff_"