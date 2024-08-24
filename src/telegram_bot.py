
import logging

from telegram import Bot
from telegram.ext import Updater, CommandHandler

from src.config import TELEGRAM_TOKEN
from utils import load_subscribers, save_subscribers

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_TOKEN)
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher


def start(update, context):
    """Handles the /start command to subscribe the user to news updates."""
    user_id = update.message.chat_id
    logger.info(f"Received /start command from {user_id}")
    subscribers = load_subscribers()

    if user_id not in subscribers:
        subscribers.add(user_id)
        save_subscribers(subscribers)
        update.message.reply_text("Вы подписаны на новости.")
        logger.info(f"User {user_id} subscribed to news")
    else:
        update.message.reply_text("Вы уже подписаны на новости.")
        logger.info(f"User {user_id} already subscribed to news")


def stop(update, context):
    """Handles the /stop command to unsubscribe the user from news updates."""
    user_id = update.message.chat_id
    logger.info(f"Received /stop command from {user_id}")
    subscribers = load_subscribers()

    if user_id in subscribers:
        subscribers.remove(user_id)
        save_subscribers(subscribers)
        update.message.reply_text("Вы отписаны от новостей и удалены из списка. Хорошего дня")
        logger.info(f"User {user_id} unsubscribed from news")
    else:
        update.message.reply_text("Вы не были подписаны на новости.")
        logger.info(f"User {user_id} was not subscribed to news")


# Registering command handlers
start_handler = CommandHandler('start', start)
stop_handler = CommandHandler('stop', stop)
dispatcher.add_handler(start_handler)
dispatcher.add_handler(stop_handler)

