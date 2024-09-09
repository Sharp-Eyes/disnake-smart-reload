from __future__ import annotations

import ast
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import pathlib
import sys
import typing
import weakref

from smart_reload import parser

if typing.TYPE_CHECKING:
    import types

__all__: typing.Sequence[str] = ("register_hook", "deregister_hook")


class ShittyLoader(importlib.machinery.SourceFileLoader):
    def __init__(self, fullname: str, path: str) -> types.NoneType:
        super().__init__(fullname, path)
        self.dependencies: typing.MutableSet[types.ModuleType] = weakref.WeakSet()
        self.dependents: typing.MutableSet[types.ModuleType] = weakref.WeakSet()

    def exec_module(self, module: types.ModuleType) -> None:
        # First, execute the module. This guarantees that all dependencies are
        # also imported. We use this fact to make it easier to traverse the
        # imports for ast-parsing.
        super().exec_module(module)

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

    def walk_dependents(self) -> typing.Generator[tuple[types.ModuleType, int]]:
        yield from self._walk_dependents(0)

    def _walk_dependents(self, depth: int) -> typing.Generator[tuple[types.ModuleType, int]]:
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

        result: list[set[types.ModuleType]] = [set() for _ in range(max_depth + 1)]
        for dependent, depth in found.items():
            result[depth].add(dependent)

        return result


class ShittyFinder(importlib.machinery.PathFinder):

    valid_paths: typing.ClassVar[set[pathlib.Path]]

    @classmethod
    def set_valid_paths(cls, *valid_paths: str | pathlib.Path):
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


_FINDER = ShittyFinder()
_FINDER.set_valid_paths(pathlib.Path())


def register_hook() -> None:
    if _FINDER in sys.meta_path:
        msg = "Import hook is already registered."
        raise RuntimeError(msg)

    sys.meta_path.insert(0, _FINDER)


def deregister_hook() -> None:
    try:
        sys.meta_path.remove(_FINDER)
    except ValueError as exc:
        msg = "Import hook is not registered."
        raise RuntimeError(msg) from exc
