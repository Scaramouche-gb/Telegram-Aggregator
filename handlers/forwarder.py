from aiogram import Router, Bot
from aiogram.types import Message
from database.bd import db
from database.logging import log

router = Router()

@router.message()
async def forward_to_target(message: Message, bot: Bot):
    if message.text and message.text.startswith('/'):
        return
    
    if not db.get_reply_mode():
        return

    content_text = message.text or message.caption or ""
    
    for word in db.get_ignore_words():
        if word.lower() in content_text.lower():
            log.info(f"Сообщение {message.message_id} заблокировано (стоп слово {word})")
            await message.reply(f"<b>Сообщение не переслано</b>\n\nНайдено стоп слово '{word}'", parse_mode="HTML")
            return

    target = db.get_target_channel()
    if not target:
        log.warning("Сообщение получено, но целевой канал (target) не установлен!")
        return
    
    try:
        await bot.forward_message(
            chat_id=target,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        log.info(f"Сообщение успешно переслано в целевой канал: {target}")
    except Exception as e:
        log.error(f"Ошибка при пересылке ботом в канал {target}: {e}")
