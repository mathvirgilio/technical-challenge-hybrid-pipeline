from fastapi.testclient import TestClient

from hybrid_pipeline.api.app import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_modernize_minimal():
    sql = (
        "CREATE OR REPLACE FUNCTION fn_test() RETURNS INT LANGUAGE plpgsql "
        "AS $$ BEGIN RETURN 1; END; $$;"
    )
    response = client.post("/modernize", json={"source_code": sql})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("success", "partial", "failure")
    assert "report" in body
