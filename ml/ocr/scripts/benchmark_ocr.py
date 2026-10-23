"""Real model benchmark. Does not use mocks, PDF text extraction or an LLM."""

import json
import re
import time
from pathlib import Path

from PIL import Image

from alfa_ocr.engines import Engine

ROOT = Path(__file__).resolve().parents[1]


def distance(left, right):
    row = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        new = [i]
        for j, b in enumerate(right, 1):
            new.append(min(new[-1] + 1, row[j] + 1, row[j - 1] + (a != b)))
        row = new
    return row[-1]


def normalized(text):
    return re.sub(r"\s+", " ", text.casefold()).strip()


def run():
    truth = json.loads((ROOT / "fixtures/generated/truth.json").read_text(encoding="utf-8"))
    report = {
        "synthetic_only": True,
        "method": "lowercase + collapse whitespace; Levenshtein CER/WER; cold load separated from warm page inference",
        "engines": {},
    }
    for name in ["paddle", "tesseract"]:
        engine = Engine(name)
        start = time.monotonic()
        engine.load()
        result = {
            "mkldnn": engine.mkldnn if name == "paddle" else None,
            "version": engine.version(),
            "load_seconds": round(time.monotonic() - start, 3),
            "cases": {},
        }
        for case, text in truth.items():
            start = time.monotonic()
            blocks = engine.recognize(Image.open(ROOT / f"fixtures/generated/{case}.png"))
            actual = normalized(" ".join(b.text for b in blocks))
            expected = normalized(text)
            result["cases"][case] = {
                "cer": round(distance(expected, actual) / len(expected), 5),
                "wer": round(distance(expected.split(), actual.split()) / len(expected.split()), 5),
                "seconds": round(time.monotonic() - start, 3),
                "blocks": len(blocks),
            }
        blocks = engine.recognize(Image.open(ROOT / "fixtures/generated/financial_rotated.jpg"))
        expected = normalized(truth["financial"])
        actual = normalized(" ".join(b.text for b in blocks))
        result["cases"]["financial_rotated"] = {
            "cer": round(distance(expected, actual) / len(expected), 5),
            "wer": round(distance(expected.split(), actual.split()) / len(expected.split()), 5),
        }
        result["mean_clean_cer"] = round(
            sum(v["cer"] for k, v in result["cases"].items() if k != "financial_rotated")
            / len(truth),
            5,
        )
        report["engines"][name] = result
    target = ROOT / "reports/ocr-benchmark.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    run()
