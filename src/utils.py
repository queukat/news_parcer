import hashlib
import logging
import os
from urllib.parse import urljoin

from src.config import SUBSCRIBERS_FILE, NEWS_HASH_FILE

logger = logging.getLogger(__name__)


def load_news_history():
    """Loads the history of processed news."""
    if os.path.exists('NEWS_HASH_FILE'):
        with open(NEWS_HASH_FILE, 'r') as file:
            return set(file.read().splitlines())
    return set()


def save_news_history(hash_value):
    """Saves the hash of the processed news to history."""
    with open(NEWS_HASH_FILE, 'a') as file:
        file.write(hash_value + '\n')


def load_subscribers():
    """Loads the list of subscribers from the file."""
    if os.path.exists(SUBSCRIBERS_FILE):
        with open(SUBSCRIBERS_FILE, 'r') as file:
            subscribers = set(map(int, file.read().splitlines()))
        logger.info(f"Loaded {len(subscribers)} subscribers")
    else:
        subscribers = set()
        logger.info("No subscribers file found, starting fresh")
    return subscribers


def save_subscribers(subscribers):
    """Saves the list of subscribers to the file."""
    with open(SUBSCRIBERS_FILE, 'w') as file:
        for user_id in subscribers:
            file.write(f"{user_id}\n")
    logger.info(f"Saved {len(subscribers)} subscribers")


def extract_images_from_html(soup, base_url):
    """Extracts images from HTML."""
    images = []

    def add_image(img_url, caption=""):
        """Adds an image to the list if it was correctly extracted."""
        if img_url and not img_url.startswith('data:image'):
            img_url = urljoin(base_url, clean_url(img_url))
            images.append((img_url, caption))
            logger.info(f"Found image: {img_url} with caption '{caption}'")

    if "investitor.me" in base_url:
        logger.info("Processing images for investitor.me")
        primary_div = soup.find('div', id='primary')
        if primary_div:
            main_div = primary_div.find('main', id='main')
            if main_div:
                single_post_media_wrap_div = main_div.find('div', class_='single-post-media-wrap')
                if single_post_media_wrap_div:
                    img_tag = single_post_media_wrap_div.find('img')
                    caption_tag = single_post_media_wrap_div.find('div', class_='single-post-media-desc')
                    if img_tag and img_tag.get('src'):
                        caption = caption_tag.get_text(strip=True) if caption_tag else ''

                        add_image(img_tag['src'], caption)

    elif "rtcg.me" in base_url:
        logger.info("Processing images for rtcg.me")
        story_full_div = soup.find('div', class_='storyFull fix')
        if story_full_div:

            logger.info("Начинается обработка блоков с изображениями внутри 'storyFull fix'")


            for div in story_full_div.find_all('div'):
                if 'box-center' in div.get('class', []) or 'box-left' in div.get('class', []) or 'box-right' in div.get('class', []):

                    box_image_div = div.find('div', class_='boxImage')
                    if box_image_div:
                        img_tag = box_image_div.find('img')
                        caption_tag = box_image_div.find('span', class_='boxImageCaption')
                        if img_tag and img_tag.get('src'):
                            img_url = urljoin(base_url, clean_url(img_tag['src']))
                            caption = caption_tag.get_text(strip=True) if caption_tag else ''
                            add_image(img_url, caption)

            logger.info("Начинается обработка блоков с тегом <figure> внутри 'storyFull fix'")
            for figure in story_full_div.find_all('figure'):
                img_tag = figure.find('img')
                caption_tag = figure.find('figcaption') or figure.find('footer')
                if img_tag and img_tag.get('src'):
                    img_url = img_tag['src']
                    caption = caption_tag.get_text(strip=True) if caption_tag else ''
                    add_image(img_url, caption)

    else:
        logger.info("Processing images in 'elementor-element' blocks with specific widgets")
        for div in soup.find_all('div', class_='elementor-element'):
            widget_type = div.get('data-widget_type', '')
            if 'theme-post-featured-image' in widget_type or 'theme-post-content' in widget_type:
                img_tag = div.find('img')
                if img_tag and img_tag.get('src'):

                    srcset = img_tag.get('srcset')
                    img_url = srcset.split(',')[-1].split()[0] if srcset else img_tag['src']
                    caption_tag = div.find('figcaption') or div.find('span', class_='elementor-icon-list-text')
                    caption = caption_tag.get_text(strip=True) if caption_tag else ''
                    add_image(img_url, caption)

        logger.info("Processing images in 'mainArticleImg' blocks")
        for div in soup.find_all('div', class_='mainArticleImg'):
            img_tag = div.find('img')
            if img_tag and img_tag.get('src'):
                add_image(img_tag['src'])

        logger.info("Processing images in 'btArticleBody' blocks")
        for div in soup.find_all('div', class_='btArticleBody'):
            img_tags = div.find_all('img')
            for img_tag in img_tags:
                if img_tag.get('src'):
                    add_image(img_tag.get('src'))

        logger.info("Processing images in 's-feat' blocks")
        for div in soup.find_all('div', class_='s-feat'):
            lightbox_div = div.find('div', class_='featured-lightbox-trigger')
            if lightbox_div:
                add_image(lightbox_div.get('data-source'))

        logger.info("Extracting images from <app-article-image> tags")
        for app_image in soup.find_all('app-article-image'):
            img_tag = app_image.find('img')
            if img_tag:
                add_image(img_tag.get('srcset') or img_tag.get('src'))

        logger.info("Extracting images from <picture> tags")
        for picture_tag in soup.find_all('picture'):
            img_tag = picture_tag.find('img')
            if img_tag:
                add_image(img_tag.get('srcset') or img_tag.get('src'))

        logger.info("Processing images from 'data-bg' and 'background-image' attributes")
        for section in soup.find_all('section'):
            data_bg = section.get('data-bg')
            style_bg = section.get('style')
            if data_bg:
                add_image(data_bg)
            elif style_bg and 'background-image' in style_bg:
                style_url = style_bg.split('url(')[-1].split(')')[0].strip('\'"')
                add_image(style_url)

        logger.info("Processing images in 'herald-post-thumbnail' blocks")
        for div in soup.find_all('div', class_='herald-post-thumbnail'):
            noscript_tag = div.find('noscript')
            img_tag = noscript_tag.find('img') if noscript_tag else div.find('img')
            if img_tag and img_tag.get('src'):
                caption_tag = div.find('figure', class_='wp-caption-text')
                caption = caption_tag.get_text(strip=True) if caption_tag else ''
                add_image(img_tag.get('src'), caption)

        logger.info("Processing images in 'post-container cf' blocks")
        for post_container in soup.find_all('div', class_='post-container cf'):
            img_tag = post_container.find('img')
            if img_tag and img_tag.get('src'):
                add_image(img_tag.get('src'))

    logger.info(f"Extracted {len(images)} images from HTML")
    return images


def generate_content_hash(content, title):
    """Generates a hash for the content and title."""
    hasher = hashlib.sha256()
    hasher.update(content.encode('utf-8'))
    hasher.update(title.encode('utf-8'))
    return hasher.hexdigest()


def clean_url(url):
    """Removes parameters from the URL and returns a clean URL."""
    return url.split('?')[0]
