"""Motor de recomendação de LLMs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from allun.catalogo import ModeloLLM
from allun.hardware import PerfilHardware

MARGEM = 1.10  # o modelo precisa caber com 10% de folga


class Preferencia(str, Enum):
    QUALQUER = "qualquer"
    SOMENTE_LOCAL = "somente_local"
    SOMENTE_ONLINE = "somente_online"


@dataclass
class Recomendacao:
    principal: ModeloLLM | None
    alternativas_locais: list[ModeloLLM] = field(default_factory=list)
    online_gratuitos: list[ModeloLLM] = field(default_factory=list)
    online_pagos: list[ModeloLLM] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _por_qualidade(modelos: list[ModeloLLM]) -> list[ModeloLLM]:
    return sorted(modelos, key=lambda m: m.qualidade, reverse=True)


def recomendar(
    hw: PerfilHardware,
    catalogo: list[ModeloLLM],
    preferencia: Preferencia = Preferencia.QUALQUER,
) -> Recomendacao:
    memoria = hw.memoria_modelo_gb
    avisos: list[str] = []

    locais: list[ModeloLLM] = []
    if preferencia != Preferencia.SOMENTE_ONLINE:
        locais = _por_qualidade(
            [
                m
                for m in catalogo
                if m.tipo == "local"
                and m.especialidade is None  # modelos de especialista não são o padrão geral
                and m.memoria_min_gb * MARGEM <= memoria
            ]
        )
        # RAM livre agora pode ser menor que a total; avisa em vez de excluir.
        if locais and locais[0].tamanho_gb and hw.ram_disponivel_gb < locais[0].tamanho_gb * 1.5:
            avisos.append(
                f"RAM livre ({hw.ram_disponivel_gb:.1f} GB) está baixa para {locais[0].nome}. "
                "Feche outros programas antes de carregá-lo."
            )

    online_gratis: list[ModeloLLM] = []
    online_pago: list[ModeloLLM] = []
    if preferencia != Preferencia.SOMENTE_LOCAL:
        online = [m for m in catalogo if m.tipo == "online"]
        online_gratis = _por_qualidade([m for m in online if m.custo == "gratuito"])
        online_pago = _por_qualidade([m for m in online if m.custo == "pago"])

    if locais:
        principal, alternativas = locais[0], locais[1:]
    elif preferencia == Preferencia.SOMENTE_LOCAL:
        principal, alternativas = None, []
        avisos.append("Nenhum modelo local do catálogo cabe nesta máquina.")
    else:
        alternativas = []
        principal = (online_gratis or online_pago or [None])[0]
        if principal is not None:
            avisos.append(
                "Nenhum modelo local cabe nesta máquina; recomendando opção online."
                if preferencia == Preferencia.QUALQUER
                else "Preferência somente online aplicada."
            )

    avisos.extend(hw.avisos)
    return Recomendacao(principal, alternativas, online_gratis, online_pago, avisos)
