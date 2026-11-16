import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { ChaveStatus, ModeloStatus } from "../types";

type Filtro = "todos" | "local" | "gratuito" | "pago";

interface Baixando {
  modelo: ModeloStatus;
  status: string;
  pct: number | null;
  erro?: string;
}

function Status({ m }: { m: ModeloStatus }) {
  if (m.tipo === "local") {
    if (m.instalado) return <span className="selo selo-ok">instalado</span>;
    if (m.cabe === false) return <span className="selo selo-erro">não cabe</span>;
    return <span className="selo">não instalado</span>;
  }
  if (m.anonimo) return <span className="selo selo-aviso">sem chave</span>;
  return m.disponivel ? (
    <span className="selo selo-ok">chave definida</span>
  ) : (
    <span className="selo">falta chave</span>
  );
}

function LinhaChave({
  chave,
  url,
  aoAtualizar,
}: {
  chave: ChaveStatus;
  url: string | null;
  aoAtualizar: () => void;
}) {
  const [editando, setEditando] = useState(false);
  const [valor, setValor] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  function fechar() {
    setEditando(false);
    setValor(""); // a chave digitada não fica na memória do painel
    setErro(null);
  }

  async function salvar() {
    setOcupado(true);
    setErro(null);
    try {
      await api.definirChave(chave.nome, valor.trim());
      fechar();
      aoAtualizar();
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setOcupado(false);
    }
  }

  async function remover() {
    if (!window.confirm(`Remover ${chave.nome}? Ela também sai do arquivo .env.`)) return;
    setOcupado(true);
    try {
      await api.apagarChave(chave.nome);
      aoAtualizar();
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="linha-chave">
      <div className="linha-chave-topo">
        <code>{chave.nome}</code>
        {chave.definida ? (
          <span className="sub">
            {chave.mascara} · {chave.origem === ".env" ? "no .env" : "no ambiente do sistema"}
          </span>
        ) : (
          <span className="sub">não definida</span>
        )}
        {url && !chave.definida && (
          <a href={url} target="_blank" rel="noreferrer" className="sub">
            criar chave
          </a>
        )}
        {!editando && (
          <span className="linha-chave-acoes">
            <button className="botao sec" onClick={() => setEditando(true)} disabled={ocupado}>
              {chave.definida ? "Alterar" : "Inserir"}
            </button>
            {chave.definida && chave.origem === ".env" && (
              <button className="botao sec perigo" onClick={remover} disabled={ocupado}>
                Remover
              </button>
            )}
          </span>
        )}
      </div>
      {chave.definida && chave.origem === "ambiente" && (
        <p className="sub">
          Esta chave vem do ambiente do sistema. O valor salvo aqui vale até reiniciar o Allun; depois
          o ambiente do sistema volta a prevalecer.
        </p>
      )}
      {editando && (
        <form
          className="linha-chave-form"
          onSubmit={(e) => {
            e.preventDefault();
            void salvar();
          }}
        >
          <input
            type="password"
            autoFocus
            autoComplete="off"
            spellCheck={false}
            placeholder="Cole a chave aqui"
            value={valor}
            onChange={(e) => setValor(e.target.value)}
            aria-label={`Valor de ${chave.nome}`}
          />
          <button className="botao" type="submit" disabled={ocupado || !valor.trim()}>
            Salvar
          </button>
          <button className="botao sec" type="button" onClick={fechar} disabled={ocupado}>
            Cancelar
          </button>
        </form>
      )}
      {erro && <p className="texto-erro">{erro}</p>}
    </div>
  );
}

interface Props {
  modelos: ModeloStatus[];
  ollama: boolean;
  aoAtualizar: () => void;
}

export function Modelos({ modelos, ollama, aoAtualizar }: Props) {
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [confirmando, setConfirmando] = useState<ModeloStatus | null>(null);
  const [baixando, setBaixando] = useState<Baixando | null>(null);
  const controle = useRef<AbortController | null>(null);

  // Sair da tela interrompe o download; o Ollama retoma de onde parou numa próxima tentativa.
  useEffect(() => () => controle.current?.abort(), []);

  const lista = useMemo(
    () =>
      modelos
        .filter((m) =>
          filtro === "todos"
            ? true
            : filtro === "local"
              ? m.tipo === "local"
              : m.tipo === "online" && m.custo === filtro,
        )
        .sort((a, b) => b.qualidade - a.qualidade),
    [modelos, filtro],
  );

  async function iniciarDownload(m: ModeloStatus) {
    setConfirmando(null);
    const c = new AbortController();
    controle.current = c;
    setBaixando({ modelo: m, status: "Iniciando…", pct: null });
    try {
      await api.baixarModelo(m.id, c.signal, (ev) => {
        if (ev.tipo === "progresso") {
          setBaixando((b) =>
            b
              ? {
                  ...b,
                  status: ev.status,
                  pct: ev.total ? Math.floor((ev.completed * 100) / ev.total) : b.pct,
                }
              : b,
          );
        } else if (ev.tipo === "erro") {
          setBaixando((b) => (b ? { ...b, erro: ev.mensagem } : b));
        }
      });
      setBaixando((b) => (b && !b.erro ? null : b));
    } catch (e) {
      const abortou = e instanceof DOMException && e.name === "AbortError";
      setBaixando((b) => (abortou ? null : b ? { ...b, erro: (e as Error).message } : b));
    } finally {
      controle.current = null;
      aoAtualizar();
    }
  }

  return (
    <div className="pagina">
      <h1>Modelos e provedores</h1>
      <p className="sub">
        Modelos locais rodam no Ollama ({ollama ? "ativo" : "parado"}). Provedores online usam uma
        chave de API, que você insere aqui e fica salva no arquivo <code>.env</code> desta máquina.
        O painel mostra só os 4 últimos caracteres.
      </p>

      {baixando && (
        <div className="cartao progresso">
          <b>Baixando {baixando.modelo.nome}</b>
          {baixando.erro ? (
            <p className="texto-erro">{baixando.erro}</p>
          ) : (
            <>
              <p className="sub">
                {baixando.status}
                {baixando.pct !== null ? ` · ${baixando.pct}%` : ""}. Mantenha esta tela aberta.
              </p>
              <div className="barra">
                <div style={{ width: `${baixando.pct ?? 5}%` }} />
              </div>
            </>
          )}
          <button
            className="botao sec"
            onClick={() => (baixando.erro ? setBaixando(null) : controle.current?.abort())}
          >
            {baixando.erro ? "Fechar" : "Cancelar download"}
          </button>
        </div>
      )}

      <div className="abas">
        {(["todos", "local", "gratuito", "pago"] as Filtro[]).map((f) => (
          <button key={f} className={f === filtro ? "ativo" : ""} onClick={() => setFiltro(f)}>
            {f === "todos"
              ? "Todos"
              : f === "local"
                ? "Locais"
                : f === "gratuito"
                  ? "Online gratuitos"
                  : "Online pagos"}
          </button>
        ))}
      </div>

      <div className="lista">
        {lista.map((m) => (
          <div key={m.id + m.provedor} className="item-modelo">
            <div className="item-topo">
              <b>{m.nome}</b>
              <Status m={m} />
              <span className="etiqueta suave">{m.provedor}</span>
              {m.custo === "pago" && <span className="selo selo-aviso">pago</span>}
              {m.tipo === "local" && !m.instalado && (
                <button
                  className="botao"
                  disabled={!ollama || baixando !== null}
                  title={ollama ? "Baixar no Ollama" : "O Ollama precisa estar ativo"}
                  onClick={() => setConfirmando(m)}
                >
                  Baixar
                </button>
              )}
            </div>
            <code className="id">{m.id}</code>
            {m.observacao && <p className="sub">{m.observacao}</p>}
            {m.tipo === "online" &&
              m.chaves?.map((c) => (
                <LinhaChave key={c.nome} chave={c} url={m.chave_url} aoAtualizar={aoAtualizar} />
              ))}
            {m.tipo === "local" && (
              <p className="sub">
                Precisa de {m.memoria_min_gb} GB de memória
                {m.tamanho_gb ? ` · download de ${m.tamanho_gb} GB` : ""}
              </p>
            )}
          </div>
        ))}
      </div>

      {confirmando && (
        <div className="fundo-modal" onClick={() => setConfirmando(null)}>
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label="Confirmar download"
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Baixar {confirmando.nome}?</h3>
            <p>
              O download ocupa cerca de{" "}
              <b>{confirmando.tamanho_gb ? `${confirmando.tamanho_gb} GB` : "alguns GB"}</b> de
              disco e usa sua conexão. O arquivo fica no Ollama.
            </p>
            {confirmando.cabe === false && (
              <p className="alerta-modal">
                Este modelo exige {confirmando.memoria_min_gb} GB de memória e não cabe com folga
                nesta máquina. Ele pode ficar muito lento ou falhar.
              </p>
            )}
            <div className="acoes-modal">
              <button className="botao sec" onClick={() => setConfirmando(null)}>
                Cancelar
              </button>
              <button className="botao" onClick={() => iniciarDownload(confirmando)}>
                Baixar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


