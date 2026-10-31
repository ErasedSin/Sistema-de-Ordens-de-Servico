import sqlite3
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from app.database import get_db, init_db

Tipo = Literal["desktop", "notebook", "celular", "impressora", "outro"]
Status = Literal["aberta", "em_analise", "aguardando_peca", "concluida", "cancelada"]

TRANSICOES = {
    "aberta": {"em_analise", "cancelada"},
    "em_analise": {"aguardando_peca", "concluida", "cancelada"},
    "aguardando_peca": {"em_analise", "cancelada"},
    "concluida": set(),
    "cancelada": set(),
}

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Sistema de Ordens de Serviço", lifespan=lifespan)


class ClienteIn(BaseModel):
    nome: str = Field(min_length=2, max_length=100)
    telefone: str = Field(min_length=8, max_length=20)
    email: Optional[str] = Field(default=None, pattern=EMAIL)


class Cliente(ClienteIn):
    id: int
    criado_em: str


class EquipamentoIn(BaseModel):
    cliente_id: int
    tipo: Tipo
    marca: str = Field(min_length=1, max_length=60)
    modelo: str = Field(min_length=1, max_length=60)
    numero_serie: Optional[str] = Field(default=None, max_length=60)


class Equipamento(EquipamentoIn):
    id: int
    criado_em: str


class OrdemIn(BaseModel):
    equipamento_id: int
    defeito_relatado: str = Field(min_length=5, max_length=500)


class OrdemUpdate(BaseModel):
    diagnostico: Optional[str] = Field(default=None, max_length=1000)
    valor: Optional[float] = Field(default=None, ge=0)


class StatusIn(BaseModel):
    status: Status


class Historico(BaseModel):
    status_anterior: Optional[str]
    status_novo: str
    alterado_em: str


class Ordem(BaseModel):
    id: int
    equipamento_id: int
    defeito_relatado: str
    diagnostico: Optional[str]
    status: Status
    valor: Optional[float]
    aberta_em: str
    concluida_em: Optional[str]


class OrdemDetalhe(Ordem):
    historico: list[Historico]


def um(db, sql, params, mensagem):
    row = db.execute(sql, params).fetchone()
    if row is None:
        raise HTTPException(404, mensagem)
    return dict(row)


def detalhe_ordem(db, ordem_id):
    ordem = um(db, "SELECT * FROM ordens_servico WHERE id = ?", (ordem_id,), "Ordem não encontrada")
    historico = db.execute(
        "SELECT status_anterior, status_novo, alterado_em FROM historico_status WHERE ordem_id = ? ORDER BY id",
        (ordem_id,),
    )
    ordem["historico"] = [dict(h) for h in historico]
    return ordem


