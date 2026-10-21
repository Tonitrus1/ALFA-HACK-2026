"""Run the fixed development queries against real local E5 / Qdrant, without an LLM."""

import json
from datetime import UTC, datetime
from pathlib import Path

from alfa_assistant.cli import dump, service
from alfa_assistant.config import Settings


def main():
    cfg = Settings()
    kb = service(cfg)
    questions = json.loads(Path("evaluation/rag-questions.json").read_text(encoding="utf-8"))
    rows = []
    for row in questions:
        query = row["question"] + "\n" + row.get("previous_question", "")
        found = kb.search(query)
        expected = row["expected"]
        rows.append(
            {
                "id": row["id"],
                "question": row["question"],
                "expected": expected,
                "titles": [f["title"] for f in found],
                "found_count": len(found),
                "hit_at_5": any(expected in f["title"] for f in found) if expected else None,
                "abstained": not found,
            }
        )
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "experimental": True,
        "llm_used": False,
        "threshold": cfg.dense_min_score,
        "answerable_hit_at_5": sum(r["hit_at_5"] is True for r in rows),
        "answerable_count": sum(bool(r["expected"]) for r in rows),
        "unanswerable_abstained": sum(not r["expected"] and r["abstained"] for r in rows),
        "unanswerable_count": sum(not r["expected"] for r in rows),
        "rows": rows,
    }
    dump(Path("reports/retrieval-development.json"), report)
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}))


if __name__ == "__main__":
    main()
