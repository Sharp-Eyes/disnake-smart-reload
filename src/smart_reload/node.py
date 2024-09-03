from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    import collections.abc

__all__: typing.Sequence[str] = ("ModuleNode",)


class ModuleNode:
    path: str
    name: str
    package: str | None

    def __init__(self, path: str, name: str, package: str | None = None) -> None:
        self.path = path
        self.name = name
        self.package = package
        self._dependents: set[ModuleNode] = set()
        self._dependencies: set[ModuleNode] = set()

    @property
    def dependents(self) -> collections.abc.Set[ModuleNode]:
        return self._dependents

    @property
    def dependencies(self) -> collections.abc.Set[ModuleNode]:
        return self.dependencies

    def __hash__(self) -> int:
        # Probably unique enough?
        return hash(self.path)

    def add_dependent(self, dependent: ModuleNode) -> None:
        self._dependents.add(dependent)
        dependent._dependencies.add(self)

    def add_dependency(self, dependency: ModuleNode) -> None:
        self._dependencies.add(dependency)
        dependency._dependents.add(self)

    def walk_dependencies(self) -> collections.abc.Iterator[tuple[ModuleNode, int]]:
        for dependency in self._dependencies:
            yield from dependency._walk_dependencies(1)

    def _walk_dependencies(
        self,
        depth: int,
    ) -> collections.abc.Iterator[tuple[ModuleNode, int]]:
        yield self, depth
        for dependency in self._dependencies:
            yield from dependency._walk_dependencies(depth + 1)

    def walk_dependents(self) -> collections.abc.Iterator[tuple[ModuleNode, int]]:
        for dependent in self._dependents:
            yield from dependent._walk_dependents(1)

    def _walk_dependents(
        self,
        depth: int,
    ) -> collections.abc.Iterator[tuple[ModuleNode, int]]:
        yield self, depth
        for dependent in self._dependents:
            yield from dependent._walk_dependents(depth + 1)
