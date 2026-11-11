from datetime import datetime, timedelta, timezone

from app.auth import criar_usuario
from app.database import get_conn, init_db
from app.main import TRANSICOES

USUARIO_DEMO = "demo"
SENHA_DEMO = "demo1234"

CLIENTES = [
    ("Marina Toledo", "(21) 98811-2040", "marina.toledo@exemplo.com"),
    ("Rafael Quintela", "(21) 97702-3311", None),
    ("Padaria Pão Dourado", "(21) 3344-5566", "contato@paodourado.exemplo.com"),
    ("Helena Bastos", "(21) 99654-7788", "helena.bastos@exemplo.com"),
    ("Otávio Ramalho", "(21) 98123-9090", None),
    ("Escritório Nogueira & Prado", "(21) 2233-4455", "ti@nogueiraprado.exemplo.com"),
]

EQUIPAMENTOS = [
    (0, "notebook", "Lenovo", "IdeaPad 3", "PF2A7XQ1"),
    (1, "desktop", "Positivo", "Master D380", None),
    (2, "impressora", "Epson", "L3250", "X8EK004512"),
    (2, "desktop", "Dell", "OptiPlex 3080", "7FJ2KX3"),
    (3, "celular", "Samsung", "Galaxy A54", None),
    (4, "notebook", "Acer", "Aspire 5", "NXHN3AL00X"),
    (5, "notebook", "Dell", "Latitude 5420", "9QK1L33"),
    (5, "impressora", "HP", "LaserJet M111w", None),
]

ORDENS = [
    (0, "Notebook muito lento e esquentando bastante", "Pasta térmica ressecada e cooler sujo", 180.0,
     ["em_analise", "concluida"], 12),
    (1, "Não liga, nenhuma luz acende", "Fonte queimada", 320.0,
     ["em_analise", "aguardando_peca", "em_analise", "concluida"], 9),
    (2, "Impressora puxando duas folhas de uma vez", None, None, ["em_analise"], 3),
    (3, "Tela azul ao abrir o sistema da padaria", "Pente de memória com defeito", 210.0,
     ["em_analise", "aguardando_peca"], 5),
    (4, "Tela trincada depois de uma queda", None, None, ["cancelada"], 7),
    (5, "Wi-Fi cai toda hora", None, None, [], 1),
    (6, "Teclado com várias teclas falhando", "Teclado precisa ser trocado", 260.0,
     ["em_analise", "aguardando_peca"], 4),
    (7, "Papel enroscando na saída", "Rolete de tração gasto", 95.0, ["em_analise", "concluida"], 15),
    (0, "Pediu formatação e backup dos arquivos", None, None, [], 0),
]


def quando(dias_atras: float) -> str:
    momento = datetime.now(timezone.utc) - timedelta(days=dias_atras)
    return momento.strftime("%Y-%m-%d %H:%M:%S")


def popular(db) -> bool:
    if db.execute("SELECT 1 FROM usuarios WHERE usuario = ?", (USUARIO_DEMO,)).fetchone() is None:
        criar_usuario(db, USUARIO_DEMO, SENHA_DEMO)
    if db.execute("SELECT COUNT(*) FROM clientes").fetchone()[0] > 0:
        return False

    with db:
        clientes = [
            db.execute("INSERT INTO clientes (nome, telefone, email) VALUES (?, ?, ?)", c).lastrowid
            for c in CLIENTES
        ]
        equipamentos = [
            db.execute(
                "INSERT INTO equipamentos (cliente_id, tipo, marca, modelo, numero_serie) VALUES (?, ?, ?, ?, ?)",
                (clientes[dono], tipo, marca, modelo, serie),
            ).lastrowid
            for dono, tipo, marca, modelo, serie in EQUIPAMENTOS
        ]
        for equipamento, defeito, diagnostico, valor, caminho, dias in ORDENS:
            ordem = db.execute(
                "INSERT INTO ordens_servico (equipamento_id, defeito_relatado, aberta_em) VALUES (?, ?, ?)",
                (equipamentos[equipamento], defeito, quando(dias)),
            ).lastrowid
            db.execute(
                "INSERT INTO historico_status (ordem_id, status_anterior, status_novo, alterado_em) "
                "VALUES (?, NULL, 'aberta', ?)",
                (ordem, quando(dias)),
            )
            atual = "aberta"
            for passo, novo in enumerate(caminho, start=1):
                if novo not in TRANSICOES[atual]:
                    raise ValueError(f"Seed com transição inválida: {atual} -> {novo}")
                momento = quando(dias - passo * dias / (len(caminho) + 1))
                db.execute(
                    "INSERT INTO historico_status (ordem_id, status_anterior, status_novo, alterado_em) "
                    "VALUES (?, ?, ?, ?)",
                    (ordem, atual, novo, momento),
                )
                if novo == "concluida":
                    db.execute("UPDATE ordens_servico SET concluida_em = ? WHERE id = ?", (momento, ordem))
                atual = novo
            db.execute(
                "UPDATE ordens_servico SET status = ?, diagnostico = ?, valor = ? WHERE id = ?",
                (atual, diagnostico, valor, ordem),
            )
    return True


if __name__ == "__main__":
    init_db()
    conn = get_conn()
    try:
        criou = popular(conn)
    finally:
        conn.close()
    print("Dados de exemplo criados." if criou else "O banco já tinha dados; só conferi o usuário demo.")
