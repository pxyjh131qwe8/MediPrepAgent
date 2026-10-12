import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["LLM_API_KEY"] = ""
os.environ["DEBUG"] = "false"

from fastapi.testclient import TestClient

from app.api.main import app


def test_consultation_runs_full_team_and_preserves_negation():
    payload = {
        "symptoms": "头痛三天，但没有胸痛、呼吸困难和肢体无力",
        "duration": "3天",
        "thread_id": "integration-test",
    }

    with TestClient(app) as client:
        response = client.post("/health/consult", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["risk_result"]["risk_level"] == "LOW"
    assert set(data["risk_result"]["negated_signals"]) >= {"胸痛", "呼吸困难", "肢体无力"}
    assert data["department_result"]["primary_department"] == "神经内科"
    assert len(data["agent_trace"]) == 5
    assert data["quality"]["safety_reviewed"] is True
    assert data["evidence"][0]["source"] == "headache.md"
