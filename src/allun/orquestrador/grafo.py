"""Grafo LangGraph (Comandante -> Especialista) e fluxo em streaming."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .agentes import AGENTE_PADRAO, AGENTES, Agente
from .contexto import ArquivoContexto, Memoria, montar_mensagens, planejar_contexto
from .llm import ProvedorLLM, contexto_de
from .roteador import escolher_agente

Historico = Sequence[dict[str, str]]


class Estado(TypedDict, total=False):
    pergunta: str
    historico: list[dict[str, str]]
    agente: str
    resposta: str


def construir_grafo(llm: ProvedorLLM, agentes: dict[str, Agente] | None = None):
    agentes = agentes or AGENTES
    if AGENTE_PADRAO not in agentes:
        raise ValueError(f"O agente '{AGENTE_PADRAO}' é obrigatório.")

    async def comandante(estado: Estado) -> Estado:
        return {"agente": await escolher_agente(llm, estado["pergunta"], agentes)}

    def criar_especialista(agente: Agente):
        async def especialista(estado: Estado) -> Estado:
            resposta = await llm.completar(
                montar_mensagens(agente, estado["pergunta"], estado.get("historico", ())),
                agente.temperatura,
            )
            return {"resposta": resposta}

        return especialista

    grafo = StateGraph(Estado)
    grafo.add_node("comandante", comandante)
    for nome, agente in agentes.items():
        grafo.add_node(nome, criar_especialista(agente))
        grafo.add_edge(nome, END)
    grafo.add_edge(START, "comandante")
    grafo.add_conditional_edges(
        "comandante", lambda e: e["agente"], {nome: nome for nome in agentes}
    )
    return grafo.compile()


async def orquestrar(llm: ProvedorLLM, pergunta: str, historico: Historico = ()) -> Estado:
    return await construir_grafo(llm).ainvoke({"pergunta": pergunta, "historico": list(historico)})


async def responder(
    llm: ProvedorLLM, pergunta: str, agente: str | None = None, historico: Historico = ()
) -> Estado:
    """Se `agente` for informado, pula o Comandante e fala direto com o especialista."""
    if agente is None:
        return await orquestrar(llm, pergunta, historico)
    if agente not in AGENTES:
        raise ValueError(f"Agente desconhecido: {agente}")
    resposta = await llm.completar(
        montar_mensagens(AGENTES[agente], pergunta, historico), AGENTES[agente].temperatura
    )
    return {"pergunta": pergunta, "agente": agente, "resposta": resposta}


async def transmitir_resposta(
    llm: ProvedorLLM,
    pergunta: str,
    agente: str | None = None,
    historico: Historico = (),
    especialistas: dict[str, Any] | None = None,
    memoria: Memoria | None = None,
    orcamento_tokens: int | None = None,
    instrucoes_extra: str | None = None,
    arquivos: Sequence[ArquivoContexto] = (),
) -> AsyncIterator[dict[str, Any]]:
    """Gera eventos: primeiro {"tipo": "agente"}, depois vários {"tipo": "trecho"}.

    `especialistas` mapeia agente -> provedor próprio (ex.: modelo de código). O Comandante
    sempre usa `llm`. O orçamento de contexto vem do modelo que vai responder, salvo se
    `orcamento_tokens` for informado.
    """
    if agente is None:
        agente = await escolher_agente(llm, pergunta)
    elif agente not in AGENTES:
        raise ValueError(f"Agente desconhecido: {agente}")
    yield {"tipo": "agente", "agente": agente}
    especialista = AGENTES[agente]
    destino = (especialistas or {}).get(agente, llm)
    plano = planejar_contexto(
        especialista,
        pergunta,
        historico,
        memoria,
        orcamento_tokens or contexto_de(destino),
        instrucoes_extra,
        arquivos,
    )
    if arquivos:
        yield {
            "tipo": "contexto",
            "arquivos_lidos": plano.arquivos_inteiros,
            "arquivos_cortados": plano.arquivos_cortados,
            "arquivos_fora": plano.arquivos_fora,
        }
    async for trecho in destino.transmitir(plano.mensagens, especialista.temperatura):
        yield {"tipo": "trecho", "texto": trecho}
