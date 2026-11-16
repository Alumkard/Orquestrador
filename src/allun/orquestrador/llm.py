"""Acesso unificado a LLMs (litellm) e cadeia de fallback."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from collections.abc import AsyncIterator
from typing import Protocol

from allun.catalogo import ModeloLLM
from allun.recomendador import Recomendacao

Mensagens = list[dict[str, str]]


class ProvedorLLM(Protocol):
    nome: str

    async def completar(self, mensagens: Mensagens, temperatura: float | None = None) -> str: ...

    def transmitir(
        self, mensagens: Mensagens, temperatura: float | None = None
    ) -> AsyncIterator[str]: ...


class ErroLLM(RuntimeError):
    """Nenhum provedor conseguiu responder."""


class ProvedorLiteLLM:
    def __init__(self, modelo: ModeloLLM, api_base: str | None = None):
        self.modelo = modelo
        self.nome = modelo.id
        self.api_base = api_base

    @property
    def _id_litellm(self) -> str:
        return f"ollama_chat/{self.modelo.id}" if self.modelo.tipo == "local" else self.modelo.id

    def _parametros(self, mensagens: Mensagens, temperatura: float | None) -> dict:
        params: dict = {"model": self._id_litellm, "messages": mensagens, "timeout": 300}
        if temperatura is not None:
            params["temperature"] = temperatura
        if self.modelo.tipo == "local":
            params["api_base"] = self.api_base or "http://localhost:11434"
            params["keep_alive"] = "30m"  # evita recarregar o modelo a cada pergunta
            params["num_ctx"] = self.modelo.orcamento_contexto  # o mesmo usado pelo planejador
        return params

    async def completar(self, mensagens: Mensagens, temperatura: float | None = None) -> str:
        import litellm  # importação lenta, só quando necessário

        litellm.drop_params = True  # modelos novos recusam parâmetros como temperature

        resposta = await litellm.acompletion(**self._parametros(mensagens, temperatura))
        return resposta.choices[0].message.content or ""

    async def transmitir(
        self, mensagens: Mensagens, temperatura: float | None = None
    ) -> AsyncIterator[str]:
        import litellm

        litellm.drop_params = True
        fluxo = await litellm.acompletion(**self._parametros(mensagens, temperatura), stream=True)
        async for pedaco in fluxo:
            texto = pedaco.choices[0].delta.content
            if texto:
                yield texto


class ProvedorComFallback:
    """Tenta cada provedor em ordem; guarda qual respondeu e o que falhou."""

    def __init__(
        self,
        provedores: list[ProvedorLLM],
        espera_primeiro: float = 240.0,
        espera_entre: float = 90.0,
    ):
        self.espera_primeiro = espera_primeiro
        self.espera_entre = espera_entre
        if not provedores:
            raise ValueError("Informe ao menos um provedor.")
        self.provedores = provedores
        self.nome = provedores[0].nome
        self.ultimo_usado: str | None = None
        self.falhas: list[str] = []

    async def completar(self, mensagens: Mensagens, temperatura: float | None = None) -> str:
        for p in self.provedores:
            try:
                texto = await p.completar(mensagens, temperatura)
            except Exception as erro:  # noqa: BLE001  qualquer falha aciona o próximo
                self.falhas.append(f"{p.nome}: {erro}")
                continue
            self.ultimo_usado = p.nome
            return texto
        raise ErroLLM("Todos os provedores falharam:\n" + "\n".join(self.falhas))

    async def transmitir(
        self, mensagens: Mensagens, temperatura: float | None = None
    ) -> AsyncIterator[str]:
        """Só troca de provedor se o anterior falhar antes de emitir o primeiro trecho.

        Um provedor parado (sem emitir nada por `espera_primeiro` ou `espera_entre` segundos)
        conta como falha, para a resposta não ficar pendurada para sempre.
        """
        for p in self.provedores:
            emitiu = False
            fluxo = p.transmitir(mensagens, temperatura).__aiter__()
            try:
                while True:
                    espera = self.espera_entre if emitiu else self.espera_primeiro
                    try:
                        trecho = await asyncio.wait_for(fluxo.__anext__(), espera)
                    except StopAsyncIteration:
                        return
                    except TimeoutError as erro:
                        raise TimeoutError(f"sem resposta há {espera:.0f} s") from erro
                    if not emitiu:
                        emitiu = True
                        self.ultimo_usado = p.nome
                    yield trecho
            except Exception as erro:
                if emitiu:
                    raise ErroLLM(f"{p.nome} caiu no meio da resposta: {erro}") from erro
                self.falhas.append(f"{p.nome}: {erro}")
            finally:
                aclose = getattr(fluxo, "aclose", None)
                if aclose:
                    await aclose()
        raise ErroLLM("Todos os provedores falharam:\n" + "\n".join(self.falhas))


class ProvedorAnonimo:
    """Endpoint compatível com OpenAI que aceita chamadas sem chave (LLM7, OVHcloud...).

    Não envia cabeçalho Authorization, pois alguns serviços rejeitam chaves falsas.
    """

    def __init__(self, modelo: ModeloLLM):
        if not modelo.api_base:
            raise ValueError(f"{modelo.id}: modelo anônimo precisa de api_base.")
        self.modelo = modelo
        self.nome = f"{modelo.id}@{modelo.provedor}"

    def _requisitar(self, mensagens: Mensagens, temperatura: float | None) -> str:
        corpo: dict = {"model": self.modelo.id, "messages": mensagens}
        if temperatura is not None:
            corpo["temperature"] = temperatura
        req = urllib.request.Request(
            self.modelo.api_base.rstrip("/") + "/chat/completions",
            data=json.dumps(corpo).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)["choices"][0]["message"]["content"] or ""
        except urllib.error.HTTPError as erro:
            raise ErroLLM(
                f"HTTP {erro.code}: {erro.read().decode(errors='replace')[:200]}"
            ) from erro

    async def completar(self, mensagens: Mensagens, temperatura: float | None = None) -> str:
        return await asyncio.to_thread(self._requisitar, mensagens, temperatura)

    async def transmitir(
        self, mensagens: Mensagens, temperatura: float | None = None
    ) -> AsyncIterator[str]:
        yield await self.completar(mensagens, temperatura)


def criar_provedor(modelo: ModeloLLM, url_ollama: str | None = None) -> ProvedorLLM:
    if modelo.anonimo and modelo.api_base:
        return ProvedorAnonimo(modelo)
    return ProvedorLiteLLM(modelo, url_ollama)


def _tem_chaves(modelo: ModeloLLM, env: dict[str, str] | os._Environ) -> bool:
    return all(env.get(chave) for chave in modelo.chaves_env)


def montar_cadeia(
    rec: Recomendacao,
    permitir_pagos: bool = False,
    permitir_anonimos: bool = False,
    ambiente: dict[str, str] | None = None,
) -> list[ModeloLLM]:
    """Ordem de tentativa: locais (maior primeiro), online gratuitos, depois pagos.

    - Online com chave só entra se todas as variáveis de ambiente do modelo existirem.
    - Pagos só entram com permissão explícita.
    - Anônimos (sem chave, ex.: LLM7, OVHcloud) só entram com permissão explícita, porque
      os prompts vão a um terceiro sem cadastro nem garantias de privacidade.
    """
    env = os.environ if ambiente is None else ambiente

    def liberado(m: ModeloLLM) -> bool:
        if m.tipo == "local":
            return True
        if m.anonimo:
            return permitir_anonimos
        return _tem_chaves(m, env)

    locais = [m for m in [rec.principal, *rec.alternativas_locais] if m and m.tipo == "local"]
    online_principal = [rec.principal] if rec.principal and rec.principal.tipo == "online" else []
    pagos = rec.online_pagos if permitir_pagos else []
    cadeia: list[ModeloLLM] = []
    for m in [*locais, *online_principal, *rec.online_gratuitos, *pagos]:
        if m not in cadeia and liberado(m):
            cadeia.append(m)
    return cadeia


def montar_especialistas(
    catalogo: list[ModeloLLM],
    memoria_gb: float,
    instalados: list[str] | None,
    geral: ProvedorComFallback,
    url_ollama: str | None = None,
) -> dict[str, ProvedorComFallback]:
    """Cadeias por agente: modelos de especialidade instalados e que cabem, depois a cadeia geral.

    Só entram modelos já instalados. Nada é baixado automaticamente.
    """
    if not instalados:
        return {}
    por_agente: dict[str, list[ModeloLLM]] = {}
    for m in catalogo:
        cabe = m.memoria_min_gb * 1.1 <= memoria_gb
        if m.tipo == "local" and m.especialidade and m.id in instalados and cabe:
            por_agente.setdefault(m.especialidade, []).append(m)
    return {
        agente: ProvedorComFallback(
            [
                *(criar_provedor(m, url_ollama) for m in sorted(ms, key=lambda x: -x.qualidade)),
                *geral.provedores,
            ]
        )
        for agente, ms in por_agente.items()
    }


def contexto_de(provedor: object) -> int:
    """Orçamento de contexto de um provedor ou cadeia: o menor entre os modelos dela.

    Usa o menor porque o fallback pode cair em qualquer um deles.
    """
    from .contexto import CONTEXTO_PADRAO

    provedores = getattr(provedor, "provedores", [provedor])
    valores = [p.modelo.orcamento_contexto for p in provedores if getattr(p, "modelo", None)]
    return min(valores) if valores else CONTEXTO_PADRAO
