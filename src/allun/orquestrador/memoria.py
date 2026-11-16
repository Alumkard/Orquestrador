"""Memória em camadas: as mensagens antigas viram um resumo e uma lista de fatos.

Roda depois da resposta, em segundo plano, para não atrasar o usuário. Custa uma
geração extra do modelo a cada `GATILHO` mensagens novas.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from .contexto import Memoria, simbolizar
from .llm import ProvedorLLM

JANELA_CURTA = 4  # mensagens mais recentes que nunca entram no resumo
GATILHO = 8  # resume quando houver tantas mensagens fora do resumo
MAX_FATOS = 10
_MAX_CARACTERES_MENSAGEM = 1200
_MAX_CARACTERES_LOTE = 6000  # cabe no contexto de 4096 tokens junto com o prompt

PROMPT_MEMORIA = (
    "Você atualiza a memória de uma conversa entre um usuário e um assistente. "
    'Responda SOMENTE com JSON no formato {"resumo": "...", "fatos": ["..."]}. '
    "resumo: até 120 palavras, em português, com o que foi pedido, decidido e entregue, "
    "juntando a memória atual com as novas mensagens. "
    f"fatos: até {MAX_FATOS} itens curtos e duradouros (preferências, restrições, nomes, "
    "decisões). Mantenha os fatos atuais que continuam válidos. Não invente nada."
)


def precisa_atualizar(memoria: Memoria, total_mensagens: int) -> bool:
    return total_mensagens - memoria.cobertas >= GATILHO


def _formatar(mensagens: Sequence[dict[str, str]]) -> str:
    linhas = []
    for m in mensagens:
        quem = "usuário" if m["role"] == "user" else "assistente"
        texto = simbolizar(m["content"]).strip()
        if len(texto) > _MAX_CARACTERES_MENSAGEM:
            texto = texto[:_MAX_CARACTERES_MENSAGEM] + "…"
        linhas.append(f"[{quem}] {texto}")
    # Se acumulou demais (ex.: resumos anteriores falharam), fica com as mais recentes.
    while len(linhas) > 1 and sum(len(x) for x in linhas) > _MAX_CARACTERES_LOTE:
        linhas.pop(0)
    return "\n".join(linhas)


def interpretar_memoria(resposta: str) -> Memoria | None:
    """Aceita JSON cercado por texto ou por ```json; devolve None se não der para usar."""
    achado = re.search(r"\{.*\}", resposta, re.DOTALL)
    if not achado:
        return None
    try:
        dados = json.loads(achado.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(dados, dict):
        return None
    resumo = dados.get("resumo")
    resumo = resumo.strip()[:1500] if isinstance(resumo, str) else ""
    fatos_brutos = dados.get("fatos")
    fatos = [
        f.strip()[:200]
        for f in (fatos_brutos if isinstance(fatos_brutos, list) else [])
        if isinstance(f, str) and f.strip()
    ][:MAX_FATOS]
    if not resumo and not fatos:
        return None
    return Memoria(resumo=resumo, fatos=fatos)


async def atualizar_memoria(
    llm: ProvedorLLM, historico: Sequence[dict[str, str]], atual: Memoria
) -> Memoria | None:
    """Devolve a memória nova, ou None se não for hora de atualizar ou o modelo falhar."""
    if not precisa_atualizar(atual, len(historico)):
        return None
    ate = len(historico) - JANELA_CURTA
    novas = historico[atual.cobertas : ate]
    memoria_atual = atual.texto() if not atual.vazia else "(vazia)"
    resposta = await llm.completar(
        [
            {"role": "system", "content": PROMPT_MEMORIA},
            {
                "role": "user",
                "content": f"Memória atual:\n{memoria_atual}\n\nNovas mensagens:\n"
                + _formatar(novas),
            },
        ],
        0.0,
    )
    nova = interpretar_memoria(resposta)
    if nova is None:
        return None
    nova.cobertas = ate
    return nova
