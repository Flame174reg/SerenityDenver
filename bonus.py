import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import os
import json

# Путь к файлу для хранения ID сообщения с кнопкой
CACHE_FILE = "cached_message_id.json"

# Модальное окно для ввода данных персонажа и доказательства
class PromoModal(Modal, title="Данные персонажа"):
    statik = TextInput(
        label="#StaticID",
        placeholder="Введите статический ID персонажа",
        style=discord.TextStyle.paragraph,
        required=True
    )
    bank_account = TextInput(
        label="Номер банковского счёта",
        placeholder="Номер счёта можно посмотреть, открыв инвентарь и наведясь на банковскую карту",
        style=discord.TextStyle.paragraph,
        required=True
    )
    proof = TextInput(
        label="Доказательство ввода промокода",
        placeholder="Вставьте ссылку на скриншот полного экрана, загруженного на Imgur/Yapix",
        style=discord.TextStyle.paragraph,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        target_channel_id = 1495255508368490506
        mention_role_id = 1495255260321677462  # ID роли для упоминания
        channel = interaction.client.get_channel(target_channel_id)

        embed = discord.Embed(
            title="📥 Новый ответ на бонусы",
            color=discord.Color.green()
        )
        embed.add_field(name="Пользователь", value=interaction.user.mention, inline=False)
        embed.add_field(name="#StaticID", value=self.statik.value, inline=False)
        embed.add_field(name="Номер банковского счёта", value=self.bank_account.value, inline=False)
        embed.add_field(name="Доказательство ввода промокода", value=self.proof.value, inline=False)

        if channel:
            await channel.send(
                content=f"<@&{mention_role_id}>",
                embed=embed
            )

        await interaction.response.send_message("✅ Данные отправлены!", ephemeral=True)

# Кнопка для запуска модального окна
class PromoButton(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Получить бонусы",
        style=discord.ButtonStyle.primary,
        custom_id="promo:get_bonus"  # <-- обязательный параметр для persistent View
    )
    async def get_bonus(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(PromoModal())

# Кэшированное сообщение с кнопкой
class PromoCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cached_message_id = self.load_cached_message_id()

    def load_cached_message_id(self):
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as file:
                data = json.load(file)
                return data.get('message_id', None)
        return None

    def save_cached_message_id(self, message_id):
        with open(CACHE_FILE, 'w') as file:
            json.dump({'message_id': message_id}, file)

    async def send_embed_with_button(self, ctx):
        role_id = 1495255260321677462
        support_role_id = 1366915536818274406
        if discord.utils.get(ctx.author.roles, id=role_id):
            embed = discord.Embed(
                title="Как получить бонусы за промокод?",
                description=(
                    "```1. Введите команду /promo SERENITY в игровой чат.\n"
                    "2. Сделайте полный скриншот с подтверждением ввода команды.\n"
                    "3. Отправьте скриншот в качестве доказательства активации.\n"
                    "4. Ожидайте уведомление о начислении бонуса.```\n"
                    f"<@&{support_role_id}> — выдаётся всем, кто использует промокод и поддерживает нашу семью "
                    "на сервере Seattle.\n"
                    "Также данная роль присваивается всем, кто оказал помощь семье. Это может быть финансовая помощь в развитии семьи, организация и участие в мероприятиях, предоставление ресурсов или любая иная значимая помощь, направленная на укрепление и развитие нашей семьи. Список не является исчерпывающим."
                ),
                color=discord.Color.from_rgb(255, 255, 255)
            )
            embed.set_image(url="https://i.imgur.com/46TDn4m.png")
            embed.set_footer(text="Регистрируйтесь и присоединяйтесь — мы ждём вас на Seattle!")

            channel = self.bot.get_channel(1495255508368490506)
            if channel:
                if self.cached_message_id:
                    try:
                        cached_message = await channel.fetch_message(self.cached_message_id)
                        await cached_message.edit(embed=embed, view=PromoButton())
                    except discord.NotFound:
                        message = await channel.send(embed=embed, view=PromoButton())
                        self.save_cached_message_id(message.id)
                        self.cached_message_id = message.id
                else:
                    message = await channel.send(embed=embed, view=PromoButton())
                    self.save_cached_message_id(message.id)
                    self.cached_message_id = message.id
        else:
            msg = await ctx.send("❌ У вас нет прав на использование этой команды.")
            await msg.delete(delay=5)

    @commands.command(name="madam")
    async def madam_command(self, ctx):
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        await self.send_embed_with_button(ctx)

# Асинхронная регистрация когы
async def setup(bot: commands.Bot):
    await bot.add_cog(PromoCommand(bot))
    bot.add_view(PromoButton())  # Регистрация persistent кнопки
