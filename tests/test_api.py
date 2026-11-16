import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from allun import api
from allun.armazenamento import Armazenamento
from allun.orquestrador import ProvedorComFallback


class Falso:
    def __init__(self, nome="falso", trechos=("Olá", " mundo"), erro=None):
        self.nome, self.trechos, self.erro = nome, trechos, erro
        self.mensagens = []

    async def completar(self, mensagens, temperatura=None):
        return "geral"

    async def transmitir(self, mensagens, temperatura=None):
        self.mensagens.append(mensagens)
        if self.erro:
            raise self.erro
        for t in self.trechos:
            yield t


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "montar_especialistas_api", lambda pedido, llm: {})
    app = api.criar_app(Armazenamento(tmp_path / "api.db"), aquecer=False)
    app.state.agendados = []
    app.state.agendar_memoria = lambda tarefa_id, llm: app.state.agendados.append(tarefa_id)
    return TestClient(app)


def eventos(resp):
    return [json.loads(l[6:]) for l in resp.text.splitlines() if l.startswith("data: ")]


def test_agentes_diagnostico_e_modelos(cliente):
    assert {a["nome"] for a in cliente.get("/api/agentes").json()} >= {"geral", "programador"}
    d = cliente.get("/api/diagnostico").json()
    assert d["perfil"] in {"leve", "medio", "potente"} and "recomendacao" in d
    m = cliente.get("/api/modelos").json()
    assert "ollama_ativo" in m and all("disponivel" in x for x in m["modelos"])


def test_crud_de_tarefas(cliente):
    t = cliente.post("/api/tarefas", json={"titulo": "Teste"}).json()
    assert cliente.get("/api/tarefas").json()[0]["id"] == t["id"]
    assert cliente.get(f"/api/tarefas/{t['id']}").json()["mensagens"] == []
    assert cliente.delete(f"/api/tarefas/{t['id']}").status_code == 204
    assert cliente.get(f"/api/tarefas/{t['id']}").status_code == 404


def test_mensagem_em_streaming_e_persistencia(cliente, monkeypatch):
    llm = Falso()
    monkeypatch.setattr(api, "montar_llm", lambda pedido: ProvedorComFallback([llm]))
    t = cliente.post("/api/tarefas", json={}).json()
    r = cliente.post(f"/api/tarefas/{t['id']}/mensagens", json={"texto": "escreva em python"})
    ev = eventos(r)
    assert ev[0] == {"tipo": "agente", "agente": "programador"}
    assert "".join(e["texto"] for e in ev if e["tipo"] == "trecho") == "Olá mundo"
    assert ev[-1]["tipo"] == "fim" and ev[-1]["modelo"] == "falso"
    salvas = cliente.get(f"/api/tarefas/{t['id']}").json()["mensagens"]
    assert [m["papel"] for m in salvas] == ["usuario", "allun"] and salvas[1][
        "texto"
    ] == "Olá mundo"

    # segunda pergunta: o histórico vai ao modelo, sem duplicar a pergunta atual
    cliente.post(f"/api/tarefas/{t['id']}/mensagens", json={"texto": "e em python de novo?"})
    papeis = [m["role"] for m in llm.mensagens[-1]]
    assert papeis == ["system", "user", "assistant", "user"]


def test_erro_do_modelo_e_registrado(cliente, monkeypatch):
    llm = Falso(erro=RuntimeError("sem memória"))
    monkeypatch.setattr(api, "montar_llm", lambda pedido: ProvedorComFallback([llm]))
    t = cliente.post("/api/tarefas", json={}).json()
    r = cliente.post(f"/api/tarefas/{t['id']}/mensagens", json={"texto": "oi", "agente": "geral"})
    assert eventos(r)[-1]["tipo"] == "erro"
    ultima = cliente.get(f"/api/tarefas/{t['id']}").json()["mensagens"][-1]
    assert ultima["erro"] is True and "sem memória" in ultima["texto"]


