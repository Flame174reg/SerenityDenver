import asyncio
import discord
from discord import app_commands
from discord.ext import commands

GUILD_ID = 1495254978418446376
ROLE_ID = 1495255260321677462
CHANNEL_ID = 1495255591751520317
RANK_ROLE_IDS = [
    1495255217825124442,  # BEGINNER (1 ранг)
    1495255211957027017,  # JUNIOR (2 ранг)
    1495255266369998959,  # ETHEREAL (3 ранг)
    1495255199059804180,  # SENTINEL (4 ранг)
    1495255205711843478,  # AMBIENT (5 ранг)
    1495255230164762704,  # ARIAL (6 ранг)
]
FORM_TITLE = "<a:bear:1453171719878742068> Отчёт на Повышение"

class PromotionView(discord.ui.View):
    def __init__(self, promotion_cog):
        super().__init__(timeout=None)
        self.promotion_cog = promotion_cog

    @discord.ui.button(label="Повыситься", style=discord.ButtonStyle.success, custom_id="submit_report_button")
    async def submit_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.guild is None:
            await interaction.response.send_message("Эта кнопка работает только в сервере.", ephemeral=True)
            return

        modal = PromotionModal(self.promotion_cog, interaction.user)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Смена фамилии", style=discord.ButtonStyle.primary, custom_id="name_change_button")
    async def name_change(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.guild is None:
            await interaction.response.send_message("Эта кнопка работает только в сервере.", ephemeral=True)
            return

        modal = NameChangeModal(self.promotion_cog, interaction.user)
        await interaction.response.send_modal(modal)

class PromotionModal(discord.ui.Modal, title="Подать отчёт на повышение"):
    def __init__(self, promotion_cog, user):
        super().__init__()
        self.promotion_cog = promotion_cog
        self.user = user

    goods_and_metallurgy = discord.ui.TextInput(
        label="Явка на товары и Металлургию",
        placeholder="Скриншот с плашета.",
        required=False,
    )
    family_balance_top_up = discord.ui.TextInput(
        label="Пополнение баланса семьи",
        placeholder="Только для тех, кто выбрал повышение за деньги (Скрин с планшета).",
        required=False,
    )
    time_in_family = discord.ui.TextInput(
        label="Как давно в семье?",
        placeholder="Скриншот с планшета.",
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.client.get_channel(CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Не удалось найти канал для отчёта.", ephemeral=True)
            return

        user_tag = self.user.mention

        content = f"<@&{ROLE_ID}> Новый отчёт от {user_tag}"
        embed = discord.Embed(title=FORM_TITLE, color=discord.Color.from_rgb(255, 255, 255))
        embed.add_field(
            name="Явка на товары и Металлургию",
            value=self.goods_and_metallurgy.value or "Не указано",
            inline=False,
        )
        embed.add_field(
            name="Пополнение баланса семьи",
            value=self.family_balance_top_up.value or "Не указано",
            inline=False,
        )
        embed.add_field(name="Как давно в семье?", value=self.time_in_family.value, inline=False)
        embed.set_footer(text="We are Serenity.")

        view = ActionView(self.user)

        await channel.send(content=content, embed=embed, view=view)
        await interaction.response.send_message("Ваш отчёт был отправлен!", ephemeral=True)

        await self.promotion_cog.refresh_form(channel)

class NameChangeModal(discord.ui.Modal, title="Смена фамилии"):
    def __init__(self, promotion_cog, user):
        super().__init__()
        self.promotion_cog = promotion_cog
        self.user = user

    proof = discord.ui.TextInput(
        label="Доказательства смены фамилии:",
        placeholder="Скрин с планшета",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.client.get_channel(CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Не удалось найти канал для отчёта.", ephemeral=True)
            return

        user_tag = self.user.mention

        content = f"<@&{ROLE_ID}> Запрос смены фамилии от {user_tag}"
        embed = discord.Embed(title="<a:bear:1453171719878742068> Смена Фамилии", color=discord.Color.from_rgb(255, 255, 255))
        embed.add_field(name="Доказательства смены фамилии", value=self.proof.value, inline=False)
        embed.set_footer(text="We are Serenity.")

        view = ActionView(self.user)

        await channel.send(content=content, embed=embed, view=view)
        await interaction.response.send_message("Ваш запрос на повышение был отправлен!", ephemeral=True)

        await self.promotion_cog.refresh_form(channel)

class ActionView(discord.ui.View):
    def __init__(self, report_author):
        super().__init__(timeout=None)
        self.report_author = report_author
        self.report_author_id = getattr(report_author, "id", None)
        self.report_author_tag = getattr(report_author, "mention", str(report_author))

    @discord.ui.button(label="Одобрить", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("У вас нет прав для этого действия.", ephemeral=True)
            return

        member = None
        if interaction.guild and self.report_author_id is not None:
            member = interaction.guild.get_member(self.report_author_id)
            if member is None:
                try:
                    member = await interaction.guild.fetch_member(self.report_author_id)
                except discord.NotFound:
                    member = None

        if member is None:
            await interaction.response.send_message("Не удалось найти участника, повышение не выдано.", ephemeral=True)
            return

        current_index = None
        current_role = None
        for idx in range(len(RANK_ROLE_IDS) - 1, -1, -1):
            role = member.get_role(RANK_ROLE_IDS[idx])
            if role:
                current_index = idx
                current_role = role
                break

        if current_index is None:
            await interaction.response.send_message("У участника нет повышаемых рангов.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]

        if current_index == len(RANK_ROLE_IDS) - 1:
            embed.color = discord.Color.orange()
            content = (
                "Отчёт обработан.\n"
                f"Подано: {self.report_author_tag}\n"
                f"Обработал: {interaction.user.mention}\n"
                "Статус: уже максимальный ранг, повышение не требуется."
            )
            await interaction.message.edit(content=content, embed=embed, view=None)
            try:
                notice = discord.Embed(
                    title="Максимальный ранг",
                    description="Вы и так максимальный ранг. Куда собрался, молодой?",
                    color=discord.Color.orange(),
                )
                await member.send(embed=notice)
            except discord.Forbidden:
                pass
            await interaction.response.send_message("Пользователь уже на максимальном ранге.", ephemeral=True)
            return

        next_role_id = RANK_ROLE_IDS[current_index + 1]
        next_role = interaction.guild.get_role(next_role_id) if interaction.guild else None
        if not next_role:
            await interaction.response.send_message("Не удалось найти роль следующего ранга.", ephemeral=True)
            return

        try:
            if current_role:
                await member.remove_roles(current_role, reason="Повышение по отчёту")
            await member.add_roles(next_role, reason="Повышение по отчёту")
        except discord.Forbidden:
            await interaction.response.send_message("Недостаточно прав для изменения ролей.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        content = (
            f"<a:check_raveninha:1348277505659764756> Отчёт одобрен.\n"
            f"Подано: {self.report_author_tag}\n"
            f"Одобрил: {interaction.user.mention}\n"
            f"Новый ранг: {next_role.mention}"
        )

        await interaction.message.edit(content=content, embed=embed, view=None)
        await interaction.response.send_message("Отчёт одобрен.", ephemeral=True)

    @discord.ui.button(label="Отказать", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("У вас нет прав для этого действия.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        content = (
            f"<a:uncheck_raveninha:1348277499284557937> Отчёт отклонён.\n"
            f"Подано: {self.report_author_tag}\n"
            f"Отклонил: {interaction.user.mention}"
        )

        await interaction.message.edit(content=content, embed=embed, view=None)
        await interaction.response.send_message("Отчёт отклонён.", ephemeral=True)

class Promotion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.form_message_id = None
        self.restore_task = None

    async def cog_load(self):
        self.bot.tree.add_command(self.promotion, guild=discord.Object(id=GUILD_ID))
        self.bot.add_view(PromotionView(self))
        self.restore_task = self.bot.loop.create_task(self._restore_existing_form())

    async def _restore_existing_form(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(CHANNEL_ID)
        if not channel or not self.bot.user:
            return

        form_messages = []
        async for message in channel.history(limit=50):
            if message.author.id != self.bot.user.id:
                continue
            if not message.embeds:
                continue
            if message.embeds[0].title != FORM_TITLE:
                continue
            form_messages.append(message)

        if form_messages:
            form_messages.sort(key=lambda m: m.created_at, reverse=True)
            latest = form_messages[0]
            self.form_message_id = latest.id
            for idx, duplicate in enumerate(form_messages[1:], start=1):
                if idx > 5:
                    break
                try:
                    await duplicate.delete()
                except discord.HTTPException:
                    pass
                await asyncio.sleep(0.25)
        else:
            await self.refresh_form(channel)

    async def refresh_form(self, channel: discord.TextChannel):
        if self.form_message_id:
            try:
                old_msg = await channel.fetch_message(self.form_message_id)
                await old_msg.delete()
            except discord.NotFound:
                pass

        embed = discord.Embed(
            title=FORM_TITLE,
            description=(
                "Перед подачей отчёта, внимательно проверьте:\n"
                "1. Все ссылки должны быть рабочими и актуальными.\n"
                "2. Все условия для повышения должны быть выполнены полностью.\n\n"
                "**Несоблюдение этих пунктов может привести к отклонению отчёта.**"
            ),
            color=discord.Color.from_rgb(255, 255, 255)
        )
        embed.set_image(url="https://i.ibb.co/HL4Gq9Hs/FULL-HD-13.png")

        view = PromotionView(self)
        msg = await channel.send(embed=embed, view=view)
        self.form_message_id = msg.id

    @app_commands.command(name="повышение", description="Отправить форму на повышение")
    @app_commands.checks.has_role(ROLE_ID)
    async def promotion(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Не удалось найти канал.", ephemeral=True)
            return

        await self.refresh_form(channel)
        await interaction.response.send_message("Форма обновлена и отправлена в канал.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Promotion(bot))
