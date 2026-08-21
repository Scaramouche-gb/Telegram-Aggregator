import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from telethon import TelegramClient
from config import settings
from database.logging import log

session_dir = "database/session"
os.makedirs(session_dir, exist_ok=True)
session_path = os.path.join(session_dir, "userbot")

client = TelegramClient(session_path, settings.api_id, settings.api_hash)

async def main():
    log.info("Запуск создание сессии")
    await client.start()

    me = await client.get_me()
    log.info(f"Успешная авторизация, Аккаунт {me.first_name} (@{me.username})")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

