import { useMemo, useState } from "react";
import { Icon, Logo } from "../icons";
import type { Diagnostico, TarefaResumo, Tela } from "../types";

interface Props {
  tela: Tela;
  tarefas: TarefaResumo[];
  ativaId: string | null;
  diagnostico: Diagnostico | null;
  ollama: boolean | null;
  versao: string;
  aoNavegar: (t: Tela) => void;
  aoNovaTarefa: () => void;
  aoAbrirTarefa: (id: string) => void;
  aoRemoverTarefa: (id: string) => void;
}

const NAV: { tela: Tela; rotulo: string; icone: "team" | "chip" | "plug" }[] = [
  { tela: "equipe", rotulo: "Equipe de IA", icone: "team" },
  { tela: "hardware", rotulo: "Hardware", icone: "chip" },
  { tela: "modelos", rotulo: "Modelos e provedores", icone: "plug" },
];

function grupoDe(criadaSegundos: number): string {
  const criada = criadaSegundos * 1000;
  const dia = 86_400_000;
  const inicioHoje = new Date().setHours(0, 0, 0, 0);
  if (criada >= inicioHoje) return "Hoje";
  if (criada >= inicioHoje - dia) return "Ontem";
  return "Anteriores";
}

export function Sidebar(p: Props) {
  const [busca, setBusca] = useState("");

  const filtradas = useMemo(
    () => p.tarefas.filter((t) => t.titulo.toLowerCase().includes(busca.toLowerCase())),
    [p.tarefas, busca],
  );
  const grupos = useMemo(() => {
    const mapa = new Map<string, TarefaResumo[]>();
    for (const t of filtradas) {
      const g = grupoDe(t.criada);
      mapa.set(g, [...(mapa.get(g) ?? []), t]);
    }
    return [...mapa.entries()];
  }, [filtradas]);

  return (
    <aside className="sidebar">
      <div className="marca">
        <Logo />
        <span className="marca-nome">Allun</span>
        <span className="versao">v{p.versao}</span>
      </div>

      <label className="busca">
        <Icon nome="search" />
        <input
          placeholder="Pesquisar"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          aria-label="Pesquisar tarefas"
        />
      </label>

      <nav className="nav">
        <button
          className={"nav-item" + (p.tela === "chat" && p.ativaId === null ? " ativo" : "")}
          onClick={p.aoNovaTarefa}
        >
          <Icon nome="plus" /> Nova tarefa
        </button>
        {NAV.map((n) => (
          <button
            key={n.tela}
            className={"nav-item" + (p.tela === n.tela ? " ativo" : "")}
            onClick={() => p.aoNavegar(n.tela)}
          >
            <Icon nome={n.icone} /> {n.rotulo}
          </button>
        ))}
      </nav>

      <div className="lista-tarefas">
        {grupos.length === 0 && <p className="vazio-lateral">Nenhuma tarefa ainda.</p>}
        {grupos.map(([grupo, itens]) => (
          <section key={grupo}>
            <h4>{grupo}</h4>
            {itens.map((t) => (
              <div
                key={t.id}
                className={"tarefa" + (t.id === p.ativaId && p.tela === "chat" ? " ativo" : "")}
              >
                <button className="tarefa-titulo" onClick={() => p.aoAbrirTarefa(t.id)}>
                  {t.titulo}
                </button>
                <button
                  className="tarefa-remover"
                  title="Remover tarefa"
                  aria-label={`Remover ${t.titulo}`}
                  onClick={() => p.aoRemoverTarefa(t.id)}
                >
                  <Icon nome="trash" tamanho={14} />
                </button>
              </div>
            ))}
          </section>
        ))}
      </div>

      <div className="cartao-maquina" onClick={() => p.aoNavegar("hardware")} role="button">
        <div className="cartao-linha">
          <span className="cartao-titulo">Esta máquina</span>
          {p.diagnostico && <span className={`selo selo-${p.diagnostico.perfil}`}>{p.diagnostico.perfil}</span>}
        </div>
        <span className="cartao-sub">
          {p.diagnostico
            ? `${p.diagnostico.hardware.ram_total_gb.toFixed(0)} GB RAM · ${p.diagnostico.hardware.nucleos} núcleos`
            : "Detectando hardware…"}
        </span>
        <span className="cartao-sub">
          <i className={"ponto " + (p.ollama ? "ok" : p.ollama === false ? "erro" : "")} />
          {p.ollama === null ? "Verificando Ollama…" : p.ollama ? "Ollama ativo" : "Ollama parado"}
        </span>
      </div>
    </aside>
  );
}


