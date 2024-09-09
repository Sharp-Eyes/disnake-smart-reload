# TODO: Remove!

"""Reload manager implementation."""

from __future__ import annotations

import signal
import importlib
import importlib.util
import pathlib
import sys
import typing

from smart_reload import node as node_m
from smart_reload import parser
from smart_reload import watchdog

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

    def __init__(self, path: str | None = None, interval: float = 1) -> None:
        self.path = pathlib.Path(path) if path else pathlib.Path()
        self._file_watchdog = watchdog.SyncWatchdog(self, interval)
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

    def build_module_nodes(
        self,
        name: str,
        package: str | None = None,
    ) -> node_m.ModuleNode:
        resolved_name = parser.resolve_name(name, package)

        node = self._build_module_nodes(resolved_name, None, set())
        assert node  # Should never not exist as name resolution would've failed.
        return node

    def _build_module_nodes(
        self,
        name: str,
        package: str | None,
        resolved: set[str],
    ) -> node_m.ModuleNode | None:
        resolved_name = parser.resolve_name(name, package)
        resolved.add(resolved_name)

        module = sys.modules[resolved_name]
        if not module.__file__:
            # This is a namespace package.
            return None

        path = pathlib.Path(module.__file__).resolve()
        if path.is_dir():
            # This is a namespace package.
            return None

        try:
            data = parser.parse_module(path)
        except TypeError:
            # This module isn't implemented in python; probably part of stdlib.
            return None

        # The module isn't on the path or whitelist; or is on the blacklist.
        # TODO: Implement whitelist/blacklist
        if self.path.resolve() not in path.parents:
            raise ValueError

        # Parse the module to find all imports.
        node_visitor = parser.ModuleVisitor(module.__package__)
        node_visitor.visit(data)
        imported_modules = node_visitor.imported_modules

        # Make a node and recursively make nodes for its dependencies.
        node = node_m.ModuleNode(str(path), name=name, package=package)
        for module_name in imported_modules - resolved:
            try:
                node_module = self._build_module_nodes(module_name, None, resolved)

            except ValueError:  # TODO: change this error to another that makes sense
                continue

            if node_module:
                node.add_dependency(node_module)
                self._modules[module_name] = node_module

        return node

    def load_module(self, name: str, package: str | None = None) -> None:
        """Load a module.

        Automatically registers all child modules for use in reloading.
        """
        self._load(name, package)
        node = self.build_module_nodes(name, package)

        if not node:
            # maybe we should raise an error or a warning?
            return

        self._modules[node.name] = node

    def reload_module(self, name: str, *, package: str | None = None) -> None:
        """Reload a module.

        Automatically reloads all child modules.
        """
        resolved_name = parser.resolve_name(name, package)
        node = self._modules[resolved_name]
        top_level: set[node_m.ModuleNode] = set()

        # Unload all dependencies in reverse order...
        with self._file_watchdog.modules_lock:
            order = self.find_dependency_order(node)
            for dependencies in order:
                for dependency in dependencies:
                    print(dependency.name, "unloaded")
                    self._unload(dependency.name, dependency.package)
                    if not dependency.dependents:
                        top_level.add(dependency)

            for dependency in top_level:
                # Load the main extension again and related modules (automatically imports what it needs).
                self.load_module(dependency.name, dependency.package)

    def unload_module(self, name: str, package: str | None = None) -> None:
        """Unload a module.

        Automatically unloads all child modules that are safe to unload.
        """
        self._unload(name, package)
        resolved_name = parser.resolve_name(name, package)

        node = self.modules[resolved_name]
        for dependency, _ in node.walk_dependencies():
            if not dependency.dependents:  # Safe to unload too
                self._unload(dependency.name, dependency.package)
                self._modules.pop(dependency.name)

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

    def watch(self) -> None:
        """Starts watching for file changes."""
        self._file_watchdog.thread.start()

        def closer(*args) -> None:
            print("called")
            self._file_watchdog.is_closed.set()

        signal.signal(signal.SIGINT, closer)
        signal.signal(signal.SIGTERM, closer)