def test_validacao_de_entrada(cliente):
    t = cliente.post("/api/tarefas", json={}).json()
    url = f"/api/tarefas/{t['id']}/mensagens"
    assert cliente.post(url, json={"texto": ""}).status_code == 422
    assert cliente.post(url, json={"texto": "oi", "agente": "x"}).status_code == 422
    assert cliente.post(url, json={"texto": "oi", "modelo": "x"}).status_code == 422
    assert (
        cliente.post("/api/tarefas/nao-existe/mensagens", json={"texto": "oi"}).status_code == 404
    )
    assert cliente.get(f"/api/tarefas/{t['id']}").json()["mensagens"] == []  # nada gravado


def test_download_exige_confirmacao(cliente, monkeypatch):
    chamadas = []

    class FalsoOllama:
        url = "x"

        def eventos_download(self, tag):
            chamadas.append(tag)
            yield {"status": "baixando", "completed": 50, "total": 100}

    monkeypatch.setattr(api, "_ollama", lambda: FalsoOllama())
    monkeypatch.setattr(api, "_instalados", list)
    assert cliente.post("/api/modelos/baixar", json={"modelo": "qwen2.5:3b"}).status_code == 400
    assert chamadas == []
    assert (
        cliente.post("/api/modelos/baixar", json={"modelo": "nada", "confirmar": True}).status_code
        == 422
    )
    assert (
        cliente.post(
            "/api/modelos/baixar", json={"modelo": "gemini/gemini-2.5-flash", "confirmar": True}
        ).status_code
        == 422
    )
    r = cliente.post("/api/modelos/baixar", json={"modelo": "qwen2.5:3b", "confirmar": True})
    ev = eventos(r)
    assert chamadas == ["qwen2.5:3b"]
    assert ev[0]["completed"] == 50 and ev[-1]["tipo"] == "fim"


def test_programador_usa_modelo_de_codigo(cliente, monkeypatch):
    geral, codigo = Falso("geral-llm", ("geral",)), Falso("coder", ("codigo",))
    llm = ProvedorComFallback([geral])
    monkeypatch.setattr(api, "montar_llm", lambda pedido: llm)
    monkeypatch.setattr(
        api,
        "montar_especialistas_api",
        lambda pedido, l: {"programador": ProvedorComFallback([codigo])},
    )
    t = cliente.post("/api/tarefas", json={}).json()
    url = f"/api/tarefas/{t['id']}/mensagens"
    ev = eventos(cliente.post(url, json={"texto": "escreva em python"}))
    assert ev[-1]["modelo"] == "coder" and "codigo" in [e.get("texto") for e in ev]
    ev = eventos(cliente.post(url, json={"texto": "oi", "agente": "geral"}))
    assert ev[-1]["modelo"] == "geral-llm"
    msgs = cliente.get(f"/api/tarefas/{t['id']}").json()["mensagens"]
    assert [m.get("modelo") for m in msgs if m["papel"] == "allun"] == ["coder", "geral-llm"]


# ---------- chaves de API ----------

CABECALHO = {"X-Allun-Painel": "1"}


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(api, "montar_especialistas_api", lambda pedido, llm: {})
    app = api.criar_app(Armazenamento(tmp_path / "k.db"), aquecer=False)
    return TestClient(app, base_url="http://localhost")


def test_inserir_alterar_e_remover_chave(local, tmp_path):
    url = "/api/chaves/GROQ_API_KEY"
    r = local.put(url, json={"valor": "gsk_segredo123456"}, headers=CABECALHO)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["definida"] and corpo["mascara"] == "••••3456" and corpo["origem"] == ".env"
    assert "segredo" not in r.text  # nunca devolve a chave

    modelos = local.get("/api/modelos")
    assert "gsk_segredo" not in modelos.text
    groq = next(m for m in modelos.json()["modelos"] if m["id"].startswith("groq/"))
    assert groq["disponivel"] is True and groq["chaves"][0]["mascara"] == "••••3456"

    local.put(url, json={"valor": "gsk_outra_chave_9999"}, headers=CABECALHO)  # alterar
    assert (tmp_path / "nao-existe.env").read_text() == "GROQ_API_KEY=gsk_outra_chave_9999\n"

    r = local.delete(url, headers=CABECALHO)
    assert r.status_code == 200 and r.json()["definida"] is False


