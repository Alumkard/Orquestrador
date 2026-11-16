"""Modelos de dados do hardware detectado."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

# Memória mínima para considerar uma GPU como dedicada (placas com menos que isso
# são tratadas como integradas ou com leitura duvidosa).
VRAM_MIN_DEDICADA_GB = 2.0
_MARCAS_INTEGRADAS = (
    "iris",
    "uhd",
    "hd graphics",
    "radeon graphics",
    "radeon(tm) graphics",
    "vega",
)


class Perfil(IntEnum):
    LEVE = 0
    MEDIO = 1
    POTENTE = 2

    @property
    def rotulo(self) -> str:
        return self.name.lower()


@dataclass(frozen=True)
class GPU:
    nome: str
    fabricante: str | None = None
    vram_gb: float | None = None  # None quando o sistema não informa

    @property
    def dedicada(self) -> bool:
        if self.vram_gb is None or self.vram_gb < VRAM_MIN_DEDICADA_GB:
            return False
        nome = self.nome.lower()
        return not any(marca in nome for marca in _MARCAS_INTEGRADAS)


@dataclass
class PerfilHardware:
    ram_total_gb: float
    ram_disponivel_gb: float
    nucleos: int
    gpus: list[GPU] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def apple_silicon(self) -> bool:
        return any((g.fabricante or "").lower() == "apple" for g in self.gpus)

    @property
    def maior_vram_gb(self) -> float:
        return max((g.vram_gb for g in self.gpus if g.dedicada), default=0.0)

    @property
    def gpu_dedicada(self) -> bool:
        return self.maior_vram_gb > 0

    @property
    def memoria_modelo_gb(self) -> float:
        """Memória que um modelo pode ocupar sem sufocar a máquina."""
        if self.apple_silicon:
            return round(self.ram_total_gb * 0.6, 2)
        # O Ollama divide camadas entre GPU e CPU; uma GPU pequena nunca reduz
        # a capacidade que a RAM já oferece.
        return round(max(self.maior_vram_gb * 0.9, self.ram_total_gb * 0.5), 2)
