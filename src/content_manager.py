import logging
import time

from telegram import Bot
from urllib.parse import quote

from config import MAX_MESSAGE_LENGTH, TELEGRAM_TOKEN

logger = logging.getLogger(__name__)


def send_long_message(bot: Bot, chat_id, text, parse_mode, title, link=None, tags=None):
    """Sends a long message in multiple parts if necessary."""
    logger.info(f"Starting to send long message to {chat_id}")

    title_length = len(f"<b>{title}</b>\n\n")
    continuation_text = "\n\n<b>Продолжение следует...</b>"
    final_text = f'\n\n<a href="{link}">Читать на сайте</a>\n\n{tags}' if link and tags else ""

    previous_part = ""

    logger.debug(f"Initial text length: {len(text)}")
    logger.debug(f"Title length: {title_length}, Continuation text length: {len(continuation_text)}")

    while len(text) > 0:
        available_length = MAX_MESSAGE_LENGTH - title_length - len(continuation_text)
        logger.debug(f"Available length for current part: {available_length}")
        logger.debug(f"Current remaining text: {text[:60]}... (length: {len(text)})")

        if len(text) > available_length:
            part = text[:available_length].strip()
            text = text[available_length:].strip()
            part += continuation_text
            logger.debug(f"Text split into part: {part[:60]}... (length: {len(part)})")
            logger.debug(f"Remaining text after split: {text[:60]}... (length: {len(text)})")
        else:
            part = text.strip() + final_text
            text = ""
            logger.debug(f"Final part to send: {part[:60]}... (length: {len(part)})")
            logger.debug("No remaining text left to send.")

        if part == previous_part:
            logger.warning(
                f"Detected duplicate part: {part[:60]}... (length: {len(part)}), stopping sending to prevent loops.")
            break

        logger.debug(f"Sending part of message: {part[:60]}... (length: {len(part)})")
        bot.send_message(chat_id=chat_id, text=f"<b>{title}</b>\n\n{part}", parse_mode=parse_mode)
        logger.debug(f"Sent part of long message: {part[:60]}...")

        previous_part = part
        logger.info(f"Sent part of long message: {part[:60]}...")

        # Small delay to avoid flooding
        time.sleep(2)

    logger.info("Finished sending long message.")


def split_content_by_length(content, max_length):
    """Splits the text into parts with a maximum length, avoiding word breaks."""
    if len(content) <= max_length:
        return content, ""

    split_point = content[:max_length].rfind(' ')

    if split_point == -1:
        split_point = content.find(' ', max_length)
        if split_point == -1:
            split_point = max_length

    if len(content[split_point:].strip()) < 5:
        next_split_point = content.find(' ', split_point + 1)
        if next_split_point != -1:
            split_point = next_split_point

    while split_point < len(content) - 1 and content[split_point + 1] in ",.!?":
        split_point = content.find(' ', split_point + 1)
        if split_point == -1:
            break

    return content[:split_point].strip(), content[split_point:].strip()
