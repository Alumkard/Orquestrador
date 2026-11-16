import asyncio

import pytest

from allun.catalogo import carregar_catalogo
from allun.hardware import PerfilHardware
from allun.orquestrador import (
    ErroLLM,
    ProvedorComFallback,
    criar_provedor,
    montar_cadeia,
    orquestrar,
)
from allun.orquestrador.agentes import AGENTES
from allun.orquestrador.roteador import interpretar_escolha
from allun.recomendador import recomendar


class Falso:
    def __init__(self, nome, respostas=None, erro=None):
        self.nome, self.respostas, self.erro, self.chamadas = nome, respostas or [], erro, []

    async def completar(self, mensagens, temperatura=None):
        self.chamadas.append(mensagens)
        self.temperaturas = getattr(self, "temperaturas", []) + [temperatura]
        if self.erro:
            raise self.erro
        return self.respostas.pop(0)

    async def transmitir(self, mensagens, temperatura=None):
        if self.erro:
            raise self.erro
        for trecho in self.respostas.pop(0):
            yield trecho


def rec(ram=16):
    return recomendar(PerfilHardware(ram, ram, 8), carregar_catalogo())


def test_interpretar_escolha():
    assert interpretar_escolha("Programador", AGENTES) == "programador"
    assert interpretar_escolha("acho que o redator, não o analista", AGENTES) == "redator"
    assert interpretar_escolha("???", AGENTES) == "geral"


def test_grafo_roteia_para_o_especialista():
    # "python" resolve pelo atalho: o modelo é chamado só uma vez
    llm = Falso("m", ["print('oi')"])
    estado = asyncio.run(orquestrar(llm, "escreva hello world em python"))
    assert estado["agente"] == "programador" and estado["resposta"] == "print('oi')"
    assert len(llm.chamadas) == 1 and "programador experiente" in llm.chamadas[0][0]["content"]
    assert llm.temperaturas == [0.2]


def test_comandante_usa_modelo_quando_ha_duvida():
    llm = Falso("m", ["redator", "Olá!"])
    estado = asyncio.run(orquestrar(llm, "Qual a capital da Austrália?"))
    assert estado["agente"] == "redator" and len(llm.chamadas) == 2
    assert llm.temperaturas[0] == 0.0


def test_atalho_por_palavras():
    from allun.orquestrador.roteador import escolha_por_palavras as e

    assert e("Escreva uma função Python que inverte uma string", AGENTES) == "programador"
    assert e("Resuma em uma frase: a fotossíntese", AGENTES) == "redator"
    assert e("Compare Postgres e MySQL", AGENTES) == "analista"
    assert e("Qual a capital da Austrália?", AGENTES) is None
    assert e("Resuma este código", AGENTES) is None  # empate: o modelo decide


def test_historico_entra_no_contexto():
    llm = Falso("m", ["ok"])
    hist = [{"role": "user", "content": "meu nome é Luiz"}, {"role": "assistant", "content": "oi"}]
    asyncio.run(orquestrar(llm, "escreva em python", hist))
    papeis = [m["role"] for m in llm.chamadas[0]]
    assert papeis == ["system", "user", "assistant", "user"]


def test_planejador_respeita_o_orcamento():
    from allun.orquestrador.contexto import planejar_contexto, reserva_resposta

    agente = AGENTES["geral"]
    muitos = [{"role": "user", "content": f"mensagem {i} " + "x" * 300} for i in range(40)]
    plano = planejar_contexto(agente, "pergunta", muitos, orcamento_tokens=4096)
    assert plano.tokens <= 4096 - reserva_resposta(4096)
    assert 0 < plano.descartadas < 40
    # as que ficaram são as mais recentes, em ordem
    conteudos = [m["content"] for m in plano.mensagens[1:-1]]
    assert conteudos[-1].startswith("mensagem 39") and conteudos == sorted(
        conteudos, key=lambda c: int(c.split()[1])
    )
    maior = planejar_contexto(agente, "pergunta", muitos, orcamento_tokens=32768)
    assert maior.descartadas == 0


