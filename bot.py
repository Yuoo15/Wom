"""
🌸 Women's Day Invitation Bot — aiogram 3.7+
• /start    → приглашение с случайным цветом дресс-кода
• /invite   → рассылка по INVITE_LIST (только администратор)
• /stats    → статистика ответов (только администратор)
• /list     → список гостей с цветами (только администратор)
• /remind   → напомнить «Приду» и «Возможно» (только администратор)
• Авто-напоминание за 2 часа до события
• Блокировка ответа после первого нажатия
• Без базы данных
"""

import asyncio
import random
import logging
import os
from datetime import datetime, timezone, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

# ──────────────────────────────────────────────────────────────────────────────
#  НАСТРОЙКИ — читаются из переменных окружения Railway
# ──────────────────────────────────────────────────────────────────────────────

BOT_TOKEN     = os.getenv("BOT_TOKEN")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

CAFE_NAME     = "Black Fish kafesı"
CAFE_ADDRESS  = "улица Гагарина, 1В Карабалык"
EVENT_DATE    = "10 марта"
EVENT_TIME    = "19:00"

# Точное время события для авто-напоминания (UTC)
# UTC+5: 19:00 местного = 14:00 UTC
EVENT_DATETIME_UTC = datetime(2026, 3, 10, 14, 0, tzinfo=timezone.utc)

# Список username для /invite (без @)
INVITE_LIST = [
    "A1dus",
    "sfd",
    "userfsdfdsname3",
]

DRESS_COLORS = [
    "чёрный",
    "белый",
    "красный",
    "бордовый",
    "тёмно-синий",
    "изумрудный",
    "серебряный",
    "золотой",
]

# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp  = Dispatcher()

# ─── ХРАНИЛИЩЕ В ПАМЯТИ ───────────────────────────────────────────────────────

user_colors:   dict[int, str]  = {}
user_answered: dict[int, str]  = {}
user_names:    dict[int, str]  = {}
user_usernames: dict[int, str] = {}
auto_reminder_sent: set[int]   = set()

# ─── КЛАВИАТУРЫ ───────────────────────────────────────────────────────────────

def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Приду 🌸"),      KeyboardButton(text="Не смогу ❌")],
            [KeyboardButton(text="Возможно 🤔"),   KeyboardButton(text="Где находится? 📍")],
            [KeyboardButton(text="Дресс-код 👗"),  KeyboardButton(text="Кто будет? 👀")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери ответ...",
    )

def locked_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Где находится? 📍")],
            [KeyboardButton(text="Дресс-код 👗"),  KeyboardButton(text="Кто будет? 👀")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Ответ принят ✅",
    )

# ─── ТЕКСТЫ ───────────────────────────────────────────────────────────────────

def build_invite(color: str) -> str:
    return (
        "🌸 <b>Персональное приглашение</b>\n\n"
        "Привет 🙂\n\n"
        "Мы собираем небольшую компанию на вечер в кафе "
        f"в честь <b>International Women's Day</b>.\n"
        "Только приятные люди, уютная атмосфера и хороший вечер.\n\n"
        f"📍 <b>Место:</b> кафе {CAFE_NAME}\n"
        f"📅 <b>Дата:</b> {EVENT_DATE}\n"
        f"🕒 <b>Время:</b> {EVENT_TIME}\n\n"
        f"👗 <b>Твой дресс-код:</b> случайно выпал цвет — <b>{color}</b>.\n"
        "<i>Каждой гостье свой цвет — получится необычная атмосфера.</i>\n\n"
        "✨ Музыка, живое общение и приятная компания гарантированы.\n\n"
        "Количество мест ограничено — нажми кнопку ниже ⬇️"
    )

