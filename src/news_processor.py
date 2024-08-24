import logging
import os
import random
import time
import urllib
from time import sleep
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from telegram import Bot

from src.azure_client import translate_and_summarize, summarize_text, analytics_client
from src.config import SENT_NEWS_FILE, RSS_FEEDS, FILTER_KEYWORDS
from src.config import TELEGRAM_TOKEN
from src.content_manager import send_long_message, split_content_by_length
from text_processor import fetch_article_content
from utils import load_subscribers, load_news_history, save_news_history, generate_content_hash, \
    extract_images_from_html, clean_url

logger = logging.getLogger(__name__)

# Initialize the bot with the token
bot = Bot(token=TELEGRAM_TOKEN)


def load_sent_news():
    """Loads the list of sent news from the file and returns it as a set."""
    logger.info(f"Loading sent news from {SENT_NEWS_FILE}")
    if os.path.exists(SENT_NEWS_FILE):
        with open(SENT_NEWS_FILE, 'r') as file:
            sent_news = set(file.read().splitlines())
        logger.info(f"Loaded {len(sent_news)} sent news entries")
    else:
        logger.info(f"No sent news file found, starting fresh")
        sent_news = set()
    return sent_news


def save_sent_news(guid):
    """Saves the GUID of the sent news to the file."""
    try:
        logger.info(f"Saving GUID {guid} to {SENT_NEWS_FILE}")
        with open(SENT_NEWS_FILE, 'a') as file:
            file.write(f"{guid}\n")
        logger.info(f"GUID {guid} saved to {SENT_NEWS_FILE}")
    except Exception as e:
        logger.error(f"Failed to save GUID {guid} to {SENT_NEWS_FILE}: {str(e)}")


def check_for_news():
    """Main loop to check and send news updates to subscribers."""
    logger.info("Starting news check...")

    while True:
        subscribers = load_subscribers()

        if not subscribers:
            logger.info("No subscribers found. Skipping news check.")
            sleep(3600)
            continue

        sent_news = load_sent_news()

        for feed in RSS_FEEDS:
            news = fetch_rss_feed(feed, sent_news)
            for item in news:
                process_news_item(item, sent_news, subscribers)

        gov_me_news = fetch_gov_me_news(sent_news)
        for item in gov_me_news:
            process_news_item(item, sent_news, subscribers)

        logger.info("News send process completed")
        sleep(3600)


def fetch_rss_feed(url, sent_news):
    """Fetches the RSS feed from the provided URL."""
    logger.info(f"Fetching RSS feed from {url}")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/58.0.3029.110 Safari/537.3"
        }
        response = requests.get(url, headers=headers)
        logger.debug(f"Received status code {response.status_code} from {url}")
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item')
        news = []

        for item in items:
            title = item.title.text.strip()
            link = item.link.text.strip()
            guid = item.guid.text.strip() if item.guid else link

            # Filter news by keywords in URL and check if the news has already been sent
            if any(keyword in link.lower() for keyword in FILTER_KEYWORDS) or guid in sent_news:
                logger.debug(f"Skipping news with filtered content or already sent: {title}")
                continue

            news.append({'title': title, 'link': link, 'guid': guid})

        logger.info(f"Fetched {len(news)} new items from RSS feed")
        return news
    except Exception as e:
        logger.error(f"Error fetching RSS feed from {url}: {str(e)}")
        return []


def process_news_item(item, sent_news, subscribers):
    """Processes each news item and sends it to subscribers."""
    rss_title = item['title']
    link = clean_url(item['link'])
    guid = item['guid'] if 'guid' in item else link

    # Skip already sent news
    if guid in sent_news:
        logger.info(f"News with GUID {guid} has already been sent, skipping.")
        return

    try:
        logger.info(f"Processing news item: {rss_title} (GUID: {guid})")
        # Fetch article content based on source
        if "gov.me" in link:
            logger.info(f"Processing gov.me article: {link}")
            article_data = {
                'title': item.get('title', ''),
                'content': item.get('full_text', ''),
                'images': item.get('images', []),
                'videos': item.get('videos', [])
            }
        else:
            logger.debug(f"Fetching content from {link}")
            article_data = fetch_article_content(link)
            logger.debug(f"Fetched article data: {article_data}")


        if article_data == "duplicate":
            logger.info(f"Article is a hash duplicate: {rss_title}. Skipping.")
            return


        if article_data == "vector":
            logger.info(f"Vector found article duplicate: {rss_title}. Skipping.")
            return


        if article_data is None:
            logger.info(f"Article data is None for {rss_title}. Skipping.")
            return


        if article_data['content'] is None:
            logger.info(
                f"Content is None for {rss_title}. Skipping.")
            return


        if not article_data['content']:
            logger.info(f"No content found for {rss_title}. Skipping.")
            return


        logger.debug(f"Translating title and content for {rss_title}")
        # Translate title and content together
        full_text = article_data['title'] + "\n\n" + article_data['content']
        translated_full_text = translate_and_summarize(full_text, target_language='ru', summarize=False)


        translated_title, translated_content = translated_full_text.split('\n\n', 1)

        logger.debug(f"Translated title: {translated_title}")
        logger.debug(f"Translated content (first 100 chars): {translated_content[:100]}...")

        if "balkaninsight.com" in link:
            translated_content += "\n\nКонец бесплатной версии"

        # Summarize only the translated content (not the title)
        translated_content = summarize_text(analytics_client, translated_content)


        tags = determine_tags(translated_content, link)
        logger.debug(f"Determined tags for {link}: {tags}")
        initial_message = f"<b>{translated_title}</b>\n\n"
        remaining_content = translated_content

        # Send message based on available images and content length
        if article_data['images']:
            primary_image = article_data['images'][0]
            encoded_image_url = urllib.parse.quote(primary_image, safe=':/')
            max_caption_length = 1024 - len(initial_message) - len("\n\n<b>Продолжение внизу</b>")

            logger.debug(f"Image URL: {primary_image}")
            logger.debug(f"Max caption length: {max_caption_length}")

            if len(remaining_content) > max_caption_length:
                caption, remaining_content = split_content_by_length(remaining_content, max_caption_length)
                caption = initial_message + caption + "\n\n<b>Продолжение внизу</b>"
            else:
                caption = initial_message + remaining_content
                remaining_content = ""
                final_text = f'\n\n<a href="{link}">Читать на сайте</a>' + (f'\n\n{tags}' if tags else "")
                caption += final_text

            for user_id in subscribers:
                logger.info(f"Sending image with caption to {user_id}")
                bot.send_photo(chat_id=user_id, photo=encoded_image_url, caption=caption, parse_mode='HTML')
                time.sleep(1.5)

        if remaining_content:
            for user_id in subscribers:
                logger.info(f"Sending remaining content to {user_id}")
                send_long_message(bot,chat_id=user_id, text=remaining_content, parse_mode='HTML',
                                  title=translated_title, link=link, tags=tags)

        save_sent_news(guid)
        sent_news.add(guid)

    except Exception as e:
        logger.error(f"Failed to fetch or translate article: {rss_title}\n{link}\nError: {str(e)}")

