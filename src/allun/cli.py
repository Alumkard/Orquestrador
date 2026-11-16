"""Interface de linha de comando do Allun."""

from __future__ import annotations

import argparse
import asyncio
import sys

from allun import __version__
from allun.catalogo import ModeloLLM, carregar_catalogo
from allun.configuracao import carregar_env
from allun.hardware import PerfilHardware, classificar, detectar_hardware
from allun.integracao import ClienteOllama, ErroOllama
from allun.integracao.ollama import URL_PADRAO
from allun.recomendador import Preferencia, Recomendacao, recomendar


def _linha_modelo(m: ModeloLLM) -> str:
    return f"{m.nome} ({m.id}, {m.custo})"


def formatar_diagnostico(hw: PerfilHardware, rec: Recomendacao) -> str:
    perfil = classificar(hw)
    linhas = [
        "== Hardware ==",
        f"RAM: {hw.ram_total_gb:.1f} GB (livre: {hw.ram_disponivel_gb:.1f} GB)",
        f"Núcleos físicos: {hw.nucleos}",
    ]
    if hw.gpus:
        for g in hw.gpus:
            vram = f"{g.vram_gb:.1f} GB" if g.vram_gb else "VRAM desconhecida"
            tipo = "dedicada" if g.dedicada else "integrada/virtual"
            linhas.append(f"GPU: {g.nome} [{tipo}, {vram}]")
    else:
        linhas.append("GPU: nenhuma detectada")
    linhas += [
        f"Memória útil para modelos: {hw.memoria_modelo_gb:.1f} GB",
        f"Perfil: {perfil.rotulo}",
        "",
        "== Recomendação ==",
    ]
    if rec.principal:
        linhas.append(f"Principal: {_linha_modelo(rec.principal)}")
    else:
        linhas.append("Principal: nenhuma opção disponível")
    for titulo, lista in (
        ("Outros locais", rec.alternativas_locais),
        ("Online gratuitos", rec.online_gratuitos),
        ("Online pagos", rec.online_pagos),
    ):
        if lista:
            linhas.append(f"{titulo}: " + "; ".join(_linha_modelo(m) for m in lista))
    for aviso in rec.avisos:
        linhas.append(f"Aviso: {aviso}")
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="allun", description="Orquestrador adaptativo de agentes."
    )
    parser.add_argument("--version", action="version", version=f"allun {__version__}")
    sub = parser.add_subparsers(dest="comando", required=True)
    diag = sub.add_parser("diagnostico", help="Mostra hardware, perfil e modelo recomendado.")
    diag.add_argument(
        "--preferencia",
        choices=[p.value for p in Preferencia],
        default=Preferencia.QUALQUER.value,
    )
    diag.add_argument("--catalogo", help="Caminho de um catalogo.json alternativo.")
    sub.add_parser("modelos", help="Lista os modelos instalados no Ollama.")
    baixar = sub.add_parser("baixar", help="Baixa um modelo no Ollama, com confirmação.")
    baixar.add_argument("modelo", nargs="?", help="Tag do Ollama. Padrão: o recomendado.")
    baixar.add_argument("--sim", action="store_true", help="Confirma o download sem perguntar.")
    perguntar = sub.add_parser("perguntar", help="Envia uma pergunta a um modelo local.")
    perguntar.add_argument("texto")
    perguntar.add_argument("--modelo", help="Tag do Ollama. Padrão: o recomendado.")
    orq = sub.add_parser("orquestrar", help="Roteia a tarefa a um especialista e responde.")
    orq.add_argument("texto")
    orq.add_argument(
        "--permitir-pagos", action="store_true", help="Permite APIs pagas no fallback."
    )
    orq.add_argument(
        "--permitir-anonimos",
        action="store_true",
        help="Permite endpoints sem chave (LLM7, OVHcloud). Seus prompts vão a terceiros sem cadastro.",
    )
    servir = sub.add_parser("servir", help="Inicia a API e o painel web.")
    servir.add_argument("--porta", type=int, default=8000)
    servir.add_argument("--host", default="127.0.0.1")
    for p in (baixar, perguntar, orq):
        p.add_argument("--url", default=URL_PADRAO, help="URL do servidor Ollama.")
    sub.choices["modelos"].add_argument("--url", default=URL_PADRAO)
    args = parser.parse_args(argv)
    carregar_env()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        return _executar(args)
    except ErroOllama as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1