@app.post("/clientes", response_model=Cliente, status_code=201)
def criar_cliente(dados: ClienteIn, db: sqlite3.Connection = Depends(get_db)):
    try:
        with db:
            cur = db.execute(
                "INSERT INTO clientes (nome, telefone, email) VALUES (?, ?, ?)",
                (dados.nome, dados.telefone, dados.email),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Já existe um cliente com esse e-mail")
    return um(db, "SELECT * FROM clientes WHERE id = ?", (cur.lastrowid,), "Cliente não encontrado")


@app.get("/clientes", response_model=list[Cliente])
def listar_clientes(busca: Optional[str] = None, db: sqlite3.Connection = Depends(get_db)):
    if busca:
        rows = db.execute("SELECT * FROM clientes WHERE nome LIKE ? ORDER BY nome", (f"%{busca}%",))
    else:
        rows = db.execute("SELECT * FROM clientes ORDER BY nome")
    return [dict(r) for r in rows]


@app.get("/clientes/{cliente_id}", response_model=Cliente)
def obter_cliente(cliente_id: int, db: sqlite3.Connection = Depends(get_db)):
    return um(db, "SELECT * FROM clientes WHERE id = ?", (cliente_id,), "Cliente não encontrado")


@app.put("/clientes/{cliente_id}", response_model=Cliente)
def atualizar_cliente(cliente_id: int, dados: ClienteIn, db: sqlite3.Connection = Depends(get_db)):
    um(db, "SELECT id FROM clientes WHERE id = ?", (cliente_id,), "Cliente não encontrado")
    try:
        with db:
            db.execute(
                "UPDATE clientes SET nome = ?, telefone = ?, email = ? WHERE id = ?",
                (dados.nome, dados.telefone, dados.email, cliente_id),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Já existe um cliente com esse e-mail")
    return um(db, "SELECT * FROM clientes WHERE id = ?", (cliente_id,), "Cliente não encontrado")


@app.delete("/clientes/{cliente_id}", status_code=204)
def remover_cliente(cliente_id: int, db: sqlite3.Connection = Depends(get_db)):
    um(db, "SELECT id FROM clientes WHERE id = ?", (cliente_id,), "Cliente não encontrado")
    try:
        with db:
            db.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Cliente possui ordens de serviço e não pode ser removido")
    return Response(status_code=204)


@app.post("/equipamentos", response_model=Equipamento, status_code=201)
def criar_equipamento(dados: EquipamentoIn, db: sqlite3.Connection = Depends(get_db)):
    um(db, "SELECT id FROM clientes WHERE id = ?", (dados.cliente_id,), "Cliente não encontrado")
    with db:
        cur = db.execute(
            "INSERT INTO equipamentos (cliente_id, tipo, marca, modelo, numero_serie) VALUES (?, ?, ?, ?, ?)",
            (dados.cliente_id, dados.tipo, dados.marca, dados.modelo, dados.numero_serie),
        )
    return um(db, "SELECT * FROM equipamentos WHERE id = ?", (cur.lastrowid,), "Equipamento não encontrado")


@app.get("/equipamentos", response_model=list[Equipamento])
def listar_equipamentos(cliente_id: Optional[int] = None, db: sqlite3.Connection = Depends(get_db)):
    if cliente_id is not None:
        rows = db.execute("SELECT * FROM equipamentos WHERE cliente_id = ? ORDER BY id", (cliente_id,))
    else:
        rows = db.execute("SELECT * FROM equipamentos ORDER BY id")
    return [dict(r) for r in rows]


@app.get("/equipamentos/{equipamento_id}", response_model=Equipamento)
def obter_equipamento(equipamento_id: int, db: sqlite3.Connection = Depends(get_db)):
    return um(db, "SELECT * FROM equipamentos WHERE id = ?", (equipamento_id,), "Equipamento não encontrado")


@app.post("/ordens", response_model=OrdemDetalhe, status_code=201)
def abrir_ordem(dados: OrdemIn, db: sqlite3.Connection = Depends(get_db)):
    um(db, "SELECT id FROM equipamentos WHERE id = ?", (dados.equipamento_id,), "Equipamento não encontrado")
    with db:
        cur = db.execute(
            "INSERT INTO ordens_servico (equipamento_id, defeito_relatado) VALUES (?, ?)",
            (dados.equipamento_id, dados.defeito_relatado),
        )
        db.execute(
            "INSERT INTO historico_status (ordem_id, status_anterior, status_novo) VALUES (?, NULL, 'aberta')",
            (cur.lastrowid,),
        )
    return detalhe_ordem(db, cur.lastrowid)


@app.get("/ordens", response_model=list[Ordem])
def listar_ordens(status: Optional[Status] = None, db: sqlite3.Connection = Depends(get_db)):
    if status:
        rows = db.execute("SELECT * FROM ordens_servico WHERE status = ? ORDER BY id DESC", (status,))
    else:
        rows = db.execute("SELECT * FROM ordens_servico ORDER BY id DESC")
    return [dict(r) for r in rows]


@app.get("/ordens/{ordem_id}", response_model=OrdemDetalhe)
def obter_ordem(ordem_id: int, db: sqlite3.Connection = Depends(get_db)):
    return detalhe_ordem(db, ordem_id)


@app.patch("/ordens/{ordem_id}", response_model=OrdemDetalhe)
def atualizar_ordem(ordem_id: int, dados: OrdemUpdate, db: sqlite3.Connection = Depends(get_db)):
    ordem = um(db, "SELECT * FROM ordens_servico WHERE id = ?", (ordem_id,), "Ordem não encontrada")
    if ordem["status"] in ("concluida", "cancelada"):
        raise HTTPException(409, "Ordem encerrada não pode ser alterada")
    campos = dados.model_dump(exclude_unset=True)
    if campos:
        sets = ", ".join(f"{campo} = ?" for campo in campos)
        with db:
            db.execute(f"UPDATE ordens_servico SET {sets} WHERE id = ?", (*campos.values(), ordem_id))
    return detalhe_ordem(db, ordem_id)


@app.patch("/ordens/{ordem_id}/status", response_model=OrdemDetalhe)
def mudar_status(ordem_id: int, dados: StatusIn, db: sqlite3.Connection = Depends(get_db)):
    ordem = um(db, "SELECT * FROM ordens_servico WHERE id = ?", (ordem_id,), "Ordem não encontrada")
    permitidos = TRANSICOES[ordem["status"]]
    if dados.status not in permitidos:
        raise HTTPException(
            409,
            f"Não é possível ir de {ordem['status']} para {dados.status}. Permitidos: {sorted(permitidos) or 'nenhum'}",
        )
    with db:
        db.execute(
            "UPDATE ordens_servico SET status = ?, "
            "concluida_em = CASE WHEN ? = 'concluida' THEN datetime('now') ELSE concluida_em END WHERE id = ?",
            (dados.status, dados.status, ordem_id),
        )
        db.execute(
            "INSERT INTO historico_status (ordem_id, status_anterior, status_novo) VALUES (?, ?, ?)",
            (ordem_id, ordem["status"], dados.status),
        )
    return detalhe_ordem(db, ordem_id)


@app.get("/relatorios/resumo")
def resumo(db: sqlite3.Connection = Depends(get_db)):
    por_status = {
        r["status"]: r["total"]
        for r in db.execute("SELECT status, COUNT(*) AS total FROM ordens_servico GROUP BY status")
    }
    valor = db.execute(
        "SELECT COALESCE(SUM(valor), 0) AS total FROM ordens_servico WHERE status = 'concluida'"
    ).fetchone()["total"]
    return {"ordens_por_status": por_status, "valor_concluidas": valor}
