from __future__ import annotations
import ast
import contextlib
import sys
import types
import typing

import pytest
from smart_reload import parser


_ModulesT = typing.TypeVar("_ModulesT", bound=typing.Collection[str])


@contextlib.contextmanager
def mock_modules(modules: _ModulesT) -> typing.Generator[_ModulesT]:
    # Take a sequence of module names and temporarily add them to sys.modules.
    # To be safe, raise if the module name already exists.
    try:
        for module in modules:
            if module in sys.modules:
                msg = "Cannot safely mock already existing module."
                raise RuntimeError(msg)

            sys.modules[module] = types.ModuleType(module, None)

        # Yield the sequence to the test function.
        yield modules

    finally:
        # Clear the modules from sys.modules after the test function finishes.
        for module in modules:
            sys.modules.pop(module, None)


@contextlib.contextmanager
def mock_package(
    visitor: parser.ModuleVisitor,
    package: str | None,
) -> typing.Generator[parser.ModuleVisitor]:
    old = visitor.package
    visitor.package = package

    yield visitor

    visitor.package = old


class TestResolveName:
    # NOTE: Assuming file structure
    #
    # <root>
    # |- A
    # |  |- a.py
    # |  |- B
    # |  |  |- b.py
    # |  |  |- C
    # |  |  |  |- c.py

    @pytest.mark.parametrize(
        ("stmt", "expected"),
        [
            ("import A", "A"),
            ("import A.a", "A.a"),
            ("from A import a", "A.a"),
            ("from A.B import b", "A.B.b"),
            ("from A.B.C import c", "A.B.C.c"),
        ],
    )
    def test_resolve_name_absolute(self, stmt: str, expected: str) -> None:
        element = ast.parse(stmt).body[0]
        assert isinstance(element, (ast.Import, ast.ImportFrom))

        module = element.module if isinstance(element, ast.ImportFrom) else None
        name = element.names[0].name
        package = None
        level = 0

        resolved = parser.resolve_name(name, package, module=module, level=level)
        assert resolved == expected

    @pytest.mark.parametrize(
        ("stmt", "package", "expected"),
        [
            ("from . import a", "A", "A.a"),
            ("from .B import b", "A", "A.B.b"),
            ("from .. import a", "A.B", "A.a"),
            ("from .C import c", "A.B", "A.B.C.c"),
            ("from .. import b", "A.B.C", "A.B.b"),
            ("from ... import a", "A.B.C", "A.a"),
        ],
    )
    def test_resolve_name_relative(
        self,
        stmt: str,
        package: str | None,
        expected: str,
    ) -> None:
        element = ast.parse(stmt).body[0]
        assert isinstance(element, ast.ImportFrom)

        module = element.module
        name = element.names[0].name
        level = element.level

        resolved = parser.resolve_name(name, package, module=module, level=level)
        assert resolved == expected

    def test_resolve_name_fail_relative_no_package(self) -> None:
        with pytest.raises(
            RuntimeError,
            match="No package specified for relative import.",
        ):
            parser.resolve_name("a", None, level=1)

    def test_resolve_name_fail_relative_too_deep(self) -> None:
        # Equivalent to `from ... import a` in A.B.b (package A.B).
        with pytest.raises(
            RuntimeError,
            match="Attempted relative import beyond top-level package",
        ):
            print(parser.resolve_name("a", "A.B", level=3))


class TestModuleVisitor:
    # NOTE: Assuming file structure
    #
    # <root>
    # |- A
    # |  |- a.py
    # |  |- B
    # |  |  |- b.py
    # |  |  |- C
    # |  |  |  |- c.py

    @pytest.fixture
    def visitor(self) -> parser.ModuleVisitor:
        return parser.ModuleVisitor(None)

    def test_visit_import_absolute(self, visitor: parser.ModuleVisitor) -> None:
        body = (
            "import A\n"
            "import A.a\n"
            "from A import a\n"
            "from A.B import b\n"
            "from A.B.C import c\n"
        )

        with mock_modules({"A", "A.a", "A.B.b", "A.B.C.c"}) as modules:
            visitor.visit(ast.parse(body))

            assert visitor.imported_modules == modules

    @pytest.mark.parametrize(
        ("package", "body"),
        [
            # NOTE: We're always importing A.a, A.B.b, A.B.C.c,
            #       just relative to different packages.
            (
                "A",
                (
                    "from . import a\n"
                    "from .B import b\n"
                    "from .B.C import c\n"
                ),
            ),
            (
                "A.B",
                (
                    "from .. import a\n"
                    "from . import b\n"
                    "from .C import c\n"
                ),
            ),
            (
                "A.B.C",
                (
                    "from ... import a\n"
                    "from .. import b\n"
                    "from . import c\n"
                ),
            ),
        ],
    )
    def test_visit_import_relative(
        self,
        visitor: parser.ModuleVisitor,
        package: str,
        body: str,
    ) -> None:
        with (
            mock_modules({"A", "A.a", "A.B", "A.B.b", "A.B.C", "A.B.C.c"}) as modules,
            mock_package(visitor, package),
        ):
            visitor.visit(ast.parse(body))

            assert visitor.imported_modules == modules

    @pytest.mark.parametrize("body", ["import A.a as foo", "from A import a as foo"])
    def test_visit_import_aliased(
        self,
        visitor: parser.ModuleVisitor,
        body: str,
    ) -> None:
        with mock_modules({"A.a"}) as modules:
            visitor.visit(ast.parse(body))

            assert visitor.imported_modules == modules

    def test_visit_import_relative_no_package(
        self,
        visitor: parser.ModuleVisitor,
    ) -> None:
        with pytest.raises(
            RuntimeError,
            match="No package specified for relative import.",
        ):
            # NOTE: The visitor has self.package set to None.
            visitor.visit(ast.parse("from . import a"))
