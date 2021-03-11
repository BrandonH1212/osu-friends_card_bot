"""
osu manager cog
"""

from discord.ext import commands
from discord import File
from .lib.drawing import get_dump_image
from config.config import img_config


class OsuManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.group(name='man', pass_context=True)
    async def manage(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Invalid man command passed...')

    @manage.command(name='help')
    async def help(self, ctx):
        await ctx.send("This is a help page.")

    @manage.command(name='menu')
    async def menu(self, ctx):
        file_path = get_dump_image(img_config.MENU_MAPPING)
        await ctx.send(file=File(file_path))
