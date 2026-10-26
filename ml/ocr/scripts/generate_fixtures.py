"""Only invented data. Intentionally invalid identifiers, never real customers."""

import json
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures/generated"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

CASES = {
    "passport": [
        "СИНТЕТИЧЕСКИЙ ПРИМЕР - НЕ ДОКУМЕНТ",
        "ПАСПОРТ ГРАЖДАНИНА РФ",
        "Фамилия Имя Отчество: ИВАНОВ ИВАН ИВАНОВИЧ",
        "Дата рождения: 15.05.1990",
        "Серия паспорта: 0000",
        "Номер паспорта: 000001",
    ],
    "inn": [
        "СИНТЕТИЧЕСКИЙ ПРИМЕР - НЕ ДОКУМЕНТ",
        "СВИДЕТЕЛЬСТВО ИНН",
        "ФИО: ИВАНОВ ИВАН ИВАНОВИЧ",
        "ИНН физического лица: 000000000001",
    ],
    "snils": [
        "СИНТЕТИЧЕСКИЙ ПРИМЕР - НЕ ДОКУМЕНТ",
        "СНИЛС",
        "ФИО: ИВАНОВ ИВАН ИВАНОВИЧ",
        "Страховой номер: 000-000-000 01",
    ],
    "statement": [
        "СИНТЕТИЧЕСКИЙ ПРИМЕР - НЕ ДОКУМЕНТ",
        "БАНКОВСКАЯ ВЫПИСКА",
        "Компания: ООО СИНТЕТИКА",
        "ИНН организации: 0000000002",
        "Период: 2025 год",
        "Валюта: RUB. Суммы в рублях.",
        "Выручка: 12000000.00",
        "Чистая прибыль: 1500000.00",
    ],
    "financial": [
        "СИНТЕТИЧЕСКИЙ ПРИМЕР - НЕ ДОКУМЕНТ",
        "ФИНАНСОВЫЙ ОТЧЕТ",
        "Компания: ООО СИНТЕТИКА",
        "Период: 2025 год. Валюта: RUB. Суммы в рублях.",
        "Выручка: 12000000.00",
        "Чистая прибыль: 1500000.00",
        "EBIT: 2000000.00",
        "Капитал: 5000000.00",
        "Активы всего: 10000000.00",
        "Оборотные активы: 4000000.00",
        "Краткосрочные обязательства: 2500000.00",
        "Общий долг: 3000000.00",
    ],
    "conflict": [
        "СИНТЕТИЧЕСКИЙ ПРИМЕР - НЕ ДОКУМЕНТ",
        "УТОЧНЕННЫЙ ФИНАНСОВЫЙ ОТЧЕТ",
        "Компания: ООО СИНТЕТИКА",
        "Период: 2025 год. Валюта: RUB. Суммы в рублях.",
        "Выручка: 13000000.00",
    ],
    "other": [
        "СИНТЕТИЧЕСКИЙ ПРИМЕР - НЕ ДОКУМЕНТ",
        "СПРАВКА",
        "Регистрационный код: DEMO-2026",
        "Контактное лицо: ИВАНОВ ИВАН ИВАНОВИЧ",
    ],
}


def generate():
    OUT.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(FONT_PATH, 32)
    truth = {}
    for name, lines in CASES.items():
        image = Image.new("RGB", (1654, 2339), "white")
        draw = ImageDraw.Draw(image)
        for index, line in enumerate(lines):
            draw.text((90, 130 + index * 75), line, font=font, fill="black")
        image.save(OUT / f"{name}.png")
        # PDF intentionally contains only a raster image: no text layer shortcut.
        pdf = pymupdf.open()
        page = pdf.new_page(width=794, height=1123)
        page.insert_image(page.rect, filename=str(OUT / f"{name}.png"))
        pdf.save(OUT / f"{name}.pdf", deflate=True, garbage=4)
        truth[name] = "\n".join(lines)
    image = Image.open(OUT / "financial.png")
    image.rotate(2, fillcolor="white").save(OUT / "financial_rotated.jpg", quality=65)
    Image.new("RGB", (1000, 1400), "white").save(OUT / "blank.png")
    pdf = pymupdf.open()
    for _index in range(51):
        pdf.new_page()
    pdf.save(OUT / "over_limit.pdf")
    (OUT / "truth.json").write_text(
        json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Generated {len(CASES)} synthetic cases, rotated scan, blank and 51-page PDF")


if __name__ == "__main__":
    generate()
