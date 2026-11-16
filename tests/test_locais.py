from pathlib import Path

from allun.locais import descrever_locais, locais_em_uso


def test_locais_avisam_variaveis_e_pasta_temporaria(tmp_path, monkeypatch):
    # conftest define ALLUN_ENV e ALLUN_PROJETOS (dentro do tmp_path, que é temporário)
    info = locais_em_uso(tmp_path / "x.db")
    assert info["banco"] == str(tmp_path / "x.db")
    assert any("ALLUN_PROJETOS" in a for a in info["avisos"])
    assert any("banco de tarefas" in a.lower() and "temporária" in a for a in info["avisos"])
    assert any(linha.startswith("AVISO:") for linha in descrever_locais(tmp_path / "x.db"))


def test_sem_avisos_no_local_padrao(monkeypatch):
    for nome in ("ALLUN_DB", "ALLUN_ENV", "ALLUN_PROJETOS"):
        monkeypatch.delenv(nome, raising=False)
    info = locais_em_uso(Path.home() / "AppData" / "Local" / "Allun" / "allun.db")
    assert info["avisos"] == []


def test_avisa_quando_o_codigo_mudou_depois_do_inicio(monkeypatch):
    from allun import locais

    monkeypatch.setattr(locais, "INICIO", 0.0)  # como se a API tivesse subido em 1970
    assert locais.codigo_alterado_depois_do_inicio()
    assert any("versão antiga" in a for a in locais.locais_em_uso()["avisos"])
    monkeypatch.setattr(locais, "INICIO", 9e12)
    assert not locais.codigo_alterado_depois_do_inicio()
