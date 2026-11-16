import pytest


@pytest.fixture(autouse=True)
def sem_env_real(tmp_path, monkeypatch):
    """Os testes nunca leem o .env do usuário nem gravam na pasta real de projetos."""
    monkeypatch.setenv("ALLUN_ENV", str(tmp_path / "nao-existe.env"))
    monkeypatch.setenv("ALLUN_PROJETOS", str(tmp_path / "projetos"))
    # tmp_path fica dentro de AppData\Local, que é pasta protegida; nos testes, AppData é outra.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "_localappdata"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "_appdata"))
