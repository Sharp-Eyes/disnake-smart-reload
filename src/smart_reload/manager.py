from __future__ import annotations
import importlib
import importlib.util
import sys
import typing

from smart_reload import node as node_m

__all__: typing.Sequence[str] = ("ReloadManager", "import_module", "unload_module")


def import_module(name: str, package: str | None = None):
    importlib.import_module(name, package)


def unload_module(name: str, package: str | None = None):
    sys.modules.pop(importlib.util.resolve_name(name, package))


class ReloadManager:

    _modules: dict[str, node_m.ModuleNode]

    def __init__(self):
        self._modules = {}

        self._load = import_module
        self._unload = unload_module

    @property
    def modules(self) -> typing.Mapping[str, node_m.ModuleNode]:
        return self._modules

    def set_loader(self, loader: typing.Callable[[str, str | None], None] | None):
        if not loader:
            self._load = import_module
        else:
            self._load = loader

    def set_unloader(self, unloader: typing.Callable[[str, str | None], None] | None):
        if not unloader:
            self._load = unload_module
        else:
            self._load = unloader

    def load_module(self, name: str, package: str | None = None):
        self._load(name, package)

        ...  # Make ModuleNodes for the imported module

    def reload_module(self, name: str, *, package: str):
        self._unload(name, package=package)

        # Unload all dependencies in reverse order...
        node = self._modules[name]
        for dependencies in self.find_dependency_order(node):
            for dependency in dependencies:
                self._unload(dependency.name, dependency.package)

        # Load the main extension again (automatically imports what it needs).
        self.load_module(name, package=package)

    def unload_module(self, name: str, package: str | None):
        self._unload(name, package=package)

        node = self.modules[name]
        for dependency, _ in node.walk_dependencies():
            if not dependency.dependents:  # Safe to unload too
                self._unload(name, package)

    def find_dependency_order(self, module: node_m.ModuleNode):
        depth_map = {module: 0}
        min_depth = 0
        max_depth = 0
    
        # First check all dependencies of the module, keep only the occurrence of each
        # dependency at greatest depth.
        for dependency, search_depth in module.walk_dependencies():
            if dependency not in depth_map or search_depth > depth_map[dependency]:
                depth_map[dependency] = search_depth

            if search_depth > max_depth:
                max_depth = search_depth

        # For each dependency, check all dependents. If we find a dependent we haven't
        # added yet, add it. Keep only the occurrence of each dependent at smallest depth.
        for dependency, dep_depth in depth_map.copy().items():
            for dependent, search_depth in dependency.walk_dependents():
                actual_depth = dep_depth - search_depth

                if dependent not in depth_map:
                    depth_map[dependent] = actual_depth
                elif actual_depth > depth_map[dependency]:
                    raise RuntimeError("Idk how to solve this but ideally it never happens")

                if actual_depth < min_depth:
                    min_depth = actual_depth

        # Finally we combine the result into a list of sets. We need to house min_depth
        # through max_depth (inclusive) sets; each set holds the dependencies for that depth.
        order: list[set[node_m.ModuleNode]] = [set() for _ in range(min_depth, max_depth+1)]
        for dependency, depth in depth_map.items():
            order[depth - min_depth].add(dependency)

        return order
