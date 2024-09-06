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
    name: str,
    package: str | None,
    *,
    module: str | None = None,
    level: int | None = None,
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
            resolved = resolve_name(alias.name, self.package, level=0)
            if resolved in sys.modules:
                self.imported_modules.add(resolved)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module:
            # From-import with a module specified:
            # check if the module itself can be resolved.
            resolved = resolve_name(node.module, self.package, level=node.level)
            if resolved in sys.modules:
                self.imported_modules.add(resolved)

        elif self.package:
            # Relative from-import where the module is any number of ``.``s:
            # try resolving the package as a module.
            resolved = resolve_name("", self.package, level=node.level-1)
            if resolved in sys.modules:
                self.imported_modules.add(resolved)

        for alias in node.names:
            # Check if any of the imports can be resolved.
            resolved = resolve_name(
                alias.name,
                self.package,
                module=node.module,
                level=node.level,
            )
            if resolved in sys.modules:
                self.imported_modules.add(resolved)
