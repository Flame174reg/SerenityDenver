# -*- coding: utf-8 -*-
# giveaways.py — гивэвеи с персистентными вьюхами, счётчиком участников и тегом роли над эмбедой.
# Требуется: discord.py >= 2.3  (pip install -U discord.py)

import asyncio
import contextlib
import datetime as dt
import os
import random
import re
from dataclasses import dataclass
from typing import Optional, Sequence, List, Tuple

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands, tasks

# === НАСТРОЙКИ ===
GUILD_ID = 1334888994496053282
ROLE_TAG_ID = 1334890846226485388  # тэгнем эту роль над эмбедой

# Postgres (public.give, public.guild_settings)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

# === УТИЛИТЫ ===
# поддерживаем и кириллицу, и латиницу в суффиксах: с/s, м/m, ч/h, д/d, w
DUR_RE = re.compile(r"(?P<value>\d+)\s*(?P<unit>[смчдwsmhd])", re.IGNORECASE)


def parse_duration(s: str) -> dt.timedelta:
    s = s.strip()
    if not s:
        raise ValueError("Пустая длительность")
    total = dt.timedelta()
    for m in DUR_RE.finditer(s):
        val = int(m.group("value"))
        unit = m.group("unit").lower()
        if unit in ("с", "s"):
            total += dt.timedelta(seconds=val)
        elif unit in ("м", "m"):
            total += dt.timedelta(minutes=val)
        elif unit in ("ч", "h"):
            total += dt.timedelta(hours=val)
        elif unit in ("д", "d"):
            total += dt.timedelta(days=val)
        elif unit in ("w",):
            total += dt.timedelta(weeks=val)
    if total.total_seconds() <= 0:
        raise ValueError("Неверная длительность")
    return total


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def fmt_dt(ts: dt.datetime) -> str:
    return discord.utils.format_dt(ts, style="R")


# === ДАННЫЕ (Postgres) ===
@dataclass
class Giveaway:
    id: int
    guild_id: int
    channel_id: int
    message_id: int
    prize: str
    winners_count: int
    ends_at: dt.datetime
    host_id: int
    finished: bool


DEFAULT_COLOR_HEX = "5865F2"
DEFAULT_COLOR_INT = int(DEFAULT_COLOR_HEX, 16)
DEFAULT_EMOJI = "🎉"


_PG_POOL: Optional[asyncpg.Pool] = None
_PG_POOL_LOCK = asyncio.Lock()


async def pg_pool() -> asyncpg.Pool:
    global _PG_POOL
    if _PG_POOL and not _PG_POOL._closed:
        return _PG_POOL
    async with _PG_POOL_LOCK:
        if _PG_POOL and not _PG_POOL._closed:
            return _PG_POOL
        _PG_POOL = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            timeout=10,
            command_timeout=30,
        )
        return _PG_POOL


async def pg_close_pool() -> None:
    global _PG_POOL
    if _PG_POOL:
        await _PG_POOL.close()
        _PG_POOL = None


def giveaway_from_row(row: asyncpg.Record) -> Giveaway:
    return Giveaway(
        id=int(row["id"]),
        guild_id=int(row["guild_id"]),
        channel_id=int(row["channel_id"]),
        message_id=int(row["messege_id"]),
        prize=row["name"],
        winners_count=int(row["winner_count"]),
        ends_at=row["end_date"].astimezone(dt.timezone.utc),
        host_id=int(row["host_id"]),
        finished=bool(row["finished"]),
    )


# === Postgres: таблица give ===

async def pg_create_give(
    guild_id: int,
    channel_id: int,
    prize: str,
    winners: int,
    ends_at: dt.datetime,
    host_id: int,
) -> int:
    """
    Создаёт запись в public.give БЕЗ message_id (messege_id='0' временно).
    Возвращает ID розыгрыша.
    """
    pool = await pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO public.give(
                guild_id, channel_id, "name",
                user_ids, end_date, finished,
                messege_id, host_id, winner_count
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
            """,
            guild_id,
            channel_id,
            prize,
            None,             # user_ids
            ends_at,
            False,            # finished
            "0",              # временно, потом обновим
            str(host_id),
            winners,
        )
        return int(row["id"])


async def pg_set_message_id(give_id: int, message_id: int) -> None:
    pool = await pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE public.give SET messege_id = $1 WHERE id = $2",
            str(message_id),
            give_id,
        )


async def pg_get_give(give_id: int) -> Optional[Giveaway]:
    pool = await pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, guild_id, channel_id, "name",
                   user_ids, end_date, finished,
                   messege_id, host_id, winner_count
            FROM public.give
            WHERE id = $1
            """,
            give_id,
        )
        if not row:
            return None
        return giveaway_from_row(row)


