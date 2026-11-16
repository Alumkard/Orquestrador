import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { Chat, type Transmissao } from "./components/Chat";
import { Composer } from "./components/Composer";
import { Sidebar } from "./components/Sidebar";
import { Equipe } from "./pages/Equipe";
import { Hardware } from "./pages/Hardware";
import { Modelos } from "./pages/Modelos";
import type {
  Agente,
  Diagnostico,
  ModeloStatus,
  Opcoes,
  ArquivosLidos,
  ResultadoArquivos,
  Tarefa,
  TarefaResumo,
  Tela,
} from "./types";

const novoId = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
const titulo = (t: string) => (t.length > 40 ? t.slice(0, 40) + "…" : t);

export default function App() {
  const [tela, setTela] = useState<Tela>("chat");
  const [tarefas, setTarefas] = useState<TarefaResumo[]>([]);
  const [ativa, setAtiva] = useState<Tarefa | null>(null);
  const [transmissao, setTransmissao] = useState<(Transmissao & { tarefaId: string }) | null>(null);
  const cancelar = useRef<AbortController | null>(null);
  const buffer = useRef({ texto: "", agendado: false });

  const [versao, setVersao] = useState("0.1.0");
  const [ollama, setOllama] = useState<boolean | null>(null);
  const [apiOff, setApiOff] = useState(false);
  const [diagnostico, setDiagnostico] = useState<Diagnostico | null>(null);
  const [agentes, setAgentes] = useState<Agente[]>([]);
  const [modelos, setModelos] = useState<ModeloStatus[]>([]);
  const [opcoes, setOpcoes] = useState<Opcoes>({
    agente: null,
    modelo: null,
    permitir_pagos: false,
    permitir_anonimos: false,
    salvar_arquivos: true,
  });
  const [pastaNova, setPastaNova] = useState("");

  const recarregarModelos = useCallback(() => {
    api
      .modelos()
      .then((r) => {
        setModelos(r.modelos);
        setOllama(r.ollama_ativo);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    api
      .saude()
      .then((s) => {
        setVersao(s.versao);
        setOllama(s.ollama);
        setApiOff(false);
      })
      .catch(() => setApiOff(true));
    api.tarefas.listar().then(setTarefas).catch(() => undefined);
    api.agentes().then(setAgentes).catch(() => undefined);
    api.diagnostico().then(setDiagnostico).catch(() => undefined);
    recarregarModelos();
  }, [recarregarModelos]);

  const abrirTarefa = useCallback(async (id: string) => {
    setTela("chat");
    try {
      setAtiva(await api.tarefas.obter(id));
    } catch {
      setAtiva(null);
    }
  }, []);

  const removerTarefa = useCallback(
    async (id: string) => {
      await api.tarefas.remover(id).catch(() => undefined);
      setTarefas((ts) => ts.filter((t) => t.id !== id));
      if (ativa?.id === id) setAtiva(null);
    },
    [ativa],
  );

  const enviar = useCallback(
    async (texto: string) => {
      if (cancelar.current) return; // uma resposta por vez
      // A tela de erro não é uma tarefa real: a próxima mensagem tenta criar uma tarefa de novo.
      let tarefa = ativa && ativa.id !== "erro" ? ativa : null;
      if (!tarefa) {
        try {
          const nova = await api.tarefas.criar(titulo(texto), pastaNova.trim() || undefined);
          setPastaNova("");
          tarefa = { ...nova, mensagens: [] };
          setTarefas((ts) => [nova, ...ts]);
        } catch (e) {
          setAtiva({
            id: "erro",
            titulo: "Erro",
            criada: Date.now() / 1000,
            pasta: null,
            pasta_efetiva: "",
            pasta_automatica: true,
            mensagens: [{ id: novoId(), papel: "allun", texto: String((e as Error).message), erro: true }],
          });
          return;
        }
      }
      const tarefaId = tarefa.id;
      setTela("chat");
      setAtiva({ ...tarefa, mensagens: [...tarefa.mensagens, { id: novoId(), papel: "usuario", texto }] });

      const controle = new AbortController();
      cancelar.current = controle;
      buffer.current = { texto: "", agendado: false };
      const inicio = Date.now();
      setTransmissao({ tarefaId, agente: null, texto: "", inicio });

      let acumulado = "";
      let agente: string | undefined;
      let arquivos: ResultadoArquivos | undefined;
      let lidos: ArquivosLidos | undefined;
      const descarregar = () => {
        buffer.current.agendado = false;
        setTransmissao((t) => (t ? { ...t, texto: acumulado } : t));
      };

      try {
        await api.enviarMensagem(tarefaId, texto, opcoes, controle.signal, (ev) => {
          if (ev.tipo === "agente") {
            agente = ev.agente;
            setTransmissao((t) => (t ? { ...t, agente: ev.agente } : t));
          } else if (ev.tipo === "trecho") {
            acumulado += ev.texto;
            if (!buffer.current.agendado) {
              buffer.current.agendado = true;
              setTimeout(descarregar, 80); // agrupa trechos para não redesenhar a cada token
            }
          } else if (ev.tipo === "contexto") {
            const { tipo: _t, ...resto } = ev;
            lidos = resto;
            setTransmissao((t) => (t ? { ...t, lidos: resto } : t));
          } else if (ev.tipo === "arquivos") {
            const { tipo: _tipo, ...resto } = ev;
            arquivos = resto;
          } else if (ev.tipo === "fim") {
            // A memória é atualizada em segundo plano; busca a versão nova depois de um tempo.
            setTimeout(() => {
              api.tarefas
                .obter(tarefaId)
                .then((t) => setAtiva((a) => (a?.id === tarefaId ? { ...a, memoria: t.memoria } : a)))
                .catch(() => undefined);
            }, 60_000);
            setAtiva((t) =>
              t?.id === tarefaId
                ? {
                    ...t,
                    mensagens: [
                      ...t.mensagens,
                      {
                        id: novoId(),
                        papel: "allun",
                        texto: acumulado,
                        agente,
                        modelo: ev.modelo,
                        duracao_s: ev.duracao_s,
                        arquivos,
                        lidos,
                      },
                    ],
                  }
                : t,
            );
          } else if (ev.tipo === "erro") {
            setAtiva((t) =>
              t?.id === tarefaId
                ? {
                    ...t,
                    mensagens: [
                      ...t.mensagens,
                      { id: novoId(), papel: "allun", texto: ev.mensagem, agente, erro: true },
                    ],
                  }
                : t,
            );
          }
        });
      } catch (e) {
        const abortou = e instanceof DOMException && e.name === "AbortError";
        setAtiva((t) =>
          t?.id === tarefaId
            ? {
                ...t,
                mensagens: [
                  ...t.mensagens,
                  abortou
                    ? {
                        id: novoId(),
                        papel: "allun",
                        texto: acumulado ? acumulado + "\n\n*(interrompido)*" : "*(interrompido)*",
                        agente,
                      }
                    : { id: novoId(), papel: "allun", texto: (e as Error).message, erro: true },
                ],
              }
            : t,
        );
      } finally {
        cancelar.current = null;
        setTransmissao(null);
      }
    },
    [ativa, opcoes, pastaNova],
  );

  const mudarPasta = useCallback(async () => {
    if (!ativa || ativa.id === "erro") return;
    const atual = ativa.pasta ?? "";
    const valor = window.prompt(
      "Pasta do projeto (caminho completo). Deixe vazio para usar a pasta automática.",
      atual,
    );
    if (valor === null) return;
    try {
      const t = await api.tarefas.definirPasta(ativa.id, valor.trim() || null);
      setAtiva((a) => (a?.id === t.id ? { ...a, ...t } : a));
      setTarefas((ts) => ts.map((x) => (x.id === t.id ? { ...x, ...t } : x)));
    } catch (e) {
      window.alert((e as Error).message);
    }
  }, [ativa]);

  const abrirPasta = useCallback(async () => {
    if (!ativa || ativa.id === "erro") return;
    try {
      await api.tarefas.abrirPasta(ativa.id);
    } catch (e) {
      window.alert((e as Error).message);
    }
  }, [ativa]);

  const transmitindoAqui = transmissao !== null && transmissao.tarefaId === ativa?.id;
  const sidebarAtiva = ativa && ativa.id !== "erro" ? ativa.id : null;

  return (
    <div className="app">
      <Sidebar
        tela={tela}
        tarefas={tarefas}
        ativaId={sidebarAtiva}
        diagnostico={diagnostico}
        ollama={apiOff ? false : ollama}
        versao={versao}
        aoNavegar={(t) => {
          setTela(t);
          if (t === "modelos") recarregarModelos();
        }}
        aoNovaTarefa={() => {
          setAtiva(null);
          setTela("chat");
        }}
        aoAbrirTarefa={abrirTarefa}
        aoRemoverTarefa={removerTarefa}
      />

      <main className="principal">
        {apiOff && (
          <div className="faixa-erro">
            API fora do ar. Rode <code>python -m allun servir</code> e recarregue a página.
          </div>
        )}
        <header className="topo">
          <h2>
            {tela === "chat"
              ? (ativa?.titulo ?? "Nova tarefa")
              : { equipe: "Equipe de IA", hardware: "Hardware", modelos: "Modelos e provedores" }[
                  tela
                ]}
          </h2>
          {tela === "chat" && ativa && ativa.id !== "erro" && (
            <div className="topo-pasta">
              <span className="sub" title={ativa.pasta_efetiva}>
                📁 {ativa.pasta_efetiva}
                {ativa.pasta_automatica ? " (automática)" : ""}
              </span>
              <button className="botao sec" onClick={mudarPasta}>
                Alterar pasta
              </button>
              <button className="botao sec" onClick={abrirPasta}>
                Abrir
              </button>
            </div>
          )}
        </header>

        {tela === "chat" && (
          <>
            <Chat
              tarefa={ativa}
              transmissao={transmitindoAqui ? transmissao : null}
              diagnostico={diagnostico}
              aoSugerir={enviar}
              pastaNova={pastaNova}
              aoMudarPastaNova={setPastaNova}
              aoAbrirPasta={abrirPasta}
            />
            <Composer
              agentes={agentes}
              modelos={modelos}
              transmitindo={transmissao !== null}
              opcoes={opcoes}
              aoMudarOpcoes={setOpcoes}
              aoEnviar={enviar}
              aoCancelar={() => cancelar.current?.abort()}
            />
          </>
        )}
        {tela === "equipe" && <Equipe agentes={agentes} />}
        {tela === "hardware" && <Hardware d={diagnostico} />}
        {tela === "modelos" && (
          <Modelos modelos={modelos} ollama={ollama === true} aoAtualizar={recarregarModelos} />
        )}
      </main>
    </div>
  );
}





