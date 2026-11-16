from allun.armazenamento import Armazenamento


def test_tarefas_e_mensagens(tmp_path):
    b = Armazenamento(tmp_path / "t.db")
    t = b.criar_tarefa("  Minha tarefa  ")
    assert t["titulo"] == "Minha tarefa"
    b.adicionar_mensagem(t["id"], "usuario", "oi")
    b.adicionar_mensagem(t["id"], "allun", "olá", agente="geral", modelo="m", duracao_s=1.5)
    b.adicionar_mensagem(t["id"], "allun", "falhou", erro=True)
    obtida = b.obter_tarefa(t["id"])
    assert [m["papel"] for m in obtida["mensagens"]] == ["usuario", "allun", "allun"]
    assert obtida["mensagens"][1]["agente"] == "geral" and obtida["mensagens"][2]["erro"] is True
    # erros não entram no contexto do modelo
    assert b.historico(t["id"]) == [
        {"role": "user", "content": "oi"},
        {"role": "assistant", "content": "olá"},
    ]


def test_remover_apaga_mensagens_e_persiste(tmp_path):
    caminho = tmp_path / "t.db"
    b = Armazenamento(caminho)
    t = b.criar_tarefa("x")
    b.adicionar_mensagem(t["id"], "usuario", "oi")
    assert [x["id"] for x in Armazenamento(caminho).listar_tarefas()] == [t["id"]]
    assert b.remover_tarefa(t["id"]) is True and b.remover_tarefa(t["id"]) is False
    assert b.obter_tarefa(t["id"]) is None and b.historico(t["id"]) == []


def test_recupera_se_o_banco_for_apagado_com_o_servidor_rodando(tmp_path):
    caminho = tmp_path / "sub" / "t.db"
    b = Armazenamento(caminho)
    b.criar_tarefa("antes")
    caminho.unlink()
    caminho.parent.rmdir()
    assert b.listar_tarefas() == []  # não levanta "no such table"
    t = b.criar_tarefa("depois")
    assert [x["id"] for x in b.listar_tarefas()] == [t["id"]]


def test_memoria_da_tarefa(tmp_path):
    b = Armazenamento(tmp_path / "m.db")
    t = b.criar_tarefa("x")
    assert b.obter_memoria(t["id"]) is None
    assert b.salvar_memoria(t["id"], "resumo", ["fato ç"], 4)
    assert b.obter_memoria(t["id"]) == {"resumo": "resumo", "fatos": ["fato ç"], "cobertas": 4}
    b.salvar_memoria(t["id"], "novo", [], 8)
    assert b.obter_memoria(t["id"])["cobertas"] == 8
    b.remover_tarefa(t["id"])
    assert b.obter_memoria(t["id"]) is None
    assert b.salvar_memoria(t["id"], "x", [], 1) is False  # tarefa apagada no meio do resumo