async def pg_list_running(guild_id: int) -> List[Giveaway]:
    pool = await pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, guild_id, channel_id, "name",
                   user_ids, end_date, finished,
                   messege_id, host_id, winner_count
            FROM public.give
            WHERE guild_id = $1 AND finished = FALSE
            ORDER BY end_date ASC
            """,
            guild_id,
        )
        return [giveaway_from_row(r) for r in rows]


async def pg_due() -> List[Giveaway]:
    """
    Все розыгрыши, у которых пора подводить итоги.
    """
    pool = await pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, guild_id, channel_id, "name",
                   user_ids, end_date, finished,
                   messege_id, host_id, winner_count
            FROM public.give
            WHERE finished = FALSE AND end_date <= NOW()
            """
        )
        return [giveaway_from_row(r) for r in rows]


async def pg_set_finished(give_id: int, finished: bool) -> None:
    pool = await pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE public.give SET finished = $1 WHERE id = $2",
            finished,
            give_id,
        )


async def pg_mark_running(give_id: int) -> None:
    await pg_set_finished(give_id, False)


async def pg_mark_ended(give_id: int) -> None:
    await pg_set_finished(give_id, True)


async def pg_get_user_ids(give_id: int) -> List[int]:
    pool = await pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_ids FROM public.give WHERE id = $1",
            give_id,
        )
        if not row or row["user_ids"] is None:
            return []
        parts = [p for p in str(row["user_ids"]).split(",") if p.strip()]
        return [int(p) for p in parts]


async def pg_set_user_ids(give_id: int, user_ids: List[int]) -> None:
    pool = await pg_pool()
    async with pool.acquire() as conn:
        user_ids_str = ",".join(str(uid) for uid in user_ids) if user_ids else None
        await conn.execute(
            "UPDATE public.give SET user_ids = $1 WHERE id = $2",
            user_ids_str,
            give_id,
        )


async def pg_toggle_entry(give_id: int, user_id: int) -> tuple[bool, List[int]]:
    """
    Добавляет или удаляет участника.
    Возвращает (joined, current_user_ids).
    joined = True  -> пользователь добавлен
    joined = False -> пользователь удалён
    """
    pool = await pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_ids FROM public.give WHERE id = $1 FOR UPDATE",
            give_id,
        )
        current: set[int] = set()
        if row and row["user_ids"]:
            for p in str(row["user_ids"]).split(","):
                p = p.strip()
                if p:
                    current.add(int(p))

        joined: bool
        if user_id in current:
            current.remove(user_id)
            joined = False
        else:
            current.add(user_id)
            joined = True

        user_ids_list = sorted(current)
        user_ids_str = ",".join(str(uid) for uid in user_ids_list) if user_ids_list else None

        await conn.execute(
            "UPDATE public.give SET user_ids = $1 WHERE id = $2",
            user_ids_str,
            give_id,
        )

        return joined, user_ids_list


# === Postgres: guild_settings ===

async def get_guild_settings(guild_id: int) -> Tuple[int, str]:
    """
    Получить настройки гильдии (color_int, emoji) из Postgres.guild_settings.
    Если записи нет — создаём дефолт и возвращаем его.
    """
    pool = await pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT color_hex, emoji FROM public.guild_settings WHERE guild_id = $1",
            guild_id,
        )
        if row:
            color_hex = row["color_hex"] or DEFAULT_COLOR_HEX
            emoji = row["emoji"] or DEFAULT_EMOJI
            return int(color_hex, 16), emoji

        # Строки нет — создаём с дефолтами
        await conn.execute(
            """
            INSERT INTO public.guild_settings (guild_id)
            VALUES ($1)
            ON CONFLICT (guild_id) DO NOTHING
            """,
            guild_id,
        )
        return DEFAULT_COLOR_INT, DEFAULT_EMOJI


