import re
import discord
from discord import app_commands
from discord.ext import commands

ROLE_ID = 1345130001338601563
GUILD_ID = 1334888994496053282
CHANNEL_ID = 1370884710993236109

EMBED_TITLE = "Запись участников"
CLOSE_MARKER = "Запись закрыта."


class SignUpModal(discord.ui.Modal, title="Открыть запись на контракт"):
    title_input = discord.ui.TextInput(label="Название контракта:", max_length=100)
    max_participants = discord.ui.TextInput(
        label="Максимальное количество участников:",
        style=discord.TextStyle.short,
    )

    def __init__(self, interaction: discord.Interaction, bot: commands.Bot):
        super().__init__()
        self.interaction = interaction
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            max_count = int(self.max_participants.value)
        except ValueError:
            await interaction.response.send_message(
                "Укажи число в поле максимального количества участников.",
                ephemeral=True,
            )
            return

        content = (
            f"Открыта запись на контракт: {self.title_input.value}\n"
            f"Запись открыта: {interaction.user.mention}\n"
            f"Максимальное количество участников: {max_count}"
        )

        view = SignUpView(interaction.user, max_count, content)
        embed = view.build_embed()

        channel = interaction.guild.get_channel(CHANNEL_ID)
        if not channel:
            await interaction.response.send_message(
                "Не удалось найти канал для записи.", ephemeral=True
            )
            return

        message = await channel.send(content=content, embed=embed, view=view)
        view.message = message
        await interaction.response.send_message("Запись открыта!", ephemeral=True)


