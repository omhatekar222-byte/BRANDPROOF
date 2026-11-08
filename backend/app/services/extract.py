"""Text extraction for uploaded content and knowledge documents.

Every extractor either returns the document's real text or raises a clear
ExtractionError. Nothing is fabricated when a file cannot be read. OCR is only
attempted when its optional dependencies are installed; otherwise the caller is
told that image analysis is unavailable in this deployment.
"""
from __future__ import annotations

import io
import re
import zipfile
from html import unescape
from pathlib import Path

from app.services.pdf import PdfExtractionError, extract_pdf


class ExtractionError(Exception):
    pass


DOCX_EXTENSIONS = {".docx"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _extract_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            if "word/document.xml" not in names:
                raise ExtractionError("This file is not a readable Word document (.docx).")
            xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
    except zipfile.BadZipFile as exc:
        raise ExtractionError("This .docx file is corrupted and could not be read.") from exc

    xml = re.sub(r"</w:p\s*>", "\n", xml)
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    xml = re.sub(r"<w:br[^>]*/>", "\n", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    text = unescape(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_image(data: bytes) -> str:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as exc:  # noqa: BLE001 - optional dependency
        raise ExtractionError(
            "Image text extraction (OCR) is not available in this deployment. "
            "Upload a PDF, DOCX, TXT or MD file with selectable text instead."
        ) from exc
    try:
        return pytesseract.image_to_string(Image.open(io.BytesIO(data))).strip()
    except Exception as exc:  # noqa: BLE001 - provider/tooling error
        raise ExtractionError("OCR could not read this image.") from exc


def extract_text(filename: str, data: bytes) -> str:
    """Return extracted text for a supported upload, or raise ExtractionError."""
    suffix = Path(filename or "").suffix.lower()
    if suffix in PDF_EXTENSIONS:
        try:
            return extract_pdf(data)["text"]
        except PdfExtractionError as exc:
            raise ExtractionError(str(exc)) from exc
    if suffix in DOCX_EXTENSIONS:
        return _extract_docx(data)
    if suffix in TEXT_EXTENSIONS:
        return data.decode("utf-8", errors="replace").strip()
    if suffix in IMAGE_EXTENSIONS:
        return _extract_image(data)
    raise ExtractionError(
        "Unsupported file type. Supported: PDF, DOCX, TXT, MD"
        + (" and image files where OCR is available." if True else ".")
    )


def is_supported_extension(filename: str) -> bool:
    suffix = Path(filename or "").suffix.lower()
    return suffix in (
        DOCX_EXTENSIONS | TEXT_EXTENSIONS | PDF_EXTENSIONS | IMAGE_EXTENSIONS
    )
