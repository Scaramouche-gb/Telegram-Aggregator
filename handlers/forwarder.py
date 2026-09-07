import asyncio
from aiogram import Router, Bot
from aiogram.types import Message
from database.bd import db
from database.logging import log

router = Router()

bot_album_buffers = {}
bot_processed_groups = set()
bot_processed_messages = set()

@router.message()
async def forward_to_target(message: Message, bot: Bot):
    if message.text and message.text.startswith('/'):
        return
    
    if not db.get_reply_mode():
        return

    content_text = message.text or message.caption or ""
    
    for word in db.get_ignore_words():
        if word.lower() in content_text.lower():
            log.info(f"Сообщение {message.message_id} заблокировано (стоп слово '{word}')")
            await message.reply(f"<b>Сообщение не переслано</b>\n\nНайдено стоп слово '{word}'", parse_mode="HTML")
            return

    target = db.get_target_channel()
    if not target:
        log.warning("Сообщение получено, но целевой канал (target) не установлен!")
        return

    # 1. Если это АЛЬБОМ (медиа-группа) со стороны бота
    if message.media_group_id:
        mg_id = message.media_group_id
        if mg_id in bot_processed_groups:
            return

        if mg_id not in bot_album_buffers:
            bot_album_buffers[mg_id] = [message.message_id]
            await asyncio.sleep(2.0)

            msg_ids = bot_album_buffers.pop(mg_id, [])
            if msg_ids and mg_id not in bot_processed_groups:
                bot_processed_groups.add(mg_id)
                if len(bot_processed_groups) > 500:
                    bot_processed_groups.pop()

                try:
                    await bot.forward_messages(
                        chat_id=target,
                        from_chat_id=message.chat.id,
                        message_ids=msg_ids
                    )
                    log.info(f"Альбом из {len(msg_ids)} сообщений успешно переслан в целевой канал: {target}")
                except Exception as e:
                    log.error(f"Ошибка при пересылке альбома ботом в канал {target}: {e}")
        else:
            bot_album_buffers[mg_id].append(message.message_id)
        return

    # 2. Если это ОДИНОЧНОЕ сообщение
    if message.message_id in bot_processed_messages:
        return
    bot_processed_messages.add(message.message_id)
    if len(bot_processed_messages) > 1000:
        bot_processed_messages.pop()

    try:
        await bot.forward_message(
            chat_id=target,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        log.info(f"Сообщение успешно переслано в целевой канал: {target}")
    except Exception as e:
        log.error(f"Ошибка при пересылке ботом в канал {target}: {e}")
