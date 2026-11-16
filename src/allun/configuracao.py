"""Leitura do arquivo `.env` com as chaves de API (sem dependências externas)."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _interpretar(linha: str) -> tuple[str, str] | None:
    linha = linha.strip()
    if not linha or linha.startswith("#") or "=" not in linha:
        return None
    nome, _, valor = linha.partition("=")
    nome = nome.removeprefix("export ").strip()
    valor = valor.strip()
    if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
        valor = valor[1:-1]
    elif " #" in valor:  # comentário no fim da linha, só fora de aspas
        valor = valor.split(" #", 1)[0].strip()
    return (nome, valor) if nome.isidentifier() and valor else None


def caminho_env() -> Path:
    return Path(os.environ.get("ALLUN_ENV") or RAIZ / ".env")


def carregar_env(caminho: Path | str | None = None) -> list[str]:
    """Carrega variáveis do `.env` sem sobrescrever as que já existem no ambiente.

    Procura `ALLUN_ENV`, depois `.env` na raiz do projeto. Devolve os nomes carregados
    (nunca os valores).
    """
    alvo = Path(caminho) if caminho else caminho_env()
    if not alvo.is_file():
        return []
    carregadas = []
    for linha in alvo.read_text(encoding="utf-8").splitlines():
        par = _interpretar(linha)
        if par and par[0] not in os.environ:
            os.environ[par[0]] = par[1]
            carregadas.append(par[0])
    return carregadas


# ---------- edição de chaves pelo painel ----------

_NOME_VALIDO = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
_VALOR_VALIDO = re.compile(r"^[\x21-\x7e]{1,512}$")  # ASCII visível, sem espaço nem quebra de linha


def validar_chave(nome: str, valor: str) -> str:
    """Devolve o valor limpo ou levanta ValueError. Barra injeção de linhas no `.env`."""
    if not _NOME_VALIDO.match(nome):
        raise ValueError("Nome de variável inválido.")
    valor = valor.strip()
    if not _VALOR_VALIDO.match(valor):
        raise ValueError("A chave deve ter de 1 a 512 caracteres visíveis, sem espaços.")
    return valor


def _linha_da(nome: str, linha: str) -> bool:
    par = linha.strip().removeprefix("export ").lstrip()
    return par.startswith((nome + "=", nome + " ="))


def _gravar_env(alvo: Path, linhas: list[str]) -> None:
    alvo.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=alvo.parent, prefix=".env.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(linhas).rstrip("\n") + "\n")
        os.replace(tmp, alvo)  # troca atômica: nunca deixa o arquivo pela metade
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def salvar_chave(nome: str, valor: str, caminho: Path | str | None = None) -> None:
    """Grava `nome=valor` no `.env` (mantendo o resto do arquivo) e no ambiente atual."""
    valor = validar_chave(nome, valor)
    alvo = Path(caminho) if caminho else caminho_env()
    linhas = alvo.read_text(encoding="utf-8").splitlines() if alvo.is_file() else []
    novas, achou = [], False
    for linha in linhas:
        if _linha_da(nome, linha):
            if not achou:
                novas.append(f"{nome}={valor}")
            achou = True  # descarta duplicatas
        else:
            novas.append(linha)
    if not achou:
        novas.append(f"{nome}={valor}")
    _gravar_env(alvo, novas)
    os.environ[nome] = valor


def remover_chave(nome: str, caminho: Path | str | None = None) -> None:
    """Esvazia a chave: tira do `.env` e do ambiente atual."""
    if not _NOME_VALIDO.match(nome):
        raise ValueError("Nome de variável inválido.")
    alvo = Path(caminho) if caminho else caminho_env()
    if alvo.is_file():
        linhas = [
            x for x in alvo.read_text(encoding="utf-8").splitlines() if not _linha_da(nome, x)
        ]
        _gravar_env(alvo, linhas)
    os.environ.pop(nome, None)


def mascarar(valor: str) -> str:
    """Mostra só os 4 últimos caracteres (e nada se a chave for curta)."""
    return "••••" + valor[-4:] if len(valor) >= 12 else "••••"


def definida_no_env(nome: str, caminho: Path | str | None = None) -> bool:
    alvo = Path(caminho) if caminho else caminho_env()
    if not alvo.is_file():
        return False
    for linha in alvo.read_text(encoding="utf-8").splitlines():
        par = _interpretar(linha) if _linha_da(nome, linha) else None
        if par:
            return True
    return False
