"""Leitura e validação do catálogo de LLMs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CAMINHO_PADRAO = Path(__file__).with_name("catalogo.json")
_TIPOS = {"local", "online"}
_CUSTOS = {"gratuito", "pago"}


@dataclass(frozen=True)
class ModeloLLM:
    id: str
    nome: str
    tipo: str
    provedor: str
    qualidade: int
    memoria_min_gb: float
    custo: str
    tamanho_gb: float | None = None
    chaves_env: tuple[str, ...] = ()  # variáveis de ambiente exigidas (todas)
    api_base: str | None = None  # endpoint compatível com OpenAI, quando não é padrão do litellm
    observacao: str | None = None
    chave_url: str | None = None  # onde o usuário cria a chave de API
    especialidade: str | None = None  # agente que prefere este modelo (ex.: "programador")
    contexto_tokens: int | None = None  # janela de contexto usada pelo Allun

    @property
    def orcamento_contexto(self) -> int:
        """Locais: 4096 (mais que isso deixa a CPU lenta). Online: 32768, salvo indicação."""
        return self.contexto_tokens or (4096 if self.tipo == "local" else 32768)

    @property
    def anonimo(self) -> bool:
        """Online sem nenhuma chave: os prompts vão a um terceiro sem cadastro."""
        return self.tipo == "online" and not self.chaves_env


def carregar_catalogo(caminho: Path | str | None = None) -> list[ModeloLLM]:
    dados = json.loads(Path(caminho or CAMINHO_PADRAO).read_text(encoding="utf-8"))
    modelos: list[ModeloLLM] = []
    for item in dados["modelos"]:
        try:
            modelo = ModeloLLM(**{**item, "chaves_env": tuple(item.get("chaves_env", ()))})
        except TypeError as erro:
            raise ValueError(f"Entrada inválida no catálogo ({item.get('id')}): {erro}") from erro
        if modelo.tipo not in _TIPOS or modelo.custo not in _CUSTOS:
            raise ValueError(f"Tipo ou custo inválido no catálogo: {modelo.id}")
        modelos.append(modelo)
    return modelos
