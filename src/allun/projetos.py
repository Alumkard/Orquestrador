"""Pasta de projeto por tarefa e gravação dos arquivos que o agente escreve.

O agente não acessa o disco: ele escreve cada arquivo num bloco de código com o caminho
(```html index.html). O Allun extrai esses blocos e grava só dentro da pasta da tarefa,
com validação de caminho, limite de tamanho e cópia de segurança antes de sobrescrever.
"""

from __future__ import annotations

import os
import re
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

RAIZ_APP = Path(__file__).resolve().parents[2]
MAX_ARQUIVOS = 20
MAX_BYTES = 1_000_000
MAX_PROFUNDIDADE = 6
PASTA_INTERNA = ".allun"  # cópias de segurança; o agente não escreve aqui

INSTRUCOES_ARQUIVOS = (
    "Modo arquivos ligado: o Allun grava no projeto do usuário os arquivos que você escrever. "
    "Escreva cada arquivo inteiro num bloco de código com o caminho relativo logo depois da "
    "linguagem, assim: ```html index.html  (ou ```css css/estilo.css). Use caminhos simples, "
    "sem '..' e sem caminhos absolutos. Para alterar um arquivo, escreva-o de novo completo."
)

_NOMES_RESERVADOS = {"con", "prn", "aux", "nul"} | {
    f"{p}{i}" for p in ("com", "lpt") for i in range(1, 10)
}
_CARACTERES_PROIBIDOS = set('<>:"|?*') | {chr(i) for i in range(32)}
_LINGUAGENS_SEM_ARQUIVO = {
    "bash",
    "sh",
    "shell",
    "powershell",
    "ps",
    "ps1",
    "cmd",
    "console",
    "terminal",
    "text",
    "txt",
    "plaintext",
    "output",
    "log",
}
_PADRAO_POR_LINGUAGEM = {
    "html": "index.html",
    "css": "style.css",
    "javascript": "script.js",
    "js": "script.js",
    "python": "main.py",
    "py": "main.py",
    "typescript": "index.ts",
    "ts": "index.ts",
    "json": "dados.json",
    "sql": "consulta.sql",
}
_BLOCO = re.compile(r"^```[ \t]*([^\n`]*)\n(.*?)^```[ \t]*$", re.DOTALL | re.MULTILINE)
_PARECE_ARQUIVO = re.compile(r"^[\w.\-/\\ ]*\.[A-Za-z0-9]{1,10}$")
_ROTULO_ANTES = re.compile(
    r"(?:arquivo|file|nome do arquivo|salve como)\s*[:\-]?\s*[`*]*([\w.\-/\\]+\.[A-Za-z0-9]{1,10})[`*]*",
    re.IGNORECASE,
)
_TITULO_ANTES = re.compile(
    r"^\s*(?:#+|\*\*)\s*`?([\w.\-/\\]+\.[A-Za-z0-9]{1,10})`?\s*(?:\*\*)?\s*:?\s*$"
)


@dataclass
class ArquivoExtraido:
    caminho: str
    conteudo: str


class CaminhoInvalido(ValueError):
    pass


# ---------- pasta do projeto ----------


def base_projetos() -> Path:
    return Path(os.environ.get("ALLUN_PROJETOS") or Path.home() / "Allun" / "projetos")


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFD", texto.lower())
    sem_acento = "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", sem_acento).strip("-")[:40] or "projeto"


def pasta_automatica(tarefa: dict) -> Path:
    return base_projetos() / f"{_slug(tarefa['titulo'])}-{tarefa['id'][:6]}"


def pasta_da_tarefa(tarefa: dict) -> Path:
    return Path(tarefa["pasta"]) if tarefa.get("pasta") else pasta_automatica(tarefa)


def _proibidas() -> list[Path]:
    env = os.environ
    candidatas = [
        env.get("WINDIR") or env.get("SystemRoot"),
        env.get("ProgramFiles"),
        env.get("ProgramFiles(x86)"),
        env.get("ProgramData"),
        env.get("APPDATA"),
        env.get("LOCALAPPDATA"),
        "/etc",
        "/usr",
        "/bin",
        "/System",
    ]
    return [Path(c).resolve() for c in candidatas if c] + [RAIZ_APP]


def validar_pasta(texto: str) -> Path:
    """Valida uma pasta escolhida pelo usuário. Não cria nada."""
    texto = texto.strip().strip('"')
    if not texto:
        raise CaminhoInvalido("Informe a pasta.")
    pasta = Path(texto).expanduser()
    if not pasta.is_absolute():
        raise CaminhoInvalido("Use o caminho completo, por exemplo C:\\Projetos\\loja.")
    pasta = pasta.resolve()
    if pasta.parent == pasta:
        raise CaminhoInvalido("A raiz do disco não pode ser a pasta do projeto.")
    if pasta == Path.home().resolve():
        raise CaminhoInvalido("Escolha uma subpasta, não a pasta do usuário inteira.")
    for proibida in _proibidas():
        if pasta == proibida or proibida in pasta.parents:
            raise CaminhoInvalido(f"Pasta protegida: {proibida}. Escolha outra.")
    if pasta.exists() and not pasta.is_dir():
        raise CaminhoInvalido("O caminho existe e não é uma pasta.")
    return pasta


