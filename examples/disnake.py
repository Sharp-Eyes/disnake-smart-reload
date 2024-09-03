"""Example on how to integrate <name pending> with disnake.

Similar logic can be applied to other discord.py forks.
"""
from __future__ import annotations

from disnake.ext import commands

import smart_reload

bot = commands.Bot()
manager = smart_reload.ReloadManager()


def unload_extension(name: str, package: str | None) -> None:
    """Disnake compatibility layer for unload_module."""
    try:
        bot.unload_extension(name, package=package)
    except commands.ExtensionNotFound:
        smart_reload.unload_module(name, package)


manager.set_loader(lambda name, package: bot.load_extension(name, package=package))
manager.set_unloader(unload_extension)


manager.load_module("foo.bar")  # Use instead of bot.load_extension
