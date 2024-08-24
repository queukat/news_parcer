import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'your_default_telegram_token')
AZURE_TRANSLATION_KEY = os.getenv('AZURE_TRANSLATION_KEY', 'your_default_azure_translation_key')
AZURE_ENDPOINT = os.getenv('AZURE_ENDPOINT', 'your_default_azure_endpoint')
AZURE_ANALYTICS_KEY = os.getenv('AZURE_ANALYTICS_KEY', 'your_default_azure_analytics_key')
AZURE_ANALYTICS_ENDPOINT = os.getenv('AZURE_ANALYTICS_ENDPOINT', 'your_default_azure_analytics_endpoint')

SENT_NEWS_FILE = '../sent_news.txt'
SUBSCRIBERS_FILE = '../subscribers.txt'
MAX_MESSAGE_LENGTH = 4000
VECTORS_FILE = "news_vectors.pkl"
VOCAB_FILE = 'tfidf_vocab.pkl'
EMBEDDINGS_FILE = '../news_embeddings.pkl'
NEWS_HASH_FILE = '../news_history.txt'

RSS_FEEDS = [
    "https://www.cdm.me/feed/",
    "https://www.vijesti.me/rss",
    "https://investitor.me/feed/",
    "https://www.rtcg.me/rss.html",
    "https://balkaninsight.com/feed/",
    "https://bankar.me/feed/",
    "https://podgorica.me/feed/",
    "https://www.mans.co.me/feed/"
]

FILTER_KEYWORDS = [
    'lifestyle/', 'sport/', 'zabava/', 'kosovo', 'blog-hamas', 'horoskop',
    'zodijak', '/globus/', '/svijet/', '/dw/', '/bbc/', '/zdravlje'
]
