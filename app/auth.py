import hashlib
import hmac
import secrets
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.database import get_db

ITERACOES = 200_000
VALIDADE_TOKEN = "+8 hours"

bearer = HTTPBearer(auto_error=False)
router = APIRouter(tags=["login"])


def gerar_hash(senha: str, salt: str | None = None, iteracoes: int = ITERACOES) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(salt), iteracoes)
    return f"pbkdf2_sha256${iteracoes}${salt}${digest.hex()}"


def conferir_senha(senha: str, guardado: str) -> bool:
    _, iteracoes, salt, _ = guardado.split("$")
    return hmac.compare_digest(gerar_hash(senha, salt, int(iteracoes)), guardado)


def criar_usuario(db: sqlite3.Connection, usuario: str, senha: str) -> int:
    with db:
        cur = db.execute(
            "INSERT INTO usuarios (usuario, senha_hash) VALUES (?, ?)",
            (usuario, gerar_hash(senha)),
        )
    return cur.lastrowid


def nao_autorizado(mensagem: str) -> HTTPException:
    return HTTPException(401, mensagem, headers={"WWW-Authenticate": "Bearer"})


def usuario_atual(
    credenciais: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    if credenciais is None:
        raise nao_autorizado("Faça login para continuar")
    row = db.execute(
        "SELECT u.id, u.usuario FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id "
        "WHERE s.token = ? AND s.expira_em > datetime('now')",
        (credenciais.credentials,),
    ).fetchone()
    if row is None:
        raise nao_autorizado("Sessão inválida ou expirada. Entre de novo")
    return dict(row)


class LoginIn(BaseModel):
    usuario: str
    senha: str


class Token(BaseModel):
    token: str
    tipo: str = "bearer"


class Usuario(BaseModel):
    id: int
    usuario: str


@router.post("/login", response_model=Token)
def login(dados: LoginIn, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT id, senha_hash FROM usuarios WHERE usuario = ?", (dados.usuario,)).fetchone()
    if row is None or not conferir_senha(dados.senha, row["senha_hash"]):
        raise nao_autorizado("Usuário ou senha incorretos")
    token = secrets.token_urlsafe(32)
    with db:
        db.execute(
            "INSERT INTO sessoes (token, usuario_id, expira_em) VALUES (?, ?, datetime('now', ?))",
            (token, row["id"], VALIDADE_TOKEN),
        )
    return {"token": token}


@router.post("/logout", status_code=204)
def logout(
    credenciais: HTTPAuthorizationCredentials | None = Depends(bearer),
    _: dict = Depends(usuario_atual),
    db: sqlite3.Connection = Depends(get_db),
):
    with db:
        db.execute("DELETE FROM sessoes WHERE token = ?", (credenciais.credentials,))
    return Response(status_code=204)


@router.get("/me", response_model=Usuario)
def eu(usuario: dict = Depends(usuario_atual)):
    return usuario
