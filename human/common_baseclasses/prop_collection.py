# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements a class for replicating the functionality of bpy_prop_collections."""

import functools
from typing import Any, Callable, Iterable, TypeVar, Union, cast

from bpy.types import ID, bpy_prop_collection  # type:ignore
from HumGen3D.common.exceptions import HumGenException
from numpy import ndarray  # type:ignore

F = TypeVar("F", bound=Callable[..., Any])


def bpy_only(func: F) -> F:
    """Makes sure this method is only called on bpy_prop_collections."""  # noqa

    @functools.wraps(func)
    def wrapper_decorator(*args: Any, **kwargs: Any) -> Any:
        self = args[0]
        if not self.is_bpy:
            raise HumGenException(
                f"Cannot use {func.__name__} for non-bpy prop collection"
            )

        value = func(*args, **kwargs)
        return value

    return cast(F, wrapper_decorator)


class PropCollection:
    """Class for replicating functionality of bpy_prop_collection.

    This is used so substs of a prop collection can be used in the same way as the
    Blender built in prop collections. Some methods can only be used on the Blender
    prop collections, and will raise an exception if used on a custom prop collection.
    """

    def __init__(self, collection: Union[bpy_prop_collection, Iterable[ID]]) -> None:
        """Create a new PropCollection from either bpy_prop_collection or custom.

        Args:
            collection (Union[bpy_prop_collection, Iterable[ID]]): Collection to wrap.
                If it is a bpy_prop_collection, it will be wrapped as is. Otherwise
                it will replicate the functionality of a bpy_prop_collection.
        """
        self.is_bpy = isinstance(collection, bpy_prop_collection)
        self._collection = collection

    def find(self, item_name: str) -> int:
        """Find index of item in prop collection.

        Args:
            item_name (str): Name of item to find

        Returns:
            int: Index in list
        """
        if self.is_bpy:
            return self._collection.find(item_name)
        else:
            names = [item.name for item in self._collection]
            return names.index(item_name)

    def get(self, item_name: str, default: Any = None) -> Union[ID, Any]:  # noqa D
        if self.is_bpy:
            return self._collection.get(item_name, default)
        else:
            return next(
                (item for item in self._collection if item.name == item_name),
                None,
            )

    @bpy_only
    def foreach_get(self, attr: str, sequence: ndarray[Any, Any]) -> None:  # noqa D
        self._collection.foreach_get(attr, sequence)

    @bpy_only
    def foreach_set(self, attr: str, sequence: ndarray[Any, Any]) -> None:  # noqa D
        self._collection.foreach_set(attr, sequence)

    @bpy_only
    def items(self) -> list[Any]:  # noqa D
        return self._collection.items()

    @bpy_only
    def keys(self) -> list[Any]:  # noqa D
        return self._collection.keys()

    @bpy_only
    def values(self) -> list[Any]:  # noqa D
        return self._collection.values()

    @bpy_only
    def new(self, *items: Any) -> None:  # noqa D
        self._collection.new(*items)

    @bpy_only
    def remove(self, *items: str) -> None:  # noqa D
        self._collection.remove(*items)

    def __contains__(self, item: ID) -> bool:
        return item in self._collection  # type:ignore[operator]

    def __delitem__(self, item: ID) -> None:
        del self._collection[item]

    def __getitem__(self, item: str) -> ID:
        return cast(ID, self._collection[item])  # type:ignore[index]

    def __iter__(self) -> Iterable[ID]:
        yield from self._collection  # type:ignore[misc]

    def __len__(self) -> int:
        return len(self._collection)  # type:ignore[arg-type]

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._collection, attr)
