import sys


def correct_presetpath(path: str) -> str:
    if sys.platform not in ("win32", "win64"):
        split_path = path.split("\\")
        if isinstance(split_path, list):
            return "/".join(split_path)
        else:
            return path
    else:
        split_path = path.split("/")
        if isinstance(split_path, list):
            return "\\".join(split_path)
        else:
            return path
