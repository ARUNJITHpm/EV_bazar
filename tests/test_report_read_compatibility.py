"""Old report values remain readable and are returned without rewriting."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.internal import reports
from tests.test_report_pipeline import _assemble

pytest_plugins = ("tests.test_report_pipeline",)


def test_stored_report_with_null_operator_irr_is_returned_verbatim(monkeypatch, session):
    payload = _assemble(session).model_dump(exclude_defaults=True)
    for operator in payload["cpo"]:
        operator["irr_p50_pct"] = None
    monkeypatch.setattr(reports, "get_payload", lambda session, report_id: payload)
    app = FastAPI()
    app.include_router(reports.router, prefix="/api/internal")
    app.dependency_overrides[reports.get_session] = lambda: None
    response = TestClient(app).get(f"/api/internal/reports/{payload['report_id']}")
    assert response.status_code == 200
    assert response.json() == payload
    assert "generated_at" not in response.json()
