"""Histórico de tarefas e mensagens em SQLite (arquivo local do usuário)."""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS tarefas (
    id TEXT PRIMARY KEY,
    titulo TEXT NOT NULL,
    criada REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS mensagens (
    id TEXT PRIMARY KEY,
    tarefa_id TEXT NOT NULL REFERENCES tarefas(id) ON DELETE CASCADE,
    papel TEXT NOT NULL CHECK (papel IN ('usuario', 'allun')),
    texto TEXT NOT NULL,
    agente TEXT,
    modelo TEXT,
    duracao_s REAL,
    erro INTEGER NOT NULL DEFAULT 0,
    criada REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_mensagens_tarefa ON mensagens(tarefa_id, criada);
CREATE TABLE IF NOT EXISTS memoria (
    tarefa_id TEXT PRIMARY KEY REFERENCES tarefas(id) ON DELETE CASCADE,
    resumo TEXT NOT NULL DEFAULT '',
    fatos TEXT NOT NULL DEFAULT '[]',
    cobertas INTEGER NOT NULL DEFAULT 0,
    atualizada REAL NOT NULL
);
"""


def _migrar(con: sqlite3.Connection) -> None:
    """Colunas adicionadas depois da primeira versão (bancos antigos não as têm)."""
    novas = {"tarefas": {"pasta": "TEXT"}, "mensagens": {"arquivos": "TEXT"}}
    for tabela, colunas in novas.items():
        existentes = {linha[1] for linha in con.execute(f"PRAGMA table_info({tabela})")}
        for nome, tipo in colunas.items():
            if nome not in existentes:
                con.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}")


def caminho_padrao() -> Path:
    if env := os.environ.get("ALLUN_DB"):
        return Path(env)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "Allun" / "allun.db"


class Armazenamento:
    def __init__(self, caminho: Path | str | None = None):
        self.caminho = Path(caminho) if caminho else caminho_padrao()
        with self._conexao():
            pass  # cria o arquivo e as tabelas já na inicialização

    @contextmanager
    def _conexao(self):
        # Recria pasta e tabelas se o arquivo sumir com o servidor rodando (ex.: limpeza de disco).
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.caminho)
        con.executescript(_ESQUEMA)  # idempotente e barato (CREATE ... IF NOT EXISTS)
        _migrar(con)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            with con:  # confirma ou desfaz a transação
                yield con
        finally:
            con.close()

    def criar_tarefa(self, titulo: str, pasta: str | None = None) -> dict:
        tarefa = {"id": uuid.uuid4().hex[:12], "titulo": titulo.strip()[:80] or "Nova tarefa"}
        tarefa["criada"] = time.time()
        tarefa["pasta"] = pasta
        with self._conexao() as con:
            con.execute(
                "INSERT INTO tarefas (id, titulo, criada, pasta) VALUES (:id, :titulo, :criada, :pasta)",
                tarefa,
            )
        return tarefa

    def definir_pasta(self, tarefa_id: str, pasta: str | None) -> bool:
        with self._conexao() as con:
            cur = con.execute("UPDATE tarefas SET pasta = ? WHERE id = ?", (pasta, tarefa_id))
            return cur.rowcount > 0

    def listar_tarefas(self) -> list[dict]:
        with self._conexao() as con:
            return [dict(r) for r in con.execute("SELECT * FROM tarefas ORDER BY criada DESC")]

    def obter_tarefa(self, tarefa_id: str) -> dict | None:
        with self._conexao() as con:
            tarefa = con.execute("SELECT * FROM tarefas WHERE id = ?", (tarefa_id,)).fetchone()
            if tarefa is None:
                return None
            msgs = con.execute(
                "SELECT * FROM mensagens WHERE tarefa_id = ? ORDER BY criada, rowid", (tarefa_id,)
            ).fetchall()
        return {**dict(tarefa), "mensagens": [self._msg(m) for m in msgs]}

    @staticmethod
    def _msg(linha: sqlite3.Row) -> dict:
        d = dict(linha)
        d["erro"] = bool(d["erro"])
        if d.get("arquivos"):
            try:
                d["arquivos"] = json.loads(d["arquivos"])
            except json.JSONDecodeError:
                d["arquivos"] = None
        d.pop("tarefa_id", None)
        d.pop("criada", None)
        return {k: v for k, v in d.items() if v is not None}

    def adicionar_mensagem(
        self,
        tarefa_id: str,
        papel: str,
        texto: str,
        *,
        agente: str | None = None,
        modelo: str | None = None,
        duracao_s: float | None = None,
        erro: bool = False,
        arquivos: dict | None = None,
    ) -> dict:
        msg_id = uuid.uuid4().hex[:12]
        with self._conexao() as con:
            con.execute(
                "INSERT INTO mensagens (id, tarefa_id, papel, texto, agente, modelo, duracao_s,"
                " erro, criada, arquivos) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    msg_id,
                    tarefa_id,
                    papel,
                    texto,
                    agente,
                    modelo,
                    duracao_s,
                    int(erro),
                    time.time(),
                    json.dumps(arquivos, ensure_ascii=False) if arquivos else None,
                ),
            )
        return {"id": msg_id}

    def historico(self, tarefa_id: str) -> list[dict[str, str]]:
        """Mensagens no formato do modelo, sem as respostas de erro."""
        tarefa = self.obter_tarefa(tarefa_id)
        if tarefa is None:
            return []
        return [
            {"role": "user" if m["papel"] == "usuario" else "assistant", "content": m["texto"]}
            for m in tarefa["mensagens"]
            if not m.get("erro")
        ]

    def remover_tarefa(self, tarefa_id: str) -> bool:
        with self._conexao() as con:
            return con.execute("DELETE FROM tarefas WHERE id = ?", (tarefa_id,)).rowcount > 0

    def obter_memoria(self, tarefa_id: str) -> dict | None:
        with self._conexao() as con:
            linha = con.execute(
                "SELECT resumo, fatos, cobertas FROM memoria WHERE tarefa_id = ?", (tarefa_id,)
            ).fetchone()
        if linha is None:
            return None
        try:
            fatos = json.loads(linha["fatos"])
        except json.JSONDecodeError:
            fatos = []
        return {"resumo": linha["resumo"], "fatos": fatos, "cobertas": linha["cobertas"]}

    def salvar_memoria(self, tarefa_id: str, resumo: str, fatos: list[str], cobertas: int) -> bool:
        """Grava a memória da tarefa. Devolve False se a tarefa não existir mais."""
        with self._conexao() as con:
            if con.execute("SELECT 1 FROM tarefas WHERE id = ?", (tarefa_id,)).fetchone() is None:
                return False
            con.execute(
                "INSERT INTO memoria (tarefa_id, resumo, fatos, cobertas, atualizada)"
                " VALUES (?, ?, ?, ?, ?) ON CONFLICT(tarefa_id) DO UPDATE SET"
                " resumo = excluded.resumo, fatos = excluded.fatos,"
                " cobertas = excluded.cobertas, atualizada = excluded.atualizada",
                (tarefa_id, resumo, json.dumps(fatos, ensure_ascii=False), cobertas, time.time()),
            )
        return True
