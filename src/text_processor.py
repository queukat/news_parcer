import logging

import requests
from bs4 import BeautifulSoup
from newspaper import Article
from sentence_transformers import SentenceTransformer, util
import numpy as np
import pickle
import os
from src.config import EMBEDDINGS_FILE
from utils import extract_images_from_html, generate_content_hash
from utils import save_news_history, load_news_history

logger = logging.getLogger(__name__)

model = SentenceTransformer('all-mpnet-base-v2')
logger.debug("Multilingual BertModel successfully loaded.")
model.eval()


def get_sbert_embedding(text):
    """Получает эмбеддинг текста с использованием SBERT."""
    logger.debug(f"Received text for embedding: {text[:100]}...")
    embedding = model.encode(text, convert_to_numpy=True)
    logger.debug(f"Generated SBERT embedding of shape: {embedding.shape}")
    return embedding


def load_saved_embeddings():
    """Загружает сохраненные эмбеддинги новостей."""
    if os.path.exists(EMBEDDINGS_FILE):
        try:
            with open(EMBEDDINGS_FILE, 'rb') as f:
                embeddings = pickle.load(f)
                logger.debug(f"Loaded {len(embeddings)} embeddings from {EMBEDDINGS_FILE}")
                return embeddings
        except EOFError:
            logger.error(f"Failed to load embeddings from {EMBEDDINGS_FILE}: File is empty or corrupted.")
            return []
    logger.debug("No embeddings file found, returning empty list.")
    return []


def save_embeddings(embeddings):
    """Сохраняет эмбеддинги новостей."""
    with open(EMBEDDINGS_FILE, 'wb') as f:
        pickle.dump(embeddings, f)


def is_similar_sbert(new_embedding, saved_embeddings, threshold=0.85):
    """Проверяет схожесть нового эмбеддинга с сохраненными с использованием SBERT."""
    if len(saved_embeddings) == 0:
        logger.debug("No saved embeddings found, skipping similarity check.")
        return False

    cos_sim = util.cos_sim(new_embedding, np.vstack(saved_embeddings))
    max_similarity = cos_sim.max()

    logger.debug(f"Max similarity found: {max_similarity}")

    return max_similarity >= threshold


def fetch_article_content(url):
    """Fetches the content of the article from the given URL."""
    logger.info(f"Fetching article content from {url}")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/58.0.3029.110 Safari/537.3"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        logger.debug(f"Received response from {url} with status code {response.status_code}")
        article = Article(url)
        article.set_html(response.text)
        article.parse()
        logger.debug("HTML content set in newspaper.Article")
        soup = BeautifulSoup(article.html, 'html.parser')
        logger.debug("HTML parsed with BeautifulSoup")

        if len(article.text.strip()) == 0 or len(article.text.split()) < 20:
            logger.debug(f"Content extraction with newspaper failed, switching to manual extraction for {url}")
            full_content = extract_content_manually(soup, url)
        else:
            full_content = article.text
            logger.debug(f"Newspaper extracted content: {full_content[:20]}...")
            if "Bonus video:" in full_content:
                full_content = full_content.split("Bonus video:")[0].strip()
                logger.debug(f"Removed 'Bonus video:' section from the article content")

        news_hash = generate_content_hash(full_content[50:250], article.title.strip())
        logger.debug(f"Generated news hash: {news_hash}")

        news_history = load_news_history()
        if news_hash in news_history:
            logger.debug(f"Found duplicate news for URL {url}. Skipping content extraction.")
            return "duplicate"


        saved_embeddings = load_saved_embeddings()

        try:
            logger.debug("Starting BERT embedding process...")
            new_embedding = get_sbert_embedding(full_content)
            logger.debug(f"Generated BERT embedding: {new_embedding}")
        except Exception as e:
            logger.error(f"Failed to generate BERT embedding: {str(e)}")
            new_embedding = None

        if new_embedding is not None:

            if is_similar_sbert(new_embedding, saved_embeddings):
                logger.info(f"Vector found similar news content for URL {url}. Skipping content extraction.")
                return "vector"


            saved_embeddings.append(new_embedding)
            save_embeddings(saved_embeddings)
        else:
            logger.warning("Skipping similarity check and saving due to failure in generating embedding.")


        images = extract_images_from_html(soup, url)
        logger.debug(f"Extracted {len(images)} images")

        save_news_history(news_hash)
        logger.debug(f"Saved news hash to history")
        logger.info(f"Successfully fetched article content with images")

        return {
            'title': article.title.strip(),
            'content': full_content,
            'images': [img[0] if isinstance(img, tuple) else img for img in images],
            'videos': article.movies
        }
    except Exception as e:
        logger.error(f"Error fetching article content from {url}: {str(e)}", exc_info=True)
        return {
            'title': '',
            'content': '',
            'images': [],
            'videos': []
        }


def extract_content_manually(soup, url):
    """Manually extracts text content from HTML."""
    if "vijesti.me" in url:
        return extract_text_with_soup(soup, 'div[itemprop="articleBody"]')
    elif "bankar.me" in url:
        return extract_text_with_soup(soup, 'div.entry-content')
    elif "rtcg.me" in url:
        return extract_text_with_soup(soup, 'div.storyFull.fix')
    elif "podgorica.me" in url:
        return extract_text_with_soup(soup, 'div.elementor-widget-theme-post-content')
    elif "cdm.me" in url:
        return extract_text_with_soup(soup, 'div.entry-content.herald-entry-content')
    elif "mans.co.me" in url:
        return extract_text_with_soup(soup, 'div.post-content.description')
    elif "investitor.me" in url:
        return extract_text_with_soup(soup, 'div.entry-content.clearfix')
    else:
        return "Content not available"


def extract_text_with_soup(soup, container_selector, paragraph_selector='p'):
    """Extracts text from HTML using BeautifulSoup."""
    article_body = soup.select_one(container_selector)
    if not article_body:
        logger.warning(f"No article body found using selector: {container_selector}")
        return "Content not available"

    paragraphs = article_body.find_all(paragraph_selector)
    full_text = "\n\n".join([p.get_text(strip=True) for p in paragraphs])

    if full_text:
        logger.info(f"Successfully extracted content: {full_text[:20]}...")
    else:
        logger.warning(f"No content extracted from {container_selector}")

    return full_text



def format_table_as_code_block(table_tag):
    """Formats a table as a code block."""
    rows = table_tag.find_all('tr')
    table_data = []
    for row in rows:
        cells = row.find_all(['th', 'td'])
        cell_texts = [cell.get_text(strip=True) for cell in cells]
        table_data.append(" | ".join(cell_texts))

    table_text = "\n".join(table_data)
    return f"```\n{table_text}\n```"


def format_article_content(content):
    """Formats text by adding spaces between paragraphs."""
    paragraphs = content.split('\n')
    formatted_content = '\n\n'.join([p.strip() for p in paragraphs if p.strip()])
    logger.debug(f"Formatted article content: {formatted_content[:60]}...")
    return formatted_content

