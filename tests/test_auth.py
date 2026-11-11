from app.auth import conferir_senha, gerar_hash
from app.database import get_conn
from tests.conftest import SENHA, USUARIO

CLIENTE = {"nome": "Bruno Lima", "telefone": "21977770000"}


def test_senha_e_guardada_como_hash(anonimo):
    conn = get_conn()
    guardado = conn.execute("SELECT senha_hash FROM usuarios WHERE usuario = ?", (USUARIO,)).fetchone()[0]
    conn.close()
    assert SENHA not in guardado
    assert guardado.startswith("pbkdf2_sha256$")
    assert conferir_senha(SENHA, guardado)
    assert not conferir_senha("senha-errada", guardado)


def test_mesma_senha_gera_hashes_diferentes():
    assert gerar_hash("123456") != gerar_hash("123456")


def test_login_devolve_token(anonimo):
    r = anonimo.post("/login", json={"usuario": USUARIO, "senha": SENHA})
    assert r.status_code == 200
    token = r.json()["token"]
    me = anonimo.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["usuario"] == USUARIO


def test_senha_errada_e_usuario_inexistente_retornam_401(anonimo):
    assert anonimo.post("/login", json={"usuario": USUARIO, "senha": "errada"}).status_code == 401
    assert anonimo.post("/login", json={"usuario": "ninguem", "senha": SENHA}).status_code == 401


def test_escrita_sem_token_retorna_401(anonimo):
    r = anonimo.post("/clientes", json=CLIENTE)
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_token_invalido_retorna_401(anonimo):
    r = anonimo.post("/clientes", json=CLIENTE, headers={"Authorization": "Bearer token-inventado"})
    assert r.status_code == 401


def test_leitura_continua_livre(anonimo):
    assert anonimo.get("/ordens").status_code == 200
    assert anonimo.get("/relatorios/resumo").status_code == 200


def test_logout_invalida_o_token(client):
    assert client.post("/clientes", json=CLIENTE).status_code == 201
    assert client.post("/logout").status_code == 204
    assert client.post("/clientes", json={**CLIENTE, "nome": "Carla Dias"}).status_code == 401


def test_token_expirado_retorna_401(client):
    conn = get_conn()
    with conn:
        conn.execute("UPDATE sessoes SET expira_em = datetime('now', '-1 minute')")
    conn.close()
    assert client.get("/me").status_code == 401
