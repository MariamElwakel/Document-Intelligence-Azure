from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
import io
import os
from PIL import Image
from dotenv import load_dotenv
import numpy as np

load_dotenv()

endpoint = os.getenv("OCR_ENDPOINT")
key = os.getenv("OCR_KEY")

client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))


def ocr_crop(image, bbox, scale_x=1, scale_y=1):
    """
    Crop image using bbox + scaling and run OCR on it
    """

    # -------------------------------
    # Convert bbox → original image coords
    # -------------------------------
    left   = int(bbox["left"] * scale_x)
    top    = int(bbox["top"] * scale_y)
    right  = int((bbox["left"] + bbox["width"]) * scale_x)
    bottom = int((bbox["top"] + bbox["height"]) * scale_y)

    # -------------------------------
    # Clamp داخل حدود الصورة
    # -------------------------------
    left   = max(0, left)
    top    = max(0, top)
    right  = min(image.width, right)
    bottom = min(image.height, bottom)

    # -------------------------------
    # Fix small boxes (Azure requirement)
    # -------------------------------
    MIN_DIM = 50

    crop_w = right - left
    crop_h = bottom - top

    if crop_w < MIN_DIM:
        pad = (MIN_DIM - crop_w) // 2
        left  = max(0, left - pad)
        right = min(image.width, right + pad)

    if crop_h < MIN_DIM:
        pad = (MIN_DIM - crop_h) // 2
        top    = max(0, top - pad)
        bottom = min(image.height, bottom + pad)

    # -------------------------------
    # Crop
    # -------------------------------
    cropped = image.crop((left, top, right, bottom))

    # -------------------------------
    # Upscale لو صغير قوي
    # -------------------------------
    if cropped.width < MIN_DIM or cropped.height < MIN_DIM:
        scale = max(MIN_DIM / cropped.width, MIN_DIM / cropped.height)
        cropped = cropped.resize(
            (int(cropped.width * scale), int(cropped.height * scale)),
            Image.LANCZOS
        )

    # -------------------------------
    # Convert to bytes
    # -------------------------------
    img_bytes = io.BytesIO()
    cropped.save(img_bytes, format="PNG")
    img_bytes_value = img_bytes.getvalue()

    # -------------------------------
    # OCR باستخدام Azure Read
    # -------------------------------
    poller = client.begin_analyze_document(
        "prebuilt-read",
        body=img_bytes_value,
        content_type="application/octet-stream"
    )

    result = poller.result()

    # -------------------------------
    # Extract text
    # -------------------------------
    if result.pages:
        return " ".join(
            line.content
            for page in result.pages
            for line in (page.lines or [])
        ).strip()

    return ""