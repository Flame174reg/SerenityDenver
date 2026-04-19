import discord
from discord.ext import commands
import os
import datetime
import contextlib
from discord.ui import Button, View, TextInput, Modal

TOKEN = os.getenv("TOKEN")
APPLICATION_CHANNEL_ID = 1342034595830435850
SUBMIT_CHANNEL_ID = 1357057778551619824
ROLE_IDS = [1334890846226485388, 1334890792040267776]
GUILD_ID = 1334888994496053282
ACCEPT_CHANNEL_ID = 1334889794857206002

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.messages = True
intents.invites = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)


def current_time():
    """Return an aware UTC datetime for Discord to localize on clients."""
    return datetime.datetime.now(datetime.timezone.utc)


async def load_extension_safe(name):
    try:
        await bot.load_extension(name)
        print(f"✅ Загружено расширение: {name}")
    except Exception as e:
        print(f"❌ Ошибка при загрузке {name}: {e}")


@bot.event
async def on_ready():
    try:
        extensions = [
            "bonus", "news", "bronya", "report_db", "payouts", "attendance_stats",
            "promotion", "embed_modal", "birthday", "Otpysk",
            "giveaways", "logger_cog", "database",
            "role_parser", "contracts", "welcome", "temp_voice", "cars"
        ]
        for ext in extensions:
            await load_extension_safe(ext)

        print(f"✅ Бот запущен. Используй !sync для синхронизации команд.")

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="/promo SERENITY"
        )
        await bot.change_presence(
            status=discord.Status.online,
            activity=activity
        )

    except Exception as e:
        print(f"Ошибка при инициализации бота: {e}")


@bot.command()
@commands.is_owner()
async def sync(ctx):
    """Синхронизировать slash-команды (только для владельца бота)"""
    try:
        await ctx.message.delete()
    except:
        pass

    msg = await ctx.send("🔄 Синхронизация команд...")

    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        await msg.edit(content=f"✅ Синхронизировано {len(synced)} команд(ы).")
    except Exception as e:
        await msg.edit(content=f"❌ Ошибка: {e}")


