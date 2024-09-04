"""Reload manager implementation."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import pathlib
import sys
import typing

from smart_reload import node as node_m
from smart_reload import parser

if typing.TYPE_CHECKING:
    import collections.abc

    _LoaderFunc = collections.abc.Callable[[str, str | None], None]
    _LoaderFuncT = typing.TypeVar("_LoaderFuncT", bound=_LoaderFunc | None)

__all__: collections.abc.Sequence[str] = (
    "ReloadManager",
    "import_module",
    "unload_module",
)


def import_module(name: str, package: str | None = None) -> None:
    """Import a module."""
    importlib.import_module(name, package)


def unload_module(name: str, package: str | None = None) -> None:
    """Unload a module."""
    sys.modules.pop(importlib.util.resolve_name(name, package))


class ReloadManager:
    """Reload manager implementation.

    Modules imported through `load_module` will be registered to this manager,
    and can then be reloaded and unloaded via the manager.
    """

    _modules: dict[str, node_m.ModuleNode]

    def __init__(self, path: str | None) -> None:
        self.path = pathlib.Path(path) if path else pathlib.Path()
        self._parser = parser.Parser()
        self._modules = {}

        self._load: _LoaderFunc = import_module
        self._unload: _LoaderFunc = unload_module

    @property
    def modules(self) -> collections.abc.Mapping[str, node_m.ModuleNode]:
        """The modules registered to this manager."""
        return self._modules

    def set_loader(self, loader: _LoaderFuncT) -> _LoaderFuncT:
        """Register a custom loader function.

        If ``None`` is passed, the loader function is reset to the default
        implementation.
        """
        if loader is None:
            self._load = import_module
        else:
            self._load = loader

        return loader

    def set_unloader(self, unloader: _LoaderFuncT) -> _LoaderFuncT:
        """Register a custom unloader function.

        If ``None`` is passed, the unloader function is reset to the default
        implementation.
        """
        if unloader is None:
            self._unload = unload_module
        else:
            self._unload = unloader

        return unloader

    def _build_module_nodes(
        self,
        name: str,
        package: str | None = None,
    ) -> node_m.ModuleNode | None:
        try:
            resolved_name = importlib.util.resolve_name(name, package)
        except ImportError as e:
            raise RuntimeError(f"Couldn't find {name}") from e  # noqa: TRY003, EM102

        module_spec = importlib.util.find_spec(resolved_name)

        if not module_spec:
            # skip the module if it's not in sys.modules
            return  # noqa: RET502

        module = importlib.util.module_from_spec(module_spec)
        try:
            data = self._parser.parse_module(module)
        except TypeError:
            # skipping by default, this module is in the stdlib!
            return  # noqa: RET502

        imported_modules = self._parser.get_imports_from_module(
            module.__package__,
            data,
        )
        module_path = inspect.getsourcefile(module) or ""

        # this is not a module that we should listen for
        if self.path.resolve() not in pathlib.Path(module_path).resolve().parents:
            raise

        node = node_m.ModuleNode(module_path, name=name, package=package)

        for module_ in imported_modules.copy():
            try:
                node_module = self._build_module_nodes(module_)
            except Exception:  # noqa: BLE001
                imported_modules.remove(module_)
                continue

            if node_module:
                node.add_dependency(node_module)
            else:
                imported_modules.remove(module_)
        return node

    def load_module(self, name: str, package: str | None = None) -> typing.NoReturn:
        """Load a module.

        Automatically registers all child modules for use in reloading.
        """
        self._load(name, package)
        _node = self._build_module_nodes(name, package)
        # Make ModuleNodes for the imported module
        raise NotImplementedError

    def reload_module(self, name: str, *, package: str) -> None:
        """Reload a module.

        Automatically reloads all child modules.
        """
        self._unload(name, package)

        # Unload all dependencies in reverse order...
        node = self._modules[name]
        for dependencies in self.find_dependency_order(node):
            for dependency in dependencies:
                self._unload(dependency.name, dependency.package)

        # Load the main extension again (automatically imports what it needs).
        self.load_module(name, package=package)

    def unload_module(self, name: str, package: str | None) -> None:
        """Unload a module.

        Automatically unloads all child modules that are safe to unload.
        """
        self._unload(name, package)

        node = self.modules[name]
        for dependency, _ in node.walk_dependencies():
            if not dependency.dependents:  # Safe to unload too
                self._unload(name, package)

    def find_dependency_order(
        self,
        module: node_m.ModuleNode,
    ) -> collections.abc.Sequence[collections.abc.Set[node_m.ModuleNode]]:
        """Resolve reload dependency order for a module."""
        depth_map = {module: 0}
        min_depth = 0
        max_depth = 0

        # First check all dependencies of the module, keep only the occurrence
        # of each dependency at greatest depth.
        for dependency, search_depth in module.walk_dependencies():
            if dependency not in depth_map or search_depth > depth_map[dependency]:
                depth_map[dependency] = search_depth

            max_depth = max(search_depth, max_depth)

        # For each dependency, check all dependents. If we find a dependent we
        # haven't added yet, add it. Keep only the occurrence of each dependent
        # at smallest depth.
        for dependency, dep_depth in depth_map.copy().items():
            for dependent, search_depth in dependency.walk_dependents():
                actual_depth = dep_depth - search_depth

                if dependent not in depth_map:
                    depth_map[dependent] = actual_depth

                elif actual_depth > depth_map[dependency]:
                    msg = "Idk how to solve this but ideally it never happens"
                    raise RuntimeError(msg)

                min_depth = min(actual_depth, min_depth)

        # Finally we combine the result into a list of sets. We need to house
        # min_depth through max_depth (inclusive) sets; each set holds the
        # dependencies for that depth.
        order: list[set[node_m.ModuleNode]] = [
            set() for _ in range(min_depth, max_depth + 1)
        ]

        for dependency, depth in depth_map.items():
            order[depth - min_depth].add(dependency)

        return order
