from HumGen3D.human.hair.basehair import ImportableHair


class RegularHairSettings(ImportableHair):
    def __init__(self, _human):
        self._human = _human
        self._notstartswith = ("Eye", "ff_")
