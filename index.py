import logging
import telebot
import openai
import json
import time
import threading
import yaml
import os

# Загружаем конфиг
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

TG_BOT_TOKEN = config["TG_BOT_TOKEN"]
TG_BOT_CHATS = [str(chat) for chat in config["TG_BOT_CHATS"]]
OPENAI_API_KEY = config["OPENAI_API_KEY"]

# Папка для хранения истории чатов
HISTORY_DIR = "history"
os.makedirs(HISTORY_DIR, exist_ok=True)

# Логирование
logging.basicConfig(level=logging.INFO)
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

# Инициализация бота и OpenAI API
bot = telebot.TeleBot(TG_BOT_TOKEN, threaded=False)
client = openai.Client(api_key=OPENAI_API_KEY)

is_typing = False


def start_typing(chat_id):
    global is_typing
    is_typing = True
    threading.Thread(target=typing, args=(chat_id,), daemon=True).start()


def typing(chat_id):
    global is_typing
    while is_typing:
        bot.send_chat_action(chat_id, "typing")
        time.sleep(4)


def stop_typing():
    global is_typing
    is_typing = False


def get_history(chat_id):
    history_file = os.path.join(HISTORY_DIR, f"{chat_id}.json")
    if os.path.exists(history_file):
        with open(history_file, "r") as file:
            return json.load(file)
    return []


def save_history(chat_id, history):
    history_file = os.path.join(HISTORY_DIR, f"{chat_id}.json")
    with open(history_file, "w") as file:
        json.dump(history, file)


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я ChatGPT бот. Спроси меня что-нибудь!")


@bot.message_handler(commands=["new"])
def clear_history(message):
    save_history(message.chat.id, [])
    bot.reply_to(message, "История чата очищена!")


@bot.message_handler(func=lambda message: True, content_types=["text"])
def handle_message(message):
    if str(message.chat.id) not in TG_BOT_CHATS:
        return

    print(f"Получено сообщение от {message.chat.id}: {message.text}")  # Отладка
    start_typing(message.chat.id)
    try:
        response = process_text_message(message.text, message.chat.id)
    except Exception as e:
        response = f"Ошибка: {e}"
    stop_typing()
    bot.reply_to(message, response, parse_mode="Markdown")


def process_text_message(text, chat_id) -> str:
    model = "gpt-3.5-turbo"
    history = get_history(chat_id)
    history.append({"role": "user", "content": text})

    try:
        chat_completion = client.chat.completions.create(model=model, messages=history)
        ai_response = chat_completion.choices[0].message.content
    except openai.OpenAIError as e:
        save_history(chat_id, [])
        return f"Ошибка OpenAI: {e}"

    history.append({"role": "assistant", "content": ai_response})
    save_history(chat_id, history)
    return ai_response


if __name__ == "__main__":
    bot.infinity_polling()
