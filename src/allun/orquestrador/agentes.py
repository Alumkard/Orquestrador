"""Agentes especialistas disponíveis para o Comandante."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Agente:
    nome: str
    descricao: str
    prompt_sistema: str
    temperatura: float = 0.7
    palavras_chave: tuple[str, ...] = ()  # atalho do Comandante, sem gastar uma chamada ao modelo


AGENTE_PADRAO = "geral"

# Regras comuns: modelos pequenos tendem a ignorar restrições de formato do pedido.
_REGRAS = (
    "Siga literalmente as restrições de formato do pedido (por exemplo, 'apenas o código' "
    "ou 'um único arquivo'). Não acrescente explicações que o usuário não pediu."
)

AGENTES: dict[str, Agente] = {
    a.nome: a
    for a in (
        Agente(
            "programador",
            "escreve, explica e corrige código",
            "Você é um programador experiente. Responda em português do Brasil. "
            f"{_REGRAS} Quando pedirem um único arquivo, coloque HTML, CSS e JavaScript "
            "dentro dele (tags <style> e <script>), sem arquivos externos. "
            "Em páginas web: comece com <!DOCTYPE html>; não use imagens, fontes ou bibliotecas "
            "externas (nada de placeholder.com nem CDN); ilustre com emojis, SVG ou gradientes CSS; "
            "escolha uma paleta de cores e um estilo coerentes com o tema; use flexbox ou grid "
            "responsivo e inclua JavaScript simples para a interação principal (por exemplo "
            "filtrar, buscar ou adicionar ao carrinho).",
            temperatura=0.2,
            palavras_chave=(
                "codigo",
                "python",
                "javascript",
                "typescript",
                "html",
                "css",
                "funcao",
                "bug",
                "script",
                "sql",
                "programa",
                "webpage",
                "pagina web",
                "site",
                "react",
                "java",
                "api",
                "compil",
                "algoritmo",
                "frontend",
                "backend",
            ),
        ),
        Agente(
            "analista",
            "analisa dados, compara opções e faz cálculos ou raciocínio lógico",
            "Você é um analista rigoroso. Responda em português do Brasil. "
            f"{_REGRAS} Raciocine passo a passo e termine com a conclusão em uma frase.",
            temperatura=0.3,
            palavras_chave=(
                "compar",
                "analis",
                "calcul",
                "estatistic",
                "planilha",
                "pros e contras",
                "quanto",
                "porcentagem",
                "media",
                "decisao",
                "vale a pena",
            ),
        ),
        Agente(
            "redator",
            "escreve, resume, revisa ou traduz textos",
            "Você é um redator profissional. Responda em português do Brasil, com clareza "
            f"e boa gramática. {_REGRAS}",
            temperatura=0.6,
            palavras_chave=(
                "resum",
                "traduz",
                "traducao",
                "reescrev",
                "revis",
                "artigo",
                "e-mail",
                "email",
                "redij",
                "carta",
                "texto",
                "publicacao",
                "legenda",
            ),
        ),
        Agente(
            AGENTE_PADRAO,
            "responde perguntas gerais que não se encaixam nos demais",
            f"Você é um assistente prestativo. Responda em português do Brasil, de forma direta. {_REGRAS}",
            temperatura=0.7,
        ),
    )
}
