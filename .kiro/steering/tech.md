# Stack Tecnológica

## Linguagem e runtime
- Python 3.11+ (testado em 3.13).
- Gerenciador de pacotes: `uv`. Configuração em `pyproject.toml`.

## Bibliotecas aprovadas
- Detecção de hardware: `psutil` (CPU/RAM) e `gpu-detector` 1.0.0 (GPU, multi-fabricante).
- Orquestração (fase posterior): `langgraph`, `langchain`.
- Chamadas a LLMs (fase posterior): `litellm`, com cliente `ollama` para modelos locais.
- API e painel: `fastapi`, `uvicorn` e, em `web/`, Vite + React + TypeScript.
- Testes: `pytest`. Formatação e lint: `ruff`.

## Regras técnicas
- Todo acesso ao hardware passa por um `PerfilHardware` (dataclass), nunca por dicionários soltos.
- A detecção de GPU deve ser tolerante a falhas: se `gpu-detector` falhar ou não retornar VRAM, o sistema segue como "sem GPU útil" e registra um aviso.
- O `gpu-detector` é mantido por uma única pessoa e avisa que a precisão varia. No Windows, o VRAM vem de `AdapterRAM` (32 bits) e pode ser limitado a 4 GB. Para NVIDIA, preferir `nvidia-smi` quando disponível.
- Lógica de perfil e recomendação são funções puras, testáveis sem hardware real.
- Código assíncrono (`async/await`) apenas na camada de orquestração e I/O. Detecção e recomendação são síncronas.
- O catálogo é dado (JSON), não código. Alterar modelos não deve exigir mudar Python.
- Provedores online declaram em catalogo.json as variáveis de ambiente que exigem (chaves_env). Sem todas elas, o modelo não entra no fallback.
- Endpoints anônimos (sem chave, como LLM7 e OVHcloud) só entram no fallback com --permitir-anonimos, porque os prompts vão a terceiros sem cadastro. Modelos pagos só com --permitir-pagos.
- IDs de modelos gratuitos mudam com frequência. Revise o catálogo online periodicamente.
- Chaves de API ficam no arquivo .env da raiz (modelo em .env.example), lido por configuracao.py. O .env está no .gitignore. O painel nunca grava nem exibe chaves.
- O agente nunca acessa o disco diretamente. O Allun extrai os arquivos dos blocos de código e grava só dentro da pasta da tarefa (projetos.py): sem caminhos absolutos, sem .., sem .allun/.git, até 20 arquivos de 1 MB por resposta, com cópia da versão anterior em .allun/versoes. Pastas do sistema, AppData e a pasta do próprio Allun são recusadas.
- Leitura de arquivos para o contexto: só texto, até 200 KB, dentro da pasta do projeto; nunca .env*, *.pem, *.key nem nomes com secret; ignora .allun, .git, 
ode_modules, dist, .venv. O conteúdo vai marcado como dado, não como instrução.

