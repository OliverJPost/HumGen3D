# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Long running operations as resumable steps.

Blender freezes while Python runs, so an operation that takes more than a
moment is written as a generator that yields how far along it is, a fraction
from 0 to 1, between short chunks of work. A modal operator can then advance it
on a timer, keeping the interface alive and showing a progress bar. Code that
does not care simply calls `run()` on it.
"""

from typing import Callable, Generator, Optional, TypeVar

T = TypeVar("T")
Steps = Generator[float, None, T]
ProgressCallback = Callable[[float], None]


def run(steps: Steps[T], progress: Optional[ProgressCallback] = None) -> T:
    """Run a stepwise operation to the end in one go.

    Args:
        steps: The operation.
        progress: Called with the fraction done whenever it increases, and with
            1.0 when the operation is finished.

    Returns:
        The return value of the operation.
    """
    shown = 0.0
    while True:
        try:
            fraction = next(steps)
        except StopIteration as finished:
            if progress is not None:
                progress(1.0)
            return finished.value
        if progress is not None and fraction > shown:
            shown = fraction
            progress(fraction)


def phase(steps: Steps[T], start: float, end: float) -> Steps[T]:
    """Make a stepwise operation report as the part `start` to `end` of a larger one.

    Args:
        steps: The operation that is part of a larger one.
        start: Fraction of the larger operation that is done when this one starts.
        end: Fraction of the larger operation that is done when this one ends.

    Returns:
        The same operation, yielding remapped fractions.
    """
    span = end - start
    while True:
        try:
            fraction = next(steps)
        except StopIteration as finished:
            return finished.value
        yield start + span * min(max(fraction, 0.0), 1.0)