async def set_guild_color(guild_id: int, color_hex: str) -> None:
    color_hex = color_hex.strip().lstrip("#").upper()
    int(color_hex, 16)  # валидация

    pool = await pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO public.guild_settings (guild_id, color_hex)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE
            SET color_hex = EXCLUDED.color_hex
            """,
            guild_id,
            color_hex,
        )


async def set_guild_emoji(guild_id: int, emoji: str) -> None:
    emoji = emoji.strip()
    if not emoji:
        raise ValueError("Эмодзи не может быть пустым")

    pool = await pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO public.guild_settings (guild_id, emoji)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE
            SET emoji = EXCLUDED.emoji
            """,
            guild_id,
            emoji,
        )


# === EMBED/VIEW ===

def emb_running(
    g: Giveaway,
    color: int,
    join_emoji: str,
    host: discord.User,
    participants: int,
    display_id: Optional[int] = None,
) -> discord.Embed:
    """
    display_id — ID, который хотим показывать в футере (например, Postgres ID).
    Если None — используется g.id.
    """
    e = discord.Embed(
        title=f"Розыгрыш: {g.prize}",
        description=(
            "Нажми кнопку ниже, чтобы участвовать.\n\n"
            f"Участников: **{participants}**\n"
            f"Завершение: {fmt_dt(g.ends_at)}\n"
            f"Хост: {host.mention}\n"
            f"Кол-во победителей: **{g.winners_count}**\n"
        ),
        color=color,
        timestamp=g.ends_at
    )
    real_id = display_id if display_id is not None else g.id
    e.set_footer(text=f"ID: {real_id} • Участвуй: {join_emoji}")
    return e


def emb_ended(
    g: Giveaway,
    color: int,
    winners: Sequence[discord.User],
    display_id: Optional[int] = None,
) -> discord.Embed:
    winners_ment = ", ".join(w.mention for w in winners) if winners else "никто 😢"
    e = discord.Embed(
        title=f"✅ Итоги розыгрыша: {g.prize}",
        description=f"Победители: {winners_ment}",
        color=color,
        timestamp=utcnow()
    )
    real_id = display_id if display_id is not None else g.id
    e.set_footer(text=f"ID: {real_id}")
    return e


