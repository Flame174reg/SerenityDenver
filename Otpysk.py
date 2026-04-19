import discord
from discord.ext import commands
from discord import app_commands

# ID'ы
GUILD_ID = 1495254978418446376
ALLOWED_ROLE_ID = 1495255260321677462
VACATION_ROLE_ID = 1495255294924685492
CHANNEL_ID = 1495255612479770766

class VacationModal(discord.ui.Modal, title="Оформление отпуска"):
    period = discord.ui.TextInput(
        label="Период отпуска",
        placeholder="Пример: С 01.01 по 12.01",
        required=True,
        max_length=100
    )
    reason = discord.ui.TextInput(
        label="Причина отсутствия",
        placeholder="Новогодние праздники провожу с семьёй",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=300
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛫 Новый отпуск",
            description=f"**Пользователь:** {interaction.user.mention}\n"
                        f"**Период:** {self.period.value}\n"
                        f"**Причина:** {self.reason.value}",
            color=discord.Color.from_rgb(255, 255, 255)
        )
        channel = interaction.client.get_channel(CHANNEL_ID)
        await channel.send(embed=embed)

        # Выдача роли отпуска
        await interaction.user.add_roles(interaction.guild.get_role(VACATION_ROLE_ID))

        await interaction.response.send_message("Отпуск оформлен и роль выдана.", ephemeral=True)

        # Обновление основного сообщения с кнопками
        await self.refresh_form(channel, interaction.client)

    async def refresh_form(self, channel: discord.TextChannel, client: discord.Client):
        # Удаление предыдущих сообщений бота с кнопками
        async for message in channel.history(limit=50):
            if message.author == client.user and message.components:
                await message.delete()

        embed = discord.Embed(
            title="📋 Оформление отпуска",
            description="Оформите отпуск, если планируете отсутствовать более 3 дней.\n"
                        "После выбора даты вам будет выдана соответствующая роль.\n"
                        "По возвращении нажмите 'Вернулся/лась', чтобы снять роль.\n\n"
                        "Пожалуйста, не пользуйтесь без необходимости.",
            color=discord.Color.from_rgb(255, 255, 255)
        )
        view = VacationButtons()
        await channel.send(embed=embed, view=view)

class VacationButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Отпуск", style=discord.ButtonStyle.secondary, emoji="🚣", custom_id="vacation_request")
    async def vacation_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if VACATION_ROLE_ID in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message(
                "Вы уже находитесь в отпуске. Нажмите 'Вернулся/лась', чтобы снять роль.", ephemeral=True
            )
        else:
            await interaction.response.send_modal(VacationModal())

    @discord.ui.button(label="Вернулся/лась", style=discord.ButtonStyle.secondary, emoji="👷", custom_id="vacation_return")
    async def return_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if VACATION_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("У вас нет роли отпуска.", ephemeral=True)
            return

        await interaction.user.remove_roles(interaction.guild.get_role(VACATION_ROLE_ID))
        await interaction.response.send_message("Добро пожаловать обратно! Роль снята.", ephemeral=True)

        channel = interaction.client.get_channel(CHANNEL_ID)
        await channel.send(f"{interaction.user.mention} вернулся/лась из отпуска.")

        # Обновление основного сообщения с кнопками
        await self.refresh_form(channel, interaction.client)

    async def refresh_form(self, channel: discord.TextChannel, client: discord.Client):
        # Удаление предыдущих сообщений бота с кнопками
        async for message in channel.history(limit=50):
            if message.author == client.user and message.components:
                await message.delete()

        embed = discord.Embed(
            title="📋 Оформление отпуска",
            description="Оформите отпуск, если планируете отсутствовать более 3 дней.\n"
                        "После выбора даты вам будет выдана соответствующая роль.\n"
                        "По возвращении нажмите 'Вернулся/лась', чтобы снять роль.\n\n"
                        "Пожалуйста, не пользуйтесь без необходимости.",
            color=discord.Color.from_rgb(255, 255, 255)
        )
        view = VacationButtons()
        await channel.send(embed=embed, view=view)

class Otpysk(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="отпуск", description="Оформление отпуска")
    async def otpysk(self, interaction: discord.Interaction):
        if ALLOWED_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("У вас нет прав для использования этой команды.", ephemeral=True)
            return

        channel = interaction.client.get_channel(CHANNEL_ID)
        await self.refresh_form(channel, interaction.client)
        await interaction.response.send_message("Информация отправлена в канал.", ephemeral=True)

    async def refresh_form(self, channel: discord.TextChannel, client: discord.Client):
        # Удаление предыдущих сообщений бота с кнопками
        async for message in channel.history(limit=50):
            if message.author == client.user and message.components:
                await message.delete()

        embed = discord.Embed(
            title="📋 Оформление отпуска",
            description="Оформите отпуск, если планируете отсутствовать более 3 дней.\n"
                        "После выбора даты вам будет выдана соответствующая роль.\n"
                        "По возвращении нажмите 'Вернулся/лась', чтобы снять роль.\n\n"
                        "Пожалуйста, не пользуйтесь без необходимости.",
            color=discord.Color.from_rgb(255, 255, 255)
        )
        view = VacationButtons()
        await channel.send(embed=embed, view=view)

    async def cog_load(self):
        guild = discord.Object(id=GUILD_ID)
        self.bot.tree.add_command(self.otpysk, guild=guild)
        self.bot.add_view(VacationButtons())

async def setup(bot):
    await bot.add_cog(Otpysk(bot))
