"""FastAPI request validation tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from launchshield.app import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_health_endpoint_ok() -> None:
    with _client() as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["use_real_payments"] is False


def test_index_renders() -> None:
    with _client() as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "LaunchShield Swarm" in resp.text


def test_create_run_preset_ok() -> None:
    with _client() as client:
        resp = client.post("/api/runs", json={"mode": "preset-stress"})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["run_id"].startswith("run_")
        assert data["mode"] == "preset-stress"
        assert data["stream_url"].endswith("/events")


def test_create_run_custom_ok() -> None:
    payload = {
        "mode": "custom-standard",
        "repo_url": "https://github.com/owner/repo",
        "target_url": "https://example.com",
    }
    with _client() as client:
        resp = client.post("/api/runs", json=payload)
        assert resp.status_code == 200, resp.text
        assert resp.json()["mode"] == "custom-standard"


def test_create_run_rejects_non_github_repo() -> None:
    payload = {
        "mode": "custom-standard",
        "repo_url": "https://gitlab.com/owner/repo",
        "target_url": "https://example.com",
    }
    with _client() as client:
        resp = client.post("/api/runs", json=payload)
        assert resp.status_code == 400


def test_create_run_rejects_non_http_target() -> None:
    payload = {
        "mode": "custom-standard",
        "repo_url": "https://github.com/owner/repo",
        "target_url": "ftp://example.com",
    }
    with _client() as client:
        resp = client.post("/api/runs", json=payload)
        assert resp.status_code == 400


def test_create_run_rejects_invalid_mode() -> None:
    with _client() as client:
        resp = client.post("/api/runs", json={"mode": "nope"})
        assert resp.status_code == 422


def test_create_run_custom_requires_fields() -> None:
    with _client() as client:
        resp = client.post("/api/runs", json={"mode": "custom-standard"})
        assert resp.status_code == 400


def test_get_run_returns_404_for_unknown() -> None:
    with _client() as client:
        resp = client.get("/api/runs/does-not-exist")
        assert resp.status_code == 404
