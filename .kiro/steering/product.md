# Produto: Allun

## Objetivo
Allun é um orquestrador de agentes de IA que se adapta ao hardware do usuário. Ele detecta a máquina, recomenda o melhor LLM (local via Ollama ou online, gratuito ou pago) e então coordena agentes (Comandante e Especialistas) usando o modelo escolhido.

## Personas
- **Desenvolvedor com máquina antiga**: quer usar agentes, mas tem hardware limitado. Precisa de modelos leves.
- **Desenvolvedor com máquina potente**: quer extrair o máximo do hardware local e usar APIs pagas só em tarefas complexas.
- **Entusiasta de privacidade**: prioriza modelos locais (Ollama) para que os dados fiquem 100% na máquina.

## Princípios
- Local primeiro, gratuito primeiro. APIs pagas só como alternativa explícita.
- Nunca executar ações destrutivas ou instalar/baixar modelos sem confirmação do usuário.
- Toda mensagem ao usuário, documentação e comentários ficam em português do Brasil.
