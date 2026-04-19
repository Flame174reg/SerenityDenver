import os
import asyncio
import logging
from typing import List, Dict, Any

import asyncpg
from discord.ext import commands

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Базовое создание таблицы give (как сейчас использует giveaways.py)
SQL_INIT_GIVE = """
CREATE TABLE IF NOT EXISTS public.give (
    id           INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guild_id     BIGINT       NOT NULL,
    channel_id   BIGINT       NOT NULL,
    "name"       VARCHAR      NOT NULL,
    user_ids     VARCHAR      NULL,
    end_date     TIMESTAMPTZ  NOT NULL,
    finished     BOOLEAN      NOT NULL DEFAULT FALSE,
    messege_id   VARCHAR      NOT NULL,
    host_id      VARCHAR      NOT NULL,
    winner_count INT          NOT NULL
);
"""
#
# Дополнительные ALTER'ы на случай, если таблица уже была создана раньше
# и в ней нет каких-то новых колонок.
SQL_ALTER_GIVE = """
ALTER TABLE public.give
    ADD COLUMN IF NOT EXISTS guild_id     BIGINT;
ALTER TABLE public.give
    ADD COLUMN IF NOT EXISTS channel_id   BIGINT;
ALTER TABLE public.give
    ADD COLUMN IF NOT EXISTS "name"       VARCHAR;
ALTER TABLE public.give
    ADD COLUMN IF NOT EXISTS user_ids     VARCHAR;
ALTER TABLE public.give
    ADD COLUMN IF NOT EXISTS end_date     TIMESTAMPTZ;
ALTER TABLE public.give
    ADD COLUMN IF NOT EXISTS finished     BOOLEAN;
ALTER TABLE public.give
    ADD COLUMN IF NOT EXISTS messege_id   VARCHAR;
ALTER TABLE public.give
    ADD COLUMN IF NOT EXISTS host_id      VARCHAR;
ALTER TABLE public.give
    ADD COLUMN IF NOT EXISTS winner_count INT;
"""

# Базовое создание таблицы guild_settings
SQL_INIT_GUILD_SETTINGS = """
CREATE TABLE IF NOT EXISTS public.guild_settings (
    guild_id  BIGINT PRIMARY KEY,
    color_hex VARCHAR(6) NOT NULL DEFAULT '5865F2',
    emoji     VARCHAR(64) NOT NULL DEFAULT '🎉'
);
"""

# Дополнительные ALTER'ы для guild_settings
SQL_ALTER_GUILD_SETTINGS = """
ALTER TABLE public.guild_settings
    ADD COLUMN IF NOT EXISTS color_hex VARCHAR(6) NOT NULL DEFAULT '5865F2';
ALTER TABLE public.guild_settings
    ADD COLUMN IF NOT EXISTS emoji     VARCHAR(64) NOT NULL DEFAULT '🎉';
"""


class DatabaseManager:
    def __init__(self):
        self.connection: asyncpg.Connection | None = None
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is not set")

    async def connect(self):
        """Подключение к базе данных PostgreSQL"""
        if self.connection and not self.connection.is_closed():
            return

        try:
            self.connection = await asyncpg.connect(self.database_url)
            logger.info("Successfully connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    async def disconnect(self):
        """Отключение от базы данных"""
        if self.connection and not self.connection.is_closed():
            await self.connection.close()
            logger.info("Disconnected from database")

    async def init_schema(self):
        """
        Инициализация схемы БД:
        1) создаём таблицы give и guild_settings, если их ещё нет
        2) добавляем недостающие колонки через ALTER TABLE ... ADD COLUMN IF NOT EXISTS
        """
        if not self.connection or self.connection.is_closed():
            await self.connect()

        try:
            # Базовое создание
            await self.connection.execute(SQL_INIT_GIVE)
            await self.connection.execute(SQL_INIT_GUILD_SETTINGS)

            # Мягкое "обновление" структуры (добавление новых колонок, если они появились в коде)
            await self.connection.execute(SQL_ALTER_GIVE)
            await self.connection.execute(SQL_ALTER_GUILD_SETTINGS)

            logger.info("✅ Tables `give` and `guild_settings` are initialized/updated and ready.")
        except Exception as e:
            logger.error(f"Error while initializing/updating tables: {e}")
            raise

    async def get_test_data(self) -> List[Dict[str, Any]]:
        """Простая проверка: получение всех строк из таблицы give"""
        try:
            if not self.connection or self.connection.is_closed():
                await self.connect()

            query = "SELECT * FROM public.give"
            rows = await self.connection.fetch(query)

            data = [dict(row) for row in rows]

            logger.info(f"Retrieved {len(data)} records from `give` table")
            return data

        except Exception as e:
            logger.error(f"Error fetching data from `give` table: {e}")
            return []


class DatabaseMonitor(commands.Cog):
    """Ког, который инициализирует БД"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_manager = DatabaseManager()

    async def cog_load(self):
        await self.bot.wait_until_ready()
        try:
            await self.db_manager.connect()
            await self.db_manager.init_schema()
        except Exception as e:
            logger.error(f"Initial DB setup failed: {e}")

    def cog_unload(self):
        # Аккуратно закрываем соединение
        asyncio.create_task(self.db_manager.disconnect())

    # Если нужно — можно добавить команду для ручной проверки
    @commands.command(name="db_check")
    @commands.is_owner()
    async def db_check(self, ctx: commands.Context):
        """Ручная проверка БД"""
        data = await self.db_manager.get_test_data()
        await ctx.send(f"В таблице `give` сейчас {len(data)} записей.")


async def setup(bot: commands.Bot):
    await bot.add_cog(DatabaseMonitor(bot))
