from io import BytesIO

from pypdf import PdfReader


class PdfExtractionError(Exception):
    pass


def extract_pdf(data: bytes) -> dict:
    """Return {"text": str, "pages": [{"page": int, "text": str}]}.

    Page numbers come from the actual PDF page objects. If the PDF has no
    embedded text layer (e.g. a scan) we fail clearly instead of fabricating
    content; OCR is a documented limitation.
    """
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                raise PdfExtractionError("This PDF is password protected and cannot be read.") from exc
        pages = []
        for i, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append({"page": i, "text": text})
        full = "\n\n".join(p["text"] for p in pages).strip()
        if not full:
            raise PdfExtractionError(
                "No selectable text was found in this PDF. It may be a scanned image; "
                "OCR is not enabled in this deployment."
            )
        return {"text": full, "pages": pages}
    except PdfExtractionError:
        raise
    except Exception as exc:
        raise PdfExtractionError("The PDF could not be read. It may be corrupted.") from exc
