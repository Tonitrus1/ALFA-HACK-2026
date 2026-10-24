"""Backend context is a trusted, read-only per-company snapshot, never a client override."""
import pytest
from alfa_assistant.bank import BackendContextGateway
from alfa_assistant.errors import ServiceError
from alfa_assistant.schemas import DocumentsArgs


def test_backend_snapshot_has_no_synthetic_applications():
    bank = BackendContextGateway({"company_id": "company-a", "products": [
        {"id": "credit", "documents": [{"title": "Отчётность"}]}], "applications": [
        {"id": "real-app", "company_id": "company-a", "product_id": "credit", "status": "REVIEW"}]})
    assert bank.application("real-app", "company-a")["provenance"]["type"] == "BACKEND_SNAPSHOT"
    assert bank.documents(DocumentsArgs(application_id="real-app"), "company-a")["documents"]
    for app, company in [("real-app", "company-b"), ("demo-app-1", "company-a")]:
        with pytest.raises(ServiceError):
            bank.application(app, company)
