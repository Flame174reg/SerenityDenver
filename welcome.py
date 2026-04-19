import asyncio
import random
from typing import Dict

import discord
from discord.ext import commands

WELCOME_CHANNEL_ID = 1495255474780635296
GUILD_ID = 1495254978418446376


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.invite_cache: Dict[int, Dict[str, int]] = {}
        self._lock = asyncio.Lock()
        self.images = [
            "https://i.ibb.co/XZRD86HR/5.png",
            "https://i.ibb.co/9mKTrYb1/attention1.png",
            "https://i.ibb.co/R1zSfHZ/attention2.png",
            "https://i.ibb.co/5WRwWVfb/attention3.png",
            "https://i.ibb.co/ZRj7WK3H/attention4.png",
            "https://i.ibb.co/TxG8Pmh6/attention5.png",
            "https://i.ibb.co/JRf520YF/attention6.png",
            "https://i.ibb.co/GvWvWV5L/attention7.png",
            "https://i.ibb.co/LXDFkC4b/attention8.png",
            "https://i.ibb.co/CpZLsxY9/attention9.png",
            "https://i.ibb.co/NckXJpm/attention10.png",
            "https://i.ibb.co/G4V0KJs6/attention11.png",
            "https://i.ibb.co/W4npmXnp/1.png",
            "https://i.ibb.co/q30D5pn9/2.png",
            "https://i.ibb.co/Y7KC3cyt/3.png",
            "https://i.ibb.co/XkpFYRmX/4.png",
        ]

    async def cog_load(self):
        await self._refresh_invites()

    async def _refresh_invites(self):
        async with self._lock:
            for guild in self.bot.guilds:
                try:
                    invites = await guild.invites()
                except Exception:
                    continue
                self.invite_cache[guild.id] = {inv.code: inv.uses or 0 for inv in invites}

    @commands.Cog.listener()
    async def on_ready(self):
        # Обновляем кэш инвайтов при старте.
        await self._refresh_invites()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        guild = member.guild
        inviter = None

        try:
            invites_before = self.invite_cache.get(guild.id, {})
            invites_now = await guild.invites()
            for inv in invites_now:
                before_count = invites_before.get(inv.code, 0)
                now_count = inv.uses or 0
                if now_count > before_count:
                    inviter = inv.inviter
                    break
            # Обновляем кэш
            self.invite_cache[guild.id] = {inv.code: inv.uses or 0 for inv in invites_now}
        except Exception:
            pass

        channel = guild.get_channel(WELCOME_CHANNEL_ID) or self.bot.get_channel(WELCOME_CHANNEL_ID)
        if channel is None:
            return

        inviter_text = inviter.mention if inviter else "неизвестно"
        content = f"{member.mention} присоединяется к нам по приглашению {inviter_text}"

        description = (
            "Для подачи заявки в нашу семью переходите в канал <#1495255487061426286>.\n"
            "Для получения роли **Family Friends/Best Friend** обращайтесь к старшему составу семьи предварительно изменив ник по форме.\n"
            "`Пример: Friend Milo | Имя Static`\n\n"
            "В канале <#1495255508368490506> Вы сможете получить приятный бонус за введённый промокод `/SERENITY`.\n"
            "В разделе Guides собраны разного рода памятки, гайды и ссылки на полезные ресурсы.\n"
            "**Ждём именно твою заявку!**"
        )

        embed = discord.Embed(
            title="<:serenity:1391919045309104309> Добро пожаловать в Serenity!",
            description=description,
            color=discord.Color.from_rgb(255, 255, 255),
        )
        embed.set_image(url=random.choice(self.images))

        try:
            await channel.send(content=content, embed=embed)
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
