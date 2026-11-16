import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Icon } from "../icons";
import type { ArquivosLidos, Diagnostico, Mensagem, ResultadoArquivos, Tarefa } from "../types";

export interface Transmissao {
  agente: string | null;
  texto: string;
  inicio: number;
  lidos?: ArquivosLidos;
}

function Lidos({ l }: { l: ArquivosLidos }) {
  if (!l.arquivos_lidos.length && !l.arquivos_cortados.length && !l.arquivos_fora.length) return null;
  return (
    <div className="lidos">
      {l.arquivos_lidos.length > 0 && <span>📄 Leu: {l.arquivos_lidos.join(", ")}</span>}
      {l.arquivos_cortados.length > 0 && (
        <span className="aviso-lido">
          Leu em parte (grande demais para o modelo): {l.arquivos_cortados.join(", ")}
        </span>
      )}
      {l.arquivos_fora.length > 0 && <span>Não couberam: {l.arquivos_fora.join(", ")}</span>}
    </div>
  );
}

interface Props {
  tarefa: Tarefa | null;
  transmissao: Transmissao | null;
  diagnostico: Diagnostico | null;
  aoSugerir: (texto: string) => void;
  pastaNova: string;
  aoMudarPastaNova: (pasta: string) => void;
  aoAbrirPasta: () => void;
}

const SUGESTOES = [
  "Escreva uma função Python que inverte uma string",
  "Resuma em uma frase: a fotossíntese converte luz em energia química",
  "Compare Postgres e MySQL para um sistema de pedidos",
];

/** Modelos pequenos às vezes devolvem HTML puro, sem cercas de código; sem isso o Markdown o esconde. */
export function prepararMarkdown(texto: string): string {
  const t = texto.trimStart();
  if (/^<!doctype html|^<html/i.test(t) && !t.startsWith("```")) {
    return "```html\n" + texto.trim() + (t.includes("</html") ? "\n```" : "");
  }
  return texto;
}

function Copiar({ texto }: { texto: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button
      className="acao"
      onClick={async () => {
        await navigator.clipboard.writeText(texto);
        setOk(true);
        setTimeout(() => setOk(false), 1500);
      }}
    >
      <Icon nome={ok ? "check" : "copy"} tamanho={13} /> {ok ? "Copiado" : "Copiar"}
    </button>
  );
}