def build_reminder(color: str) -> str:
    return (
        "⏰ <b>Напоминание о вечере!</b>\n\n"
        f"Через 2 часа начинается наш вечер в кафе {CAFE_NAME}.\n\n"
        f"📍 {CAFE_ADDRESS}\n"
        f"🕒 {EVENT_TIME}\n"
        f"👗 Твой цвет: <b>{color}</b>\n\n"
        "Ждём тебя! 🌸"
    )

# ─── УВЕДОМЛЕНИЕ ОРГАНИЗАТОРУ ─────────────────────────────────────────────────

async def notify_admin(message: Message, answer_text: str) -> None:
    user     = message.from_user
    username = f" (@{user.username})" if user.username else ""
    color    = user_colors.get(user.id, "—")

    await bot.send_message(
        ADMIN_CHAT_ID,
        f"📩 <b>Новый ответ</b>\n\n"
        f"👤 {user.full_name}{username}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"👗 Цвет: <b>{color}</b>\n\n"
        f"💬 Ответ: <b>{answer_text}</b>",
    )

# ─── БЛОКИРОВКА ───────────────────────────────────────────────────────────────

async def is_locked(message: Message) -> bool:
    if message.from_user.id in user_answered:
        prev = user_answered[message.from_user.id]
        await message.answer(
            f"✅ Ты уже ответила: <b>{prev}</b>\n\n"
            "Ответ изменить нельзя. Если срочно — напиши организатору напрямую.",
            reply_markup=locked_keyboard(),
        )
        return True
    return False

# ─── СОХРАНЕНИЕ ПОЛЬЗОВАТЕЛЯ ──────────────────────────────────────────────────

def save_user(message: Message) -> None:
    uid = message.from_user.id
    user_names[uid]      = message.from_user.full_name
    user_usernames[uid]  = f"@{message.from_user.username}" if message.from_user.username else ""

# ─── /start ───────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    uid = message.from_user.id
    save_user(message)

    if uid in user_answered:
        color = user_colors.get(uid, "—")
        await message.answer(
            f"🌸 Ты уже зарегистрирована!\n\n"
            f"Твой ответ: <b>{user_answered[uid]}</b>\n"
            f"Твой цвет: <b>{color}</b>",
            reply_markup=locked_keyboard(),
        )
        return

    color = user_colors.setdefault(uid, random.choice(DRESS_COLORS))
    await message.answer(build_invite(color), reply_markup=main_keyboard())

# ─── /invite ──────────────────────────────────────────────────────────────────

@dp.message(Command("invite"))
async def cmd_invite(message: Message) -> None:
    if message.from_user.id != ADMIN_USER_ID:
        await message.answer("⛔️ Нет доступа.")
        return

    await message.answer(f"📤 Рассылка для {len(INVITE_LIST)} гостей...")

    sent, failed = 0, 0
    for username in INVITE_LIST:
        color = random.choice(DRESS_COLORS)
        try:
            await bot.send_message(
                chat_id=f"@{username}",
                text=build_invite(color),
                reply_markup=main_keyboard(),
            )
            sent += 1
        except Exception as e:
            logger.warning(f"❌ @{username}: {e}")
            failed += 1
        await asyncio.sleep(0.5)

    await message.answer(
        f"✅ Готово. Отправлено: <b>{sent}</b>, не удалось: <b>{failed}</b>"
    )

# ─── /stats ───────────────────────────────────────────────────────────────────

@dp.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if message.from_user.id != ADMIN_USER_ID:
        await message.answer("⛔️ Нет доступа.")
        return

    coming = sum(1 for v in user_answered.values() if v == "Приду 🌸")
    maybe  = sum(1 for v in user_answered.values() if v == "Возможно 🤔")
    no     = sum(1 for v in user_answered.values() if v == "Не смогу ❌")
    total  = len(user_answered)

    await message.answer(
        "📊 <b>Статистика ответов</b>\n\n"
        f"✅ Приду:      <b>{coming}</b>\n"
        f"🤔 Возможно:  <b>{maybe}</b>\n"
        f"❌ Не смогу:  <b>{no}</b>\n"
        f"──────────────\n"
        f"📋 Всего ответили: <b>{total}</b>"
    )

