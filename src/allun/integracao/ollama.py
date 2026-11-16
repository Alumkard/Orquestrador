"""Cliente mínimo da API HTTP do Ollama (sem dependências externas)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator

URL_PADRAO = "http://localhost:11434"


class ErroOllama(RuntimeError):
    """Falha ao falar com o servidor Ollama."""


class ClienteOllama:
    def __init__(self, url: str = URL_PADRAO, timeout: float = 600.0):
        self.url = url.rstrip("/")
        self.timeout = timeout

    def _abrir(self, caminho: str, corpo: dict | None = None, timeout: float | None = None):
        dados = json.dumps(corpo).encode() if corpo is not None else None
        req = urllib.request.Request(
            self.url + caminho,
            data=dados,
            headers={"Content-Type": "application/json"},
            method="POST" if corpo is not None else "GET",
        )
        try:
            return urllib.request.urlopen(req, timeout=timeout or self.timeout)
        except urllib.error.HTTPError as erro:
            detalhe = erro.read().decode(errors="replace")
            raise ErroOllama(f"Ollama respondeu {erro.code}: {detalhe}") from erro
        except (urllib.error.URLError, OSError) as erro:
            raise ErroOllama(
                f"Não foi possível conectar ao Ollama em {self.url}. "
                "Ele está instalado e em execução? (https://ollama.com)"
            ) from erro

    def disponivel(self) -> bool:
        try:
            with self._abrir("/api/tags", timeout=3):
                return True
        except ErroOllama:
            return False

    def listar(self) -> list[str]:
        with self._abrir("/api/tags", timeout=10) as resp:
            return [m["name"] for m in json.load(resp).get("models", [])]

    def instalado(self, tag: str) -> bool:
        instalados = self.listar()
        # "llama3.2:3b" também pode aparecer como "llama3.2:3b" exato; "x" vira "x:latest"
        return tag in instalados or (":" not in tag and f"{tag}:latest" in instalados)

    def _linhas(self, caminho: str, corpo: dict) -> Iterator[dict]:
        with self._abrir(caminho, corpo) as resp:
            for linha in resp:
                if linha.strip():
                    evento = json.loads(linha)
                    if "error" in evento:
                        raise ErroOllama(evento["error"])
                    yield evento

    def baixar(self, tag: str, progresso: Callable[[str, int, int], None] | None = None) -> None:
        for ev in self._linhas("/api/pull", {"model": tag, "stream": True}):
            if progresso:
                progresso(ev.get("status", ""), ev.get("completed", 0), ev.get("total", 0))

    def eventos_download(self, tag: str) -> Iterator[dict]:
        """Eventos brutos do `pull` (status, completed, total)."""
        yield from self._linhas("/api/pull", {"model": tag, "stream": True})

    def gerar(self, tag: str, prompt: str) -> Iterator[str]:
        for ev in self._linhas("/api/generate", {"model": tag, "prompt": prompt, "stream": True}):
            if ev.get("response"):
                yield ev["response"]
