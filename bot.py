# bot.py
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from aiogram.filters import CommandStart, Command
import asyncio
import sqlite3
import datetime
import math
import os

# --------------------------------------------
# Переменная с токеном берётся из Railway
# В коде она НЕ должна быть видна открыто
# --------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ID администратора (твой ID в Telegram)
ADMINS = {123456789}


# ============ РАБОТА С БАЗОЙ ДАННЫХ ============

def create_db():
    conn = sqlite3.connect("ozon.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            role TEXT CHECK(role IN ('admin', 'staff')) NOT NULL,
            point_id INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER PRIMARY KEY,
            point_id INTEGER,
            status TEXT CHECK(status IN ('open', 'closed')),
            time DATETIME,
            lat REAL,
            lon REAL
        )
    """)
    conn.commit()
    conn.close()


def user_exists(user_id: int):
    conn = sqlite3.connect("ozon.db")
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone() is not None
    conn.close()
    return result


def add_staff_by_forward(from_user_id: int, point_id: int):
    if user_exists(from_user_id):
        return False
    conn = sqlite3.connect("ozon.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (user_id, role, point_id) VALUES (?, ?, ?)",
        (from_user_id, "staff", point_id)
    )
    conn.commit()
    conn.close()
    return True


def add_admin(from_user_id: int):
    if user_exists(from_user_id):
        return False
    conn = sqlite3.connect("ozon.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (user_id, role, point_id) VALUES (?, ?, NULL)",
        (from_user_id, "admin")
    )
    conn.commit()
    conn.close()
    return True


def get_user_role(user_id: int):
    if user_id in ADMINS:
        return "admin"
    conn = sqlite3.connect("ozon.db")
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def get_points():
    conn = sqlite3.connect("ozon.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name, lat, lon FROM points ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "name": r[1], "lat": r[2], "lon": r[3]}
        for r in rows
    ]


def get_point_by_id(point_id: int):
    points = get_points()
    for p in points:
        if p["id"] == point_id:
            return p
    return None


def add_point(name: str, lat: float, lon: float):
    conn = sqlite3.connect("ozon.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO points (name, lat, lon) VALUES (?, ?, ?)",
        (name, lat, lon)
    )
    conn.commit()
    conn.close()


def get_session(user_id: int):
    conn = sqlite3.connect("ozon.db")
    cur = conn.cursor()
    cur.execute("SELECT point_id, status, time, lat, lon FROM sessions WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {"point_id": row[0], "status": row[1], "time": row[2], "lat": row[3], "lon": row[4]}
    return None


def upsert_session(user_id: int, point_id: int, status: str, time: datetime.datetime, lat: float, lon: float):
    conn = sqlite3.connect("ozon.db")
    cur = conn.cursor()
    cur.execute(
        "REPLACE INTO sessions (user_id, point_id, status, time, lat, lon) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, point_id, status, time.isoformat(), lat, lon)
    )
    conn.commit()
    conn.close()


# ============ РАССТОЯНИЕ ПО ГЕОЛОКАЦИИ ============

def distance(lat1, lon1, lat2, lon2) -> float:
    R = 6371000
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


MAX_DISTANCE = 150  # метров


# ============ ОТПРАВКА АЛЕРТОВ АДМИНУ ============

async def send_alert(bot: Bot, text: str):
    admins = set(ADMINS)
    conn = sqlite3.connect("ozon.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE role = 'admin'")
    rows = cur.fetchall()
    conn.close()
    for r in rows:
        admins.add(r[0])
    for admin_id in admins:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass


# ============ КОМАНДЫ АДМИНИСТРАТОРА ============

@dp.message(Command("points"))
async def cmd_points(message: Message, bot: Bot):
    if get_user_role(message.from_user.id) != "admin":
        await message.answer("Команда доступна только администраторам.")
        return
    points = get_points()
    text = "Список пунктов Озон:\n"
    for p in points:
        text += f"{p['id']}. {p['name']} {p['lat']:.5f}, {p['lon']:.5f}\n"
    if not points:
        text = "Пока нет ни одного пункта. Добавьте через /add_point."
    await message.answer(text)


@dp.message(Command("add_point"))
async def cmd_add_point(message: Message, bot: Bot):
    if get_user_role(message.from_user.id) != "admin":
        await message.answer("Команда доступна только администраторам.")
        return
    args = message.text.split(maxsplit=3)
    if len(args) < 3:
        await message.answer("Использование: /add_point 55.75222 37.61558 Название ПВЗ")
        return
    try:
        lat = float(args[1])
        lon = float(args[2])
        name = args[3]
        add_point(name, lat, lon)
        await message.answer(f"✅ Пункт добавлен:\n{name} ({lat:.5f}, {lon:.5f})")
    except ValueError:
        await message.answer("Координаты должны быть числами.")


@dp.message(Command("start"))
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    role = get_user_role(user_id)
    if role == "staff":
        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Открыт")],
                [KeyboardButton(text="Закрыт")],
            ],
            resize_keyboard=True
        )
        await message.answer("Нажимайте кнопки при открытии и закрытии пункта.", reply_markup=kb)
    elif role == "admin":
        await message.answer("Привет, администратор. Доступные команды: /points /add_point /bind_staff.")
    else:
        await message.answer("Вы не зарегистрированы. Обратитесь к админу.")


@dp.message(F.is_forwarded)
async def handle_forward(message: Message, bot: Bot):
    if get_user_role(message.from_user.id) != "admin":
        await message.answer("Добавлять сотрудников могут только администраторы.")
        return
    if not message.forward_from:
        await message.answer("Не смог распознать пользователя в пересланном сообщении.")
        return
    user_id = message.forward_from.id
    role = get_user_role(user_id)
    if role == "staff":
        await message.answer("Этот пользователь уже как сотрудник.")
        return
    if role == "admin":
        await message.answer("Этот пользователь уже администратор.")
        return
    points = get_points()
    if not points:
        await message.answer("Сначала добавьте хотя бы один пункт через /add_point.")
        return
    text = "Выберите ID пункта для сотрудника:\n"
    for p in points:
        text += f"{p['id']}. {p['name']}\n"
    await message.answer(text)


@dp.message(Command("bind_staff"))
async def cmd_bind_staff(message: Message, bot: Bot):
    if get_user_role(message.from_user.id) != "admin":
        await message.answer("Команда доступна только администраторам.")
        return
    args = message.text.split()
    if len(args) != 3:
        await message.answer("Использование: /bind_staff 123456789 1 (ID пользователя, ID пункта).")
        return
    user_id = int(args[1])
    point_id = int(args[2])
    if add_staff_by_forward(user_id, point_id):
        await message.answer("Сотрудник добавлен.")
    else:
        await message.answer("Пользователь уже есть в базе.")


# ==================== ЛОГИКА ОТКРЫТИЯ / ЗАКРЫТИЯ ====================

@dp.message(F.text == "Открыт")
async def open_point(message: Message, bot: Bot):
    user_id = message.from_user.id
    role = get_user_role(user_id)
    if role != "staff":
        await message.answer("Только сотрудники могут нажимать эту кнопку.")
        return
    now = datetime.datetime.now()
    hour = now.hour
    minute = now.minute
    points = get_points()
    point = points[0] if points else None
    if not point:
        await message.answer("Ещё не добавлен ни один пункт.")
        return

    if hour < 9:
        await send_alert(bot, f"⚠️ ПВЗ {point['name']} открыто слишком рано: {hour}:{minute}")
    if hour > 10:
        await send_alert(bot, f"⚠️ ПВЗ {point['name']} открыто с опозданием: {hour}:{minute}")

    if message.location:
        lat = message.location.latitude
        lon = message.location.longitude
        dist = distance(lat, lon, point["lat"], point["lon"])
        if dist > MAX_DISTANCE:
            await send_alert(
                bot,
                f"⚠️ Геолокация при открытии {point['name']}: {dist:.0f} м от точки ({lat:.6f}, {lon:.6f})"
            )
        await message.answer(f"Открыто. Расстояние до точки: {dist:.0f} м.")
    else:
        await message.answer("Открыто (без геолокации).")
        await send_alert(bot, f"⚠️ Открытие {point['name']} без геолокации.")

    upsert_session(
        user_id=user_id,
        point_id=point["id"],
        status="open",
        time=now,
        lat=message.location.latitude if message.location else None,
        lon=message.location.longitude if message.location else None
    )


@dp.message(F.text == "Закрыт")
async def close_point(message: Message, bot: Bot):
    user_id = message.from_user.id
    role = get_user_role(user_id)
    if role != "staff":
        await message.answer("Только сотрудники могут нажимать эту кнопку.")
        return
    now = datetime.datetime.now()
    hour = now.hour
    minute = now.minute
    points = get_points()
    point = points[0] if points else None
    if not point:
        await message.answer("Ещё не добавлен ни один пункт.")
        return

    if hour < 20:
        await send_alert(bot, f"⚠️ ПВЗ {point['name']} закрыто слишком рано: {hour}:{minute}")
    if hour > 22:
        await send_alert(bot, f"⚠️ ПВЗ {point['name']} закрыто с задержкой: {hour}:{minute}")

    if message.location:
        lat = message.location.latitude
        lon = message.location.longitude
        dist = distance(lat, lon, point["lat"], point["lon"])
        if dist > MAX_DISTANCE:
            await send_alert(
                bot,
                f"⚠️ Геолокация при закрытии {point['name']}: {dist:.0f} м от точки ({lat:.6f}, {lon:.6f})"
            )
        await message.answer(f"Закрыто. Расстояние до точки: {dist:.0f} м.")
    else:
        await message.answer("Закрыто (без геолокации).")
        await send_alert(bot, f"⚠️ Закрытие {point['name']} без геолокации.")

    upsert_session(
        user_id=user_id,
        point_id=point["id"],
        status="closed",
        time=now,
        lat=message.location.latitude if message.location else None,
        lon=message.location.longitude if message.location else None
    )


# ==================== ЗАПУСК БОТА ====================

dp = Dispatcher()


async def main():
    create_db()
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())