class RejectionReasonModal(Modal, title="Причина отказа"):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        self.reason_input = TextInput(
            label="Укажите причину отказа",
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            try:
                await interaction.response.defer(ephemeral=True)
            except discord.NotFound:
                return
        guild = bot.get_guild(GUILD_ID)
        member = guild.get_member(self.user_id)
        if member:
            try:
                await member.send(
                    f"К сожалению, вам отказано.\n"
                    f"Причина: {self.reason_input.value}"
                )
            except:
                pass
            await member.kick(
                reason=f"Отклонена заявка: {self.reason_input.value}"
            )

        # Добавляем статус и причину, затем удаляем кнопки
        original_message = interaction.message
        if original_message and original_message.embeds:
            embed = original_message.embeds[0]
            embed.color = discord.Color.from_rgb(255, 0, 0)
            embed.add_field(
                name="Статус",
                value=f"Заявка отклонена <@{interaction.user.id}>",
                inline=False
            )
            embed.add_field(
                name="Причина",
                value=self.reason_input.value,
                inline=False
            )
            await original_message.edit(embed=embed, view=None)

        await interaction.followup.send(
            "Заявка отклонена и пользователь исключён.",
            ephemeral=True
        )


class RejectionReasonView(View):
    def __init__(self, user_id: int, message_id: int, channel_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.message_id = message_id
        self.channel_id = channel_id

    async def _handle_rejection(self, interaction: discord.Interaction, reason_label: str, dm_text: str):
        if not interaction.response.is_done():
            try:
                await interaction.response.defer(ephemeral=True)
            except discord.NotFound:
                return

        guild = bot.get_guild(GUILD_ID)
        member = guild.get_member(self.user_id) if guild else None

        if member:
            try:
                await member.send(dm_text)
            except:
                pass
            await member.kick(reason=f"Отклонена заявка: {reason_label}")

        channel = bot.get_channel(self.channel_id)
        if channel:
            try:
                original_message = await channel.fetch_message(self.message_id)
            except (discord.NotFound, discord.Forbidden):
                original_message = None

            if original_message and original_message.embeds:
                embed = original_message.embeds[0]
                embed.color = discord.Color.from_rgb(255, 0, 0)
                embed.add_field(
                    name="Решение",
                    value=f"Заявка отклонена <@{interaction.user.id}>",
                    inline=False
                )
                embed.add_field(
                    name="Причина",
                    value=reason_label,
                    inline=False
                )
                await original_message.edit(embed=embed, view=None)

        if interaction.message:
            with contextlib.suppress(discord.HTTPException):
                await interaction.message.edit(
                    content="Заявка отклонена и пользователь исключён.",
                    view=None
                )

        with contextlib.suppress(discord.HTTPException):
            await interaction.followup.send(
                "Заявка отклонена и пользователь исключён.",
                ephemeral=True
            )

    @discord.ui.button(label="Требования", style=discord.ButtonStyle.secondary)
    async def reject_requirements(self, interaction: discord.Interaction, _: discord.ui.Button):
        dm_text = (
            "К сожалению, Вы не соответствуете требованиям для вступления. "
            "Причина связана с правилами семьи и условиями набора участников."
        )
        await self._handle_rejection(interaction, "Требования", dm_text)

    @discord.ui.button(label="Неккоректная", style=discord.ButtonStyle.secondary)
    async def reject_incorrect(self, interaction: discord.Interaction, _: discord.ui.Button):
        dm_text = (
            "К сожалению Ваша заявка заполнена не по форме. Прочитайте внимательно вопросы и "
            "заполните вновь. Вот ссылка - https://discord.gg/4YX46cs39M. "
            "При некорректном заполнении заявки во второй раз мы будем вынуждены занести Вас в ЧС."
        )
        await self._handle_rejection(interaction, "Неккоректная", dm_text)


class ApplicationModal(discord.ui.Modal, title="Подача заявки в Serenity"):
    def __init__(self):
        super().__init__(title="Подача заявки в Serenity")

        self.nickname_input = TextInput(
            label="RP имя, фамилия, StaticID, имя и возраст IRL?",
            max_length=1000,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.nickname_input)

        self.experience_input = TextInput(
            label="Был ли у Вас опыт в гос. семьях?",
            max_length=1000,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.experience_input)

        self.reasons_input = TextInput(
            label="Почему Вы выбрали нашу семью?",
            max_length=1000,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.reasons_input)

        self.discovery_input = TextInput(
            label="Как Вы узнали о нашей семье?",
            max_length=1000,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.discovery_input)

        self.values_input = TextInput(
            label="Какие ожидания у вас от семьи?",
            max_length=1000,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.values_input)

    async def on_submit(self, interaction: discord.Interaction):
        application_data = {
            "nickname": self.nickname_input.value,
            "experience": self.experience_input.value,
            "reasons": self.reasons_input.value,
            "discovery": self.discovery_input.value,
            "values": self.values_input.value,
            "user_id": interaction.user.id,
            "user_name": interaction.user.name
        }

        embed = discord.Embed(
            title="Новая заявка на вступление в Serenity",
            color=discord.Color.from_rgb(255, 255, 255)
        )
        embed.add_field(
            name="RP имя, фамилия, StaticID, имя и возраст IRL?",
            value=self.nickname_input.value,
            inline=False
        )
        embed.add_field(
            name="Был ли у Вас опыт в гос. семьях?",
            value=self.experience_input.value,
            inline=False
        )
        embed.add_field(
            name="Почему Вы выбрали нашу семью?",
            value=self.reasons_input.value,
            inline=False
        )
        embed.add_field(
            name="Как Вы узнали о нашей семье?",
            value=self.discovery_input.value,
            inline=False
        )
        embed.add_field(
            name="Какие ожидания у вас от семьи?",
            value=self.values_input.value,
            inline=False
        )
        embed.add_field(
            name="Пользователь",
            value=f"<@{interaction.user.id}>",
            inline=False
        )
        embed.add_field(
            name="Username и ID",
            value=f"`{interaction.user.name}` | `{interaction.user.id}`",
            inline=False
        )
        embed.timestamp = current_time()

        # Кнопки без callback, только с custom_id (всё обрабатываем в on_interaction)
        accept_button = Button(
            label="Принять",
            style=discord.ButtonStyle.success,
            custom_id=f"application_accept:{application_data['user_id']}"
        )
        reject_button = Button(
            label="Отклонить",
            style=discord.ButtonStyle.danger,
            custom_id=f"application_reject:{application_data['user_id']}"
        )

        view = View(timeout=None)
        view.add_item(accept_button)
        view.add_item(reject_button)

        channel = bot.get_channel(APPLICATION_CHANNEL_ID)
        if channel:
            await channel.send(
                content=f"<@&1345130001338601563> <@&1370868838240878592>",
                embed=embed,
                view=view
            )

        await interaction.response.send_message(
            "Ваша заявка отправлена. Ожидайте рассмотрения!",
            ephemeral=True
        )


@bot.command()
async def new(ctx):
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        print("Нет прав на удаление сообщения.")
    except discord.HTTPException as e:
        print(f"Ошибка удаления: {e}")

    channel = bot.get_channel(SUBMIT_CHANNEL_ID)

    if channel:
        embed = discord.Embed(
            title="Заявка на вступление в семью Serenity",
            description=(
                "Перед подачей заявки внимательно и подробно ответьте на все вопросы.\n"
                "Заявки, заполненные с ошибками или не соответствующие правилам семьи, будут отклонены.\n\n"
                "После отправки заявки дождитесь её рассмотрения — Бот свяжется с вами в личных сообщениях, "
                "уведомит о результате и при положительном решении направит в приёмную."
            ),
            color=discord.Color.from_rgb(255, 255, 255)
        )
        embed.set_image(url="https://i.ibb.co/nNTmPtQK/image.png")

        button = Button(
            label="Подать заявку",
            style=discord.ButtonStyle.primary,
            custom_id="submit_application"
        )
        view = View()
        view.add_item(button)

        await channel.send(embed=embed, view=view)
    else:
        await ctx.send("Канал подачи заявки не найден.")


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return

    custom_id = interaction.data.get("custom_id", "")

    # Кнопка подачи заявки
    if custom_id == "submit_application":
        await interaction.response.send_modal(ApplicationModal())
        return

    # Кнопка принятия заявки
    if custom_id.startswith("application_accept:"):
        try:
            user_id = int(custom_id.split(":", 1)[1])
        except ValueError:
            await interaction.response.send_message(
                "Ошибка обработки заявки (неверный формат custom_id).",
                ephemeral=True
            )
            return

        guild = bot.get_guild(GUILD_ID)
        member = guild.get_member(user_id) if guild else None

        if member:
            for role_id in ROLE_IDS:
                role = guild.get_role(role_id)
                if role:
                    await member.add_roles(role)
            try:
                await member.send(
                    "Вы приняты! Как будет время и возможность, "
                    "свяжитесь с High Staff семьи или перейдите в канал "
                    "<#1334889794857206002> прямо сейчас."
                )
            except:
                pass

        if interaction.message and interaction.message.embeds:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.from_rgb(0, 255, 0)
            embed.add_field(
                name="Статус",
                value=f"Заявка принята <@{interaction.user.id}>",
                inline=False
            )
            await interaction.message.edit(embed=embed, view=None)

        await interaction.response.send_message(
            "Заявка принята.",
            ephemeral=True
        )
        return

    # Кнопка отклонения заявки
    if custom_id.startswith("application_reject:"):
        try:
            user_id = int(custom_id.split(":", 1)[1])
        except ValueError:
            await interaction.response.send_message(
                "Ошибка обработки заявки (неверный формат custom_id).",
                ephemeral=True
            )
            return

        view = RejectionReasonView(
            user_id=user_id,
            message_id=interaction.message.id,
            channel_id=interaction.channel_id
        )
        await interaction.response.send_message(
            "Выберите причину отказа:",
            view=view,
            ephemeral=True
        )
        return


bot.run(TOKEN)