def test_edicao_de_chave_exige_cabecalho_e_host_local(local, tmp_path):
    url = "/api/chaves/GROQ_API_KEY"
    assert local.put(url, json={"valor": "gsk_abcdef123456"}).status_code == 403
    assert local.delete(url).status_code == 403
    externo = TestClient(local.app, base_url="http://evil.example")
    assert (
        externo.put(url, json={"valor": "gsk_abcdef123456"}, headers=CABECALHO).status_code == 403
    )
    assert not (tmp_path / "nao-existe.env").exists()


def test_so_aceita_variaveis_do_catalogo_e_valores_validos(local):
    assert (
        local.put("/api/chaves/PATH", json={"valor": "x" * 20}, headers=CABECALHO).status_code
        == 404
    )
    assert local.delete("/api/chaves/PATH", headers=CABECALHO).status_code == 404
    r = local.put("/api/chaves/GROQ_API_KEY", json={"valor": "a\nB=c"}, headers=CABECALHO)
    assert r.status_code == 422


def test_erro_inesperado_mostra_a_causa(tmp_path, monkeypatch):
    base = Armazenamento(tmp_path / "e.db")
    app = api.criar_app(base, aquecer=False)
    monkeypatch.setattr(base, "listar_tarefas", lambda: 1 / 0)
    r = TestClient(app, raise_server_exceptions=False).get("/api/tarefas")
    assert r.status_code == 500 and "ZeroDivisionError" in r.json()["detail"]


def test_resposta_agenda_memoria_e_usa_a_memoria_salva(cliente, monkeypatch):
    import asyncio as aio

    llm = Falso()
    monkeypatch.setattr(api, "montar_llm", lambda pedido: ProvedorComFallback([llm]))
    t = cliente.post("/api/tarefas", json={}).json()
    url = f"/api/tarefas/{t['id']}/mensagens"
    eventos(cliente.post(url, json={"texto": "oi", "agente": "geral"}))
    assert cliente.app.state.agendados == [t["id"]]

    # resumo em segundo plano, executado aqui de forma direta
    for i in range(4):
        eventos(cliente.post(url, json={"texto": f"msg {i}", "agente": "geral"}))
    resumidor = Falso()

    async def completar(mensagens, temperatura=None):
        return '{"resumo": "Conversa de teste.", "fatos": ["Usuário se chama Luiz"]}'

    resumidor.completar = completar
    aio.run(cliente.app.state.atualizar_memoria(t["id"], ProvedorComFallback([resumidor])))
    mem = cliente.get(f"/api/tarefas/{t['id']}").json()["memoria"]
    assert mem["fatos"] == ["Usuário se chama Luiz"] and mem["cobertas"] == 6

    eventos(cliente.post(url, json={"texto": "quem sou eu?", "agente": "geral"}))
    sistema = llm.mensagens[-1][0]["content"]
    assert "Usuário se chama Luiz" in sistema
    assert len(llm.mensagens[-1]) == 1 + 4 + 1  # sistema, 4 recentes fora do resumo, pergunta


# ---------- arquivos do projeto ----------


def test_resposta_com_codigo_grava_na_pasta_automatica(cliente, monkeypatch, tmp_path):
    llm = Falso(trechos=("Pronto:\n```html index.html\n<h1>Loja</h1>\n```",))
    monkeypatch.setattr(api, "montar_llm", lambda pedido: ProvedorComFallback([llm]))
    t = cliente.post("/api/tarefas", json={"titulo": "Loja"}).json()
    assert t["pasta_automatica"] is True
    ev = eventos(cliente.post(f"/api/tarefas/{t['id']}/mensagens", json={"texto": "crie em html"}))
    arq = next(e for e in ev if e["tipo"] == "arquivos")
    pasta = Path(arq["pasta"])
    assert pasta.parent == tmp_path / "projetos"
    assert (pasta / "index.html").read_text(encoding="utf-8") == "<h1>Loja</h1>\n"
    assert arq["gravados"][0]["situacao"] == "criado"
    assert "Modo arquivos ligado" in llm.mensagens[-1][0]["content"]
    salvo = cliente.get(f"/api/tarefas/{t['id']}").json()["mensagens"][-1]
    assert salvo["arquivos"]["gravados"][0]["caminho"] == "index.html"

    # segunda vez: o agente sabe o que já existe
    eventos(cliente.post(f"/api/tarefas/{t['id']}/mensagens", json={"texto": "mude o html"}))
    assert "Arquivos que já existem no projeto: index.html" in llm.mensagens[-1][0]["content"]


