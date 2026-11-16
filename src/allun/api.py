"""API HTTP do Allun (FastAPI) e hospedagem do painel web."""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import threading
import time
from collections.abc import AsyncIterator, Iterator
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from allun import __version__
from allun.armazenamento import Armazenamento
from allun.catalogo import ModeloLLM, carregar_catalogo
from allun.configuracao import (
    carregar_env,
    definida_no_env,
    mascarar,
    remover_chave,
    salvar_chave,
    validar_chave,
)
from allun.hardware import PerfilHardware, classificar, detectar_hardware
from allun.integracao import ClienteOllama, ErroOllama
from allun.orquestrador import (
    AGENTES,
    ErroLLM,
    Memoria,
    ProvedorComFallback,
    atualizar_memoria,
    criar_provedor,
    montar_cadeia,
    montar_especialistas,
    transmitir_resposta,
)
from allun.orquestrador.contexto import ArquivoContexto
from allun.orquestrador.roteador import escolha_por_palavras
from allun.projetos import (
    INSTRUCOES_ARQUIVOS,
    CaminhoInvalido,
    arquivos_para_contexto,
    extrair_arquivos,
    gravar_arquivos,
    listar_arquivos,
    pasta_da_tarefa,
    validar_pasta,
)
from allun.recomendador import recomendar

PASTA_WEB = Path(__file__).resolve().parents[2] / "web" / "dist"


class PedidoTarefa(BaseModel):
    titulo: str = Field(default="Nova tarefa", max_length=200)
    pasta: str | None = Field(default=None, max_length=400)  # vazio = pasta automática


class PedidoPasta(BaseModel):
    pasta: str | None = Field(default=None, max_length=400)


class PedidoMensagem(BaseModel):
    texto: str = Field(min_length=1, max_length=20000)
    agente: str | None = None  # None = o Comandante escolhe
    modelo: str | None = None  # None = cadeia automática com fallback
    permitir_pagos: bool = False
    permitir_anonimos: bool = False
    salvar_arquivos: bool = True  # grava os blocos de código com nome na pasta do projeto


class PedidoChave(BaseModel):
    valor: str = Field(max_length=600)


class PedidoDownload(BaseModel):
    modelo: str
    confirmar: bool = False


@lru_cache(maxsize=1)
def _hardware_em_cache(janela: int) -> PerfilHardware:
    return detectar_hardware()


