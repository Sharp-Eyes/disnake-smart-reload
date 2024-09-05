from __future__ import annotations

import disnake
import smart_reload
from disnake.ext import commands
from smart_reload import manager

# suppress the shitty warnings
bot = commands.Bot(
    command_prefix=commands.when_mentioned,
    intents=disnake.Intents.none(),
)
manager = manager.ReloadManager("src")


def unload_extension(name: str, package: str | None) -> None:
    """Disnake compatibility layer for unload_module."""
    try:
        bot.unload_extension(name, package=package)
    except commands.ExtensionNotFound:
        smart_reload.unload_module(name, package)


manager.set_loader(lambda name, package: bot.load_extension(name, package=package))  # type: ignore
manager.set_unloader(unload_extension)

manager.load_module("src.cogs.foo")
