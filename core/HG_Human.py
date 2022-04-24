from typing import List, Union

import bpy
from bpy.types import FloatVectorProperty, Object


class Human:
    rig_obj: Object

    creation_phase: CreationPhaseSettings
    finalize_phase: FinalizePhaseSettings
    phase: Union[CreationPhaseSettings, FinalizePhaseSettings]
    hair: HairSettings
    skin: SkinSettings
    teeth: TeethSettings
    eyes: EyeSettings

    def __init__(self, existing_human: Object = None):
        self.rig_obj = existing_human

    def __repr__(self):
        pass  # TODO

    @property
    def gender(self) -> str:
        """Gender of this human in ("male", "female")"""
        return self.rig_obj.HG.gender

    @property
    def name(self) -> str:
        pass  # TODO

    @name.setter
    def name(self, name: str):
        pass  # TODO

    @property
    def location(self) -> FloatVectorProperty:
        pass  # TODO

    @location.setter
    def location(self, location: FloatVectorProperty):
        pass  # TODO

    @property
    def rotation(self) -> FloatVectorProperty:
        pass  # TODO

    @rotation.setter
    def rotation(self, location: FloatVectorProperty):
        pass  # TODO

    def objects(self) -> List[Object]:
        pass  # TODO

    def delete(self) -> None:
        pass  # TODO

    def finish_creation_phase(self) -> None:
        pass  # TODO

    def revert_to_creation_phase(self) -> None:
        pass  # TODO
