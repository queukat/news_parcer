import logging
import time

from telegram import Bot
from telegram.ext import Updater

from src.config import TELEGRAM_TOKEN
from news_processor import check_for_news

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_TOKEN)
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Start the bot
logger.info("Starting bot polling")
updater.start_polling()

try:
    while True:
        logger.info("Starting news check...")
        check_for_news()
        logger.info("News check completed")
        time.sleep(3600)
except KeyboardInterrupt:
    logger.info("Bot stopped manually.")


if __name__ == '__main__':
    check_for_news()