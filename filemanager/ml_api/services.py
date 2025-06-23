# ml_api/services.py
import pytesseract
import spacy
import cv2
import numpy as np
from datetime import datetime
import re
import logging
from pathlib import Path
from django.conf import settings
import pdf2image
from docx import Document
import zipfile
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Load NLP models
try:
    nlp = spacy.load(settings.SPACY_MODEL)
except OSError:
    logger.error(f"Spacy model {settings.SPACY_MODEL} not found. Please install it first.")
    nlp = None


def run_tesseract(image_path):
    """Обработка изображения с помощью Tesseract OCR"""
    try:
        # Установите путь к Tesseract если нужно
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

        # Чтение изображения
        img = cv2.imread(image_path)
        if img is None:
            return {"status": "error", "message": "Could not read image file"}

        # Преобразование в оттенки серого
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Применение пороговой обработки
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Распознавание текста
        custom_config = r'--oem 3 --psm 6 -l rus+eng'
        text = pytesseract.image_to_string(thresh, config=custom_config)

        return {
            "status": "success",
            "text": text,
            "language": "rus+eng"
        }
    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}")
        return {"status": "error", "message": str(e)}


def run_spacy(text):
    """Анализ текста с помощью spaCy NER"""
    try:
        if not nlp:
            return {"status": "error", "message": "Spacy model not loaded"}

        doc = nlp(text)

        # Извлечение именованных сущностей
        entities = [
            {"text": ent.text, "type": ent.label_, "start": ent.start_char, "end": ent.end_char}
            for ent in doc.ents
        ]

        return {
            "status": "success",
            "entities": entities,
            "language": "ru"
        }
    except Exception as e:
        logger.error(f"NER processing failed: {str(e)}")
        return {"status": "error", "message": str(e)}


def preprocess_image(image_path):
    """Preprocess image for better OCR results"""
    try:
        # Read image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("Could not read image")

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        # Denoise
        denoised = cv2.fastNlMeansDenoising(thresh, h=10)

        return denoised
    except Exception as e:
        logger.error(f"Image preprocessing failed: {str(e)}")
        return None


def process_image_with_ocr(image_path):
    """Process image file with OCR"""
    try:
        # Preprocess image
        processed_img = preprocess_image(image_path)
        if processed_img is None:
            return {'status': 'error', 'message': 'Image preprocessing failed'}

        # Run Tesseract OCR
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
        custom_config = r'--oem 3 --psm 6 -l rus+eng'
        text = pytesseract.image_to_string(processed_img, config=custom_config)

        if not text.strip():
            return {'status': 'error', 'message': 'No text found in image'}

        # Analyze text
        analysis = analyze_text(text)

        return {
            'status': 'success',
            'type': 'ocr',
            'data': {
                'text': text,
                'language': analysis['language'],
                'entities': analysis['entities'],
                'sentiment': analysis['sentiment']
            },
            'metadata': {
                'processing_steps': ['grayscale', 'thresholding', 'denoising'],
                'original_path': image_path
            }
        }
    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def process_text_with_ner(text):
    """Process text with NER"""
    try:
        if not nlp:
            return {'status': 'error', 'message': 'NLP model not loaded'}

        # Analyze text
        analysis = analyze_text(text)

        return {
            'status': 'success',
            'type': 'ner',
            'data': {
                'text': text,
                'language': analysis['language'],
                'entities': analysis['entities'],
                'sentiment': analysis['sentiment'],
                'keywords': analysis['keywords']
            },
            'metadata': {
                'model': settings.SPACY_MODEL
            }
        }
    except Exception as e:
        logger.error(f"NER processing failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def analyze_text(text):
    """Analyze text for language, entities, sentiment, etc."""
    if not text.strip():
        return {
            'language': 'unknown',
            'entities': [],
            'sentiment': 'neutral',
            'keywords': []
        }

    # Detect language
    language = detect_language(text)

    # Extract entities if NLP model is available
    entities = []
    keywords = []
    if nlp:
        doc = nlp(text)
        entities = [
            {'text': ent.text, 'type': ent.label_, 'start': ent.start_char, 'end': ent.end_char}
            for ent in doc.ents
        ]

        # Extract keywords (nouns and proper nouns)
        keywords = [
                       token.text for token in doc
                       if token.pos_ in ('NOUN', 'PROPN') and len(token.text) > 3
                   ][:10]

    # Simple sentiment analysis
    sentiment = analyze_sentiment(text, language)

    return {
        'language': language,
        'entities': entities,
        'sentiment': sentiment,
        'keywords': keywords
    }


def detect_language(text):
    """Detect language of text (simple implementation)"""
    cyrillic_count = sum(1 for c in text if 'а' <= c <= 'я' or 'А' <= c <= 'Я')
    ratio = cyrillic_count / max(len(text), 1)
    return 'ru' if ratio > 0.3 else 'en'


def analyze_sentiment(text, language='ru'):
    """Simple sentiment analysis"""
    positive_words_ru = ['хорош', 'отличн', 'прекрасн', 'рекоменд', 'довол']
    negative_words_ru = ['плох', 'ужасн', 'недовол', 'разочарован']

    positive_words_en = ['good', 'excellent', 'great', 'recommend', 'happy']
    negative_words_en = ['bad', 'terrible', 'disappoint', 'poor']

    positive_words = positive_words_ru if language == 'ru' else positive_words_en
    negative_words = negative_words_ru if language == 'ru' else negative_words_en

    text_lower = text.lower()
    positive = sum(1 for word in positive_words if word in text_lower)
    negative = sum(1 for word in negative_words if word in text_lower)

    if positive > negative:
        return 'positive'
    elif negative > positive:
        return 'negative'
    return 'neutral'


def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using OCR"""
    try:
        images = pdf2image.convert_from_path(pdf_path)
        text = ""
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

        for i, image in enumerate(images):
            page_text = pytesseract.image_to_string(image, lang='rus+eng')
            text += f"\n\nPage {i + 1}:\n{page_text}"

        return text.strip()
    except Exception as e:
        logger.error(f"PDF extraction failed: {str(e)}")
        return None


def extract_text_from_docx(docx_path):
    """Extract text from DOCX file"""
    try:
        doc = Document(docx_path)
        return "\n".join(para.text for para in doc.paragraphs if para.text.strip())
    except Exception as e:
        logger.error(f"DOCX extraction failed: {str(e)}")
        return None