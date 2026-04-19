import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import random
import re

GUILD_ID = 1334888994496053282
BIRTHDAY_CHANNEL_ID = 1350539298637873162
birthday_data = {}  # user_id: {"date": "12.07", "wish": "..."}
congrated_today = set()

congrats = [
    "Желаем счастья, здоровья и много радости!",
    "Пусть сбудется всё, о чём мечтаешь!",
    "Ты делаешь этот мир лучше — с днём рождения!",
    "Пусть каждый день будет как праздник!",
    "Твоя семья гордится тобой!",
    "Оставайся таким же светлым человеком!",
    "Счастья, вдохновения и добра тебе!",
    "Ты заслуживаешь только самого лучшего!",
    "Спасибо, что ты с нами! С праздником!",
    "Сегодня твой день — улыбайся!",
    "Ты даришь тепло — прими его в ответ!",
    "Пусть жизнь будет полна удивительных моментов!",
    "Окружай себя любовью и уютом!",
    "Ты важен для нас — с днюхой!",
    "Пусть впереди будет только свет!",
    "Светись, сияй, удивляй!",
    "Пусть этот день будет волшебным!",
    "Пусть исполняется задуманное!",
    "Ты заслуживаешь бесконечных радостей!",
    "С днём рождения от всей души!"
]

async def load_birthdays_from_channel(channel):
    birthday_data.clear()
    async for msg in channel.history(limit=100):
        if msg.author.bot and msg.embeds:
            embed = msg.embeds[0]
            if embed.title and "Новый день рождения!" in embed.title:
                match = re.search(r"<:.*?:\d+> <@(\d+)> (\d{2}\.\d{2}) празднует", embed.description)
                wish_match = re.search(r"\*\*Пожелания:\*\* (.+)", embed.description)
                if match:
                    user_id, date = match.groups()
                    wish = wish_match.group(1) if wish_match else "—"
                    birthday_data[user_id] = {"date": date, "wish": wish.strip()}

class BirthdayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Указать дату", style=discord.ButtonStyle.primary, custom_id="birthday_button")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BirthdayModal())

class BirthdayModal(discord.ui.Modal, title="Укажите свою дату рождения"):
    birthday = discord.ui.TextInput(label="Ваш день Рождения:", placeholder="например, 12.07", required=True)
    wish = discord.ui.TextInput(label="Ваши пожелания:", placeholder="Чего бы вы хотели в этот день?", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        date = self.birthday.value.strip()

        if not date.count(".") == 1 or not all(part.isdigit() for part in date.split(".")):
            await interaction.response.send_message("Неверный формат даты. Используйте формат день.месяц (например, 12.07)", ephemeral=True)
            return

        embed = discord.Embed(
            title="Новый день рождения!",
            description=f"<:serenity:1391919340022005900> <@{user.id}> {date} празднует свой день рождения!\n\n:confetti_ball: **Пожелания:** {self.wish.value.strip() or '—'}",
            color=discord.Color.from_rgb(255, 255, 255)
        )

        channel = interaction.client.get_channel(BIRTHDAY_CHANNEL_ID)
        await channel.send(embed=embed)

        # Удалить старое сообщение с кнопкой и отправить новое
        async for msg in channel.history(limit=20):
            if msg.author == interaction.client.user and msg.embeds:
                if msg.embeds[0].title and "Укажите дату рождения" in msg.embeds[0].title:
                    await msg.delete()
                    break

        await channel.send(
            embed=discord.Embed(
                title="Укажите дату рождения! 🎂",
                description=(
                    "Нажмите на кнопку ниже и введите дату рождения в формате \"день.месяц\" (например, 12.07).\n"
                    "Добавьте пожелание — и мы вас поздравим!"
                ),
                color=discord.Color.from_rgb(255, 255, 255)
            ),
            view=BirthdayView()
        )

        await interaction.response.send_message("Дата успешно добавлена!", ephemeral=True)

class Birthday(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_birthdays.start()

    async def cog_load(self):
        self.bot.add_view(BirthdayView())
        guild = discord.Object(id=GUILD_ID)
        self.bot.tree.add_command(self.birthday_command, guild=guild)

    @commands.Cog.listener()
    async def on_ready(self):
        channel = self.bot.get_channel(BIRTHDAY_CHANNEL_ID)
        await load_birthdays_from_channel(channel)
        await channel.send(
            embed=discord.Embed(
                title="Укажите дату рождения! 🎂",
                description=(
                    "Нажмите на кнопку ниже и введите дату рождения в формате \"день.месяц\" (например, 12.07).\n"
                    "Добавьте пожелание — и мы вас поздравим!"
                ),
                color=discord.Color.from_rgb(255, 255, 255)
            ),
            view=BirthdayView()
        )

    @app_commands.command(name="др", description="Отправить сообщение с кнопкой")
    async def birthday_command(self, interaction: discord.Interaction):
        channel = interaction.client.get_channel(BIRTHDAY_CHANNEL_ID)
        await channel.send(
            embed=discord.Embed(
                title="Укажите дату рождения! 🎂",
                description=(
                    "Нажмите на кнопку ниже и введите дату рождения в формате \"день.месяц\" (например, 12.07).\n"
                    "Добавьте пожелание — и мы вас поздравим!"
                ),
                color=discord.Color.from_rgb(255, 255, 255)
            ),
            view=BirthdayView()
        )
        await interaction.response.send_message("Сообщение отправлено!", ephemeral=True)

    @tasks.loop(minutes=5)
    async def check_birthdays(self):
        now = datetime.datetime.now()
        today = f"{str(now.day).zfill(2)}.{str(now.month).zfill(2)}"

        channel = self.bot.get_channel(BIRTHDAY_CHANNEL_ID)
        await load_birthdays_from_channel(channel)

        for user_id, info in birthday_data.items():
            key = f"{today}_{user_id}"
            if info.get("date") == today and key not in congrated_today:
                await channel.send(f"Сегодня <@{user_id}> празднует свой День Рождения! {random.choice(congrats)}")
                congrated_today.add(key)

async def setup(bot):
    await bot.add_cog(Birthday(bot))
