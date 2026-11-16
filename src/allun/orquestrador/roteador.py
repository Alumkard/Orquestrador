"""Comandante: escolhe qual especialista atende a tarefa."""

from __future__ import annotations

import re
import unicodedata

from .agentes import AGENTE_PADRAO, AGENTES, Agente
from .llm import ProvedorLLM


def prompt_roteador(agentes: dict[str, Agente]) -> str:
    lista = "\n".join(f"- {a.nome}: {a.descricao}" for a in agentes.values())
    return (
        "Você é o Comandante. Escolha o especialista mais adequado para a tarefa do usuário.\n"
        f"Especialistas:\n{lista}\n"
        "Responda APENAS com o nome do especialista, em minúsculas, sem mais nada."
    )


def interpretar_escolha(resposta: str, agentes: dict[str, Agente]) -> str:
    texto = resposta.lower()
    achados = [(texto.find(nome), nome) for nome in agentes if nome in texto]
    return min(achados)[1] if achados else AGENTE_PADRAO


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")


def escolha_por_palavras(pergunta: str, agentes: dict[str, Agente]) -> str | None:
    """Atalho sem modelo: devolve o especialista só quando há um vencedor claro.

    Cada chamada ao Comandante custa uma geração completa; em CPU isso são segundos.
    """
    texto = _normalizar(pergunta)
    pontos = {
        nome: sum(1 for kw in a.palavras_chave if re.search(rf"\b{re.escape(kw)}", texto))
        for nome, a in agentes.items()
    }
    ordenados = sorted(pontos.items(), key=lambda p: p[1], reverse=True)
    if ordenados[0][1] > 0 and (len(ordenados) == 1 or ordenados[0][1] > ordenados[1][1]):
        return ordenados[0][0]
    return None


async def escolher_agente(
    llm: ProvedorLLM, pergunta: str, agentes: dict[str, Agente] | None = None
) -> str:
    agentes = agentes or AGENTES
    atalho = escolha_por_palavras(pergunta, agentes)
    if atalho:
        return atalho
    resposta = await llm.completar(
        [
            {"role": "system", "content": prompt_roteador(agentes)},
            {"role": "user", "content": pergunta},
        ],
        temperatura=0.0,
    )
    return interpretar_escolha(resposta, agentes)
