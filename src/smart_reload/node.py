"""Module node implementation."""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    import collections.abc

__all__: typing.Sequence[str] = ("ModuleNode",)


class ModuleNode:
    """Module node implementation.

    This class keeps track of the dependency hierarchy between modules.
    Should only be used to track relative ordering; absolute ordering should be
    determined externally for an individual module.
    """

    path: str
    """The path to the module."""
    name: str
    """The name of the module."""
    package: str | None
    """The package to which the module belongs."""

    def __init__(self, path: str, name: str, package: str | None = None) -> None:
        self.path = path
        self.name = name
        self.package = package
        self._dependents: set[ModuleNode] = set()
        self._dependencies: set[ModuleNode] = set()

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} path={self.path}>"

    @property
    def dependents(self) -> collections.abc.Set[ModuleNode]:
        """The dependents of this module.

        That is, files that import this module.
        """
        return self._dependents

    @property
    def dependencies(self) -> collections.abc.Set[ModuleNode]:
        """The dependencies of this module.

        That is, files imported by this module.
        """
        return self.dependencies

    def __hash__(self) -> int:
        # Probably unique enough?
        return hash(self.path)

    def add_dependent(self, dependent: ModuleNode) -> None:
        """Add a dependent to this module.

        Automatically adds this module as a dependency to the other module.
        """
        self._dependents.add(dependent)
        dependent._dependencies.add(self)

    def add_dependency(self, dependency: ModuleNode) -> None:
        """Add a dependency to this module.

        Automatically adds this module as a dependents to the other module.
        """
        self._dependencies.add(dependency)
        dependency._dependents.add(self)

    def walk_dependencies(self) -> collections.abc.Iterator[tuple[ModuleNode, int]]:
        """Recursively walk though all of this module's dependencies.

        Yields a tuple of each module and its depth relative to this one.
        """
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
        """Recursively walk though all of this module's dependents.

        Yields a tuple of each module and its depth relative to this one.
        """
        for dependent in self._dependents:
            yield from dependent._walk_dependents(1)

    def _walk_dependents(
        self,
        depth: int,
    ) -> collections.abc.Iterator[tuple[ModuleNode, int]]:
        yield self, depth
        for dependent in self._dependents:
            yield from dependent._walk_dependents(depth + 1)
