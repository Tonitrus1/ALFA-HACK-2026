from alfa_ocr.backend_worker import financial_fields


def field(value, status="extracted"):
    return {"status": status, "value": value, "confidence": 0.9, "sources": [{"page": 2}]}


def test_does_not_invent_missing_fields_or_map_debt_to_liabilities():
    finance = {
        "revenue": field("123.45"),
        "total_debt": field("50"),
        "equity": field(None, "conflict"),
        "currency": field("RUB"),
    }
    assert financial_fields({"financial": finance}) == [
        {"name": "revenue", "value": "123.45", "confidence": 0.9, "page": 2}
    ]


def test_foreign_or_unknown_currency_does_not_become_rubles():
    for currency in [field("USD"), field(None, "missing")]:
        assert financial_fields({"financial": {"revenue": field("10"), "currency": currency}}) == []
