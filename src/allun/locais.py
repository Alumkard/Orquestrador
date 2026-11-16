"""Onde o Allun guarda dados nesta máquina, e avisos quando algo está fora do padrão."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from allun.armazenamento import caminho_padrao
from allun.configuracao import caminho_env
from allun.projetos import base_projetos

_VARIAVEIS = ("ALLUN_DB", "ALLUN_ENV", "ALLUN_PROJETOS")
_PACOTE = Path(__file__).resolve().parent
INICIO = time.time()  # momento em que este processo carregou o código


def codigo_alterado_depois_do_inicio() -> bool:
    """True se algum .py ou o catálogo mudou depois que a API subiu (ela roda código velho)."""
    for arquivo in (*_PACOTE.rglob("*.py"), _PACOTE / "catalogo" / "catalogo.json"):
        try:
            if arquivo.stat().st_mtime > INICIO + 1:
                return True
        except OSError:
            continue
    return False


def _em_temporaria(caminho: Path) -> bool:
    temp = Path(tempfile.gettempdir()).resolve()
    alvo = caminho.resolve()
    return alvo == temp or temp in alvo.parents


def locais_em_uso(banco: Path | None = None) -> dict:
    banco = banco or caminho_padrao()
    avisos = []
    for nome in _VARIAVEIS:
        if os.environ.get(nome):
            avisos.append(f"A variável {nome} está definida e muda o local padrão.")
    for rotulo, caminho in (
        ("O banco de tarefas", banco),
        ("A pasta de projetos", base_projetos()),
    ):
        if _em_temporaria(caminho):
            avisos.append(
                f"{rotulo} está numa pasta temporária ({caminho}) e pode ser apagado pelo Windows."
            )
    if codigo_alterado_depois_do_inicio():
        avisos.append(
            "O código do Allun mudou depois que a API foi iniciada, e ela ainda roda a versão "
            "antiga. Pare com Ctrl+C e inicie de novo."
        )
    return {
        "banco": str(banco),
        "chaves": str(caminho_env()),
        "projetos": str(base_projetos()),
        "avisos": avisos,
    }


def descrever_locais(banco: Path | None = None) -> list[str]:
    info = locais_em_uso(banco)
    linhas = [
        f"Banco de tarefas: {info['banco']}",
        f"Pasta de projetos automáticos: {info['projetos']}",
    ]
    linhas += [f"AVISO: {a}" for a in info["avisos"]]
    return linhas
