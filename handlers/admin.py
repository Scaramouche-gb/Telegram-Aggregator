from datetime import datetime
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from config import settings
from database.bd import db

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    if str(message.from_user.id) == settings.admin_id:
        await message.answer(
            f"Список команд для администратора:\n\n"
            f"/start - список команд\n"
            f"/showsettings - показать количество каналов в агрегаторе \n"
            f"/replymode - переключить статус пересылки on/off \n"
            f"/addsource (ссылка, юзернейм или id канала) (количество дней) - добавить канал \n"
            f"/removesource (ссылка, юзернейм или id канала) - удалить канал \n"
            f"/ignore - открывает список игнор слов"
        )

@router.message(Command("showsettings"))
async def show_settings(message: Message):
    if str(message.from_user.id) == settings.admin_id:
        sources = db.get_sources()
        target = db.get_target_channel() or "Не установлен"
        reply_mode = "Включён" if db.get_reply_mode() else "Выключен"

        if not sources:
            sources_text = "<i>Каналы не добавлены</i>"
        else:
            sources_list = []
            now = datetime.now()
            
            for src in sources:
                channel = src.get("channel")
                title = src.get("title")
                date_str = src.get("end_date", "Бессрочно")
                display_name = f"<b>{title}</b> (<code>{channel}</code>)" if title else f"<b>{channel}</b>"

                if date_str and date_str != "Бессрочно":
                    try:
                        expire_dt = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
                        days_left = (expire_dt - now).days
                        left_str = f"({days_left} дн.)" if days_left > 0 else "(менее 1 дн.)"
                        date_display = f"до {date_str} {left_str}"
                    except ValueError:
                        date_display = f"до {date_str}"
                else:
                    date_display = "Бессрочно"
                
                sources_list.append(
                    f'<tg-emoji emoji-id="5474359500095890971">🔹</tg-emoji> {display_name} -- {date_display}'
                )
            sources_text = "\n".join(sources_list)

        await message.answer(
            f"<b>Настройки агрегатора</b>\n\n"
            f"<b>Целевой канал:</b> {target}\n\n"
            f"<b>Режим пересылки:</b> {reply_mode}\n\n"
            f"<b>Количество каналов в агрегаторе: {len(sources)}</b>\n\n"
            f"{sources_text}"
        )

@router.message(Command("addsource"))
async def add_source(message: Message):
    if str(message.from_user.id) == settings.admin_id:
        args = message.text.split(maxsplit=2)
        if len(args) < 2:
            await message.answer("Пожалуйста, укажите ссылку/юзернейм на канал.")
            return

        channel = args[1]
        days = None
        
        if len(args) == 3:
            try:
                days = int(args[2])
            except ValueError:
                await message.answer("Количество дней должно быть числом.")
                return

        db.add_source(channel, days)

        if days:
            await message.answer(f"Канал {channel} добавлен в агрегатор на {days} дней.")
        else:
            await message.answer(f"Канал {channel} добавлен в агрегатор <b>бессрочно</b>.")

@router.message(Command("removesource"))
async def remove_source(message: Message):
    if str(message.from_user.id) == settings.admin_id:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("Пожалуйста, укажите ссылку на канал.")
            return

        channel = args[1]
        db.remove_source(channel)
        await message.answer(f"Канал {channel} удален из агрегатора.")

@router.message(Command("ignore"))
async def ignore_words(message: Message):
    if str(message.from_user.id) == settings.admin_id:
        ignore_words = db.get_ignore_words()
        if not ignore_words:
            await message.answer("Список игнор слов пуст.")
            return

        ignore_list = "\n".join(ignore_words)
        await message.answer(f"<b>Список игнор слов:</b>\n\n{ignore_list}")

@router.message(Command("settarget"))
async def set_target_channel(message: Message):
    if str(message.from_user.id) == settings.admin_id:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("Пожалуйста, укажите ссылку на канал.")
            return
        
        raw_channel = args[1].strip()

        try:
            channel = int(raw_channel)
        except ValueError:
            channel = raw_channel

        db.set_target_channel(channel)
        await message.answer(f"Канал {channel} установлен как целевой канал для пересылки.")

@router.message(Command("replymode"))
async def reply_mode(message: Message):
    if str(message.from_user.id) != settings.admin_id:
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        current_mode = "Включён" if db.get_reply_mode() else "Выключен"
        await message.answer(
            f"Текущий режим пересылки {current_mode}\n\n"
        )
        return
    
    mode_str = args[1].lower().strip()
    if mode_str == "on":
        db.set_reply_mode(True)
        await message.answer("Режим пересылки: ВКЛЮЧЁН")
    elif mode_str == "off":
        db.set_reply_mode(False)
        await message.answer("Режим пересылки: ВЫКЛЮЧЕН")
    else:
        await message.answer("Используйте только <code>on</code> или <code>off</code>")
