from HumGen3D.common.exceptions import HumGenException


def expect_rigify_exception(func):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except HumGenException:
            assert True, "Expected"
        else:
            raise AssertionError("Should throw exception")

    return wrapper
