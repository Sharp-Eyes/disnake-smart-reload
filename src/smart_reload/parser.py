from __future__ import annotations

import ast
import inspect
import typing

if typing.TYPE_CHECKING:
    import types


class Parser:
    def parse_module(self, module: types.ModuleType) -> ast.Module:
        source = inspect.getsource(module)
        return ast.parse(source, filename="<string>")

    def get_imports_from_module(self, package: str, module: ast.Module) -> list[str]:
        # ISSUE
        # e.g cogs.foo imports bar
        # ast parse cogs.foo and find bar, from here we return "bar" in the list
        # of imported modules, BUT "bar" is obiously inserted in sys.modules
        # as "cogs.bar" so importlib can't find the spec for "bar" and as
        # such it returns early
        # manager.py#L92-L97       //       parser.py#L16-L33
        imported_modules: list[str] = []
        for element in module.body:
            if not isinstance(element, (ast.Import, ast.ImportFrom)):
                continue

            if isinstance(element, ast.Import) or not element.module:
                for name in element.names:
                    imported_modules.append(name.name)  # noqa: PERF401
            else:  # noqa: PLR5501
                # alarm: relative import, add package
                if element.level != 0:
                    imported_modules.append(package + "." + element.module)
                else:
                    imported_modules.append(element.module)
        return imported_modules
