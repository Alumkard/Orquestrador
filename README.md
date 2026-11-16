# Allun

Orquestrador de agentes de IA que se adapta ao hardware. Detecta CPU, RAM e GPU, recomenda o melhor modelo (local via Ollama ou online, gratuito ou pago) e encaminha cada tarefa ao especialista certo (programador, analista, redator ou geral).

## Requisitos

- Python 3.11+
- Node.js 20+
- [Ollama](https://ollama.com) para modelos locais (opcional se usar só modelos online)

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[web,orquestrador,dev]"
npm install
npm --prefix web install
```

Chaves de API (opcional): copie `.env.example` para `.env` ou insira pelo painel, em **Modelos e provedores**. O `.env` não vai para o Git.

## Uso

```powershell
npm run dev      # API (porta 8000) + painel (http://localhost:5173)
npm start        # compila o painel e serve tudo em http://127.0.0.1:8000
```

Linha de comando:

```powershell
.\.venv\Scripts\python -m allun diagnostico   # hardware, perfil e recomendação
.\.venv\Scripts\python -m allun baixar        # baixa o modelo local recomendado
```

## Testes

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\ruff check src tests
```

## Estrutura

- `src/allun/hardware/`: detecção e perfil da máquina
- `src/allun/catalogo/`: catálogo de modelos (`catalogo.json`)
- `src/allun/recomendador/`: escolha do modelo
- `src/allun/orquestrador/`: Comandante, especialistas, contexto e memória
- `src/allun/projetos.py`: pasta do projeto e arquivos gravados pelo agente
- `src/allun/api.py`: API FastAPI
- `web/`: painel em Vite + React
- `docs/desempenho.md`: técnicas de desempenho aplicadas e testadas
