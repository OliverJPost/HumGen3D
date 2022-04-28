import time

from .preference_func import get_prefs


def hg_log(*message, level="INFO"):
    """Writes a log message to the console. Warning, Error and Critical produce
    a color coded message.

    Args:
        message (str or list[str]): Message to display in log
        level (str): Level of log message in ('DEBUG', 'INFO', 'WARNING',
            'ERROR', 'CRITICAL') Defaults to 'INFO'.

    Raises:
        ValueError: Raised if level string is not in possible levels
    """

    log_levels = (
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
        "BACKGROUND",
    )
    if level not in log_levels:
        raise ValueError(f"{level} not found in {log_levels}")

    if get_prefs().silence_all_console_messages:
        return

    if level == "DEBUG" and not get_prefs().debug_mode:
        return

    level_tag = f"HG_{level.upper()}:\t"

    bcolors = {
        "DEBUG": "",
        "INFO": "",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "CRITICAL": "\033[91m",
        "BACKGROUND": "\033[94m",
        "ENDC": "\033[0m",
    }

    if level in bcolors:
        print(bcolors[level] + level_tag + bcolors["ENDC"], *message)


def print_context(context):
    context_dict = {
        "active": context.object,
        "active object": context.active_object,
        "selected objects": context.selected_objects,
        "area": context.area,
        "scene": context.scene,
        "mode": context.mode,
        "view layer": context.view_layer,
        "visible objects": context.visible_objects,
    }

    hg_log(context_dict)


def time_update(label, prev_time) -> int:
    hg_log(label, round(time.time() - prev_time, 2))
    return time.time()
