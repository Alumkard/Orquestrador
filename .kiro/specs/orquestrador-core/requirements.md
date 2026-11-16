# Requisitos: Núcleo do Allun

## História 1: Detecção de hardware
**Como** usuário com hardware limitado, **quero** que o Allun detecte minha CPU, RAM e GPU, **para** receber modelos que minha máquina consiga rodar.

### Critérios de aceitação
1. Ao iniciar, o sistema DEVE coletar RAM total, RAM disponível, núcleos físicos de CPU e a lista de GPUs (nome, fabricante, VRAM quando conhecida).
2. SE a detecção de GPU falhar, ENTÃO o sistema DEVE continuar sem GPU e registrar um aviso.
3. O sistema DEVE calcular a **memória útil para modelos** (`memoria_modelo_gb`):
   - Apple Silicon (memória unificada): 60% da RAM total.
   - Demais casos: o maior valor entre 90% da maior VRAM de GPU dedicada e 50% da RAM total (o Ollama divide camadas entre GPU e CPU).
   - GPU integrada (Iris, UHD, Radeon Graphics, Vega) ou com VRAM menor que 2 GB nunca conta como dedicada.
4. O sistema DEVE classificar o perfil pela `memoria_modelo_gb`: `leve` (< 4), `medio` (4 a < 10), `potente` (>= 10).
5. SE a máquina tiver menos de 4 núcleos físicos, ENTÃO o perfil DEVE cair um nível (mínimo `leve`).
6. SE a RAM total for menor que 8 GB e não houver GPU dedicada, ENTÃO o perfil DEVE ser `leve`.

## História 2: Recomendação de LLM
**Como** usuário, **quero** uma recomendação de LLM conforme meu hardware e minha preferência (local, online ou qualquer), **para** não pesquisar manualmente.

### Critérios de aceitação
1. O sistema DEVE ler o catálogo de LLMs (`catalogo.json`).
2. O sistema DEVE descartar modelos locais cujo `memoria_min_gb` exceda a `memoria_modelo_gb`.
3. O sistema DEVE ordenar modelos locais pelo maior que cabe (qualidade), com margem de pelo menos 10%.
4. O sistema DEVE priorizar locais para qualquer perfil e listar online gratuitos e depois pagos como alternativas.
5. SE nenhum modelo local couber, ENTÃO a recomendação principal DEVE ser um online gratuito, com aviso explicando o motivo.
6. A preferência `somente_local` DEVE excluir modelos online. A preferência `somente_online` DEVE excluir locais.

## Fora do escopo desta spec
Download de modelos no Ollama e o grafo LangGraph (specs futuras).

