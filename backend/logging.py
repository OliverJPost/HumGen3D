# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import time

from .preferences import get_prefs


def hg_log(*message: object, level: str = "INFO") -> None:
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
        print(bcolors[level] + level_tag + bcolors["ENDC"], *message)  # noqa T201


def time_update(label: str, prev_time: float) -> float:
    """Logging function to time code.

    Args:
        label: What to print for this time update
        prev_time: Output of a previous time_update or time.perf_counter()

    Returns:
        time.perf_counter() output
    """
    hg_log(label, round(time.perf_counter() - prev_time, 2))
    return time.perf_counter()
