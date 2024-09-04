from __future__ import annotations

import ast
import importlib
import importlib._bootstrap
import importlib.util
import sys
import types


def parse_module(path: str) -> ast.Module:
    """Parse a module given its path, returning an ast object
    representing its source.
    """
    with open(path, "r") as module_file:
        module = ast.parse(module_file.read(), filename="<string>")
    return module


class ModuleVisitor(ast.NodeVisitor):
    def __init__(self, name: str, package: str | None) -> None:
        super().__init__()
        self.module_name: str = name
        self.package: str | None = package
        self.imported_modules: set[str] = set()

    def _resolve_relative_package(self, name: str, level: int) -> str:
        return importlib._bootstrap._resolve_name(  # type: ignore
            name,
            package=self.package,
            level=level,
        )

    def visit_Import(self, node: ast.Import) -> None:
        for import_name in node.names:
            self.imported_modules.add(import_name.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            # relative import
            # e.g from .Y import X, etc...
            for alias in node.names:
                if node.module:
                    name = node.module + "." + alias.name
                else:
                    name = alias.name

                if self.package:
                    self.imported_modules.add(
                        self._resolve_relative_package(name, node.level)
                    )
                else:
                    self.imported_modules.add(name)
        else:
            # non-relative import
            # e.g from Y import X, etc...
            if not node.module:
                # should never happen
                return

            for alias in node.names:
                if not alias.asname:
                    continue
                if isinstance(
                    sys.modules[node.module].__dict__[alias.asname], types.ModuleType
                ):
                    self.imported_modules.add(node.module + "." + alias.asname)
            self.imported_modules.add(node.module)


class Parser:
    def parse_module(self, path: str) -> ast.Module:
        """Parse a module given its path, returning an ast object
        representing its source.
        """
        with open(path, "r") as module_file:
            module = ast.parse(module_file.read(), filename="<string>")
        return module

    def get_imports_from_module(self, package: str, module: ast.Module) -> set[str]:
        imported_modules: set[str] = set()
        for element in module.body:
            if not isinstance(element, (ast.Import, ast.ImportFrom)):
                continue

            if (
                isinstance(element, ast.Import)
                or not element.module
                and not element.level
            ):
                for name in element.names:
                    imported_modules.add(name.name)  # noqa: PERF401
            else:  # noqa: PLR5501
                # alarm: relative import, add package
                if element.level != 0:
                    for alias in element.names:
                        if element.module:
                            name = element.module + "." + alias.name
                        else:
                            name = alias.name

                        imported_modules.add(
                            importlib._bootstrap._resolve_name(  # type: ignore
                                name,
                                package=package,
                                level=element.level,
                            )
                        )
                else:
                    for alias in element.names:
                        if element.module:
                            name = element.module + "." + alias.name
                        else:
                            name = alias.name
                        imported_modules.add(name)
        return imported_modules
