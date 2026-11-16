from pathlib import Path

import pytest

from allun.projetos import (
    ArquivoExtraido,
    CaminhoInvalido,
    caminho_seguro,
    extrair_arquivos,
    gravar_arquivos,
    listar_arquivos,
    pasta_automatica,
    validar_pasta,
)


def nomes(resposta):
    return {a.caminho: a.conteudo for a in extrair_arquivos(resposta)}


def test_extrai_caminho_do_cabecalho_do_bloco():
    r = "Pronto:\n```html index.html\n<h1>oi</h1>\n```\n```css:css/estilo.css\nh1{}\n```\n"
    assert nomes(r) == {"index.html": "<h1>oi</h1>\n", "css/estilo.css": "h1{}\n"}
    assert nomes('```python title="app.py"\nprint(1)\n```') == {"app.py": "print(1)\n"}
    assert nomes("```main.py\nx = 1\n```") == {"main.py": "x = 1\n"}


def test_extrai_caminho_da_linha_anterior():
    r = "**Arquivo: `script.js`**\n```javascript\nalert(1)\n```\n\n### style.css\n```css\na{}\n```"
    assert nomes(r) == {"script.js": "alert(1)\n", "style.css": "a{}\n"}


def test_sem_nome_so_adivinha_sem_ambiguidade():
    assert nomes("```html\n<p>x</p>\n```") == {"index.html": "<p>x</p>\n"}
    assert set(nomes("```html\na\n```\n```css\nb\n```\n```js\nc\n```")) == {
        "index.html",
        "style.css",
        "script.js",
    }
    assert nomes("```python\na\n```\n```python\nb\n```") == {}  # dois .py: ambíguo
    assert nomes("```bash\npip install x\n```") == {}  # comandos não viram arquivo
    assert nomes("```cobol\nx\n```") == {}
    assert nomes("Só texto, sem código.") == {}


def test_html_puro_sem_bloco_vira_index():
    assert set(nomes("<!DOCTYPE html>\n<html></html>")) == {"index.html"}


@pytest.mark.parametrize(
    "rel",
    [
        "../fora.txt",
        "a/../../fora.txt",
        "/etc/passwd",
        "C:\\Windows\\x.txt",
        "C:x.txt",
        "~/x.txt",
        ".allun/versoes/x",
        ".git/config",
        "con.txt",
        "a/nul",
        "nome?.txt",
        "a/b/c/d/e/f/g.txt",
        "",
        "pasta /x.txt",
    ],
)
def test_caminho_seguro_recusa(tmp_path, rel):
    with pytest.raises(CaminhoInvalido):
        caminho_seguro(tmp_path, rel)


def test_caminho_seguro_aceita(tmp_path):
    assert (
        caminho_seguro(tmp_path, "./css\\estilo.css") == (tmp_path / "css" / "estilo.css").resolve()
    )
    assert caminho_seguro(tmp_path, ".gitignore").name == ".gitignore"


def test_gravar_cria_altera_com_copia_e_rejeita(tmp_path):
    pasta = tmp_path / "proj"
    r = gravar_arquivos(
        pasta, [ArquivoExtraido("index.html", "v1"), ArquivoExtraido("../x", "mal")]
    )
    assert r["gravados"] == [{"caminho": "index.html", "bytes": 2, "situacao": "criado"}]
    assert r["rejeitados"][0]["caminho"] == "../x" and not (tmp_path / "x").exists()

    r = gravar_arquivos(pasta, [ArquivoExtraido("index.html", "v2")])
    assert r["gravados"][0]["situacao"] == "alterado"
    assert (pasta / "index.html").read_text() == "v2"
    copias = list((pasta / ".allun" / "versoes").rglob("index.html"))
    assert len(copias) == 1 and copias[0].read_text() == "v1"

    assert (
        gravar_arquivos(pasta, [ArquivoExtraido("index.html", "v2")])["gravados"][0]["situacao"]
        == "igual"
    )
    assert listar_arquivos(pasta) == ["index.html"]  # a pasta interna não aparece


def test_gravar_limites(tmp_path):
    grande = ArquivoExtraido("g.txt", "x" * 1_000_001)
    muitos = [ArquivoExtraido(f"a{i}.txt", "x") for i in range(25)]
    r = gravar_arquivos(tmp_path, [grande, *muitos])
    assert {x["caminho"] for x in r["rejeitados"]} >= {"g.txt"}
    assert len(r["gravados"]) == 19 and len(r["rejeitados"]) == 7  # 1 grande + 6 além do limite


def test_pasta_automatica_usa_titulo_e_id(tmp_path):
    p = pasta_automatica({"id": "abc123def456", "titulo": "Loja de Música em Goiânia!"})
    assert p == tmp_path / "projetos" / "loja-de-musica-em-goiania-abc123"


def test_validar_pasta(tmp_path, monkeypatch):
    assert validar_pasta(str(tmp_path / "novo")) == (tmp_path / "novo").resolve()
    for ruim in ("relativa/pasta", "", "C:\\", str(Path.home())):
        with pytest.raises(CaminhoInvalido):
            validar_pasta(ruim)
    monkeypatch.setenv("WINDIR", str(tmp_path / "win"))
    with pytest.raises(CaminhoInvalido, match="protegida"):
        validar_pasta(str(tmp_path / "win" / "sub"))
    arquivo = tmp_path / "f.txt"
    arquivo.write_text("x")
    with pytest.raises(CaminhoInvalido):
        validar_pasta(str(arquivo))


def test_leitura_para_contexto_prioriza_e_filtra(tmp_path):
    import os
    import time

    from allun.projetos import arquivos_para_contexto

    (tmp_path / "css").mkdir()
    (tmp_path / "index.html").write_text("<h1>oi</h1>", encoding="utf-8")
    (tmp_path / "css" / "style.css").write_text("h1{}", encoding="utf-8")
    (tmp_path / "app.js").write_text("alert(1)", encoding="utf-8")
    (tmp_path / ".env").write_text("SEGREDO=1", encoding="utf-8")
    (tmp_path / "chave.pem").write_text("x", encoding="utf-8")
    (tmp_path / "foto.png").write_bytes(b"\x89PNG")
    (tmp_path / "latin1.txt").write_bytes("ação".encode("latin-1"))
    (tmp_path / ".allun" / "versoes").mkdir(parents=True)
    (tmp_path / ".allun" / "versoes" / "old.html").write_text("velho", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("x", encoding="utf-8")
    agora = time.time()
    os.utime(tmp_path / "app.js", (agora + 10, agora + 10))  # o mais recente

    lidos = arquivos_para_contexto(tmp_path, "mude o style.css", recentes=["index.html"])
    caminhos = [c for c, _ in lidos]
    assert caminhos[:3] == ["css/style.css", "index.html", "app.js"]
    assert set(caminhos) == {"css/style.css", "index.html", "app.js"}  # sem segredos, binários etc.
    assert dict(lidos)["index.html"] == "<h1>oi</h1>"
    assert arquivos_para_contexto(tmp_path / "nao-existe") == []
