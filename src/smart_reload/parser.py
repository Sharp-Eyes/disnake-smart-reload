from __future__ import annotations

import ast
import importlib
import importlib._bootstrap
import importlib.util
import sys
import types


def resolve_name(
    module: str | None,
    name: str,
    package: str | None,
    level: int,
) -> str:
    """Resolve parts of an import statement to an absolute import."""
    fullname = f"{module}.{name}" if module else name

    if not package:
        if not fullname.startswith("."):
            # TODO: remove after testing or maybe log instead?
            print(f"resolved {{{module=}, {name=}, {package=}, {level=}}} to {fullname!r}")
            return fullname

        # Should essentially never happen as the modules passed actual importing;
        # no package specified for relative import
        raise RuntimeError

    base, *remainder = package.rsplit(".", level - 1)
    if len(remainder) == level:
        # Should essentially never happen as the modules passed actual importing;
        # attempted relative import beyond top-level package
        raise RuntimeError

    resolved = f"{base}.{fullname}" if name else base
    # TODO: remove after testing or maybe log instead?
    print(f"resolved {{{module=}, {name=}, {package=}, {level=}}} to {resolved!r}.")
    return resolved


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

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            resolved = resolve_name(None, alias.name, self.package, 0)
            if resolved in sys.modules:
                self.imported_modules.add(resolved)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            resolved = resolve_name(None, node.module, self.package, node.level)
            if resolved in sys.modules:
                self.imported_modules.add(resolved)

        for alias in node.names:
            resolved = resolve_name(node.module, alias.name, self.package, node.level)
            if resolved in sys.modules:
                self.imported_modules.add(resolved)


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
