from __future__ import annotations
import importlib
import typing

from disnake.ext import commands  # TODO: possibly make lib-agnostic???

from smart_reload import node

__all__: typing.Sequence[str] = ("ExtensionManager",)


class ExtensionManager:

    bot: commands.Bot
    _modules: dict[str, node.ModuleNode]

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._modules = {}

    @property
    def modules(self) -> typing.Mapping[str, node.ModuleNode]:
        return self._modules

    def load_extension(self, name: str, *, package: str | None = None):
        self.bot.load_extension(name, package=package)

        ...  # Make ModuleNodes for the imported extension (sys.modules[name])

    def reload_extension(self, name: str, *, package: str):
        self.bot.unload_extension(name, package=package)

        # Unload all dependencies in reverse order...
        node = self._modules[name]
        for dependencies in reversed(self.find_dependency_order(node)):
            for dependency in dependencies:
                ...  # Unload dependency

        # Load all dependencies in order...
        for dependencies in self.find_dependency_order(node):
            for dependency in dependencies:
                importlib.import_module(dependency.name, package=dependency.package)

        self.bot.load_extension(name, package=package)

    def unload_extension(self, name: str, *, package: str | None):
        self.bot.unload_extension(name, package=package)

        node = self.modules[name]
        for dependency, _ in node.walk_dependencies():
            if not dependency.dependents:  # Safe to unload too
                ...  # Unload dependency

    def find_dependency_order(self, module: node.ModuleNode):
        depth_map = {module: 0}
        min_depth = 0
        max_depth = 0
    
        # First check all dependencies of the module, keep only the occurrence of each
        # dependency at greatest depth (earliest import as we import in reverse.)
        for dependency, search_depth in module.walk_dependencies():
            if dependency not in depth_map or search_depth > depth_map[dependency]:
                depth_map[dependency] = search_depth

            if search_depth > max_depth:
                max_depth = search_depth

        # For each dependency, check all dependents. If we find a dependent we haven't
        # added yet, add it. Keep only the occurrence of each depdent at smallest depth.
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
        # The sets are populated reverse depth order. 
        order: list[set[node.ModuleNode]] = [set() for _ in range(min_depth, max_depth+1)]
        for dependency, depth in depth_map.items():
            order[max_depth - depth].add(dependency)

        return order
