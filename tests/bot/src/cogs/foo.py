from __future__ import annotations

from disnake.ext import commands
from . import bar
from ..utils import useful_file


class Test(commands.Cog):
    ...


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Test())
