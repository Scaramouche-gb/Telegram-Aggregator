import asyncio 
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from config import settings
from database.logging import log
from handlers import admin, forwarder
from services.parser import client as userbot_client, sync_sources_task

dp = Dispatcher()
dp.include_router(admin.router)
dp.include_router(forwarder.router)

is_stopping = False

def global_exception_handler(loop, context):
    msg = context.get("exception", context["message"])
    log.error(f"Необработанное исключение в asyncio: {msg}")

async def run_supervised(name: str, coro_func):
    while True:
        try:
            log.info(f"Запуск сервиса {name}...")
            await coro_func()
        except (asyncio.CancelledError, KeyboardInterrupt):
            log.info(f"Сервис {name} остановлен штатно.")
            break
        except Exception as e:
            log.error(f"Сбой в {name}: {e}. Перезапуск через 5 секунд...", exc_info=True)
            await asyncio.sleep(5)

async def start_bot():
    session = AiohttpSession(timeout=10)
    bot = Bot(
            token=settings.bot_token,
            session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )    
    log.info("Telegram Бот запускает polling...")
    try:
        await dp.start_polling(bot, handle_signals=False)
    finally:
        await bot.session.close()

sync_task_started = False

async def start_userbot():
    global sync_task_started
    log.info("Запуск Telethon Юзербота...")
    if not userbot_client.is_connected():
        await userbot_client.start()
        log.info("[Telethon] Соединение установлено")
    
    if not sync_task_started:
        asyncio.create_task(sync_sources_task())
        sync_task_started = True

    await userbot_client.run_until_disconnected()

async def main():
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(global_exception_handler)

    log.info("Запуск Агрегатора...")

    bot_task = asyncio.create_task(run_supervised("Telegram Bot", start_bot))
    userbot_task = asyncio.create_task(run_supervised("Telethon Userbot", start_userbot))

    try:
        await asyncio.gather(bot_task, userbot_task)
    except (asyncio.CancelledError, KeyboardInterrupt):
        log.info("Получен сигнал на остановку процессов...")
    finally:
        log.info("Последовательное отключение сервисов...")

        bot_task.cancel()
        userbot_task.cancel()

        await asyncio.gather(bot_task, userbot_task, return_exceptions=True)

        if userbot_client.is_connected():
            await userbot_client.disconnect()
            log.info("Сессия Telethon отключена")
        
        log.info("Агрегатор полностью остановлен")

if __name__ == "__main__":
    try: 
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