def _modelo_local_recomendado() -> ModeloLLM | None:
    rec = recomendar(detectar_hardware(), carregar_catalogo(), Preferencia.SOMENTE_LOCAL)
    return rec.principal


def _escolher_tag(modelo: str | None) -> str | None:
    if modelo:
        return modelo
    recomendado = _modelo_local_recomendado()
    if recomendado is None:
        print("Nenhum modelo local cabe nesta máquina. Use `allun diagnostico`.", file=sys.stderr)
        return None
    return recomendado.id


def _orquestrar(args: argparse.Namespace) -> int:
    from allun.orquestrador import (
        ErroLLM,
        ProvedorComFallback,
        criar_provedor,
        montar_cadeia,
        orquestrar,
    )

    rec = recomendar(detectar_hardware(), carregar_catalogo())
    cadeia = montar_cadeia(
        rec, permitir_pagos=args.permitir_pagos, permitir_anonimos=args.permitir_anonimos
    )
    ollama = ClienteOllama(args.url)
    if ollama.disponivel():
        instalados = ollama.listar()
        cadeia = [m for m in cadeia if m.tipo == "online" or m.id in instalados]
    else:
        print("Ollama indisponível; usando só modelos online.", file=sys.stderr)
        cadeia = [m for m in cadeia if m.tipo == "online"]
    if not cadeia:
        print(
            "Nenhum modelo disponível. Baixe um modelo (`allun baixar`) ou defina uma chave de API.",
            file=sys.stderr,
        )
        return 1
    llm = ProvedorComFallback([criar_provedor(m, args.url) for m in cadeia])
    print("Ordem de tentativa: " + " -> ".join(m.id for m in cadeia))
    try:
        estado = asyncio.run(orquestrar(llm, args.texto))
    except ErroLLM as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    print(f"[{estado['agente']} via {llm.ultimo_usado}]")
    print(estado["resposta"])
    return 0


def _executar(args: argparse.Namespace) -> int:
    if args.comando == "diagnostico":
        hw = detectar_hardware()
        rec = recomendar(hw, carregar_catalogo(args.catalogo), Preferencia(args.preferencia))
        print(formatar_diagnostico(hw, rec))
        return 0

    if args.comando == "orquestrar":
        return _orquestrar(args)
    if args.comando == "servir":
        import uvicorn

        print(f"Allun em http://{args.host}:{args.porta}")
        uvicorn.run("allun.api:criar_app", factory=True, host=args.host, port=args.porta)
        return 0

    cliente = ClienteOllama(args.url)
    if args.comando == "modelos":
        instalados = cliente.listar()
        print("\n".join(instalados) if instalados else "Nenhum modelo instalado.")
        return 0

    tag = _escolher_tag(args.modelo)
    if tag is None:
        return 1

    if args.comando == "baixar":
        if cliente.instalado(tag):
            print(f"{tag} já está instalado.")
            return 0
        if not args.sim:
            resposta = input(f"Baixar {tag}? Isso pode ocupar vários GB de disco [s/N] ")
            if resposta.strip().lower() not in {"s", "sim"}:
                print("Download cancelado.")
                return 0
        ultimo = ""

        def mostrar(status: str, feito: int, total: int) -> None:
            nonlocal ultimo
            texto = f"{status} {feito * 100 // total}%" if total else status
            if texto != ultimo:
                print(texto)
                ultimo = texto

        cliente.baixar(tag, mostrar)
        print(f"{tag} instalado.")
        return 0

    # perguntar
    if not cliente.instalado(tag):
        print(f"{tag} não está instalado. Rode `allun baixar {tag}`.", file=sys.stderr)
        return 1
    for pedaco in cliente.gerar(tag, args.texto):
        print(pedaco, end="", flush=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
