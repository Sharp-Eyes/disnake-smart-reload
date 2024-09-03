import typing

from smart_reload import ModuleNode, ReloadManager

manager = ReloadManager()


def display_order(order: typing.Iterable[typing.Iterable[ModuleNode]]) -> None:
    print([[node.name for node in dependencies] for dependencies in order])


A = ModuleNode("/path/to/A", "A")
B = ModuleNode("/path/to/B", "B")
C = ModuleNode("/path/to/C", "C")
U = ModuleNode("/path/to/U", "U")

A.add_dependency(U)
B.add_dependency(C)
C.add_dependency(U)


display_order(manager.find_dependency_order(A))
