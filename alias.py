# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Keeps `import HumGen3D` working when the package has another name.

Scripts use the add-on as `from HumGen3D import Human`. As a Blender extension
the package is really `bl_ext.<repository>.humgen3d`, a name that even differs
between users. So the add-on puts a finder on `sys.meta_path` that answers for
`HumGen3D` and everything below it by handing out the modules of the real
package. Both names then share one module object per module, so there is never
a second copy of a class. Submodules not imported yet are imported on demand
under their real name.

The finder is a no-op when the package already is `HumGen3D` (legacy install
and the tests). `HG3D`, the name of an early version, is kept as a second alias.
"""
import importlib
import importlib.abc
import importlib.util
import sys
from importlib.machinery import ModuleSpec
from types import ModuleType
from typing import Dict, Optional, Sequence, Tuple

from .package import PUBLIC_NAME, addon_package

ALIASES: Tuple[str, ...] = (PUBLIC_NAME, "HG3D")


class AliasFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Resolves `<alias>[.sub.module]` to the modules of `package`."""

    def __init__(self, aliases: Sequence[str], package: str) -> None:
        self.aliases = tuple(aliases)
        self.package = package
        # The real `__spec__` of a module, between create_module and exec_module
        self._specs: Dict[str, Optional[ModuleSpec]] = {}

    def real_name(self, name: str) -> Optional[str]:
        """The name in the real package of an aliased module name, or None."""
        for alias in self.aliases:
            if name == alias:
                return self.package
            if name.startswith(alias + "."):
                return self.package + name[len(alias):]
        return None

    def find_spec(self, name, path=None, target=None):  # type: ignore[no-untyped-def]
        if self.real_name(name) is None:
            return None
        return importlib.util.spec_from_loader(name, self)

    def create_module(self, spec: ModuleSpec) -> ModuleType:
        real_name = self.real_name(spec.name)
        assert real_name is not None
        module = importlib.import_module(real_name)
        # The import machinery writes the alias spec on the module after this;
        # exec_module puts the real one back.
        self._specs[module.__name__] = module.__spec__
        return module

    def exec_module(self, module: ModuleType) -> None:
        # Already executed under its real name, only undo the spec change.
        if module.__name__ in self._specs:
            module.__spec__ = self._specs.pop(module.__name__)


_finder: Optional[AliasFinder] = None


def install() -> None:
    """Put the alias finder in place, once per package name."""
    global _finder
    package = addon_package()
    if _finder is not None and _finder.package == package:
        if _finder not in sys.meta_path:
            sys.meta_path.insert(0, _finder)
        return
    uninstall()
    aliases = [alias for alias in ALIASES if alias != package]
    if not aliases:
        return
    _finder = AliasFinder(aliases, package)
    sys.meta_path.insert(0, _finder)


def uninstall() -> None:
    """Remove the finder and the alias entries it put in `sys.modules`."""
    global _finder
    if _finder is None:
        return
    if _finder in sys.meta_path:
        sys.meta_path.remove(_finder)
    for name in list(sys.modules):
        module = sys.modules[name]
        if _finder.real_name(name) is not None and getattr(module, "__name__", name) != name:
            del sys.modules[name]
    _finder = None


def installed() -> Optional[AliasFinder]:
    """The active finder, for tests."""
    return _finder
