import io
import warnings
from pathlib import Path

import pymupdf
from PIL import Image

from .config import MAX_PAGES, MAX_PIXELS
from .models import ServiceError

Image.MAX_IMAGE_PIXELS = MAX_PIXELS
warnings.simplefilter("error", Image.DecompressionBombWarning)


def inspect(path: Path) -> tuple[str, int]:
    """Trust decoded content, never the filename or supplied MIME type."""
    try:
        with path.open("rb") as stream:
            prefix = stream.read(8)
        if prefix.startswith(b"%PDF-"):
            with pymupdf.open(path) as pdf:
                if pdf.needs_pass or pdf.page_count < 1:
                    raise ServiceError("PDF_ENCRYPTED_OR_EMPTY")
                if pdf.page_count > MAX_PAGES:
                    raise ServiceError("TOO_MANY_PAGES", 413)
                for page in pdf:
                    if page.rect.width <= 0 or page.rect.height <= 0:
                        raise ServiceError("INVALID_PAGE")
                    if page.rect.width * page.rect.height * (200 / 72) ** 2 > MAX_PIXELS:
                        raise ServiceError("PAGE_TOO_LARGE", 413)
                return "application/pdf", pdf.page_count
        with Image.open(path) as image:
            if image.format not in {"PNG", "JPEG", "TIFF"}:
                raise ServiceError("UNSUPPORTED_FORMAT", 415)
            count = getattr(image, "n_frames", 1)
            if count > MAX_PAGES:
                raise ServiceError("TOO_MANY_PAGES", 413)
            for index in range(count):
                image.seek(index)
                if image.width * image.height > MAX_PIXELS:
                    raise ServiceError("PAGE_TOO_LARGE", 413)
                image.load()
            return {"PNG": "image/png", "JPEG": "image/jpeg", "TIFF": "image/tiff"}[
                image.format
            ], count
    except ServiceError:
        raise
    except Exception:
        raise ServiceError("INVALID_DOCUMENT") from None


def render(path: Path, media_type: str, dpi: int):
    if media_type == "application/pdf":
        with pymupdf.open(path) as pdf:
            for page in pdf:
                pixmap = page.get_pixmap(dpi=dpi, alpha=False, colorspace=pymupdf.csRGB)
                # Rasterize even text PDFs: benchmark always exercises actual OCR.
                yield Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
    else:
        with Image.open(path) as image:
            for index in range(getattr(image, "n_frames", 1)):
                image.seek(index)
                yield image.convert("RGB")
