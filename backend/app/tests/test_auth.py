"""
Tests for authentication endpoints.
Run with: pytest app/tests/ -v
"""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data


def test_login_invalid_credentials():
    with patch("app.api.v1.routers.auth._get_service") as mock_svc:
        from app.core.exceptions import UnauthorizedException
        mock_instance = MagicMock()
        mock_instance.login.side_effect = UnauthorizedException("Invalid email or password")
        mock_svc.return_value = mock_instance

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@test.com", "password": "wrongpass"},
        )
        assert response.status_code == 401


def test_me_unauthenticated():
    response = client.get("/api/v1/auth/me")
    # 403 because HTTPBearer raises 403 when no token is provided
    assert response.status_code == 403


def test_register_requires_authentication():
    # Desde la Fase 2, POST /auth/register es solo para administradores.
    # (La validación 422 con un admin autenticado se prueba en test_auth_security.py)
    response = client.post("/api/v1/auth/register", json={"email": "bad"})
    assert response.status_code == 403