function tamanho(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`;
}

const ROTULO = { criado: "novo", alterado: "alterado", igual: "sem mudança" } as const;

function Arquivos({ r, aoAbrirPasta }: { r: ResultadoArquivos; aoAbrirPasta: () => void }) {
  return (
    <div className="arquivos">
      <div className="arquivos-topo">
        <b>Arquivos no projeto</b>
        <span className="sub" title={r.pasta}>
          {r.pasta}
        </span>
        <button className="botao sec" onClick={aoAbrirPasta}>
          Abrir pasta
        </button>
      </div>
      {r.erro && <p className="texto-erro">{r.erro}</p>}
      <ul>
        {r.gravados.map((a) => (
          <li key={a.caminho}>
            <code>{a.caminho}</code> <span className="sub">{tamanho(a.bytes)}</span>{" "}
            <span className={"selo" + (a.situacao === "criado" ? " selo-ok" : a.situacao === "alterado" ? " selo-aviso" : "")}>
              {ROTULO[a.situacao]}
            </span>
          </li>
        ))}
        {r.rejeitados.map((a) => (
          <li key={"x" + a.caminho}>
            <code>{a.caminho}</code> <span className="selo selo-erro">recusado</span>{" "}
            <span className="sub">{a.motivo}</span>
          </li>
        ))}
      </ul>
      {r.gravados.some((a) => a.situacao === "alterado") && (
        <p className="sub">A versão anterior de cada arquivo alterado fica em .allun/versoes.</p>
      )}
    </div>
  );
}

function Cartao({ m, aoAbrirPasta }: { m: Mensagem; aoAbrirPasta: () => void }) {
  if (m.papel === "usuario") {
    return (
      <div className="linha-usuario">
        <div className="bolha-usuario">{m.texto}</div>
      </div>
    );
  }
  return (
    <div className={"cartao-resposta" + (m.erro ? " erro" : "")}>
      <div className="cartao-meta">
        {m.duracao_s !== undefined && <span>Duração {m.duracao_s}s</span>}
        {m.agente && <span className="etiqueta">{m.agente}</span>}
        {m.modelo && <span className="etiqueta suave">{m.modelo}</span>}
      </div>
      {m.lidos && <Lidos l={m.lidos} />}
      {m.erro ? <p className="texto-erro">{m.texto}</p> : <ReactMarkdown>{prepararMarkdown(m.texto)}</ReactMarkdown>}
      {!m.erro && m.arquivos && <Arquivos r={m.arquivos} aoAbrirPasta={aoAbrirPasta} />}
      {!m.erro && (
        <div className="acoes">
          <Copiar texto={m.texto} />
        </div>
      )}
    </div>
  );
}

function Escrevendo({ t }: { t: Transmissao }) {
  const [seg, setSeg] = useState(0);
  useEffect(() => {
    const i = setInterval(() => setSeg(Math.round((Date.now() - t.inicio) / 1000)), 1000);
    return () => clearInterval(i);
  }, [t.inicio]);
  return (
    <div className="cartao-resposta pensando">
      <div className="cartao-meta">
        <span>{t.texto ? "Escrevendo" : "Pensando"}… {seg}s</span>
        {t.agente && <span className="etiqueta">{t.agente}</span>}
      </div>
      {t.lidos && <Lidos l={t.lidos} />}
      {t.texto ? (
        <ReactMarkdown>{prepararMarkdown(t.texto)}</ReactMarkdown>
      ) : (
        <div className="pontos">
          <i />
          <i />
          <i />
        </div>
      )}
    </div>
  );
}
export function Chat({
  tarefa,
  transmissao,
  diagnostico,
  aoSugerir,
  pastaNova,
  aoMudarPastaNova,
  aoAbrirPasta,
}: Props) {
  const fim = useRef<HTMLDivElement>(null);
  useEffect(() => {
    fim.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [tarefa?.mensagens.length, transmissao?.texto]);

  if (!tarefa) {
    return (
      <div className="boas-vindas">
        <h1>O que você precisa fazer hoje?</h1>
        <p>
          Eu sou o Comandante do Allun. Descrevo a tarefa ao especialista certo e uso o melhor
          modelo que cabe na sua máquina.
          {diagnostico?.recomendacao.principal && (
            <>
              {" "}
              Modelo recomendado agora: <b>{diagnostico.recomendacao.principal.nome}</b>.
            </>
          )}
        </p>
        <label className="pasta-nova">
          <span>Pasta do projeto (opcional)</span>
          <input
            value={pastaNova}
            onChange={(e) => aoMudarPastaNova(e.target.value)}
            placeholder={String.raw`Ex.: C:\Projetos\loja  (vazio = o Allun cria a pasta em C:\Users\<você>\Allun\projetos)`}
            spellCheck={false}
          />
        </label>
        <div className="sugestoes">
          {SUGESTOES.map((s) => (
            <button key={s} onClick={() => aoSugerir(s)}>
              <Icon nome="chat" tamanho={14} /> {s}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="conversa">
      <div className="conversa-conteudo">
        {tarefa.memoria && (tarefa.memoria.fatos.length > 0 || tarefa.memoria.resumo) && (
          <details className="memoria">
            <summary>
              Memória: {tarefa.memoria.fatos.length} fatos · resumo das primeiras{" "}
              {tarefa.memoria.cobertas} mensagens
            </summary>
            {tarefa.memoria.fatos.length > 0 && (
              <ul>
                {tarefa.memoria.fatos.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            )}
            {tarefa.memoria.resumo && <p>{tarefa.memoria.resumo}</p>}
          </details>
        )}
        {tarefa.mensagens.map((m) => (
          <Cartao key={m.id} m={m} aoAbrirPasta={aoAbrirPasta} />
        ))}
        {transmissao && <Escrevendo t={transmissao} />}
        <div ref={fim} />
      </div>
    </div>
  );
}