# ─── /list ────────────────────────────────────────────────────────────────────

@dp.message(Command("list"))
async def cmd_list(message: Message) -> None:
    if message.from_user.id != ADMIN_USER_ID:
        await message.answer("⛔️ Нет доступа.")
        return

    if not user_answered:
        await message.answer("📋 Пока никто не ответил.")
        return

    lines = ["📋 <b>Список гостей</b>\n"]
    emoji_map = {"Приду 🌸": "✅", "Возможно 🤔": "🤔", "Не смогу ❌": "❌"}

    for uid, answer in user_answered.items():
        name     = user_names.get(uid, f"id{uid}")
        username = user_usernames.get(uid, "")
        color    = user_colors.get(uid, "—")
        icon     = emoji_map.get(answer, "•")
        tag      = f" {username}" if username else ""
        lines.append(f"{icon} {name}{tag} — <b>{color}</b>")

    await message.answer("\n".join(lines))

# ─── /remind ──────────────────────────────────────────────────────────────────

@dp.message(Command("remind"))
async def cmd_remind(message: Message) -> None:
    if message.from_user.id != ADMIN_USER_ID:
        await message.answer("⛔️ Нет доступа.")
        return

    targets = {
        uid: ans for uid, ans in user_answered.items()
        if ans in ("Приду 🌸", "Возможно 🤔")
    }

    if not targets:
        await message.answer("Никого для напоминания нет.")
        return

    await message.answer(f"📢 Отправляю напоминание {len(targets)} гостям...")

    sent, failed = 0, 0
    for uid in targets:
        color = user_colors.get(uid, "—")
        try:
            await bot.send_message(
                uid,
                f"🌸 <b>Напоминание о вечере</b>\n\n"
                f"Не забудь — сегодня в <b>{EVENT_TIME}</b> ждём тебя в кафе {CAFE_NAME}!\n\n"
                f"📍 {CAFE_ADDRESS}\n"
                f"👗 Твой цвет: <b>{color}</b>\n\n"
                "До встречи! ✨",
                reply_markup=locked_keyboard(),
            )
            sent += 1
        except Exception as e:
            logger.warning(f"❌ uid {uid}: {e}")
            failed += 1
        await asyncio.sleep(0.4)

    await message.answer(
        f"✅ Напоминания отправлены: <b>{sent}</b>, не удалось: <b>{failed}</b>"
    )

# ─── КНОПКИ ОТВЕТА ────────────────────────────────────────────────────────────

@dp.message(F.text == "Приду 🌸")
async def btn_coming(message: Message) -> None:
    if await is_locked(message): return
    save_user(message)
    user_answered[message.from_user.id] = "Приду 🌸"
    await message.answer(
        f"🎉 Отлично, очень рады!\n\n"
        f"Ждём тебя <b>{EVENT_DATE} в {EVENT_TIME}</b> в кафе {CAFE_NAME}.\n"
        "Ответ зафиксирован — до встречи! 🌸",
        reply_markup=locked_keyboard(),
    )
    await notify_admin(message, "Приду 🌸")


@dp.message(F.text == "Не смогу ❌")
async def btn_no(message: Message) -> None:
    if await is_locked(message): return
    save_user(message)
    user_answered[message.from_user.id] = "Не смогу ❌"
    await message.answer(
        "Жаль 🥺 Зафиксировала твой ответ.\n"
        "Если планы изменятся — напиши организатору напрямую.",
        reply_markup=locked_keyboard(),
    )
    await notify_admin(message, "Не смогу ❌")


@dp.message(F.text == "Возможно 🤔")
async def btn_maybe(message: Message) -> None:
    if await is_locked(message): return
    save_user(message)
    user_answered[message.from_user.id] = "Возможно 🤔"
    await message.answer(
        "Хорошо, зафиксировала 🤔\n"
        "Напомним ближе к вечеру. Если решишь точно — нажми «Приду 🌸».",
        reply_markup=locked_keyboard(),
    )
    await notify_admin(message, "Возможно 🤔")