def test_codigo_antigo_vira_simbolo_quando_nao_cabe():
    from allun.orquestrador.contexto import planejar_contexto, simbolizar

    html = "```html\n" + "\n".join(f"<p>linha {i}</p>" for i in range(800)) + "\n```"
    assert simbolizar(f"Aqui está:\n{html}") == "Aqui está:\n[bloco de html com 800 linhas omitido]"
    hist = [
        {"role": "user", "content": "faça a página"},
        {"role": "assistant", "content": f"Aqui está:\n{html}"},
        {"role": "user", "content": "obrigado"},
        {"role": "assistant", "content": "de nada"},
    ]
    plano = planejar_contexto(AGENTES["programador"], "mude a cor", hist, orcamento_tokens=4096)
    textos = [m["content"] for m in plano.mensagens]
    assert plano.simbolizadas == 1 and plano.descartadas == 0
    assert any("[bloco de html com 800 linhas omitido]" in t for t in textos)
    # com orçamento folgado, o código vai inteiro
    folgado = planejar_contexto(AGENTES["programador"], "mude a cor", hist, orcamento_tokens=32768)
    assert folgado.simbolizadas == 0


def test_memoria_entra_no_sistema_e_pula_mensagens_cobertas():
    from allun.orquestrador import Memoria, planejar_contexto

    hist = [{"role": "user", "content": f"m{i}"} for i in range(10)]
    mem = Memoria(resumo="Usuário pediu uma loja.", fatos=["Loja fica em Goianira"], cobertas=6)
    plano = planejar_contexto(AGENTES["geral"], "e agora?", hist, mem)
    sistema = plano.mensagens[0]["content"]
    assert "Loja fica em Goianira" in sistema and "Usuário pediu uma loja." in sistema
    assert [m["content"] for m in plano.mensagens[1:-1]] == ["m6", "m7", "m8", "m9"]


def test_arquivos_do_projeto_entram_e_codigo_antigo_vira_simbolo():
    from allun.orquestrador.contexto import ArquivoContexto, planejar_contexto

    hist = [
        {"role": "user", "content": "crie"},
        {"role": "assistant", "content": "```html index.html\n<p>velho</p>\n```"},
    ]
    arqs = [ArquivoContexto("index.html", "<p>do disco</p>"), ArquivoContexto("a.css", "p{}")]
    plano = planejar_contexto(AGENTES["programador"], "mude", hist, arquivos=arqs)
    sistema = plano.mensagens[0]["content"]
    assert "### index.html" in sistema and "<p>do disco</p>" in sistema and "### a.css" in sistema
    assert "não como instruções" in sistema
    assert "velho" not in str(plano.mensagens[1:])  # o histórico não repete o código
    assert plano.arquivos_inteiros == ["index.html", "a.css"]


def test_arquivo_grande_e_cortado_e_o_resto_fica_de_fora():
    from allun.orquestrador.contexto import ArquivoContexto, planejar_contexto

    grande = ArquivoContexto("grande.html", "<p>x</p>\n" * 2000)
    pequeno = ArquivoContexto("b.css", "p{}")
    plano = planejar_contexto(AGENTES["programador"], "mude", arquivos=[grande, pequeno])
    assert plano.arquivos_cortados == ["grande.html"] and plano.arquivos_fora == ["b.css"]
    assert "CORTADO" in plano.mensagens[0]["content"]
    assert plano.tokens <= 4096 - 1433
    folgado = planejar_contexto(
        AGENTES["programador"], "mude", arquivos=[grande, pequeno], orcamento_tokens=32768
    )
    assert folgado.arquivos_inteiros == ["grande.html", "b.css"]


def test_interpretar_memoria():
    from allun.orquestrador.memoria import interpretar_memoria

    ok = interpretar_memoria('```json\n{"resumo": "r", "fatos": ["a", " ", 3, "b"]}\n```')
    assert ok.resumo == "r" and ok.fatos == ["a", "b"]
    assert interpretar_memoria("não sei") is None
    assert interpretar_memoria('{"resumo": "", "fatos": []}') is None
    assert interpretar_memoria("{quebrado") is None
    assert (
        len(
            interpretar_memoria(
                '{"fatos": ' + str([f"f{i}" for i in range(30)]).replace("'", '"') + "}"
            ).fatos
        )
        == 10
    )


