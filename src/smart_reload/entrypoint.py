"""Module providing basic entrypoints"""

from __future__ import annotations

import importlib.util
import sys
import typing

if typing.TYPE_CHECKING:
    import types

__all__: typing.Sequence[str] = (
    "load_module",
    "reload_module",
    "unload_module",
)


def load_module(name: str, package: str | None = None) -> None:
    """Load a module. An alias of importlib.import_module."""
    importlib.import_module(name, package)


def reload_module(name: str, package: str | None = None) -> None:
    """Reload a module. For this to work, it must first have been imported."""
    resolved = (
        importlib.util.resolve_name(name, package)
        if name.startswith(".")
        else name
    )
    # Remove the module from sys.modules, then re-import it.
    _reimport_module(sys.modules.pop(resolved))


def _reimport_module(module: types.ModuleType) -> bool:
    spec = importlib.util.find_spec(module.__name__)
    assert spec  # TODO: Check if deleting a dependent file breaks this.

    new_module = importlib.util.module_from_spec(spec)
    sys.modules[new_module.__name__] = new_module

    assert spec.loader
    spec.loader.exec_module(new_module)
    return True


def unload_module(name: str, package: str | None = None) -> None:
    """Unload a module. For this to work, it must first have been imported."""
    resolved = (
        importlib.util.resolve_name(name, package)
        if name.startswith(".")
        else name
    )
    _unload_module(sys.modules[resolved])


def _unload_module(module: types.ModuleType) -> bool:
    del sys.modules[module.__name__]
    return True