# ---------- extração dos arquivos da resposta ----------


def _caminho_do_info(info: str) -> str | None:
    """Lê o caminho do cabeçalho do bloco: 'html index.html', 'html:index.html', 'title=a.py'."""
    for parte in re.split(r"[\s:]+", info.strip()):
        parte = parte.strip("'\"`")
        parte = re.sub(
            r"^(?:title|file|filename|arquivo|path)=", "", parte, flags=re.IGNORECASE
        ).strip("'\"")
        if parte and _PARECE_ARQUIVO.match(parte):
            return parte
    return None


def _caminho_antes(texto_antes: str) -> str | None:
    linhas = [x for x in texto_antes.splitlines() if x.strip()][-2:]
    for linha in reversed(linhas):
        if m := _ROTULO_ANTES.search(linha) or _TITULO_ANTES.match(linha):
            return m.group(1)
    return None


def extrair_arquivos(resposta: str) -> list[ArquivoExtraido]:
    blocos = list(_BLOCO.finditer(resposta))
    if not blocos:
        inicio = resposta.lstrip()[:20].lower()
        if inicio.startswith(("<!doctype html", "<html")):  # HTML puro, sem bloco
            return [ArquivoExtraido("index.html", resposta.strip() + "\n")]
        return []

    nomeados: dict[str, str] = {}
    sem_nome: list[tuple[str, str]] = []
    fim_anterior = 0
    for b in blocos:
        info, conteudo = b.group(1), b.group(2)
        linguagem = (info.strip().split() or [""])[0].split(":")[0].lower()
        caminho = _caminho_do_info(info) or _caminho_antes(resposta[fim_anterior : b.start()])
        fim_anterior = b.end()
        if caminho:
            nomeados[caminho] = conteudo  # o último bloco com o mesmo nome vence
        elif linguagem not in _LINGUAGENS_SEM_ARQUIVO:
            sem_nome.append((linguagem, conteudo))

    if nomeados:
        return [ArquivoExtraido(c, t) for c, t in nomeados.items()]
    # Sem nomes: só adivinha quando não há ambiguidade (uma linguagem conhecida por bloco).
    linguagens = [lang for lang, _ in sem_nome]
    if (
        sem_nome
        and len(set(linguagens)) == len(linguagens)
        and all(lang in _PADRAO_POR_LINGUAGEM for lang in linguagens)
    ):
        return [ArquivoExtraido(_PADRAO_POR_LINGUAGEM[lang], t) for lang, t in sem_nome]
    return []


# ---------- gravação ----------


def caminho_seguro(pasta: Path, relativo: str) -> Path:
    rel = relativo.strip().replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    if (
        not rel
        or rel.startswith("/")
        or PureWindowsPath(relativo).drive
        or PurePosixPath(rel).is_absolute()
    ):
        raise CaminhoInvalido("caminho absoluto não é permitido")
    partes = PurePosixPath(rel).parts
    if len(partes) > MAX_PROFUNDIDADE:
        raise CaminhoInvalido("pastas demais no caminho")
    for parte in partes:
        if parte in ("", ".", "..") or parte.startswith("~"):
            raise CaminhoInvalido("o caminho não pode subir de pasta")
        if parte.lower() in (PASTA_INTERNA, ".git"):
            raise CaminhoInvalido(f"a pasta {parte} é reservada")
        if set(parte) & _CARACTERES_PROIBIDOS or parte.endswith((" ", ".")) or len(parte) > 100:
            raise CaminhoInvalido("nome com caracteres inválidos")
        if parte.split(".")[0].lower() in _NOMES_RESERVADOS:
            raise CaminhoInvalido("nome reservado do Windows")
    base = pasta.resolve()
    destino = (base / Path(*partes)).resolve()
    if base not in destino.parents:  # defesa extra contra links e truques de caminho
        raise CaminhoInvalido("fora da pasta do projeto")
    return destino


