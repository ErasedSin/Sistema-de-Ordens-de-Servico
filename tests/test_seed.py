from app.database import get_conn
from app.seed import CLIENTES, ORDENS, SENHA_DEMO, USUARIO_DEMO, popular


def test_seed_cria_dados_e_usuario_demo(anonimo):
    conn = get_conn()
    assert popular(conn) is True
    assert popular(conn) is False
    conn.close()

    assert len(anonimo.get("/clientes").json()) == len(CLIENTES)
    assert len(anonimo.get("/ordens").json()) == len(ORDENS)
    r = anonimo.post("/login", json={"usuario": USUARIO_DEMO, "senha": SENHA_DEMO})
    assert r.status_code == 200


def test_historico_do_seed_termina_no_status_atual(anonimo):
    conn = get_conn()
    popular(conn)
    conn.close()

    for ordem in anonimo.get("/ordens").json():
        detalhe = anonimo.get(f"/ordens/{ordem['id']}").json()
        assert detalhe["historico"][-1]["status_novo"] == ordem["status"]
        assert (detalhe["concluida_em"] is not None) == (ordem["status"] == "concluida")
