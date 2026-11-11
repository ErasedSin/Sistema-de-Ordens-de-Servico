import pytest
from fastapi.testclient import TestClient

from app.auth import criar_usuario
from app.database import get_conn
from app.main import app

USUARIO = "tecnico"
SENHA = "senha-de-teste"


@pytest.fixture
def anonimo(tmp_path, monkeypatch):
    monkeypatch.setenv("OS_DB", str(tmp_path / "teste.db"))
    with TestClient(app) as c:
        conn = get_conn()
        criar_usuario(conn, USUARIO, SENHA)
        conn.close()
        yield c


@pytest.fixture
def client(anonimo):
    r = anonimo.post("/login", json={"usuario": USUARIO, "senha": SENHA})
    anonimo.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return anonimo
