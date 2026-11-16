import type { Agente } from "../types";

export function Equipe({ agentes }: { agentes: Agente[] }) {
  return (
    <div className="pagina">
      <h1>Equipe de IA</h1>
      <p className="sub">
        O Comandante lê a tarefa e entrega ao especialista mais adequado. Você também pode escolher
        um especialista direto no campo “Para” da caixa de mensagem.
      </p>
      <div className="grade">
        <div className="cartao comandante">
          <h3>Comandante</h3>
          <p>Escolhe o especialista de cada tarefa. Se estiver em dúvida, usa o agente geral.</p>
        </div>
        {agentes.map((a) => (
          <div key={a.nome} className="cartao">
            <h3>{a.nome}</h3>
            <p>{a.descricao}</p>
            <details>
              <summary>Instrução do sistema</summary>
              <pre>{a.prompt_sistema}</pre>
            </details>
          </div>
        ))}
      </div>
    </div>
  );
}
