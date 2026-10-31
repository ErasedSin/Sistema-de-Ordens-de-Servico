import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OS_DB", str(tmp_path / "teste.db"))
    with TestClient(app) as c:
        yield c


def novo_cliente(client, email="ana@exemplo.com"):
    r = client.post("/clientes", json={"nome": "Ana Souza", "telefone": "21999990000", "email": email})
    assert r.status_code == 201
    return r.json()


def novo_equipamento(client, cliente_id):
    r = client.post(
        "/equipamentos",
        json={"cliente_id": cliente_id, "tipo": "notebook", "marca": "Dell", "modelo": "Inspiron 14"},
    )
    assert r.status_code == 201
    return r.json()


def nova_ordem(client, equipamento_id):
    r = client.post("/ordens", json={"equipamento_id": equipamento_id, "defeito_relatado": "Não liga"})
    assert r.status_code == 201
    return r.json()


def test_email_duplicado_retorna_409(client):
    novo_cliente(client)
    r = client.post("/clientes", json={"nome": "Outra Ana", "telefone": "21988880000", "email": "ana@exemplo.com"})
    assert r.status_code == 409


def test_dados_invalidos_retornam_422(client):
    r = client.post("/clientes", json={"nome": "A", "telefone": "1", "email": "invalido"})
    assert r.status_code == 422


def test_equipamento_de_cliente_inexistente_retorna_404(client):
    r = client.post(
        "/equipamentos",
        json={"cliente_id": 999, "tipo": "desktop", "marca": "Dell", "modelo": "Optiplex"},
    )
    assert r.status_code == 404


def test_fluxo_completo_da_ordem(client):
    equipamento = novo_equipamento(client, novo_cliente(client)["id"])
    ordem = nova_ordem(client, equipamento["id"])
    assert ordem["status"] == "aberta"

    for novo in ["em_analise", "concluida"]:
        r = client.patch(f"/ordens/{ordem['id']}/status", json={"status": novo})
        assert r.status_code == 200

    final = r.json()
    assert final["concluida_em"] is not None
    assert [h["status_novo"] for h in final["historico"]] == ["aberta", "em_analise", "concluida"]


def test_transicao_invalida_retorna_409(client):
    ordem = nova_ordem(client, novo_equipamento(client, novo_cliente(client)["id"])["id"])
    r = client.patch(f"/ordens/{ordem['id']}/status", json={"status": "concluida"})
    assert r.status_code == 409


def test_ordem_encerrada_nao_pode_ser_alterada(client):
    ordem = nova_ordem(client, novo_equipamento(client, novo_cliente(client)["id"])["id"])
    client.patch(f"/ordens/{ordem['id']}/status", json={"status": "cancelada"})
    r = client.patch(f"/ordens/{ordem['id']}", json={"valor": 50})
    assert r.status_code == 409


def test_nao_remove_cliente_com_ordens(client):
    cliente = novo_cliente(client)
    nova_ordem(client, novo_equipamento(client, cliente["id"])["id"])
    assert client.delete(f"/clientes/{cliente['id']}").status_code == 409


def test_resumo_soma_apenas_ordens_concluidas(client):
    equipamento = novo_equipamento(client, novo_cliente(client)["id"])
    concluida = nova_ordem(client, equipamento["id"])
    nova_ordem(client, equipamento["id"])

    client.patch(f"/ordens/{concluida['id']}/status", json={"status": "em_analise"})
    client.patch(f"/ordens/{concluida['id']}", json={"valor": 150})
    client.patch(f"/ordens/{concluida['id']}/status", json={"status": "concluida"})

    resumo = client.get("/relatorios/resumo").json()
    assert resumo["valor_concluidas"] == 150
    assert resumo["ordens_por_status"] == {"concluida": 1, "aberta": 1}