def _gravar_atomico(destino: Path, dados: bytes) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=destino.parent, prefix=".allun-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(dados)
        os.replace(tmp, destino)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def gravar_arquivos(pasta: Path, arquivos: list[ArquivoExtraido]) -> dict:
    """Grava os arquivos e devolve {"gravados": [...], "rejeitados": [...]}.

    Antes de sobrescrever um arquivo diferente, guarda a versão anterior em
    `.allun/versoes/<data-hora>/`.
    """
    gravados, rejeitados = [], []
    carimbo = time.strftime("%Y%m%d-%H%M%S")
    for i, arq in enumerate(arquivos):
        if i >= MAX_ARQUIVOS:
            rejeitados.append(
                {"caminho": arq.caminho, "motivo": f"limite de {MAX_ARQUIVOS} arquivos"}
            )
            continue
        dados = arq.conteudo.encode("utf-8")
        if len(dados) > MAX_BYTES:
            rejeitados.append({"caminho": arq.caminho, "motivo": "arquivo maior que 1 MB"})
            continue
        try:
            destino = caminho_seguro(pasta, arq.caminho)
        except CaminhoInvalido as erro:
            rejeitados.append({"caminho": arq.caminho, "motivo": str(erro)})
            continue
        relativo = destino.relative_to(pasta.resolve()).as_posix()
        situacao = "criado"
        if destino.exists():
            if destino.is_dir():
                rejeitados.append(
                    {"caminho": relativo, "motivo": "já existe uma pasta com esse nome"}
                )
                continue
            antigo = destino.read_bytes()
            if antigo == dados:
                gravados.append({"caminho": relativo, "bytes": len(dados), "situacao": "igual"})
                continue
            copia = pasta.resolve() / PASTA_INTERNA / "versoes" / carimbo / relativo
            _gravar_atomico(copia, antigo)
            situacao = "alterado"
        _gravar_atomico(destino, dados)
        gravados.append({"caminho": relativo, "bytes": len(dados), "situacao": situacao})
    return {"gravados": gravados, "rejeitados": rejeitados}


def listar_arquivos(pasta: Path, limite: int = 30) -> list[str]:
    """Arquivos do projeto (sem a pasta interna), para o agente saber o que já existe."""
    if not pasta.is_dir():
        return []
    saida = []
    for p in sorted(pasta.rglob("*")):
        rel = p.relative_to(pasta)
        if p.is_file() and rel.parts[0] not in (PASTA_INTERNA, ".git", "node_modules"):
            saida.append(rel.as_posix())
            if len(saida) >= limite:
                break
    return saida


# ---------- leitura para o contexto do agente ----------

EXTENSOES_TEXTO = {
    "html",
    "htm",
    "css",
    "scss",
    "js",
    "mjs",
    "cjs",
    "ts",
    "tsx",
    "jsx",
    "vue",
    "svelte",
    "json",
    "py",
    "md",
    "txt",
    "sql",
    "yml",
    "yaml",
    "toml",
    "xml",
    "svg",
    "csv",
    "ini",
    "cfg",
    "sh",
    "ps1",
    "bat",
    "java",
    "c",
    "h",
    "cpp",
    "cs",
    "go",
    "rs",
    "php",
    "rb",
}
MAX_BYTES_LEITURA = 200_000
_PASTAS_IGNORADAS = {PASTA_INTERNA, ".git", "node_modules", "__pycache__", ".venv", "venv", "dist"}


def _legivel(rel: PurePosixPath) -> bool:
    nome = rel.name.lower()
    if nome.startswith(".env") or "secret" in nome or nome.endswith((".key", ".pem")):
        return False  # nunca manda segredos para o modelo
    return "." in nome and nome.rsplit(".", 1)[1] in EXTENSOES_TEXTO


def arquivos_para_contexto(
    pasta: Path, mencionados: str = "", recentes: list[str] | None = None, limite: int = 30
) -> list[tuple[str, str]]:
    """Lê os arquivos de texto do projeto em ordem de prioridade.

    1. Citados no pedido pelo nome ("mude o style.css").
    2. Gravados na última resposta.
    3. Os demais, do modificado mais recentemente para o mais antigo.
    Só lê dentro da pasta (links que apontam para fora são ignorados).
    """
    if not pasta.is_dir():
        return []
    base = pasta.resolve()
    achados: list[tuple[float, str, Path]] = []
    for p in base.rglob("*"):
        try:
            rel = p.relative_to(base)
            if set(rel.parts[:-1]) & _PASTAS_IGNORADAS or rel.parts[0] in _PASTAS_IGNORADAS:
                continue
            real = p.resolve()
            if (
                not p.is_file()
                or base not in real.parents
                or not _legivel(PurePosixPath(rel.as_posix()))
            ):
                continue
            tamanho = real.stat().st_size
            if tamanho > MAX_BYTES_LEITURA:
                continue
            achados.append((real.stat().st_mtime, rel.as_posix(), real))
        except OSError:
            continue
        if len(achados) >= 200:
            break

    texto = mencionados.lower()
    recentes_set = set(recentes or [])

    def prioridade(item: tuple[float, str, Path]) -> tuple[int, float]:
        mtime, rel, _ = item
        nome = rel.rsplit("/", 1)[-1].lower()
        if rel.lower() in texto or re.search(rf"(?<![\w.]){re.escape(nome)}(?![\w])", texto):
            return (0, -mtime)
        if rel in recentes_set:
            return (1, -mtime)
        return (2, -mtime)

    saida = []
    for _, rel, real in sorted(achados, key=prioridade)[:limite]:
        try:
            saida.append((rel, real.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue  # binário ou outra codificação: fica de fora
    return saida
