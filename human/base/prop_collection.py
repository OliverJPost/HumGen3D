import functools

from bpy.types import bpy_prop_collection
from HumGen3D.human.base.exceptions import HumGenException


def bpy_only(func):
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        self = args[0]
        if not self.is_bpy:
            raise HumGenException(
                f"Cannot use {func.__name__} for non-bpy prop collection"
            )

        value = func(*args, **kwargs)
        return value

    return wrapper_decorator


class PropCollection:
    def __init__(self, collection):
        self.is_bpy = isinstance(collection, bpy_prop_collection)
        self._collection = collection

    def __contains__(self, item):
        return item in self._collection

    def __delitem__(self, item):
        del self._collection[item]

    def __getitem__(self, item):
        print(f"checking if {item} in {self._collection}")
        return self._collection[item]

    def __iter__(self):
        yield from self._collection

    def __len__(self):
        return len(self._collection)

    def find(self, item_name):
        if self.is_bpy:
            return self._collection.find(item_name)
        else:
            names = [item.name for item in self._collection]
            return names.index(item_name)

    def get(self, item_name, default=None):
        if self.is_bpy:
            return self._collection.get(item_name, default)
        else:
            return next(
                (item for item in self._collection if item.name == item_name),
                None,
            )

    def __getattr__(self, attr):
        return getattr(self._collection, attr)

    @bpy_only
    def foreach_get(self, attr, sequence):
        self._collection.foreach_get(attr, sequence)

    @bpy_only
    def foreach_set(self, attr, sequence):
        self._collection.foreach_set(attr, sequence)

    @bpy_only
    def items(self):
        return self._collection.items()

    @bpy_only
    def keys(self):
        return self._collection.keys()

    @bpy_only
    def values(self):
        return self._collection.values()

    @bpy_only
    def new(self, *items):
        self._collection.new(*items)

    @bpy_only
    def remove(self, *items):
        self._collection.remove(*items)
