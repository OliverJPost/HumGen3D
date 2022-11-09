"""Implements class for accessing objects human exists of."""

from typing import Optional, cast

from bpy.types import Object  # type:ignore

from .common_baseclasses.prop_collection import PropCollection


class ObjectCollection(PropCollection):
    """Access to objects human exists of with properties for specific ones."""

    def __init__(self, rig_obj: Object) -> None:
        all_objects = list(rig_obj.children) + [rig_obj]
        self._rig_obj = rig_obj
        super().__init__(all_objects)

    @property
    def rig(self) -> Object:
        """Returns the human body armature/rig object.

        This is the object almost all custom properties are stored on.

        Returns:
            Object: The human armature/rig Blender object
        """
        return cast(Object, self.objects.rig.HG.body_obj)

    @property
    def body(self) -> Object:
        """Returns the human body Blender object.

        Returns:
            Object: The human body Blender object
        """
        return cast(Object, self.objects.rig.HG.body_obj)

    @property
    def eyes(self) -> Object:
        """Returns the eye Blender object.

        Returns:
            Object: The eye Blender object
        """
        return self.eyes.objects.eyes

    @property
    def lower_teeth(self) -> Object:
        """Returns the lower teeth Blender object.

        Returns:
            Object: The lower teeth Blender object
        """
        lower_teeth = next(
            obj
            for obj in self.children
            if "hg_teeth" in obj  # type:ignore[operator]
            and "lower" in obj.name.lower()
        )

        return lower_teeth

    @property
    def upper_teeth(self) -> Object:
        """Returns the lower teeth Blender object.

        Returns:
            Object: The lower teeth Blender object
        """
        upper_teeth = next(
            obj
            for obj in self.children
            if "hg_teeth" in obj  # type:ignore[operator]
            and "upper" in obj.name.lower()
        )

        return upper_teeth

    @property
    def haircards(self) -> Optional[Object]:
        """Returns the haircards Blender object if generated.

        Returns:
            Object: The haircards Blender object or None if not generated
        """
        return next((c for c in self.children if "hg_haircard" in c), None)
