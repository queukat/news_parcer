import time
import logging
from azure.ai.textanalytics import TextAnalyticsClient, ExtractiveSummaryAction
from azure.ai.translation.text import TextTranslationClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.translation.text.models import InputTextItem
from config import AZURE_TRANSLATION_KEY, AZURE_ENDPOINT, AZURE_ANALYTICS_KEY, AZURE_ANALYTICS_ENDPOINT

logger = logging.getLogger(__name__)

translation_client = TextTranslationClient(endpoint=AZURE_ENDPOINT, credential=AzureKeyCredential(AZURE_TRANSLATION_KEY))
analytics_client = TextAnalyticsClient(endpoint=AZURE_ANALYTICS_ENDPOINT, credential=AzureKeyCredential(AZURE_ANALYTICS_KEY))


def translate_and_summarize(text, target_language='ru', summarize=True):
    """Translates and optionally summarizes the given text."""
    logger.debug(f"Translating text to {target_language}: {text[:60]}...")
    try:
        input_text = [InputTextItem(text=text)]
        time.sleep(1.1)
        response = translation_client.translate(content=input_text, to=[target_language], from_parameter='sr-Latn')

        if response and response[0].translations:
            translated_text = response[0].translations[0].text.strip()
            logger.debug(f"Translation result: {translated_text[:60]}...")

            if summarize and len(translated_text) > 1000:
                logger.warning("Translated text is long, summarizing...")
                translated_text = summarize_text(analytics_client, translated_text)

            return translated_text
        else:
            logger.error("Translation failed or empty response received")
            return text
    except Exception as e:
        logger.error(f"Error translating text: {str(e)}")
        if "429001" in str(e):
            time.sleep(60)
            return translate_and_summarize(text, target_language, summarize)

        return text


def summarize_text(client, text, max_sentences=20):
    """Summarizes the given text using Azure's Text Analytics API."""
    try:
        documents = [{"id": "1", "text": text}]
        poller = client.begin_analyze_actions(
            documents=documents,
            actions=[ExtractiveSummaryAction(max_sentence_count=max_sentences)]
        )
        result = poller.result()
        summary = ""
        for res in result:
            extract_summary_result = res[0]
            if extract_summary_result.is_error:
                logger.error(f"Summarization error: {extract_summary_result.code} - {extract_summary_result.message}")
            else:
                for sentence in extract_summary_result.sentences:
                    summary += sentence.text + "\n\n"
        return summary.strip()
    except Exception as e:
        logger.error(f"Error during summarization: {str(e)}")
        return text
