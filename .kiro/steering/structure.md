# Estrutura do Projeto

## Módulos
- `src/allun/hardware/`: `modelos.py` (dataclasses), `detector.py` (coleta), `perfil.py` (classificação).
- `src/allun/catalogo/`: `catalogo.json` e `gerenciador.py`.
- `src/allun/recomendador/`: `motor.py`.
- `src/allun/integracao/`: clientes de serviços externos (`ollama.py`).
- `src/allun/armazenamento.py`: histórico de tarefas e mensagens em SQLite (`%LOCALAPPDATA%\Allun\allun.db`, ou `ALLUN_DB`).
- `src/allun/projetos.py`: pasta de projeto por tarefa, extração dos arquivos da resposta e gravação segura.
- `src/allun/api.py`: API FastAPI (`/api/*`) que também serve `web/dist`.
- `web/`: painel em Vite + React + TypeScript (`npm run dev` para desenvolvimento, `npm run build` para gerar `dist`).
- `src/allun/cli.py`: interface de linha de comando.
- `src/allun/orquestrador/contexto.py`: planejador de contexto (orçamento de tokens e compressão em camadas). `memoria.py`: resumo e fatos por tarefa.
- `src/allun/orquestrador/`: `agentes/`, `grafo.py`, `roteador.py` (fase posterior).
- `tests/`: espelha a estrutura de `src/allun/`.

## Convenções
- Nomes de arquivos e funções em `snake_case`; classes em `PascalCase`.
- Nomes de domínio em português (`perfil`, `catalogo`, `recomendador`).
- Cada módulo tem `__init__.py` expondo sua API pública.
- O pacote Python se chama `allun`, com layout `src/`.