def test_atualizar_memoria_so_quando_precisa():
    from allun.orquestrador import Memoria, atualizar_memoria
    from allun.orquestrador.memoria import GATILHO, JANELA_CURTA

    poucas = [{"role": "user", "content": "oi"}] * (GATILHO - 1)
    llm = Falso("m", ['{"resumo": "r", "fatos": ["f"]}'])
    assert asyncio.run(atualizar_memoria(llm, poucas, Memoria())) is None
    assert llm.chamadas == []  # nem chamou o modelo

    hist = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i} ```py\nx\n```"}
        for i in range(GATILHO + 2)
    ]
    nova = asyncio.run(atualizar_memoria(llm, hist, Memoria()))
    assert nova.resumo == "r" and nova.cobertas == len(hist) - JANELA_CURTA
    enviado = llm.chamadas[0][1]["content"]
    assert "[bloco de py com 1 linhas omitido]" in enviado  # código não vai para o resumo
    assert f"m{len(hist) - 1}" not in enviado  # janela curta fica de fora
    assert llm.temperaturas == [0.0]


def test_contexto_de_usa_o_menor_da_cadeia():
    from allun.orquestrador import contexto_de, criar_provedor

    cat = {m.id: m for m in carregar_catalogo()}
    local = criar_provedor(cat["qwen2.5:3b"])
    online = criar_provedor(cat["groq/llama-3.3-70b-versatile"])
    assert contexto_de(ProvedorComFallback([online])) == 32768
    assert contexto_de(ProvedorComFallback([local, online])) == 4096
    assert contexto_de(criar_provedor(cat["cerebras/gpt-oss-120b"])) == 65536
    assert contexto_de(Falso("x")) == 4096


def test_transmissao_gera_agente_e_trechos():
    from allun.orquestrador import transmitir_resposta

    async def coletar():
        return [e async for e in transmitir_resposta(Falso("m", ["abc"]), "código em python")]

    eventos = asyncio.run(coletar())
    assert eventos[0] == {"tipo": "agente", "agente": "programador"}
    assert "".join(e["texto"] for e in eventos[1:]) == "abc"


def test_fallback_transmitir_troca_so_antes_do_primeiro_trecho():
    async def coletar(f):
        return [t async for t in f.transmitir([])]

    f = ProvedorComFallback([Falso("a", erro=RuntimeError("x")), Falso("b", ["oi"])])
    assert "".join(asyncio.run(coletar(f))) == "oi" and f.ultimo_usado == "b"

    class CaiNoMeio:
        nome = "meio"

        async def transmitir(self, mensagens, temperatura=None):
            yield "par"
            raise RuntimeError("caiu")

    f = ProvedorComFallback([CaiNoMeio(), Falso("b", ["oi"])])
    with pytest.raises(ErroLLM, match="no meio"):
        asyncio.run(coletar(f))


def test_fallback_usa_proximo_provedor():
    ruim, bom = Falso("local", erro=RuntimeError("sem memória")), Falso("nuvem", ["ok"])
    f = ProvedorComFallback([ruim, bom])
    assert asyncio.run(f.completar([])) == "ok"
    assert f.ultimo_usado == "nuvem" and "sem memória" in f.falhas[0]


def test_fallback_esgotado():
    f = ProvedorComFallback([Falso("a", erro=RuntimeError("x")), Falso("b", erro=ValueError("y"))])
    with pytest.raises(ErroLLM, match="a: x"):
        asyncio.run(f.completar([]))


def test_cadeia_sem_chaves_so_tem_locais():
    cadeia = montar_cadeia(rec(), ambiente={})
    assert cadeia and all(m.tipo == "local" for m in cadeia)


