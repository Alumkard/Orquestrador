"""Classificação do hardware em perfis."""

from __future__ import annotations

from .modelos import Perfil, PerfilHardware

LIMITE_MEDIO_GB = 4.0
LIMITE_POTENTE_GB = 10.0
NUCLEOS_MINIMOS = 4


def classificar(hw: PerfilHardware) -> Perfil:
    memoria = hw.memoria_modelo_gb

    if memoria >= LIMITE_POTENTE_GB:
        perfil = Perfil.POTENTE
    elif memoria >= LIMITE_MEDIO_GB:
        perfil = Perfil.MEDIO
    else:
        perfil = Perfil.LEVE

    if hw.nucleos < NUCLEOS_MINIMOS and perfil > Perfil.LEVE:
        perfil = Perfil(perfil - 1)

    if hw.ram_total_gb < 8 and not hw.gpu_dedicada:
        perfil = Perfil.LEVE

    return perfil
