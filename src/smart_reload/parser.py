from __future__ import annotations

import ast
import pathlib
import sys


def parse_module(path: str, *, is_package: bool) -> ast.Module | None:
    """
    Parse a module given its path, returning an ast object
    representing its source.
    """
    if is_package:
        path_ = (pathlib.Path(path) / "__init__.py").resolve()
        if not path_.exists():
            print("UwU")
            return

        path = path_.name

    with open(path) as module_file:
        module = ast.parse(module_file.read(), filename="<string>")
    return module


def resolve_name(
    module: str | None,
    name: str,
    package: str | None,
    level: int | None,
) -> str:
    """Resolve parts of an import statement to an absolute import."""
    fullname = f"{module}.{name}" if module else name

    if level is None:
        level = 0
        for char in fullname:
            if char != ".":
                break
            level += 1

        fullname = fullname[level:]

    if not package:
        if not fullname.startswith(".") and level == 0:
            # TODO: remove after testing or maybe log instead?
            print(
                f"resolved {{{module=}, {name=}, {package=}, {level=}}} to {fullname!r}",
            )
            return fullname

        # Should essentially never happen as the modules passed actual importing;
        msg = "No package specified for relative import."
        raise RuntimeError(msg)

    base, *remainder = package.rsplit(".", level - 1)
    if len(remainder) < level - 1:
        # Should essentially never happen as the modules passed actual importing;
        msg = "Attempted relative import beyond top-level package."
        raise RuntimeError(msg)

    resolved = f"{base}.{fullname}" if name else base
    # TODO: remove after testing or maybe log instead?
    print(f"resolved {{{module=}, {name=}, {package=}, {level=}}} to {resolved!r}.")
    return resolved


class ModuleVisitor(ast.NodeVisitor):
    def __init__(self, package: str | None) -> None:
        super().__init__()
        self.package: str | None = package
        self.imported_modules: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            resolved = resolve_name(None, alias.name, self.package, 0)
            if resolved in sys.modules:
                self.imported_modules.add(resolved)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module:
            resolved = resolve_name(None, node.module, self.package, node.level)
            if resolved in sys.modules:
                self.imported_modules.add(resolved)

        for alias in node.names:
            resolved = resolve_name(node.module, alias.name, self.package, node.level)
            if resolved in sys.modules:
                self.imported_modules.add(resolved)
