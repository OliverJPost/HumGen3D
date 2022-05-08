
import functools


def cached_property(func):
    return cached_instance(property(func))


def cached_instance(function):

    @functools.wraps(function)
    def wrapper(self, *args, **kwargs):

        cached_attribute_name = f"_{function.__name__}"
        if hasattr(self, cached_attribute_name):
            return getattr(self, cached_attribute_name)
        else:
            result = function(self, *args, **kwargs)
            setattr(self, cached_attribute_name, result)
            return result

    return wrapper
