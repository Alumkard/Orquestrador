# Desempenho dos agentes

Notas sobre o que foi aplicado no Allun e por quê. Medições feitas em um notebook de 4 núcleos, sem GPU dedicada, com `qwen2.5:3b`.

## Aplicado

| Técnica | Efeito | Onde |
|---|---|---|
| Resposta em streaming | O primeiro texto aparece em 7 a 17 s, em vez de esperar a resposta inteira (213 s no pedido do HTML). Dá para cancelar e o trecho gerado é salvo. | `llm.py`, `api.py`, `web/` |
| Atalho do Comandante por palavras-chave | Evita uma chamada inteira ao modelo só para escolher o especialista. O modelo só decide em caso de empate ou dúvida. | `roteador.py` |
| Temperatura por agente | 0,2 para código, 0,3 para análise, 0,6 para texto. Menos variação onde a precisão importa. O Comandante usa 0. | `agentes.py` |
| `keep_alive` de 30 min e `num_ctx` de 4096 no Ollama | Não recarrega o modelo a cada pergunta e fixa o tamanho do contexto, que pesa na CPU. | `llm.py` |
| Orçamento de contexto por modelo | Cada modelo tem uma janela (`contexto_tokens` no catálogo; 4096 nos locais, 32768 nos online). O planejador reserva cerca de 35% para a resposta e divide o resto entre prompt, memória (até 30%) e mensagens recentes. Inspirado no SCOPE. | `contexto.py`, `catalogo.json` |
| Compressão em camadas | Mensagens recentes entram inteiras; se não couberem, os blocos de código viram um símbolo ("[bloco de html com 120 linhas omitido]"); se nem assim couberem, saem. Não gasta chamada ao modelo. | `contexto.py` |
| Memória em camadas | A cada 8 mensagens fora do resumo, o modelo resume as antigas e extrai fatos (preferências, nomes, decisões), em segundo plano, guardando tudo no SQLite. As 4 mais recentes nunca são resumidas. Teste real com Qwen 2.5 3B: depois de 5 trocas, respondeu "Seu nome é Luiz e sua loja fica em Goianira" usando só a memória. | `memoria.py`, `armazenamento.py` |
| Modelo de código para o `programador` | Usa o Qwen 2.5 Coder quando instalado e cabe; no pedido do HTML, 186 s caiu para 123 a 138 s e a página veio com `<!DOCTYPE>`, `viewport` e `</html>`. | `catalogo.json`, `llm.py` |
| Limite de espera por provedor | Se um modelo fica 240 s sem o primeiro trecho (ou 90 s entre trechos), a resposta falha ou passa ao próximo provedor, em vez de ficar pendurada. | `llm.py` |
| Regras de formato no prompt | Modelos pequenos ignoram "apenas o código" e "um único arquivo". O prompt repete essas restrições. | `agentes.py` |

## Testado sem efeito

- **Instruções de design no prompt do `programador`** (sem imagens externas, emojis ou SVG, paleta coerente, JavaScript simples). Com o Qwen 2.5 Coder 3B, a página continuou usando `via.placeholder.com` e sem `<script>`. Modelos de 3B seguem pouco instruções detalhadas; o prompt foi mantido porque não piorou o resultado.

## Pesquisado e não aplicado

- **Headroom, paritok, TencentDB-Agent-Memory, agentmemory.** O Headroom comprime sobretudo saídas de ferramentas, logs e JSON, que o Allun ainda não usa; fica como opção quando houver ferramentas. Os outros exigem um segundo modelo ou serviços próprios, pesados para esta máquina.
- **Compressão latente (Coca-Cola) e compartilhamento de cache KV entre agentes.** Exigem acesso ao interior do modelo, que Ollama e APIs não expõem.

- **Autorrevisão em duas chamadas.** Um estudo com modelos locais ([arXiv 2607.26922](https://arxiv.org/html/2607.26922v1)) achou ganho em raciocínio matemático, com 7,4 vezes menos tokens que pipelines multiagente. Para código, a mesma técnica piorou o resultado (de 96,3% para 66,5% no HumanEval). Por isso não aplico revisão automática no `programador`. Se for testada, comece pelo `analista`.
- **Mais regras no prompt de sistema.** Um estudo de 2026 ([arXiv 2602.15228](https://arxiv.org/abs/2602.15228)) mostra que prompts mais restritivos nem sempre melhoram o código, e que exemplos (few-shot) podem piorar modelos maiores. Mantive o prompt curto.
- **Padrões de agentes.** A [recomendação da Anthropic](https://www.anthropic.com/research/building-effective-agents) é usar a solução mais simples e só somar complexidade quando medir ganho. O Allun segue isso: roteamento e um especialista por pergunta.
- **Decodificação especulativa.** Dá ganho de 2 a 4 vezes em servidores dedicados, mas não é uma opção que o Ollama exponha hoje.

## Sugestões para o Ollama (não aplicadas, mexem na sua máquina)

Variáveis de ambiente do servidor Ollama, que exigem reiniciá-lo:

- `OLLAMA_FLASH_ATTENTION=1`: reduz a memória usada pela atenção.
- `OLLAMA_KV_CACHE_TYPE=q8_0`: corta cerca de metade da memória do contexto, com pouca perda de qualidade.

Fontes: [guia de otimização do Ollama](https://tokios.mintlify.app/guides/ollama-optimization) e [ajustes contra o uso silencioso da CPU](https://dev.to/thezerodollardev/your-8gb-gpu-isnt-the-problem-4-ollama-settings-that-stop-the-silent-cpu-fallback-1m5p). Não medi o ganho nesta máquina.