# ─── ИНФОРМАЦИОННЫЕ КНОПКИ ────────────────────────────────────────────────────

@dp.message(F.text == "Дресс-код 👗")
async def btn_dresscode(message: Message) -> None:
    uid   = message.from_user.id
    color = user_colors.setdefault(uid, random.choice(DRESS_COLORS))
    kbd   = locked_keyboard() if uid in user_answered else main_keyboard()
    await message.answer(
        f"👗 <b>Твой дресс-код</b>\n\n"
        f"Тебе случайно выпал цвет — <b>{color}</b>.\n\n"
        "<i>Каждой гостье свой цвет — получится необычная атмосфера вечера.</i>",
        reply_markup=kbd,
    )


@dp.message(F.text == "Где находится? 📍")
async def btn_where(message: Message) -> None:
    uid = message.from_user.id
    kbd = locked_keyboard() if uid in user_answered else main_keyboard()
    await message.answer(
        f"📍 Кафе {CAFE_NAME}\n"
        f"Адрес: <b>{CAFE_ADDRESS}</b>\n\n"
        "Найти на карте → https://2gis.ru",
        reply_markup=kbd,
    )


@dp.message(F.text == "Кто будет? 👀")
async def btn_who(message: Message) -> None:
    uid = message.from_user.id
    kbd = locked_keyboard() if uid in user_answered else main_keyboard()
    await message.answer(
        "👀 Небольшая, приятная компания — именно те, кто сделает вечер особенным.\n\n"
        "Детали узнаешь на месте 🙂",
        reply_markup=kbd,
    )

# ─── ФОЛЛБЭК ──────────────────────────────────────────────────────────────────

@dp.message(F.text)
async def fallback(message: Message) -> None:
    uid = message.from_user.id
    if uid in user_answered:
        await message.answer(
            f"✅ Твой ответ уже принят: <b>{user_answered[uid]}</b>\n"
            "Воспользуйся кнопками ниже 👇",
            reply_markup=locked_keyboard(),
        )
    else:
        color = user_colors.setdefault(uid, random.choice(DRESS_COLORS))
        await message.answer(
            "Воспользуйся кнопками ниже 👇\n\nИли вот твоё приглашение ещё раз:",
            reply_markup=main_keyboard(),
        )
        await message.answer(build_invite(color), reply_markup=main_keyboard())

# ─── АВТО-НАПОМИНАНИЕ ─────────────────────────────────────────────────────────

async def auto_reminder_task() -> None:
    logger.info("⏰ Авто-напоминание: задача запущена")
    while True:
        await asyncio.sleep(60)
        now   = datetime.now(timezone.utc)
        delta = EVENT_DATETIME_UTC - now
        if timedelta(hours=1, minutes=59) <= delta <= timedelta(hours=2, minutes=1):
            targets = [
                uid for uid, ans in user_answered.items()
                if ans in ("Приду 🌸", "Возможно 🤔")
                and uid not in auto_reminder_sent
            ]
            if targets:
                logger.info(f"⏰ Отправляю авто-напоминание {len(targets)} гостям")
                for uid in targets:
                    color = user_colors.get(uid, "—")
                    try:
                        await bot.send_message(
                            uid,
                            build_reminder(color),
                            reply_markup=locked_keyboard(),
                        )
                        auto_reminder_sent.add(uid)
                    except Exception as e:
                        logger.warning(f"⏰ Не удалось uid {uid}: {e}")
                    await asyncio.sleep(0.4)

# ─── ЗАПУСК ───────────────────────────────────────────────────────────────────

async def main() -> None:
    logger.info("🌸 Бот запущен")
    asyncio.create_task(auto_reminder_task())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())