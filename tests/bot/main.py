from __future__ import annotations
import sys
import types  # noqa: TCH003

import smart_reload
from disnake.ext import commands

bot = commands.InteractionBot()

@smart_reload.set_loader
def extension_loader(module: types.ModuleType) -> bool:
    if callable(getattr(module, "setup", None)):
        bot.load_extension(module.__name__)
        return True

    return False  # Trigger default load logic.


@smart_reload.set_unloader
def extension_unloader(module: types.ModuleType) -> bool:
    if callable(getattr(module, "setup", None)):
        bot.unload_extension(module.__name__)
        return True

    return False  # Trigger default unload logic.



# Load extension
print("LOADING")
bot.load_extension("src.cogs.foo")
print(id(bot.extensions["src.cogs.foo"]), id(sys.modules["src.utils.useful_file"]))

# Reload utils; should reload utils and foo (and bar)
print("\nRELOADING")
smart_reload.reload_module("src.utils.useful_file")
print(id(bot.extensions["src.cogs.foo"]), id(sys.modules["src.utils.useful_file"]))

# Reload bar; should reload bar and foo (not utils)
print("\nRELOADING AGAIN")
smart_reload.reload_module("src.cogs.bar")
print(id(bot.extensions["src.cogs.foo"]), id(sys.modules["src.utils.useful_file"]))
