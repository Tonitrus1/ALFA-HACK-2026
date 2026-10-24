import json
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path

from .errors import ServiceError
from .schemas import AnnuityArgs


class SyntheticBankGateway:
    def __init__(self, fixture_path: Path):
        self.data = json.loads(fixture_path.read_text(encoding="utf-8"))

    def user(self, user_id):
        for user in self.data["users"]:
            if user["id"] == user_id:
                return user
        raise ServiceError("DEMO_USER_NOT_FOUND", 404)

    def products(self):
        return {
            "provenance": {"type": "SYNTHETIC_BANK", "fixture_version": "1"},
            "products": self.data["products"],
        }

    def application(self, application_id, company_id):
        for app in self.data["applications"]:
            if app["id"] == application_id and app["company_id"] == company_id:
                return {
                    "provenance": {"type": "SYNTHETIC_BANK", "fixture_version": "1"},
                    "application": app,
                }
        raise ServiceError("APPLICATION_NOT_FOUND", 404)

    def documents(self, args, company_id):
        product_id = args.product_id
        if args.application_id:
            app = self.application(args.application_id, company_id)["application"]
            product_id = app["product_id"]
        for p in self.data["products"]:
            if p["id"] == product_id:
                return {
                    "provenance": {"type": "SYNTHETIC_BANK", "fixture_version": "1"},
                    "product_id": product_id,
                    "documents": p["documents"],
                }
        raise ServiceError("PRODUCT_NOT_FOUND", 404)


def annuity(args: AnnuityArgs):
    with localcontext() as ctx:
        ctx.prec = 40
        r = args.annual_rate / Decimal(1200)
        payment = (
            args.amount / args.months if not r else args.amount * r / (1 - (1 + r) ** -args.months)
        )
        payment = payment.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return {
            "payment_rub": str(payment),
            "approximate_total_rub": str(payment * args.months),
            "provenance": {"type": "CALCULATION", "formula": "annuity_v1"},
            "notice": "Примерный расчёт без комиссий и индивидуальных условий. Не предложение банка.",
        }


class BackendContextGateway(SyntheticBankGateway):
    """Read-only snapshot rebuilt by the authenticated backend for every chat turn."""

    def __init__(self, context):
        self.data = context

    def products(self):
        return {"provenance": {"type": "BACKEND_SNAPSHOT"}, "products": self.data["products"]}

    def application(self, application_id, company_id):
        result = super().application(application_id, company_id)
        result["provenance"] = {"type": "BACKEND_SNAPSHOT"}
        return result

    def documents(self, args, company_id):
        result = super().documents(args, company_id)
        result["provenance"] = {"type": "BACKEND_SNAPSHOT"}
        return result
