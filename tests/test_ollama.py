import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import ClassVar

import pytest

from allun.cli import main
from allun.integracao import ClienteOllama, ErroOllama


class FalsoOllama(BaseHTTPRequestHandler):
    instalados: ClassVar[list[str]] = ["llama3.2:1b"]

    def log_message(self, *args):
        pass

    def _enviar(self, linhas):
        self.send_response(200)
        self.end_headers()
        for ev in linhas:
            self.wfile.write(json.dumps(ev).encode() + b"\n")

    def do_GET(self):
        self._enviar([{"models": [{"name": n} for n in self.instalados]}])

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/api/pull":
            if corpo["model"] == "invalido":
                return self._enviar([{"error": "modelo não encontrado"}])
            self.instalados.append(corpo["model"])
            self._enviar(
                [{"status": "baixando", "completed": 50, "total": 100}, {"status": "success"}]
            )
        else:
            self._enviar([{"response": "Olá"}, {"response": " mundo"}, {"done": True}])


@pytest.fixture
def servidor():
    FalsoOllama.instalados = ["llama3.2:1b"]
    srv = HTTPServer(("127.0.0.1", 0), FalsoOllama)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_listar_e_instalado(servidor):
    c = ClienteOllama(servidor)
    assert c.disponivel() and c.listar() == ["llama3.2:1b"]
    assert c.instalado("llama3.2:1b") and not c.instalado("qwen2.5:7b")


def test_baixar_e_gerar(servidor):
    c = ClienteOllama(servidor)
    eventos = []
    c.baixar("qwen2.5:3b", lambda s, f, t: eventos.append((s, f, t)))
    assert ("baixando", 50, 100) in eventos and c.instalado("qwen2.5:3b")
    assert "".join(c.gerar("qwen2.5:3b", "oi")) == "Olá mundo"


def test_erro_do_servidor(servidor):
    with pytest.raises(ErroOllama, match="não encontrado"):
        ClienteOllama(servidor).baixar("invalido")


def test_servidor_indisponivel():
    c = ClienteOllama("http://127.0.0.1:1")
    assert not c.disponivel()
    with pytest.raises(ErroOllama, match="Não foi possível conectar"):
        c.listar()


def test_cli_baixar_pede_confirmacao(servidor, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert main(["baixar", "qwen2.5:3b", "--url", servidor]) == 0
    assert "cancelado" in capsys.readouterr().out
    assert FalsoOllama.instalados == ["llama3.2:1b"]


def test_cli_baixar_com_sim_e_perguntar(servidor, capsys):
    assert main(["baixar", "qwen2.5:3b", "--sim", "--url", servidor]) == 0
    assert main(["perguntar", "oi", "--modelo", "qwen2.5:3b", "--url", servidor]) == 0
    assert "Olá mundo" in capsys.readouterr().out


def test_cli_perguntar_sem_instalar(servidor, capsys):
    assert main(["perguntar", "oi", "--modelo", "qwen2.5:7b", "--url", servidor]) == 1
    assert "não está instalado" in capsys.readouterr().err


def test_cli_sem_servidor(capsys):
    assert main(["modelos", "--url", "http://127.0.0.1:1"]) == 1
    assert "Erro:" in capsys.readouterr().err
