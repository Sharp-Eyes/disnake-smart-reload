from __future__ import annotations

import ast
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import pathlib
import sys
import types
import typing
import weakref

from smart_reload import parser

__all__: typing.Sequence[str] = (
    "load_module",
    "reload_module",
    "unload_module",
    "set_loader",
    "set_unloader",
    "register_hook",
    "deregister_hook",
)


P = typing.ParamSpec("P")
LoaderCallback = typing.Callable[[types.ModuleType], bool]
LoaderCallbackT = typing.TypeVar("LoaderCallbackT", bound=LoaderCallback)


# A sort-of mirror to sys.modules for modules loaded by our loader.
# This intentionally lags behind reloads until the reload is complete, so that
# we can access the previous state for dependencies/dependents.
_MODULES: typing.MutableMapping[str, types.ModuleType] = weakref.WeakValueDictionary()


def _get_old_dependents(
    module: types.ModuleType,
) -> typing.Sequence[typing.AbstractSet[types.ModuleType]]:
    """Get the dependents from the module before it was reloaded."""
    old = _MODULES[module.__name__]
    assert isinstance(old.__loader__, ShittyLoader)
    return old.__loader__.get_dependents()


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


class ShittyLoader(importlib.machinery.SourceFileLoader):
    submodule_loader: LoaderCallback
    submodule_unloader: LoaderCallback

    def __init__(self, fullname: str, path: str) -> None:
        super().__init__(fullname, path)
        self.fullname: str = fullname
        self.dependencies: typing.MutableSet[types.ModuleType] = weakref.WeakSet()
        self.dependents: typing.MutableSet[types.ModuleType] = weakref.WeakSet()

    def exec_module(self, module: types.ModuleType) -> None:
        # First, execute the module. This guarantees that all dependencies are
        # also imported. We use this fact to make it easier to traverse the
        # imports for ast-parsing.
        if self.fullname in _MODULES:
            self.reload_module(module)
        else:
            super().exec_module(module)

        _MODULES[self.fullname] = module
        self.parse_module_dependents(module)

    def reload_module(self, module: types.ModuleType) -> None:
        """Recursively reloads a module and all of its dependents."""
        dependents = _get_old_dependents(module)

        # Remove all dependents in reverse load order...
        for dependent_group in reversed(dependents):
            for dependent in dependent_group:
                # As self is directly being reloaded, it's (hopefully) already
                # been cleared from sys.modules and re-added there. Therefore,
                # we only need to do this for the remaining modules.
                if dependent.__loader__ is not self:
                    print("~ unloading", dependent.__name__)
                    success = self.submodule_unloader(dependent)
                    if not success:
                        _unload_module(dependent)
                    del _MODULES[dependent.__name__]

        # Reload dependents in load order.
        for dependent_group in dependents:
            for dependent in dependent_group:
                print("~ reloading", dependent.__name__)
                if dependent.__loader__ is self:
                    # For the module that set off the reload sequence, just
                    # execute the module. It should already have been added to
                    # sys.modules earlier on in the import cycle.
                    super().exec_module(dependent)

                else:
                    # https://docs.python.org/3/library/importlib.html#approximating-importlib-import-module
                    success = self.submodule_loader(dependent)
                    if not success:
                        _reimport_module(dependent)

    def parse_module_dependents(self, module: types.ModuleType) -> None:
        """Recursively find a module's dependencies and dependents."""
        module_ast = ast.parse(pathlib.Path(self.path).read_text())
        visitor = parser.ModuleVisitor(package=module.__package__)
        visitor.visit(module_ast)

        for dependency in visitor.imported_modules:
            if dependency not in sys.modules:
                continue

            dep_module = sys.modules[dependency]
            if not isinstance(dep_module.__loader__, ShittyLoader):
                continue

            self.dependencies.add(dep_module)
            dep_module.__loader__.dependents.add(module)
            _MODULES[dep_module.__name__] = dep_module

    def walk_dependents(self) -> typing.Generator[tuple[types.ModuleType, int]]:
        yield from self._walk_dependents(0)

    def _walk_dependents(
        self,
        depth: int,
    ) -> typing.Generator[tuple[types.ModuleType, int]]:
        yield sys.modules[self.name], depth

        for dependent in self.dependents:
            assert isinstance(dependent.__loader__, ShittyLoader)
            yield from dependent.__loader__._walk_dependents(depth+1)

    def get_dependents(self) -> typing.Sequence[typing.AbstractSet[types.ModuleType]]:
        found: dict[types.ModuleType, int] = {}
        max_depth = 0

        for dependent, depth in self.walk_dependents():
            if dependent not in found or found[dependent] < depth:
                found[dependent] = depth

            max_depth = max(depth, max_depth)

        # TODO: Validate whether this step is truly necessary.
        #       Probably gonna need some thorough unit tests for this.
        #       Low priority, as this shouldn't be much of a slowdown.
        result: list[set[types.ModuleType]] = [set() for _ in range(max_depth + 1)]
        for dependent, depth in found.items():
            result[depth].add(dependent)

        return result


class ShittyFinder(importlib.machinery.PathFinder):

    valid_paths: typing.ClassVar[set[pathlib.Path]]

    @classmethod
    def set_valid_paths(cls, *valid_paths: str | pathlib.Path) -> None:
        """Set the paths this finder should consider for dependency collection.

        This automatically includes any subdirectory (recursively).
        """
        # TODO: Contemplate whether this is really a good way to do this, lol.
        cls.valid_paths = {pathlib.Path(path).resolve() for path in valid_paths}

    @classmethod
    def find_spec(
        cls,
        fullname: str,
        path: typing.Sequence[str] | None = None,
        target: types.ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        spec = super().find_spec(fullname, path, target)
        if not spec or not spec.origin:
            return None

        if not set(pathlib.Path(spec.origin).parents) & cls.valid_paths:
            return None

        spec.loader = ShittyLoader(fullname, spec.origin)
        return spec


def set_loader(loader: LoaderCallbackT) -> LoaderCallbackT:
    ShittyLoader.submodule_loader = staticmethod(loader)
    return loader


def set_unloader(unloader: LoaderCallbackT) -> LoaderCallbackT:
    ShittyLoader.submodule_unloader = staticmethod(unloader)
    return unloader


# Construct our finder object and set the default path to cwd.
_FINDER = ShittyFinder()
_FINDER.set_valid_paths(pathlib.Path())

set_loader(_reimport_module)
set_unloader(_unload_module)


def register_hook() -> None:
    """Register the import hook.

    This allows automatic dependency collection to take automagically take
    place when any module is imported; which in turn allows recursive
    module reloading to work.
    """
    if _FINDER in sys.meta_path:
        msg = "Import hook is already registered."
        raise RuntimeError(msg)

    sys.meta_path.insert(0, _FINDER)


def deregister_hook() -> None:
    """Deregister the import hook.

    This prevents recursive reloading from working.
    """
    try:
        sys.meta_path.remove(_FINDER)
    except ValueError as exc:
        msg = "Import hook is not registered."
        raise RuntimeError(msg) from exc