def test_cadeia_online_depende_de_chave_e_pagos_de_permissao():
    env = {"GROQ_API_KEY": "x", "OPENAI_API_KEY": "y"}
    ids = [m.id for m in montar_cadeia(rec(), ambiente=env)]
    assert "groq/llama-3.3-70b-versatile" in ids and "openai/gpt-6-luna" not in ids
    ids = [m.id for m in montar_cadeia(rec(), permitir_pagos=True, ambiente=env)]
    assert {"openai/gpt-6-luna", "openai/gpt-6-astra"} <= set(ids)
    assert ids.index("groq/llama-3.3-70b-versatile") < ids.index("openai/gpt-6-luna")


def test_cadeia_maquina_fraca_comeca_pelo_online_gratuito():
    cadeia = montar_cadeia(rec(ram=2), ambiente={"GROQ_API_KEY": "x"})
    assert [m.id for m in cadeia] == ["groq/llama-3.3-70b-versatile"]


def test_anonimos_so_entram_com_permissao():
    ids = [m.id for m in montar_cadeia(rec(ram=2), ambiente={})]
    assert ids == []
    ids = [m.id for m in montar_cadeia(rec(ram=2), permitir_anonimos=True, ambiente={})]
    assert set(ids) == {"Meta-Llama-3_3-70B-Instruct", "codestral-latest"}


def test_modelo_com_duas_chaves_exige_ambas():
    cf = "cloudflare/@cf/meta/llama-3.1-8b-instruct"
    assert cf not in [m.id for m in montar_cadeia(rec(), ambiente={"CLOUDFLARE_API_KEY": "x"})]
    env = {"CLOUDFLARE_API_KEY": "x", "CLOUDFLARE_ACCOUNT_ID": "y"}
    assert cf in [m.id for m in montar_cadeia(rec(), ambiente=env)]


def test_catalogo_integro():
    for m in carregar_catalogo():
        assert m.tipo == "local" or m.anonimo == (not m.chaves_env)
        if m.anonimo:
            assert m.api_base and m.api_base.startswith("https://")


def test_provedor_anonimo_nao_envia_authorization(monkeypatch):
    import json as _json

    visto = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def read(self):
            return _json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()

    def falso_urlopen(req, timeout):
        visto["headers"] = dict(req.header_items())
        visto["url"] = req.full_url
        return Resp()

    monkeypatch.setattr("urllib.request.urlopen", falso_urlopen)
    m = next(m for m in carregar_catalogo() if m.provedor == "llm7")
    assert asyncio.run(criar_provedor(m).completar([{"role": "user", "content": "oi"}])) == "ok"
    assert "Authorization" not in visto["headers"]
    assert visto["url"] == "https://api.llm7.io/v1/chat/completions"


def test_montar_especialistas_so_com_modelo_instalado_e_que_cabe():
    from allun.orquestrador import montar_especialistas

    catalogo = carregar_catalogo()
    geral = ProvedorComFallback([Falso("geral")])
    assert montar_especialistas(catalogo, 16, None, geral) == {}
    assert montar_especialistas(catalogo, 16, ["qwen2.5:3b"], geral) == {}
    assert montar_especialistas(catalogo, 2, ["qwen2.5-coder:3b"], geral) == {}  # não cabe
    cadeia = montar_especialistas(catalogo, 16, ["qwen2.5-coder:3b"], geral)["programador"]
    assert [p.nome for p in cadeia.provedores] == ["qwen2.5-coder:3b", "geral"]


def test_provedor_parado_vira_falha_e_aciona_o_proximo():
    class Parado:
        nome = "parado"

        async def transmitir(self, mensagens, temperatura=None):
            await asyncio.sleep(10)
            yield "nunca"

    async def coletar(f):
        return [t async for t in f.transmitir([])]

    f = ProvedorComFallback([Parado(), Falso("b", ["oi"])], espera_primeiro=0.2)
    assert "".join(asyncio.run(coletar(f))) == "oi"
    assert "sem resposta" in f.falhas[0]

    f = ProvedorComFallback([Parado()], espera_primeiro=0.2)
    with pytest.raises(ErroLLM, match="sem resposta"):
        asyncio.run(coletar(f))