def extract_display_id_from_embed(embed: discord.Embed) -> Optional[int]:
    """
    Вытаскиваем ID из футера вида:
        "ID: 123 • Участвуй: 🎉"
    """
    if not embed.footer or not embed.footer.text:
        return None
    text = embed.footer.text
    m = re.search(r"ID:\s*(\d+)", text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


class JoinView(discord.ui.View):
    """
    Персистентная вью (timeout=None) с уникальным custom_id для каждого розыгрыша.
    Работает только с Postgres (public.give).
    """
    def __init__(self, giveaway_id: int, join_emoji: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.join_emoji = join_emoji

        # Кнопка участия
        self.add_item(discord.ui.Button(
            label="Участвовать",
            style=discord.ButtonStyle.success,
            emoji=join_emoji,
            custom_id=f"gw:join:{giveaway_id}"
        ))

        # Кнопка "посмотреть участников"
        self.add_item(discord.ui.Button(
            label="Посмотреть участников",
            style=discord.ButtonStyle.secondary,
            custom_id=f"gw:list:{giveaway_id}"
        ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cid = str(interaction.data.get("custom_id", "")) if interaction.data else ""
        print(f"[giveaways] interaction_check called, custom_id={cid}")

        if not cid.startswith("gw:"):
            return True  # не наш кастом-айди

        # Быстро подтверждаем interaction, чтобы не протух
        if not interaction.response.is_done():
            with contextlib.suppress(discord.HTTPException):
                await interaction.response.defer(ephemeral=True)

        # --- JOIN ---
        if cid.startswith("gw:join:"):
            gid = int(cid.split(":")[-1])
            print(f"[giveaways] parsed giveaway id from button (join): {gid}")

            g = await pg_get_give(gid)
            if not g or g.finished or utcnow() >= g.ends_at:
                with contextlib.suppress(discord.HTTPException):
                    await interaction.followup.send("⛔ Розыгрыш уже завершён.", ephemeral=True)
                return False

            joined, user_ids = await pg_toggle_entry(gid, interaction.user.id)

            try:
                if joined:
                    await interaction.followup.send("Ты в списке участников! Удачи 🍀", ephemeral=True)
                else:
                    await interaction.followup.send("Ты вышел из розыгрыша.", ephemeral=True)
            except discord.HTTPException:
                pass

            # обновим эмбед со свежим количеством участников
            try:
                if g and interaction.message:
                    color, _ = await get_guild_settings(interaction.guild_id)
                    host = (
                        interaction.guild.get_member(g.host_id)
                        or await interaction.client.fetch_user(g.host_id)
                    )

                    participants = len(user_ids)

                    display_id = None
                    if interaction.message.embeds:
                        display_id = extract_display_id_from_embed(interaction.message.embeds[0])

                    new_embed = emb_running(
                        g, color, self.join_emoji, host, participants, display_id=display_id
                    )
                    await interaction.message.edit(embed=new_embed, view=self)
            except discord.HTTPException:
                pass

            return False

        # --- LIST PARTICIPANTS ---
        if cid.startswith("gw:list:"):
            gid = int(cid.split(":")[-1])
            print(f"[giveaways] parsed giveaway id from button (list): {gid}")

            g = await pg_get_give(gid)
            if not g or g.guild_id != interaction.guild_id:
                with contextlib.suppress(discord.HTTPException):
                    await interaction.followup.send("⛔ Розыгрыш не найден.", ephemeral=True)
                return False

            ids = await pg_get_user_ids(gid)
            if not ids:
                with contextlib.suppress(discord.HTTPException):
                    await interaction.followup.send("Пока никто не участвует.", ephemeral=True)
                return False

            guild = interaction.guild
            users: List[discord.abc.User] = []
            for uid in ids:
                member = guild.get_member(uid) if guild else None
                if member is None:
                    with contextlib.suppress(Exception):
                        member = await interaction.client.fetch_user(uid)
                if member:
                    users.append(member)

            if not users:
                text = "Участников не удалось получить."
            else:
                lines = [f"{idx + 1}. {u.mention}" for idx, u in enumerate(users)]
                text = f"Участники ({len(users)}):\n" + "\n".join(lines)
                if len(text) > 1900:
                    text = text[:1900] + "\n…"

            with contextlib.suppress(discord.HTTPException):
                await interaction.followup.send(text, ephemeral=True)

            return False

        return True


# === COG ===
class Giveaways(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._tick.start()

    def cog_unload(self):
        self._tick.cancel()
        asyncio.create_task(pg_close_pool())

    @tasks.loop(seconds=15)
    async def _tick(self):
        await self.bot.wait_until_ready()
        
        # End due giveaways (with delay between each to avoid rate limits)
        try:
            due_giveaways = await pg_due()
        except (asyncpg.PostgresError, TimeoutError, OSError) as e:
            print(f"[giveaways] pg_due failed: {e}")
            return
        for i, g in enumerate(due_giveaways):
            try:
                await self._end_and_announce(g)
                # Пауза между гивэвеями чтобы избежать rate limit
                if i < len(due_giveaways) - 1:
                    await asyncio.sleep(3)
            except Exception as e:
                print(f"[giveaways] failed to end {g.id}: {e}")

    async def _end_and_announce(self, g: Giveaway):
        guild = self.bot.get_guild(g.guild_id)
        if not guild:
            await pg_mark_ended(g.id)
            return

        channel = guild.get_channel(g.channel_id) or await guild.fetch_channel(g.channel_id)
        color, _ = await get_guild_settings(g.guild_id)

        ids = await pg_get_user_ids(g.id)
        members: List[discord.User] = []
        for uid in ids:
            member = guild.get_member(uid) or await self.bot.fetch_user(uid)
            if member:
                members.append(member)

        winners: List[discord.User] = []
        if members and g.winners_count > 0:
            winners = random.sample(members, k=min(len(members), g.winners_count))

        msg = None
        display_id = None
        if g.message_id:
            with contextlib.suppress(discord.NotFound, discord.Forbidden):
                msg = await channel.fetch_message(g.message_id)
                if msg and msg.embeds:
                    display_id = extract_display_id_from_embed(msg.embeds[0])


        try:
            if msg:
                with contextlib.suppress(discord.HTTPException):
                    await msg.edit(
                        embed=emb_ended(g, color, winners, display_id=display_id),
                        view=None
                    )
            else:
                with contextlib.suppress(discord.HTTPException, discord.Forbidden):
                    await channel.send(
                        embed=emb_ended(g, color, winners, display_id=display_id)
                    )

            dm_id = display_id if display_id is not None else g.id

            for w in winners:
                with contextlib.suppress(Exception):
                    await w.send(f"🎉 Ты выиграл(а) **{g.prize}** на сервере **{guild.name}**! (ID: {dm_id})")
        finally:
            await pg_mark_ended(g.id)

    # === СЛЭШ-КОМАНДЫ (РУС) ===

    @app_commands.command(name="розыгрыш", description="Запустить розыгрыш")
    @app_commands.describe(
        длительность="Например: 30м, 2ч, 1д или составное: 1ч30м",
        победителей="Количество победителей (1–50)",
        приз="Что разыгрывается"
    )
    async def cmd_start(
        self,
        itx: discord.Interaction,
        длительность: str,
        победителей: app_commands.Range[int, 1, 50],
        приз: str
    ):
        # Сразу скрыто подтверждаем interaction, чтобы не протух
        await itx.response.defer(ephemeral=True, thinking=True)

        try:
            delta = parse_duration(длительность)
        except ValueError:
            return await itx.followup.send(
                "⛔ Неверная длительность. Примеры: 30м, 2ч, 1д, 1ч30м",
                ephemeral=True
            )

        ends = utcnow() + delta

        # создаём запись в БД (без message_id)
        gid = await pg_create_give(
            guild_id=itx.guild_id,
            channel_id=itx.channel_id,
            prize=приз,
            winners=победителей,
            ends_at=ends,
            host_id=itx.user.id,
        )

        g = await pg_get_give(gid)
        if not g:
            return await itx.followup.send("⛔ Не удалось создать розыгрыш.", ephemeral=True)

        color, emoji = await get_guild_settings(itx.guild_id)
        view = JoinView(gid, emoji)
        participants = 0

        # Отправляем основное сообщение о розыгрыше в канал
        msg = await itx.channel.send(
            content=f"<@&{ROLE_TAG_ID}>",
            embed=emb_running(g, color, emoji, itx.user, participants, display_id=gid),
            view=view,
            allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False)
        )

        # обновляем message_id в БД
        await pg_set_message_id(gid, msg.id)

        # регистрируем персистентную вью
        self.bot.add_view(view)

        # и даём пользователю тихий ответ
        await itx.followup.send(
            f"✅ Розыгрыш **#{gid}** создан.",
            ephemeral=True
        )

    @app_commands.command(name="завершить", description="Завершить розыгрыш по ID")
    @app_commands.describe(id="ID розыгрыша")
    async def cmd_end(self, itx: discord.Interaction, id: int):
        # сначала скрыто подтверждаем interaction
        await itx.response.defer(ephemeral=True, thinking=True)

        g = await pg_get_give(id)
        if not g or g.guild_id != itx.guild_id:
            return await itx.followup.send("⛔ Розыгрыш не найден.", ephemeral=True)
        if g.finished:
            return await itx.followup.send("ℹ️ Уже завершён.", ephemeral=True)

        await self._end_and_announce(g)
        await itx.followup.send("✅ Завершено.", ephemeral=True)

    @app_commands.command(name="переролл", description="Перероллить победителей по ID")
    @app_commands.describe(id="ID розыгрыша (уже завершённого)")
    async def cmd_reroll(self, itx: discord.Interaction, id: int):
        # сразу скрыто подтверждаем interaction, чтобы не получить Unknown interaction
        await itx.response.defer(ephemeral=True, thinking=True)

        g = await pg_get_give(id)
        if not g or g.guild_id != itx.guild_id:
            return await itx.followup.send("⛔ Розыгрыш не найден.", ephemeral=True)
        if not g.finished:
            return await itx.followup.send("⛔ Сначала завершите розыгрыш.", ephemeral=True)

        # делаем его снова "running"
        await pg_mark_running(g.id)
        # читаем обновлённый (finished=False)
        g = await pg_get_give(g.id)

        await self._end_and_announce(g)
        await itx.followup.send("🔁 Переролл выполнен.", ephemeral=True)

    @app_commands.command(name="список", description="Показать активные розыгрыши")
    async def cmd_list(self, itx: discord.Interaction):
        items = await pg_list_running(itx.guild_id)
        if not items:
            return await itx.response.send_message("Пока активных розыгрышей нет.", ephemeral=True)
        lines = []
        for g in items:
            ch = itx.guild.get_channel(g.channel_id) if itx.guild else None
            ch_text = ch.mention if isinstance(ch, discord.abc.GuildChannel) else f"#{g.channel_id}"
            lines.append(
                f"**ID {g.id}** • {ch_text} • {g.prize} • "
                f"победителей: **{g.winners_count}** • завершение {fmt_dt(g.ends_at)}"
            )
        await itx.response.send_message("\n".join(lines), ephemeral=True)

    # группа настроек
    settings = app_commands.Group(
        name="настройки_розыгрыша",
        description="Настроить внешний вид и эмодзи"
    )

    @settings.command(name="показать", description="Показать текущие настройки")
    async def cmd_settings_show(self, itx: discord.Interaction):
        color, emoji = await get_guild_settings(itx.guild_id)
        e = discord.Embed(title="Настройки розыгрышей", color=color)
        e.add_field(name="Цвет эмбеда", value=f"#{color:06X}")
        e.add_field(name="Эмодзи кнопки", value=emoji)
        await itx.response.send_message(embed=e, ephemeral=True)

    @settings.command(name="изменить", description="Изменить цвет эмбеда или эмодзи кнопки участия")
    @app_commands.describe(цвет_hex="HEX без #, напр. FFCC00", эмодзи="Эмодзи кнопки участия")
    async def cmd_settings_set(
        self,
        itx: discord.Interaction,
        цвет_hex: Optional[str] = None,
        эмодзи: Optional[str] = None
    ):
        if not цвет_hex and not эмодзи:
            return await itx.response.send_message(
                "Укажи хотя бы один параметр: цвет_hex или эмодзи.",
                ephemeral=True
            )
        try:
            if цвет_hex:
                await set_guild_color(itx.guild_id, цвет_hex)
            if эмодзи:
                await set_guild_emoji(itx.guild_id, эмодзи)
        except Exception as e:
            return await itx.response.send_message(f"⛔ {e}", ephemeral=True)
        await itx.response.send_message("✅ Обновлено.", ephemeral=True)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.guild is not None

    async def cog_load(self):
        print("[giveaways] cog_load called")
        guild_obj = discord.Object(id=GUILD_ID)

        # регистрируем команды на конкретную гильдию
        self.bot.tree.add_command(self.cmd_start, guild=guild_obj)
        self.bot.tree.add_command(self.cmd_end, guild=guild_obj)
        self.bot.tree.add_command(self.cmd_reroll, guild=guild_obj)
        self.bot.tree.add_command(self.cmd_list, guild=guild_obj)
        self.bot.tree.add_command(self.settings, guild=guild_obj)

        # при загрузке — восстановим только персистентные вьюхи
        # просроченные гивэвеи обработает _tick через 15 сек (избегаем rate limit)
        try:
            _, emoji = await get_guild_settings(GUILD_ID)
            running = await pg_list_running(GUILD_ID)
            print(f"[giveaways] running giveaways on load: {[g.id for g in running]}")
            for g in running:
                print(f"[giveaways] add_view for giveaway {g.id}")
                self.bot.add_view(JoinView(g.id, emoji))
        except Exception as e:
            print("Persistent views restore failed:", e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaways(bot))
