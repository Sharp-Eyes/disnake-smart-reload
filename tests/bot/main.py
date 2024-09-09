from __future__ import annotations
import sys

from disnake.ext import commands
from smart_reload import hook

bot = commands.InteractionBot()

print("LOADING")
bot.load_extension("src.cogs.foo")
print(id(sys.modules["src.cogs.foo"]))

# TODO: Somehow make sure src.cogs.foo is reloaded as a disnake extension.
print("\nRELOADING")
hook.reload_module(sys.modules["src.utils.useful_file"])
print(id(sys.modules["src.cogs.foo"]))

print("\nRELOADING AGAIN")
hook.reload_module(sys.modules["src.cogs.bar"])
print(id(sys.modules["src.cogs.foo"]))