class SignUpView(discord.ui.View):
    def __init__(
        self,
        creator: discord.User,
        max_participants: int,
        content: str,
        participants: list[discord.abc.User] | None = None,
        closed: bool = False,
        message: discord.Message | None = None,
    ):
        super().__init__(timeout=None)
        self.creator = creator
        self.max_participants = max_participants
        self.participants: list[discord.abc.User] = participants or []
        self.message: discord.Message | None = message
        self.closed = closed
        self.content = content
        self.refresh_buttons()

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title=EMBED_TITLE, color=discord.Color.from_rgb(255, 255, 255))
        if self.participants:
            description = "\n".join(
                f"{i + 1}. {getattr(user, 'mention', f'<@{user.id}>')}"
                for i, user in enumerate(self.participants)
            )
        else:
            description = "Нет записанных участников."
        embed.add_field(name="**Участники:**", value=description, inline=False)
        if self.closed:
            embed.set_footer(text=CLOSE_MARKER)
        return embed

    def is_creator_or_role(self, user: discord.Member) -> bool:
        return user == self.creator or any(role.id == ROLE_ID for role in user.roles)

    def refresh_buttons(self) -> None:
        self.clear_items()
        self.add_item(self.join)
        self.add_item(self.leave)
        if self.closed:
            self.add_item(self.open)
        else:
            self.add_item(self.close)
        self.add_item(self.silent_close)

    @discord.ui.button(label="➕", style=discord.ButtonStyle.secondary, custom_id="signup_join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            await interaction.response.send_message("Запись закрыта.", ephemeral=True)
            return

        if interaction.user in self.participants:
            await interaction.response.send_message("Ты уже записан.", ephemeral=True)
            return

        if len(self.participants) >= self.max_participants:
            await interaction.response.send_message(
                "Достигнуто максимальное число участников.", ephemeral=True
            )
            return

        self.participants.append(interaction.user)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="➖", style=discord.ButtonStyle.secondary, custom_id="signup_leave")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            await interaction.response.send_message(
                "Запись закрыта. Напиши ведущему, если нужно выйти.", ephemeral=True
            )
            return

        if interaction.user not in self.participants:
            await interaction.response.send_message("Ты не в списке.", ephemeral=True)
            return

        self.participants.remove(interaction.user)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="🔒", style=discord.ButtonStyle.secondary, custom_id="close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_creator_or_role(interaction.user):
            await interaction.response.send_message(
                "Нет прав закрывать эту запись.", ephemeral=True
            )
            return

        self.closed = True
        self.refresh_buttons()
        await self.message.edit(
            content=self.content + f"\n⚠️ {CLOSE_MARKER}", embed=self.build_embed(), view=self
        )
        await interaction.response.send_message("Запись закрыта.", ephemeral=True)

    @discord.ui.button(label="🔓", style=discord.ButtonStyle.secondary, custom_id="open")
    async def open(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_creator_or_role(interaction.user):
            await interaction.response.send_message(
                "Нет прав открывать эту запись.", ephemeral=True
            )
            return

        self.closed = False
        self.refresh_buttons()
        await self.message.edit(content=self.content, embed=self.build_embed(), view=self)
        await interaction.response.send_message("Запись открыта заново.", ephemeral=True)

    @discord.ui.button(
        label="✖️",
        style=discord.ButtonStyle.secondary,
        custom_id="silent_close",
    )
    async def silent_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_creator_or_role(interaction.user):
            await interaction.response.send_message(
                "Нет прав удалять кнопки.", ephemeral=True
            )
            return

        confirm_view = ConfirmDeleteView(self)
        warning_embed = discord.Embed(
            description=(
                "Внимание! Вы закрываете запись!\n"
                "Кнопки будут удалены. Записаться вновь будет невозможно.\n"
                "Участники более не смогут покинуть запись."
            ),
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=warning_embed, view=confirm_view, ephemeral=True)


class ConfirmDeleteView(discord.ui.View):
    def __init__(self, signup_view: SignUpView):
        super().__init__(timeout=60)
        self.signup_view = signup_view

    @discord.ui.button(label="Да. Я понимаю.", style=discord.ButtonStyle.secondary)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.signup_view.is_creator_or_role(interaction.user):
            await interaction.response.send_message("Нет прав удалять кнопки.", ephemeral=True)
            return

        self.signup_view.closed = True
        await self.signup_view.message.edit(
            content=self.signup_view.content + f"\n⚠️ {CLOSE_MARKER}",
            embed=self.signup_view.build_embed(),
            view=None,
        )
        await interaction.response.edit_message(content="Кнопки удалены. Запись закрыта.", embed=None, view=None)

    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Отменено.", embed=None, view=None)


class Bronya(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="броня", description="Открыть запись на контракт")
    async def броня(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild and not any(
            role.id == ROLE_ID for role in interaction.user.roles
        ):
            await interaction.response.send_message(
                "У тебя нет прав открывать запись.", ephemeral=True
            )
            return

        await interaction.response.send_modal(SignUpModal(interaction, self.bot))

    async def cog_load(self):
        guild = discord.Object(id=GUILD_ID)
        self.bot.tree.add_command(self.броня, guild=guild)
        await self.restore_signups()

    async def restore_signups(self):
        channel = self.bot.get_channel(CHANNEL_ID)
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        async for message in channel.history(limit=50):
            if message.author.id != self.bot.user.id:
                continue
            if not message.embeds or message.embeds[0].title != EMBED_TITLE:
                continue

            max_participants = self._parse_max_participants(message.content)
            creator = self._parse_creator(message)
            participants = self._parse_participants(message)
            closed = CLOSE_MARKER in message.content or (
                message.embeds[0].footer and message.embeds[0].footer.text == CLOSE_MARKER
            )

            view = SignUpView(
                creator=creator or message.author,
                max_participants=max_participants or max(len(participants), 1),
                content=message.content,
                participants=participants,
                closed=closed,
                message=message,
            )

            self.bot.add_view(view, message_id=message.id)

    def _parse_max_participants(self, content: str) -> int | None:
        match = re.search(r"Максимальное количество участников:\s*(\d+)", content)
        return int(match.group(1)) if match else None

    def _parse_creator(self, message: discord.Message) -> discord.abc.User | None:
        match = re.search(r"<@!?(\d+)>", message.content)
        if not match:
            return None
        user_id = int(match.group(1))
        if message.guild:
            member = message.guild.get_member(user_id)
            if member:
                return member
        return self.bot.get_user(user_id) or discord.Object(id=user_id)

    def _parse_participants(self, message: discord.Message) -> list[discord.abc.User]:
        if not message.embeds or not message.embeds[0].fields:
            return []
        field = message.embeds[0].fields[0]
        ids = re.findall(r"<@!?(\d+)>", field.value or "")
        participants: list[discord.abc.User] = []
        for user_id in ids:
            uid = int(user_id)
            member = message.guild.get_member(uid) if message.guild else None
            participants.append(member or self.bot.get_user(uid) or discord.Object(id=uid))
        return participants


async def setup(bot: commands.Bot):
    await bot.add_cog(Bronya(bot))