def hardware_atual() -> PerfilHardware:
    """Detecção custa alguns segundos; reaproveita por 60 s."""
    return _hardware_em_cache(int(time.time() // 60))


def _ollama() -> ClienteOllama:
    return ClienteOllama(os.environ.get("OLLAMA_URL", "http://localhost:11434"))


def _instalados() -> list[str] | None:
    cliente = _ollama()
    try:
        return cliente.listar() if cliente.disponivel() else None
    except ErroOllama:
        return None


def _modelo_json(m: ModeloLLM) -> dict:
    d = asdict(m)
    d["anonimo"] = m.anonimo
    return d


def montar_llm(pedido: PedidoMensagem) -> ProvedorComFallback:
    """Escolhe a cadeia de modelos para o pedido; 409 se nenhum estiver disponível."""
    catalogo = carregar_catalogo()
    if pedido.modelo:
        escolhido = next((m for m in catalogo if m.id == pedido.modelo), None)
        if escolhido is None:
            raise HTTPException(422, f"Modelo fora do catálogo: {pedido.modelo}")
        cadeia = [escolhido]
    else:
        rec = recomendar(hardware_atual(), catalogo)
        cadeia = montar_cadeia(
            rec,
            permitir_pagos=pedido.permitir_pagos,
            permitir_anonimos=pedido.permitir_anonimos,
        )
        instalados = _instalados()
        cadeia = [
            m
            for m in cadeia
            if m.tipo == "online" or (instalados is not None and m.id in instalados)
        ]
    if not cadeia:
        raise HTTPException(
            409,
            "Nenhum modelo disponível. Baixe um modelo local na tela de modelos "
            "ou defina uma chave de API.",
        )
    return ProvedorComFallback([criar_provedor(m, _ollama().url) for m in cadeia])


def montar_especialistas_api(
    pedido: PedidoMensagem, llm: ProvedorComFallback
) -> dict[str, ProvedorComFallback]:
    """Modelos de especialidade instalados (ex.: código). Não se aplica se o usuário fixou o modelo."""
    if pedido.modelo:
        return {}
    return montar_especialistas(
        carregar_catalogo(),
        hardware_atual().memoria_modelo_gb,
        _instalados(),
        llm,
        _ollama().url,
    )


HOSTS_LOCAIS = {"127.0.0.1", "localhost", "::1"}


def exigir_painel_local(request: Request) -> None:
    """Protege a edição de chaves contra páginas de outros sites e DNS rebinding.

    - O cabeçalho `X-Allun-Painel` obriga o navegador a fazer preflight CORS, que a API nega.
    - O `Host` precisa ser local (ou estar em ALLUN_HOSTS, separado por vírgulas).
    """
    host = urlparse("//" + request.headers.get("host", "")).hostname or ""
    extras = {h.strip() for h in os.environ.get("ALLUN_HOSTS", "").split(",") if h.strip()}
    if host not in HOSTS_LOCAIS | extras or request.headers.get("x-allun-painel") != "1":
        raise HTTPException(403, "Origem não autorizada para editar chaves.")


def _variaveis_permitidas() -> set[str]:
    return {c for m in carregar_catalogo() for c in m.chaves_env}


def _status_chave(nome: str) -> dict:
    valor = os.environ.get(nome, "")
    return {
        "nome": nome,
        "definida": bool(valor),
        "mascara": mascarar(valor) if valor else None,
        "origem": (".env" if definida_no_env(nome) else "ambiente") if valor else None,
    }


def _sse(evento: dict) -> str:
    return f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"


def criar_app(armazenamento: Armazenamento | None = None, aquecer: bool = True) -> FastAPI:
    app = FastAPI(title="Allun", version=__version__)

    @app.exception_handler(Exception)
    async def erro_inesperado(request: Request, erro: Exception):
        """Mostra a causa no painel em vez de um "Erro 500" sem explicação."""
        logging.getLogger("allun").exception("Erro em %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Erro interno ({type(erro).__name__}): {erro}"},
        )

    carregar_env()
    base = armazenamento or Armazenamento()

    # A primeira importação do litellm leva segundos e travaria a primeira resposta.
    if aquecer:
        threading.Thread(target=lambda: importlib.import_module("litellm"), daemon=True).start()

    # ---------- memória em segundo plano ----------
    tarefas_fundo: set[asyncio.Task] = set()  # referências evitam que o GC cancele a tarefa
    travas: dict[str, asyncio.Lock] = {}

    def _memoria_de(tarefa_id: str) -> Memoria | None:
        dados = base.obter_memoria(tarefa_id)
        return Memoria(**dados) if dados else None

    async def _atualizar_memoria(tarefa_id: str, llm: ProvedorComFallback) -> None:
        trava = travas.setdefault(tarefa_id, asyncio.Lock())
        if trava.locked():  # já há um resumo em andamento para esta tarefa
            return
        async with trava:
            try:
                nova = await atualizar_memoria(
                    llm, base.historico(tarefa_id), _memoria_de(tarefa_id) or Memoria()
                )
            except Exception:
                logging.getLogger("allun").warning("Falha ao atualizar a memória", exc_info=True)
                return
            if nova:
                base.salvar_memoria(tarefa_id, nova.resumo, nova.fatos, nova.cobertas)

    def _agendar_memoria(tarefa_id: str, llm: ProvedorComFallback) -> None:
        tarefa = asyncio.create_task(_atualizar_memoria(tarefa_id, llm))
        tarefas_fundo.add(tarefa)
        tarefa.add_done_callback(tarefas_fundo.discard)

    app.state.atualizar_memoria = _atualizar_memoria
    app.state.agendar_memoria = _agendar_memoria

    @app.get("/api/saude")
    def saude():
        return {"versao": __version__, "ollama": _instalados() is not None}

    @app.get("/api/diagnostico")
    def diagnostico():
        hw = hardware_atual()
        rec = recomendar(hw, carregar_catalogo())
        return {
            "hardware": {
                "ram_total_gb": hw.ram_total_gb,
                "ram_disponivel_gb": hw.ram_disponivel_gb,
                "nucleos": hw.nucleos,
                "gpus": [{**asdict(g), "dedicada": g.dedicada} for g in hw.gpus],
                "memoria_modelo_gb": hw.memoria_modelo_gb,
            },
            "perfil": classificar(hw).rotulo,
            "recomendacao": {
                "principal": _modelo_json(rec.principal) if rec.principal else None,
                "alternativas_locais": [_modelo_json(m) for m in rec.alternativas_locais],
                "online_gratuitos": [_modelo_json(m) for m in rec.online_gratuitos],
                "online_pagos": [_modelo_json(m) for m in rec.online_pagos],
            },
            "avisos": rec.avisos,
        }

    @app.get("/api/agentes")
    def agentes():
        return [asdict(a) for a in AGENTES.values()]

    @app.get("/api/modelos")
    def modelos():
        """Catálogo com o status de cada modelo nesta máquina."""
        hw = hardware_atual()
        instalados = _instalados()
        saida = []
        for m in carregar_catalogo():
            d = _modelo_json(m)
            if m.tipo == "local":
                d["cabe"] = m.memoria_min_gb * 1.1 <= hw.memoria_modelo_gb
                d["instalado"] = bool(instalados) and m.id in instalados
                d["disponivel"] = d["instalado"]
            else:
                d["chaves_ausentes"] = [c for c in m.chaves_env if not os.environ.get(c)]
                d["chaves"] = [_status_chave(c) for c in m.chaves_env]
                d["disponivel"] = not d["chaves_ausentes"]
            saida.append(d)
        return {"ollama_ativo": instalados is not None, "modelos": saida}

    @app.put("/api/chaves/{nome}", dependencies=[Depends(exigir_painel_local)])
    def definir_chave(nome: str, pedido: PedidoChave):
        """Insere ou altera uma chave de API. Só aceita variáveis do catálogo."""
        if nome not in _variaveis_permitidas():
            raise HTTPException(404, "Variável desconhecida.")
        try:
            validar_chave(nome, pedido.valor)
            salvar_chave(nome, pedido.valor)
        except ValueError as erro:
            raise HTTPException(422, str(erro)) from erro
        except OSError as erro:
            raise HTTPException(500, f"Não foi possível gravar o .env: {erro.strerror}") from erro
        return _status_chave(nome)  # nunca devolve o valor, só a máscara

    @app.delete("/api/chaves/{nome}", dependencies=[Depends(exigir_painel_local)])
    def apagar_chave(nome: str):
        if nome not in _variaveis_permitidas():
            raise HTTPException(404, "Variável desconhecida.")
        try:
            remover_chave(nome)
        except OSError as erro:
            raise HTTPException(500, f"Não foi possível gravar o .env: {erro.strerror}") from erro
        return _status_chave(nome)

    @app.post("/api/modelos/baixar")
    def baixar(pedido: PedidoDownload):
        """Baixa um modelo local no Ollama. Exige `confirmar: true`."""
        modelo = next(
            (m for m in carregar_catalogo() if m.id == pedido.modelo and m.tipo == "local"), None
        )
        if modelo is None:
            raise HTTPException(422, f"Modelo local fora do catálogo: {pedido.modelo}")
        if not pedido.confirmar:
            raise HTTPException(400, "O download precisa de confirmação do usuário.")
        if _instalados() is None:
            raise HTTPException(409, "Ollama indisponível. Abra o Ollama e tente de novo.")

        def eventos() -> Iterator[str]:
            try:
                for ev in _ollama().eventos_download(modelo.id):
                    yield _sse(
                        {
                            "tipo": "progresso",
                            "status": ev.get("status", ""),
                            "completed": ev.get("completed", 0),
                            "total": ev.get("total", 0),
                        }
                    )
                yield _sse({"tipo": "fim"})
            except ErroOllama as erro:
                yield _sse({"tipo": "erro", "mensagem": str(erro)})

        return StreamingResponse(eventos(), media_type="text/event-stream")

    # ---------- tarefas e conversa ----------

    @app.get("/api/tarefas")
    def listar_tarefas():
        return [_com_pasta(t) for t in base.listar_tarefas()]

    def _pasta_validada(texto: str | None) -> str | None:
        if not texto or not texto.strip():
            return None
        try:
            return str(validar_pasta(texto))
        except CaminhoInvalido as erro:
            raise HTTPException(422, str(erro)) from erro

    def _com_pasta(tarefa: dict) -> dict:
        return {
            **tarefa,
            "pasta_efetiva": str(pasta_da_tarefa(tarefa)),
            "pasta_automatica": not tarefa.get("pasta"),
        }

    @app.post("/api/tarefas", status_code=201)
    def criar_tarefa(pedido: PedidoTarefa, request: Request):
        if pedido.pasta and pedido.pasta.strip():
            exigir_painel_local(request)  # só o painel local escolhe onde gravar
        return _com_pasta(base.criar_tarefa(pedido.titulo, _pasta_validada(pedido.pasta)))

    @app.put("/api/tarefas/{tarefa_id}/pasta", dependencies=[Depends(exigir_painel_local)])
    def definir_pasta(tarefa_id: str, pedido: PedidoPasta):
        """Define a pasta do projeto. `null` ou vazio volta para a pasta automática."""
        if not base.definir_pasta(tarefa_id, _pasta_validada(pedido.pasta)):
            raise HTTPException(404, "Tarefa não encontrada.")
        return _com_pasta(base.obter_tarefa(tarefa_id))

    @app.post("/api/tarefas/{tarefa_id}/abrir-pasta", dependencies=[Depends(exigir_painel_local)])
    def abrir_pasta(tarefa_id: str):
        """Abre a pasta do projeto no Explorador de Arquivos (só Windows)."""
        tarefa = base.obter_tarefa(tarefa_id)
        if tarefa is None:
            raise HTTPException(404, "Tarefa não encontrada.")
        pasta = pasta_da_tarefa(tarefa)
        if not pasta.is_dir():
            raise HTTPException(409, "A pasta ainda não existe; ela é criada no primeiro arquivo.")
        if not hasattr(os, "startfile"):
            raise HTTPException(501, f"Abra manualmente: {pasta}")
        os.startfile(pasta)
        return {"pasta": str(pasta)}

    @app.get("/api/tarefas/{tarefa_id}")
    def obter_tarefa(tarefa_id: str):
        tarefa = base.obter_tarefa(tarefa_id)
        if tarefa is None:
            raise HTTPException(404, "Tarefa não encontrada.")
        return {**_com_pasta(tarefa), "memoria": base.obter_memoria(tarefa_id)}

    @app.delete("/api/tarefas/{tarefa_id}", status_code=204)
    def remover_tarefa(tarefa_id: str):
        if not base.remover_tarefa(tarefa_id):
            raise HTTPException(404, "Tarefa não encontrada.")

    def _continuidade(tarefa: dict, texto: str, salvar_arquivos: bool) -> str | None:
        """Num projeto com arquivos, um pedido curto e sem palavra-chave ("mude a cor do botão")
        continua com o programador, em vez de o Comandante mandar para o agente geral."""
        if not salvar_arquivos or escolha_por_palavras(texto, AGENTES) or len(texto) > 300:
            return None
        respostas = [m for m in tarefa["mensagens"] if m["papel"] == "allun" and not m.get("erro")]
        ultima = respostas[-1] if respostas else None
        if ultima and ultima.get("agente") == "programador" and ultima.get("arquivos"):
            return "programador"
        return None

    @app.post("/api/tarefas/{tarefa_id}/mensagens")
    async def enviar_mensagem(tarefa_id: str, pedido: PedidoMensagem):
        """Responde em streaming (SSE): eventos `agente`, `trecho`, `fim` ou `erro`."""
        tarefa = base.obter_tarefa(tarefa_id)
        if tarefa is None:
            raise HTTPException(404, "Tarefa não encontrada.")
        if pedido.agente and pedido.agente not in AGENTES:
            raise HTTPException(422, f"Agente desconhecido: {pedido.agente}")
        llm = montar_llm(pedido)  # falha antes de gravar a mensagem do usuário
        especialistas = montar_especialistas_api(pedido, llm)
        historico = base.historico(tarefa_id)
        memoria = _memoria_de(tarefa_id)
        pasta = pasta_da_tarefa(tarefa)
        instrucoes = None
        lidos: list[ArquivoContexto] = []
        if pedido.salvar_arquivos:
            ultima = next(
                (
                    m
                    for m in reversed(tarefa["mensagens"])
                    if m["papel"] == "allun" and m.get("arquivos")
                ),
                None,
            )
            recentes = [
                a["caminho"] for a in (ultima or {}).get("arquivos", {}).get("gravados", [])
            ]
            lidos = [
                ArquivoContexto(c, t)
                for c, t in arquivos_para_contexto(pasta, pedido.texto, recentes)
            ]
            existentes = listar_arquivos(pasta)
            instrucoes = INSTRUCOES_ARQUIVOS + (
                "\nArquivos que já existem no projeto: " + ", ".join(existentes)
                if existentes
                else ""
            )
        agente_pedido = pedido.agente or _continuidade(tarefa, pedido.texto, pedido.salvar_arquivos)
        base.adicionar_mensagem(tarefa_id, "usuario", pedido.texto)

        async def eventos() -> AsyncIterator[str]:
            inicio = time.perf_counter()
            partes: list[str] = []
            agente: str | None = None

            def fonte() -> ProvedorComFallback:
                return especialistas.get(agente or "", llm)

            def salvar(texto: str, erro: bool = False, arquivos: dict | None = None) -> float:
                duracao = round(time.perf_counter() - inicio, 1)
                base.adicionar_mensagem(
                    tarefa_id,
                    "allun",
                    texto,
                    agente=agente,
                    modelo=fonte().ultimo_usado,
                    duracao_s=duracao,
                    erro=erro,
                    arquivos=arquivos,
                )
                return duracao

            try:
                async for ev in transmitir_resposta(
                    llm,
                    pedido.texto,
                    agente_pedido,
                    historico,
                    especialistas,
                    memoria,
                    instrucoes_extra=instrucoes,
                    arquivos=lidos,
                ):
                    if ev["tipo"] == "agente":
                        agente = ev["agente"]
                    elif ev["tipo"] == "trecho":
                        partes.append(ev["texto"])
                    yield _sse(ev)
                texto = "".join(partes)
                if not texto.strip():
                    raise ErroLLM("O modelo não devolveu texto.")
                resultado = None
                extraidos = extrair_arquivos(texto) if pedido.salvar_arquivos else []
                if extraidos:
                    try:
                        resultado = {"pasta": str(pasta), **gravar_arquivos(pasta, extraidos)}
                    except OSError as erro:
                        resultado = {
                            "pasta": str(pasta),
                            "gravados": [],
                            "rejeitados": [],
                            "erro": f"Não foi possível gravar: {erro.strerror or erro}",
                        }
                    yield _sse({"tipo": "arquivos", **resultado})
                duracao = salvar(texto, arquivos=resultado)
                yield _sse(
                    {
                        "tipo": "fim",
                        "modelo": fonte().ultimo_usado,
                        "duracao_s": duracao,
                        "falhas": fonte().falhas,
                    }
                )
                # Cadeia nova: não mistura falhas do resumo com as da resposta.
                app.state.agendar_memoria(tarefa_id, ProvedorComFallback(llm.provedores))
            except ErroLLM as erro:
                salvar(str(erro), erro=True)
                yield _sse({"tipo": "erro", "mensagem": str(erro)})
            except asyncio.CancelledError:
                # usuário cancelou ou fechou a página: guarda o que já foi gerado
                if partes:
                    salvar("".join(partes) + "\n\n*(interrompido)*")
                raise

        return StreamingResponse(
            eventos(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    if PASTA_WEB.is_dir():
        app.mount("/assets", StaticFiles(directory=PASTA_WEB / "assets"), name="assets")

        @app.get("/{caminho:path}", include_in_schema=False)
        def painel(caminho: str):
            if caminho.startswith("api/"):
                raise HTTPException(404)
            arquivo = (PASTA_WEB / caminho).resolve()
            if caminho and arquivo.is_file() and PASTA_WEB in arquivo.parents:
                return FileResponse(arquivo)
            return FileResponse(PASTA_WEB / "index.html")

    return app
