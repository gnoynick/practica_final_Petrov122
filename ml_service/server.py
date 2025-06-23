from fastapi import FastAPI, UploadFile, HTTPException, status, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import logging
from typing import Dict, Any
import asyncio
from .processing import run_tesseract, run_spacy

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="File Processing API",
    description="API для обработки файлов с помощью OCR и NER",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Конфигурация обработки файлов
SUPPORTED_IMAGE_TYPES = {'.png', '.jpg', '.jpeg', '.pdf'}
SUPPORTED_TEXT_TYPES = {'.txt', '.docx', '.odt'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@app.get("/", include_in_schema=False)
async def root():
    """Корневой эндпоинт с информацией об API"""
    return {
        "message": "File Processing API",
        "endpoints": {
            "process_file": {
                "method": "POST",
                "path": "/process/",
                "description": "Обработка загруженных файлов"
            },
            "health_check": {
                "method": "GET",
                "path": "/health/",
                "description": "Проверка работоспособности сервиса"
            }
        }
    }


@app.post("/process/",
          response_model=Dict[str, Any],
          responses={
              200: {"description": "Успешная обработка файла"},
              400: {"description": "Некорректный формат или размер файла"},
              422: {"description": "Ошибка обработки содержимого"},
              500: {"description": "Внутренняя ошибка сервера"}
          })
async def process_uploaded_file(file: UploadFile = File(...)):
    """
    Обрабатывает загруженный файл, автоматически определяя тип обработки:
    - Tesseract OCR для изображений/PDF
    - spaCy NER для текстовых файлов

    Поддерживаемые форматы:
    - Изображения: PNG, JPG, JPEG, PDF
    - Текстовые: TXT, DOCX, ODT
    - Максимальный размер: 10MB
    """
    try:
        # Валидация файла
        file_ext, content = await validate_and_read_file(file)

        # Определение типа обработки
        if file_ext in SUPPORTED_IMAGE_TYPES:
            return await process_image_content(file.filename, content)
        elif file_ext in SUPPORTED_TEXT_TYPES:
            return await process_text_content(file.filename, content)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


async def validate_and_read_file(file: UploadFile) -> tuple[str, bytes]:
    """Валидация и чтение файла"""
    # Проверка размера
    file_size = len(await file.read())
    await file.seek(0)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Размер файла превышает {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )

    # Проверка расширения
    file_ext = Path(file.filename).suffix.lower()
    if not file_ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл не имеет расширения"
        )

    if file_ext not in SUPPORTED_IMAGE_TYPES | SUPPORTED_TEXT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неподдерживаемый формат файла: {file_ext}"
        )

    return file_ext, await file.read()


async def process_image_content(filename: str, content: bytes) -> Dict[str, Any]:
    """Обработка изображений через Tesseract OCR"""
    logger.info(f"Начата обработка изображения: {filename}")
    try:
        result = await asyncio.to_thread(run_tesseract, content)

        if result.get('status') != 'success':
            logger.warning(f"OCR processing failed for {filename}: {result.get('message')}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=result.get('message', 'Ошибка OCR обработки')
            )

        logger.info(f"Успешно обработано изображение: {filename}")
        return {
            "status": "success",
            "type": "ocr",
            "filename": filename,
            "result": result
        }

    except Exception as e:
        logger.error(f"Ошибка обработки изображения {filename}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка обработки изображения"
        )


async def process_text_content(filename: str, content: bytes) -> Dict[str, Any]:
    """Обработка текстовых файлов через spaCy NER"""
    logger.info(f"Начата обработка текстового файла: {filename}")
    try:
        # Попытка декодирования в UTF-8, затем в CP1251
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            text = content.decode('cp1251')

        result = await asyncio.to_thread(run_spacy, text)

        if result.get('status') != 'success':
            logger.warning(f"NER processing failed for {filename}: {result.get('message')}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=result.get('message', 'Ошибка NER обработки')
            )

        logger.info(f"Успешно обработан текстовый файл: {filename}")
        return {
            "status": "success",
            "type": "ner",
            "filename": filename,
            "result": result
        }

    except Exception as e:
        logger.error(f"Ошибка обработки текста {filename}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка обработки текста"
        )


@app.get("/health/",
         response_model=Dict[str, str],
         tags=["Мониторинг"])
async def health_check():
    """Проверка работоспособности сервиса"""
    return {
        "status": "ok",
        "service": "file_processor",
        "version": app.version
    }