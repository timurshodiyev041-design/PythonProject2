import telebot
import requests
import time
from telebot import types

TOKEN = '8284016146:AAFSXT4zcslPpw5IKpce5Lp8b7pt4hT9CwE'

bot = telebot.TeleBot(TOKEN)

# --- Кэш ---
cache = {"timestamp": 0, "rates": {}, "ok": False}
user_state = {}

# --- Предварительная загрузка курсов при старте ---
def preload_rates():
    try:
        r = requests.get("https://api.frankfurter.app/latest", timeout=3)
        data = r.json()
        data["rates"]["EUR"] = 1.0
        cache["rates"] = data["rates"]
        cache["timestamp"] = time.time()
        cache["ok"] = True
        print("✅ Курсы валют обновлены")
    except Exception as e:
        print("⚠️ Не удалось обновить курсы:", e)
        cache["ok"] = False

preload_rates()  # загрузим сразу при запуске

# --- Обновление курсов раз в 10 минут (в фоне) ---
def update_rates_if_needed():
    if time.time() - cache["timestamp"] > 600:
        preload_rates()

# --- Получение курса ---
def get_rate(base, target):
    update_rates_if_needed()

    # Если нет свежих данных — используем кэш
    if not cache["ok"]:
        return None

    rates = cache["rates"]
    manual = {"UZS": 12800}  # примерный курс к USD

    def to_usd(cur):
        if cur == "USD": return 1
        if cur == "EUR": return 1 / rates["USD"]
        if cur == "RUB": return rates["USD"] / rates.get("RUB", 90)
        if cur == "UZS": return 1 / manual["UZS"]
        return None

    def from_usd(cur):
        if cur == "USD": return 1
        if cur == "EUR": return rates["USD"]
        if cur == "RUB": return rates.get("RUB", 90) / rates["USD"]
        if cur == "UZS": return manual["UZS"]
        return None

    a = to_usd(base)
    b = from_usd(target)
    if a is None or b is None:
        return None
    return a * b

# --- Клавиатура ---
def currency_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for cur in ["USD", "EUR", "RUB", "UZS"]:
        markup.add(types.KeyboardButton(cur))
    return markup

# --- /start ---
@bot.message_handler(commands=["start"])
def start(message):
    user_state[message.chat.id] = {"from": None, "amount": None, "to": None}
    bot.send_message(
        message.chat.id,
        "💱 Привет! Я помогу быстро конвертировать валюту.\n\n"
        "Сначала выбери валюту, **из которой** хочешь перевести:",
        parse_mode="Markdown",
        reply_markup=currency_keyboard()
    )

# --- Обработка шагов ---
@bot.message_handler(content_types=["text"])
def handle_message(message):
    chat_id = message.chat.id
    text = message.text.upper().strip()

    if chat_id not in user_state:
        user_state[chat_id] = {"from": None, "amount": None, "to": None}

    state = user_state[chat_id]

    # Шаг 1: выбор исходной валюты
    if state["from"] is None:
        if text not in ["USD", "EUR", "RUB", "UZS"]:
            bot.send_message(chat_id, "❗ Выбери валюту из кнопок.", reply_markup=currency_keyboard())
            return
        state["from"] = text
        bot.send_message(chat_id, f"✅ Из валюты: {text}\nТеперь введи сумму:")
        return

    # Шаг 2: ввод суммы
    if state["amount"] is None:
        try:
            state["amount"] = float(text)
        except ValueError:
            bot.send_message(chat_id, "⚠️ Введи число, например 100 или 12.5")
            return
        bot.send_message(chat_id, "Теперь выбери валюту, **в которую** перевести:", parse_mode="Markdown", reply_markup=currency_keyboard())
        return

    # Шаг 3: выбор целевой валюты
    if state["to"] is None:
        if text not in ["USD", "EUR", "RUB", "UZS"]:
            bot.send_message(chat_id, "❗ Выбери валюту из кнопок.", reply_markup=currency_keyboard())
            return
        state["to"] = text

        base, target, amount = state["from"], state["to"], state["amount"]
        if base == target:
            bot.send_message(chat_id, "⚠️ Выбери разные валюты.")
        else:
            rate = get_rate(base, target)
            if rate:
                result = amount * rate
                bot.send_message(
                    chat_id,
                    f"💹 {amount} {base} = {result:,.2f} {target}\n(1 {base} = {rate:.2f} {target})"
                )
            else:
                bot.send_message(chat_id, "⚠️ Не удалось получить курс (использую старые данные).")

        # сброс состояния
        user_state[chat_id] = {"from": None, "amount": None, "to": None}
        bot.send_message(chat_id, "Хочешь ещё конвертировать? Выбери первую валюту:", reply_markup=currency_keyboard())

bot.polling(none_stop=True)
