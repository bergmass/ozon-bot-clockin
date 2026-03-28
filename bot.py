# bot.py
import asyncio
import sqlite3
import datetime
import math
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command

# Токен из переменной Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Твой ID в Telegram (узнай у @getmyid_bot)
ADMINS = {123456789}  # ЗАМЕНИ НА СВОЙ ID!

# Создаём Dispatcher ДО всех декораторов
dp = Dispatcher()

# ============ БАЗА ДАННЫХ ============
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

# [Все остальные функции БД остаются такими же, как были...]
# ... (остальной код функций БД, геолокации, алертов — без изменений)