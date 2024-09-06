from __future__ import annotations
import ast
import contextlib
import sys
import types
import typing

import pytest
from smart_reload import parser


@contextlib.contextmanager
def ephemeral_imports():
    modules = set(sys.modules)

    yield

    for module in set(sys.modules) - modules:
        del sys.modules[module]


class TestReloadManager:
    def test_nothing(self):
        mods = set(sys.modules)
        with ephemeral_imports():
            import disnake

        assert mods == sys.modules.keys()
