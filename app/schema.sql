CREATE TABLE IF NOT EXISTS clientes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT NOT NULL,
  telefone TEXT NOT NULL,
  email TEXT UNIQUE,
  criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS equipamentos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
  tipo TEXT NOT NULL CHECK (tipo IN ('desktop', 'notebook', 'celular', 'impressora', 'outro')),
  marca TEXT NOT NULL,
  modelo TEXT NOT NULL,
  numero_serie TEXT,
  criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ordens_servico (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  equipamento_id INTEGER NOT NULL REFERENCES equipamentos(id),
  defeito_relatado TEXT NOT NULL,
  diagnostico TEXT,
  status TEXT NOT NULL DEFAULT 'aberta'
    CHECK (status IN ('aberta', 'em_analise', 'aguardando_peca', 'concluida', 'cancelada')),
  valor REAL CHECK (valor IS NULL OR valor >= 0),
  aberta_em TEXT NOT NULL DEFAULT (datetime('now')),
  concluida_em TEXT
);

CREATE TABLE IF NOT EXISTS historico_status (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ordem_id INTEGER NOT NULL REFERENCES ordens_servico(id) ON DELETE CASCADE,
  status_anterior TEXT,
  status_novo TEXT NOT NULL,
  alterado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_equipamentos_cliente ON equipamentos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_ordens_equipamento ON ordens_servico(equipamento_id);
CREATE INDEX IF NOT EXISTS idx_ordens_status ON ordens_servico(status);
CREATE INDEX IF NOT EXISTS idx_historico_ordem ON historico_status(ordem_id);
