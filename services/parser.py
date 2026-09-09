import asyncio
import os
from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest
from datetime import datetime, timedelta
from config import settings
from database.bd import db
from database.logging import log

session_dir = "database/session"
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
processed_grouped_ids = {}  # gid -> timestamp
processed_msg_ids = {}      # (chat_id, msg_id) -> timestamp
parser_lock = asyncio.Lock()

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

    now_ts = asyncio.get_event_loop().time()
        
    try:
        text = event.text or ""

        # 1. АЛЬБОМЫ
        if event.grouped_id:
            gid = event.grouped_id
            
            async with parser_lock:
                # Если альбом уже отправлен недавно (в пределах 60 сек) - игнорируем
                if gid in processed_grouped_ids:
                    return

                if gid not in album_buffers:
                    album_buffers[gid] = [event]
                    # Запускаем сбор группы в отдельном таске, чтобы не блокировать обработчик
                    asyncio.create_task(process_album(gid))
                else:
                    album_buffers[gid].append(event)
            return

        # 2. ОДИНОЧНЫЕ СООБЩЕНИЯ
        unique_key = (chat_id, event.id)
        async with parser_lock:
            if unique_key in processed_msg_ids and (now_ts - processed_msg_ids[unique_key]) < 60:
                return
            processed_msg_ids[unique_key] = now_ts

            # Очистка старых ключей (старше 300 сек)
            if len(processed_msg_ids) > 1000:
                expired = [k for k, t in processed_msg_ids.items() if now_ts - t > 300]
                for k in expired:
                    del processed_msg_ids[k]

        channel_name = event.chat.title if event.chat else event.chat_id
        log.info(f"Отправляем одиночный пост (ID: {event.id}) из канала {channel_name}")
        await client.forward_messages(settings.bot_username, event.message)

    except Exception as e:
        log.error(f"Ошибка при обработке/пересылке сообщения: {e}")

async def process_album(gid):
    await asyncio.sleep(2.5)
    async with parser_lock:
        if gid in processed_grouped_ids:
            album_buffers.pop(gid, None)
            return

        events_list = album_buffers.pop(gid, [])
        if not events_list:
            return

        processed_grouped_ids[gid] = asyncio.get_event_loop().time()
        if len(processed_grouped_ids) > 500:
            now_ts = asyncio.get_event_loop().time()
            expired = [g for g, t in processed_grouped_ids.items() if now_ts - t > 300]
            for g in expired:
                del processed_grouped_ids[g]

    try:
        first_event = events_list[0]
        channel_name = first_event.chat.title if first_event.chat else first_event.chat_id
        log.info(f"Отправляем альбом (ID: {first_event.id}-{events_list[-1].id}) из канала {channel_name}")

        msg_objects = [e.message for e in events_list]
        await client.forward_messages(settings.bot_username, msg_objects)
    except Exception as e:
        log.error(f"Ошибка при отправке альбома {gid}: {e}")


async def check_and_subscribe(channel: str):
    try:
        clear_channel = channel.lstrip('@')
        if clear_channel.replace('-', '').isdigit():
            entity_to_join = int(clear_channel)
        else:
            entity_to_join = clear_channel

        try:
            entity = await client.get_entity(entity_to_join)
        except Exception:
            entity = await client(JoinChannelRequest(entity_to_join))
            log.info(f"Успешная подписка на канал: {channel}")
            
        title = getattr(entity, 'title', '')
        if title:
            db.update_source_title(channel, title)

        log.info(f"Канал уже доступен: {title or channel}")
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

                if not src.get("title") and channel:
                    await check_and_subscribe(channel)

                if date_str and date_str != "Бессрочно":
                    try:
                        expire_dt = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
                        if now >= expire_dt:
                            log.warning(f"Срок подписки канала {channel} Истёк, удаляем")
                            db.remove_source(channel)

                            try:
                                await client.send_message(
                                    'me',
                                    f"⚠️ **Подписка истекла!**\nКанал `{channel}` был автоматически удален из агрегатора.",
                                    parse_mode='md'
                                )
                            except Exception as e:
                                log.error(f"Не удалось отправить сообщение в Избранное: {e}")
                            continue
                        
                        time_left = expire_dt - now
                        if time_left <= timedelta(days=1) and not notified:
                            log.info(f"Предупреждение у канала {channel} осталось меньше 24 часов подписки")
                            src["notified"] = True
                            db_updated = True

                            hours_left = int(time_left.total_seconds() // 3600)
                            try:
                                await client.send_message(
                                    'me',
                                    f"⏳ **Предупреждение о подписке!**\n"
                                    f"У канала **{channel}** подписка заканчивается через **{hours_left} ч.** (до {date_str}).",
                                    parse_mode='md'
                                )
                            except Exception as e:
                                log.error(f"Не удалось отправить предупреждение в Избранное: {e}")

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

