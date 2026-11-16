import type { Diagnostico } from "../types";

export function Hardware({ d }: { d: Diagnostico | null }) {
  if (!d) return <div className="pagina"><p className="sub">Detectando hardware…</p></div>;
  const h = d.hardware;
  const pctLivre = Math.round((h.ram_disponivel_gb / h.ram_total_gb) * 100);
  const rec = d.recomendacao;

  return (
    <div className="pagina">
      <h1>Hardware</h1>
      <p className="sub">
        O perfil define quais modelos locais cabem aqui. A memória útil é o que um modelo pode
        ocupar sem sufocar a máquina.
      </p>

      <div className="grade">
        <div className="cartao">
          <h3>Perfil</h3>
          <span className={`selo grande selo-${d.perfil}`}>{d.perfil}</span>
          <p>{h.memoria_modelo_gb.toFixed(1)} GB úteis para modelos</p>
        </div>
        <div className="cartao">
          <h3>Memória RAM</h3>
          <p>
            <b>{h.ram_total_gb.toFixed(1)} GB</b> no total
          </p>
          <div className="barra" title={`${pctLivre}% livre`}>
            <div style={{ width: `${100 - pctLivre}%` }} />
          </div>
          <p className="sub">{h.ram_disponivel_gb.toFixed(1)} GB livres agora</p>
        </div>
        <div className="cartao">
          <h3>Processador</h3>
          <p>
            <b>{h.nucleos}</b> núcleos físicos
          </p>
        </div>
        <div className="cartao">
          <h3>GPU</h3>
          {h.gpus.length === 0 && <p>Nenhuma detectada</p>}
          {h.gpus.map((g) => (
            <p key={g.nome}>
              {g.nome}
              <br />
              <span className="sub">
                {g.dedicada ? "dedicada" : "integrada ou virtual"}
                {g.vram_gb ? ` · ${g.vram_gb.toFixed(1)} GB` : ""}
              </span>
            </p>
          ))}
        </div>
      </div>

      {d.avisos.length > 0 && (
        <div className="aviso">
          {d.avisos.map((a) => (
            <p key={a}>{a}</p>
          ))}
        </div>
      )}

      <h2>Recomendação</h2>
      <div className="cartao largo">
        {rec.principal ? (
          <p>
            Principal: <b>{rec.principal.nome}</b>{" "}
            <span className="etiqueta suave">{rec.principal.id}</span>
          </p>
        ) : (
          <p>Nenhuma opção disponível.</p>
        )}
        {rec.alternativas_locais.length > 0 && (
          <p className="sub">
            Outros locais: {rec.alternativas_locais.map((m) => m.nome).join(", ")}
          </p>
        )}
      </div>
    </div>
  );
}
