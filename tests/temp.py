from disnake.ext import commands
from smart_reload import ModuleNode, ExtensionManager


bot = commands.Bot()
manager = ExtensionManager(bot)


def display_order(order: list[set[ModuleNode]]):
    print([[node.name for node in dependencies] for dependencies in order])


A = ModuleNode("/path/to/A", "A")
B = ModuleNode("/path/to/B", "B")
C = ModuleNode("/path/to/C", "C")
U = ModuleNode("/path/to/U", "U")

A.add_dependency(U)
B.add_dependency(C)
C.add_dependency(U)


display_order(manager.find_dependency_order(A))