def determine_tags(content, source_url):
    """Determines tags based on content and source."""
    tags = []

    # Tags based on keywords in content
    if "гидрометеоролог" or "метеоцентр" in content.lower():
        tags.append("
    if "электричеств" in content.lower():
        tags.append("
    if "анонс записи" in content.lower():
        tags.append("
    if "война в украине" in content.lower():
        tags.append("
    if "акция протеста" in content.lower():
        tags.append("

    # Tags based on the source
    if "cdm.me" in source_url:
        tags.append("#CDM")
    elif "vijesti.me" in source_url:
        tags.append("#Vijesti")
    elif "balkaninsight.com" in source_url:
        tags.append("#BalkanInsight")
    elif "rtc" in source_url:
        tags.append("#RTCG")
    elif "investitor.me" in source_url:
        tags.append("#Investitor")
    elif "gov.me" in source_url:
        tags.append("#GOV")
    elif "bankar.me" in source_url:
        tags.append("#bankar")
    elif "podgorica.me" in source_url:
        tags.append("#Podgorica")
    elif "mans.co.me" in source_url:
        tags.append("#MANS")

    logger.info(f"Determined tags for {source_url}: {tags}")
    return "  ".join(tags)


def fetch_gov_me_news(sent_news, max_pages=10):
    """Fetches news from the gov.me website."""
    base_url = "https://www.gov.me/vijesti"
    page = 1
    news = []

    news_history = load_news_history()

    while page <= max_pages:
        url = f"{base_url}?page={page}"
        response = requests.get(url)
        sleep(random.randint(1, 3))
        if response.status_code != 200:
            logger.error(f"Failed to fetch page: {url} with status code: {response.status_code}")
            page += 1
            continue

        soup = BeautifulSoup(response.text, 'html.parser')

        news_items = soup.find_all('app-search-item')

        for item in news_items:
            link_tag = item.find('a', class_='cursor-pointer')
            if not link_tag:
                logger.info("No link found in app-search-item")
                continue

            link = "https://www.gov.me" + link_tag['href']

            if link in sent_news:
                logger.debug(f"News already sent, skipping: {link}")
                continue

            title = link_tag.text.strip() if link_tag else "Title not found"
            summary = item.find('p').text.strip() if item.find('p') else "Summary not found"
            date_tag = item.find('time')
            date = date_tag.text.strip() if date_tag else "Date not found"

            logger.debug(f"Processing article: {title}")

            full_response = requests.get(link)
            full_soup = BeautifulSoup(full_response.text, 'html.parser')

            article_body = full_soup.find('app-article-body')
            full_text = ""

            if article_body:
                section = article_body.find('section', class_='relative ui-article-spacing')
                if section:
                    paragraphs = section.find_all(['p'])
                    # paragraphs = section.find_all(['p', 'div', 'span', 'table', 'h1'])
                    for p in paragraphs:
                        current_text = p.get_text(strip=True)
                        full_text += f"\n\n{current_text}"

            news_hash = generate_content_hash(full_text[50:250], title)

            if news_hash in news_history:
                logger.debug(f"Found duplicate news for URL {link}. Skipping.")
                continue

            logger.debug(f"Final full_text: {full_text[:200]}...")
            news.append({
                'title': title,
                'link': link,
                'summary': summary,
                'date': date,
                'full_text': full_text,
                'images': extract_images_from_html(full_soup, link)
            })

            save_news_history(news_hash)

        page += 1

        if not news_items:
            logger.info("No more news items found, ending search.")
            break

    logger.info(f"Fetched {len(news)} news items from gov.me")
    return news
