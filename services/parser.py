import asyncio
import os
from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest
from datetime import datetime, timedelta
from config import settings
from database.bd import db
from database.logging import log
from aiogram import Bot

session_dir = "database/session"
system_bot = Bot(token=settings.bot_token)
os.makedirs(session_dir, exist_ok=True)
session_path = os.path.join(session_dir, "userbot")

active_sources = set()

client = TelegramClient(
    session_path,
    settings.api_id, 
    settings.api_hash,
    timeout=10,
    connection_retries=3,
    retry_delay=2
    )

album_buffers = {}

@client.on(events.NewMessage)
async def handle_new_message(event):
    chat_id = event.chat_id
    chat_username = getattr(event.chat, "username", None)

    is_source = False
    for src in db.get_sources():
        channel = str(src.get("channel", "")).lstrip('@')
        if chat_username and chat_username.lower() == channel.lower():
            is_source = True
            break
        elif str(chat_id) == channel or str(chat_id) == f'-100{channel}':
            is_source = True
            break
    
    if not is_source:
        return
        
    try:
        text = event.text or ""

        if event.grouped_id:
            gid = event.grouped_id
            if gid not in album_buffers:
                album_buffers[gid] = [event]
                await asyncio.sleep(1.5)

                events_list = album_buffers.pop(gid, [])
                if events_list:
                    first_event = events_list[0]
                    channel_name = first_event.chat.title if first_event.chat else first_event.chat_id
                    log.info(f"Отправляем альбом (ID: {first_event.id}-{events_list[-1].id}) из канала {channel_name}")

                    msg_objects = [e.message for e in events_list]
                    await client.forward_messages(settings.bot_username, msg_objects)
            else:
                album_buffers[gid].append(event)
            return

        channel_name = event.chat.title if event.chat else event.chat_id
        log.info(f"Отправляем одиночный пост (ID: {event.id}) из канала {channel_name}")
        await client.forward_messages(settings.bot_username, event.message)

    except Exception as e:
        log.error(f"Ошибка при обработке/пересылке сообщения: {e}")


async def check_and_subscribe(channel: str):
    try:
        clear_channel = channel.lstrip('@')
        if clear_channel.replace('-', '').isdigit():
            entity_to_join = int(clear_channel)
        else:
            entity_to_join = clear_channel

        try:
            await client.get_entity(entity_to_join)
        except Exception:
            await client(JoinChannelRequest(entity_to_join))
            log.info(f"Успешная подписка на канал: {channel}")
            return
        
        log.info(f"Канал уже доступен: {channel}")
    except Exception as e:
        log.error(f"Ошибка при подписке на {channel}: {e}")

async def sync_sources_task():
    global active_sources
    while True:
        try:
            sources = db.get_sources()
            now = datetime.now()
            current_sources = set()
            db_updated = False

            for src in sources:
                channel = src.get("channel")
                date_str = src.get("end_date")
                notified = src.get("notified", False)

                if date_str and date_str != "Бессрочно":
                    try:
                        expire_dt = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
                        if now >= expire_dt:
                            log.warning(f"Срок подписки канала {channel} Истёк, удаляем")
                            db.remove_source(channel)

                            try:
                                await system_bot.send_message(
                                    chat_id=settings.admin_id,
                                    text=f"⚠️<b>Подписка истекла!</b>\nКанал <code>{channel}</code> был автоматически удален из агрегатора."
                                )
                            except Exception as e:
                                log.error(f"Не удалось отправить сообщение в ЛС: {e}")
                            continue
                        
                        time_left = expire_dt - now
                        if time_left <= timedelta(days=1) and not notified:
                            log.info(f"Предупреждение у канала {channel} осталось меньше 24 часов подписки")
                            src["notified"] = True
                            db_updated = True

                            try:
                                await system_bot.send_message(
                                    chat_id=settings.admin_id,
                                    text=f"⏳ <b>Предупреждение о подписке!</b>\n"
                                         f"У канала <b>{channel}</b> подписка заканчивается через <b>{time_left.seconds // 3600} ч.</b> (до {date_str})."
                                )
                            except Exception as e:
                                log.error(f"Не удалось отправить предупреждение админу: {e}")

                    except ValueError:
                        pass
                current_sources.add(channel)
            
            if db_updated:
                data = db._load()
                data["sources"] = sources
                db._save(data)

            new_channels = current_sources - active_sources
            active_sources = current_sources

            for channel in new_channels:
                if channel:
                    await check_and_subscribe(channel)

        except Exception as e:
            log.error(f"Ошибка в цикле синхронизации источников: {e}")

        await asyncio.sleep(60)

