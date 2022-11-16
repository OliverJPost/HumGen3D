"""Implements class for accessing objects human exists of."""

from typing import Any, Iterable, Optional, Union, cast

from bpy.types import ID, Object  # type:ignore


class ObjectCollection:
    """Access to objects human exists of with properties for specific ones."""

    def __init__(self, rig_obj: Object) -> None:
        self._collection = list(rig_obj.children) + [rig_obj]
        self._rig_obj = rig_obj

    @property
    def rig(self) -> Object:
        """Returns the human body armature/rig object.

        This is the object almost all custom properties are stored on.

        Returns:
            Object: The human armature/rig Blender object
        """
        return self._rig_obj

    @property
    def body(self) -> Object:
        """Returns the human body Blender object.

        Returns:
            Object: The human body Blender object
        """
        return cast(Object, self._rig_obj.HG.body_obj)

    @property
    def eyes(self) -> Object:
        """Returns the eye Blender object.

        Returns:
            Object: The eye Blender object
        """
        return next(
            child for child in self if "hg_eyes" in child  # type:ignore[operator]
        )

    @property
    def lower_teeth(self) -> Object:
        """Returns the lower teeth Blender object.

        Returns:
            Object: The lower teeth Blender object
        """
        lower_teeth = next(
            obj
            for obj in self
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
            for obj in self
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
        return next((c for c in self if "hg_haircard" in c), None)

    def get(self, item_name: str, default: Any = None) -> Union[ID, Any]:  # noqa D
        if self.is_bpy:
            return self._collection.get(item_name, default)
        else:
            return next(
                (item for item in self._collection if item.name == item_name),
                None,
            )

    def __contains__(self, item: ID) -> bool:
        return item in self._collection  # type:ignore[operator]

    def __getitem__(self, item: str) -> ID:
        return cast(ID, self._collection[item])  # type:ignore[index, call-overload]

    def __iter__(self) -> Iterable[ID]:
        yield from self._collection  # type:ignore[misc]

    def __len__(self) -> int:
        return len(self._collection)  # type:ignore[arg-type]
