from __future__ import annotations

import ast
import importlib
import importlib._bootstrap
import importlib.util
import pathlib
import sys


def parse_module(path: str, is_package: bool) -> ast.Module | None:
    """Parse a module given its path, returning an ast object
    representing its source.
    """
    if is_package:
        path_ = (pathlib.Path(path) / "__init__.py").resolve()
        if not path_.exists():
            print("UwU")
            return

        path = path_.name

    with open(path, "r") as module_file:
        module = ast.parse(module_file.read(), filename="<string>")
    return module


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
            print(
                f"resolved {{{module=}, {name=}, {package=}, {level=}}} to {fullname!r}"
            )
            return fullname

        # Should essentially never happen as the modules passed actual importing;
        # no package specified for relative import
        raise RuntimeError

    base, *remainder = package.rsplit(".", level - 1)
    if len(remainder) == level:
        print(module, name, package)
        # Should essentially never happen as the modules passed actual importing;
        # attempted relative import beyond top-level package
        raise RuntimeError

    resolved = f"{base}.{fullname}" if name else base
    # TODO: remove after testing or maybe log instead?
    print(f"resolved {{{module=}, {name=}, {package=}, {level=}}} to {resolved!r}.")
    return resolved


class ModuleVisitor(ast.NodeVisitor):
    def __init__(self, package: str | None) -> None:
        super().__init__()
        self.package: str | None = package
        self.imported_modules: set[str] = set()

    def _resolve_relative_package(self, name: str, level: int) -> str:
        return importlib._bootstrap._resolve_name(  # type: ignore
            name,
            package=self.package,
            level=level,
        )

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