def test_salvar_arquivos_desligado_nao_grava(cliente, monkeypatch, tmp_path):
    llm = Falso(trechos=("```html index.html\nx\n```",))
    monkeypatch.setattr(api, "montar_llm", lambda pedido: ProvedorComFallback([llm]))
    t = cliente.post("/api/tarefas", json={}).json()
    ev = eventos(
        cliente.post(
            f"/api/tarefas/{t['id']}/mensagens",
            json={"texto": "html", "salvar_arquivos": False},
        )
    )
    assert not any(e["tipo"] == "arquivos" for e in ev)
    assert not (tmp_path / "projetos").exists()
    assert "Modo arquivos" not in llm.mensagens[-1][0]["content"]


def test_pasta_definida_pelo_usuario(local, tmp_path):
    destino = tmp_path / "meu-projeto"
    sem = local.post("/api/tarefas", json={"pasta": str(destino)})
    assert sem.status_code == 403  # escolher pasta exige o painel local
    t = local.post("/api/tarefas", json={"pasta": str(destino)}, headers=CABECALHO).json()
    assert t["pasta_efetiva"] == str(destino.resolve()) and t["pasta_automatica"] is False

    r = local.put(f"/api/tarefas/{t['id']}/pasta", json={"pasta": "relativa"}, headers=CABECALHO)
    assert r.status_code == 422
    assert (
        local.put(f"/api/tarefas/{t['id']}/pasta", json={"pasta": str(destino)}).status_code == 403
    )
    r = local.put(f"/api/tarefas/{t['id']}/pasta", json={"pasta": None}, headers=CABECALHO)
    assert r.json()["pasta_automatica"] is True
    assert local.post(f"/api/tarefas/{t['id']}/abrir-pasta", headers=CABECALHO).status_code == 409


def test_pedido_curto_continua_com_o_programador(cliente, monkeypatch):
    llm = Falso(trechos=("```html index.html\n<p>v1</p>\n```",))
    monkeypatch.setattr(api, "montar_llm", lambda pedido: ProvedorComFallback([llm]))
    t = cliente.post("/api/tarefas", json={}).json()
    url = f"/api/tarefas/{t['id']}/mensagens"
    assert eventos(cliente.post(url, json={"texto": "crie em html"}))[0]["agente"] == "programador"
    # sem palavra-chave: sem a regra, o Comandante (Falso.completar) mandaria para "geral"
    assert (
        eventos(cliente.post(url, json={"texto": "mude a cor do botão"}))[0]["agente"]
        == "programador"
    )
    # com o modo arquivos desligado, volta a decidir normalmente
    ev = eventos(cliente.post(url, json={"texto": "mude a cor", "salvar_arquivos": False}))
    assert ev[0]["agente"] == "geral"


def test_agente_le_o_arquivo_editado_a_mao(cliente, monkeypatch):
    llm = Falso(trechos=("```html index.html\n<p>v1</p>\n```",))
    monkeypatch.setattr(api, "montar_llm", lambda pedido: ProvedorComFallback([llm]))
    t = cliente.post("/api/tarefas", json={}).json()
    url = f"/api/tarefas/{t['id']}/mensagens"
    ev = eventos(cliente.post(url, json={"texto": "crie em html"}))
    pasta = Path(next(e for e in ev if e["tipo"] == "arquivos")["pasta"])
    (pasta / "index.html").write_text("<p>editado a mão</p>", encoding="utf-8")

    ev = eventos(cliente.post(url, json={"texto": "mude o index.html"}))
    ctx = next(e for e in ev if e["tipo"] == "contexto")
    assert ctx["arquivos_lidos"] == ["index.html"]
    sistema = llm.mensagens[-1][0]["content"]
    assert "<p>editado a mão</p>" in sistema and "<p>v1</p>" not in str(llm.mensagens[-1])
