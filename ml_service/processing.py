import pytesseract
import spacy
import cv2
import numpy as np
from datetime import datetime
import re
from typing import Dict, Any, List, Optional
from spacy.lang.ru import Russian
from spacy.tokens import Doc

# Загрузка моделей
nlp = spacy.load("ru_core_news_sm")
nlp_en = spacy.load("en_core_web_sm")

# Регулярные выражения для извлечения данных
DATE_PATTERNS = [
    r'\d{1,2}\.\d{1,2}\.\d{2,4}',
    r'\d{1,2}/\d{1,2}/\d{2,4}',
    r'\d{1,2}\s+[а-я]+\s+\d{4}'
]

MONEY_PATTERNS = [
    r'\d+\s*[рр]уб[\w]*',
    r'\$\s*\d+',
    r'\d+\s*евро',
    r'\d+\s*USD'
]


def detect_language(text: str) -> str:
    """Определение языка текста"""
    cyrillic = sum(1 for char in text if 'а' <= char <= 'я' or 'А' <= char <= 'Я')
    return 'ru' if cyrillic / len(text) > 0.3 else 'en' if text else 'unknown'


def extract_dates(text: str) -> List[str]:
    """Извлечение дат из текста"""
    dates = []
    for pattern in DATE_PATTERNS:
        dates.extend(re.findall(pattern, text))
    return dates


def extract_money(text: str) -> List[str]:
    """Извлечение денежных сумм"""
    amounts = []
    for pattern in MONEY_PATTERNS:
        amounts.extend(re.findall(pattern, text, re.IGNORECASE))
    return amounts


def analyze_sentiment(text: str, lang: str = 'ru') -> Dict[str, Any]:
    """Простой анализ тональности текста"""
    positive_words_ru = ['хорош', 'отличн', 'прекрасн', 'рекоменд', 'довол']
    negative_words_ru = ['плох', 'ужасн', 'недовол', 'разочарован', 'не рекоменд']

    positive_words_en = ['good', 'excellent', 'great', 'recommend', 'happy']
    negative_words_en = ['bad', 'terrible', 'disappoint', 'poor', 'not recommend']

    positive_words = positive_words_ru if lang == 'ru' else positive_words_en
    negative_words = negative_words_ru if lang == 'ru' else negative_words_en

    text_lower = text.lower()
    positive = sum(1 for word in positive_words if word in text_lower)
    negative = sum(1 for word in negative_words if word in text_lower)

    score = positive - negative
    sentiment = 'neutral'
    if score > 0:
        sentiment = 'positive'
    elif score < 0:
        sentiment = 'negative'

    return {
        'sentiment': sentiment,
        'score': score,
        'positive': positive,
        'negative': negative
    }


def run_tesseract(file_content: bytes) -> Dict[str, Any]:
    """Улучшенная обработка изображений с дополнительным анализом"""
    try:
        # Конвертация в numpy array
        nparr = np.frombuffer(file_content, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Предварительная обработка изображения
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Распознавание текста
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        custom_config = r'--oem 3 --psm 6 -l rus+eng'
        text = pytesseract.image_to_string(thresh, config=custom_config)

        # Дополнительный анализ
        language = detect_language(text)
        dates = extract_dates(text)
        money = extract_money(text)
        sentiment = analyze_sentiment(text, language) if len(text.split()) > 5 else None

        return {
            "status": "success",
            "text": text.strip(),
            "analysis": {
                "language": language,
                "dates": dates,
                "money_amounts": money,
                "sentiment": sentiment,
                "processing": "grayscale+contrast+threshold"
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


def run_spacy(text: str) -> Dict[str, Any]:
    """Улучшенная обработка текста с извлечением сущностей и анализом"""
    try:
        # Определение языка и выбор модели
        language = detect_language(text)
        nlp_model = nlp if language == 'ru' else nlp_en

        # Обработка текста
        doc = nlp_model(text)

        # Извлечение сущностей
        entities = [
            {"text": ent.text, "type": ent.label_, "start": ent.start_char, "end": ent.end_char}
            for ent in doc.ents
        ]

        # Дополнительный анализ
        dates = extract_dates(text)
        money = extract_money(text)
        sentiment = analyze_sentiment(text, language) if len(text.split()) > 5 else None

        # Ключевые слова (первые 5 существительных)
        keywords = [
                       token.text for token in doc
                       if token.pos_ in ['NOUN', 'PROPN'] and len(token.text) > 3
                   ][:5]

        return {
            "status": "success",
            "entities": entities,
            "analysis": {
                "language": language,
                "dates": dates,
                "money_amounts": money,
                "sentiment": sentiment,
                "keywords": keywords
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }