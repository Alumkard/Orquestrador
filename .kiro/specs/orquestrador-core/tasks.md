# Tarefas

- [x] 1. Estrutura do projeto, `pyproject.toml` e steering.
- [x] 2. Modelos de dados de hardware (`modelos.py`).
- [x] 3. Detector de hardware com `psutil` e `gpu-detector`, tolerante a falhas (`detector.py`).
- [x] 4. Classificador de perfil por memória útil (`perfil.py`).
- [x] 5. Catálogo com modelos locais (Ollama) e online (gratuitos e pagos) (`catalogo.json`, `gerenciador.py`).
- [x] 6. Motor de recomendação (`motor.py`).
- [x] 7. Testes de perfil e recomendação.
- [x] 8. CLI `allun diagnostico` que imprime hardware, perfil e recomendação.
- [x] 9. Integração com Ollama (`integracao/ollama.py`; comandos `modelos`, `baixar` com confirmação e `perguntar`).
- [x] 10. Grafo LangGraph: Comandante -> Especialista (`orquestrador/grafo.py`).
- [x] 11. Múltiplos agentes (`agentes.py`) e fallback local -> online gratuito -> pago (`llm.py`).
- [x] 12. API FastAPI e painel web em Vite (llun servir, pasta web/).
- [x] 13. Histórico no servidor (SQLite), resposta em streaming com cancelamento, memória de conversa e download de modelos com confirmação no painel.
- [x] 14. Ajustes de desempenho dos agentes (ver docs/desempenho.md).
- [x] 15. Orçamento de contexto por modelo e memória em camadas (resumo, fatos e janela curta).
- [x] 16. Agente grava arquivos na pasta do projeto (definida pelo usuário ou criada em ~/Allun/projetos), com validação de caminho e cópia da versão anterior.
- [x] 17. Agente lê os arquivos do projeto (citados no pedido, gravados por último e mais recentes) dentro do orçamento de contexto.

