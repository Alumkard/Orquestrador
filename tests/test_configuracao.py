import os

import pytest

from allun.configuracao import carregar_env


def test_carrega_sem_sobrescrever_e_sem_vazar_valores(tmp_path, monkeypatch):
    arq = tmp_path / ".env"
    arq.write_text(
        "# comentário\n"
        "GROQ_API_KEY=abc123\n"
        'GEMINI_API_KEY="com espaço"\n'
        "export HF_TOKEN='tok'\n"
        "COHERE_API_KEY=\n"  # vazia: ignorada
        "OPENAI_API_KEY=ja-no-ambiente\n"
        "MISTRAL_API_KEY=valor # comentário final\n"
        "linha sem igual\n",
        encoding="utf-8",
    )
    for nome in ("GROQ_API_KEY", "GEMINI_API_KEY", "HF_TOKEN", "COHERE_API_KEY", "MISTRAL_API_KEY"):
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "do-ambiente")

    nomes = carregar_env(arq)

    assert set(nomes) == {"GROQ_API_KEY", "GEMINI_API_KEY", "HF_TOKEN", "MISTRAL_API_KEY"}
    assert os.environ["GROQ_API_KEY"] == "abc123"
    assert os.environ["GEMINI_API_KEY"] == "com espaço"
    assert os.environ["HF_TOKEN"] == "tok"
    assert os.environ["MISTRAL_API_KEY"] == "valor"
    assert os.environ["OPENAI_API_KEY"] == "do-ambiente"  # o ambiente tem prioridade
    assert "COHERE_API_KEY" not in os.environ
    for n in nomes:  # limpa o que o teste definiu
        monkeypatch.delenv(n)


def test_arquivo_ausente_nao_falha(tmp_path):
    assert carregar_env(tmp_path / "nada.env") == []


def test_env_example_lista_todas_as_chaves_do_catalogo():
    from allun.catalogo import carregar_catalogo
    from allun.configuracao import RAIZ

    exemplo = (RAIZ / ".env.example").read_text(encoding="utf-8")
    for m in carregar_catalogo():
        for chave in m.chaves_env:
            assert f"{chave}=" in exemplo, chave
        if m.chaves_env:
            assert m.chave_url, m.id


def test_salvar_e_remover_preservam_o_resto_do_arquivo(tmp_path, monkeypatch):
    from allun.configuracao import definida_no_env, mascarar, remover_chave, salvar_chave

    arq = tmp_path / ".env"
    arq.write_text("# minhas chaves\nGROQ_API_KEY=antiga\nOUTRA=1\nGROQ_API_KEY=duplicada\n")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    salvar_chave("GROQ_API_KEY", "  gsk_nova1234567  ", arq)
    assert arq.read_text() == "# minhas chaves\nGROQ_API_KEY=gsk_nova1234567\nOUTRA=1\n"
    assert os.environ["GROQ_API_KEY"] == "gsk_nova1234567"
    assert definida_no_env("GROQ_API_KEY", arq)

    salvar_chave("GEMINI_API_KEY", "AIza1234567890", arq)  # nova chave vai para o fim
    assert arq.read_text().splitlines()[-1] == "GEMINI_API_KEY=AIza1234567890"

    remover_chave("GROQ_API_KEY", arq)
    assert "GROQ_API_KEY" not in arq.read_text() and "GROQ_API_KEY" not in os.environ
    assert "OUTRA=1" in arq.read_text()
    monkeypatch.delenv("GEMINI_API_KEY")

    assert mascarar("gsk_nova1234567") == "••••4567"
    assert mascarar("curta") == "••••"


def test_salvar_cria_o_arquivo_se_nao_existir(tmp_path, monkeypatch):
    from allun.configuracao import salvar_chave

    monkeypatch.delenv("HF_TOKEN", raising=False)
    salvar_chave("HF_TOKEN", "hf_abcdef123456", tmp_path / "sub" / ".env")
    assert (tmp_path / "sub" / ".env").read_text() == "HF_TOKEN=hf_abcdef123456\n"
    monkeypatch.delenv("HF_TOKEN")


@pytest.mark.parametrize(
    "nome, valor",
    [
        ("GROQ_API_KEY", "abc\nOUTRA=injetada"),  # injeção de linha
        ("GROQ_API_KEY", "com espaco"),
        ("GROQ_API_KEY", ""),
        ("GROQ_API_KEY", "x" * 513),
        ("GROQ_API_KEY", "acentuação"),
        ("groq_api_key", "valor"),
        ("A=B", "valor"),
        ("../PATH", "valor"),
    ],
)
def test_validacao_rejeita_valores_perigosos(tmp_path, nome, valor):
    from allun.configuracao import salvar_chave

    arq = tmp_path / ".env"
    with pytest.raises(ValueError):
        salvar_chave(nome, valor, arq)
    assert not arq.exists()
