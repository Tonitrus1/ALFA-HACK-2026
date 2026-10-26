# Third-party components

Зависимости Python и транзитивные версии: `uv.lock`. Программные лицензии не
заменяют отдельную проверку условий внешнего API при развёртывании.

| Компонент | Назначение | Лицензия / источник |
|---|---|---|
| Python 3.12 | Runtime | PSF |
| FastAPI, Uvicorn, Pydantic, HTTPX | HTTP/API/config | MIT / BSD-3-Clause (Uvicorn, HTTPX) |
| jsonschema | JSON Schema 2020-12 | MIT |
| PaddleOCR 3.3.0, PaddlePaddle 3.2.2, PaddleX 3.3.10 | CPU OCR | Apache-2.0; https://github.com/PaddlePaddle/PaddleOCR |
| PP-OCRv5_mobile_det, cyrillic_PP-OCRv5_mobile_rec | Detection / Russian recognition weights | PaddleOCR official distribution, Apache-2.0; hashes recorded during build |
| Tesseract 5, rus/eng traineddata | Comparison engine | Apache-2.0; https://github.com/tesseract-ocr/tessdata_fast |
| pytesseract | Tesseract wrapper | Apache-2.0 |
| PyMuPDF / MuPDF | PDF rendering/inspection | AGPL-3.0; https://pymupdf.readthedocs.io/en/latest/about.html#license |
| Pillow | Image decoding | MIT-CMU |
| NumPy | Image arrays | BSD-3-Clause |
| DejaVu Sans | Synthetic document font | DejaVu font license |
| uv, Ruff | Dependency locking / lint | MIT or Apache-2.0 |
| pytest | Tests | MIT |
| Debian Bookworm packages | Native runtime | Individual Debian package copyright files in image |
| AITUNNEL | External development LLM API | Provider terms; API is real, not simulated |
| Qwen3-30B-A3B | Configurable external model name | Open model upstream Apache-2.0; provider identity/revision is not verifiable from this service |
| DeepSeek-V4.1-Flash-1017 | Selected external development model alias | MIT upstream code/weights; [official release](https://api-docs.deepseek.com/news/news261017/), [model card/license](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017); provider identity/revision is not verifiable from this service |

PyMuPDF выбран для автономного модуля с открытым исходным кодом. При изменении
способа распространения учитывать AGPL либо заменить рендерер/получить лицензию.
Исходные модели/датасеты клиентов не распространяются. Все документы бенчмарка
авторские синтетические, идентификаторы намеренно невалидны; генератор включён.
Моки есть только в unit/contract tests, не в рабочем конвейере. Локальная LLM,
AV, банковские проверки, backend/frontend integration не реализованы здесь.
