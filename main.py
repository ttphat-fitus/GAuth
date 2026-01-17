from __future__ import annotations

import asyncio
import os

import discord
from discord.errors import PrivilegedIntentsRequired
from discord.ext import commands
from dotenv import load_dotenv


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    raw = raw.strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


async def main() -> None:
    load_dotenv()

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("Missing DISCORD_TOKEN in .env")

    intents = discord.Intents.default()
    intents.members = _env_bool("ENABLE_MEMBERS_INTENT", default=False)

    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready() -> None:
        try:
            synced = await bot.tree.sync()
            print(f"[GAuth] started successfully")
        except Exception as exc:
            print(f"[GAuth] Command sync failed: {exc}")

    await bot.load_extension("cogs.verification")

    try:
        await bot.start(token)
    except PrivilegedIntentsRequired:
        await bot.close()
        raise
    except Exception:
        await bot.close()
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except PrivilegedIntentsRequired:
        print("[GAuth] PrivilegedIntentsRequired")
    except KeyboardInterrupt:
        pass
