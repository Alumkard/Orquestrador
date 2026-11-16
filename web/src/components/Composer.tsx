import { useRef, useState } from "react";
import { Icon } from "../icons";
import type { Agente, ModeloStatus, Opcoes } from "../types";

interface Props {
  agentes: Agente[];
  modelos: ModeloStatus[];
  transmitindo: boolean;
  opcoes: Opcoes;
  aoMudarOpcoes: (o: Opcoes) => void;
  aoEnviar: (texto: string) => void;
  aoCancelar: () => void;
}

export function Composer({ agentes, modelos, transmitindo, opcoes, aoMudarOpcoes, aoEnviar, aoCancelar }: Props) {
  const [texto, setTexto] = useState("");
  const campo = useRef<HTMLTextAreaElement>(null);

  const disponiveis = modelos.filter((m) => m.disponivel);

  function enviar() {
    const t = texto.trim();
    if (!t || transmitindo) return;
    aoEnviar(t);
    setTexto("");
    if (campo.current) campo.current.style.height = "auto";
  }

  return (
    <div className="composer">
      <textarea
        ref={campo}
        value={texto}
        rows={1}
        placeholder="Descreva a tarefa. O Comandante escolhe o especialista certo, ou escolha um em “Para”."
        onChange={(e) => {
          setTexto(e.target.value);
          e.target.style.height = "auto";
          e.target.style.height = Math.min(e.target.scrollHeight, 200) + "px";
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            enviar();
          }
        }}
        aria-label="Mensagem"
      />
      <div className="composer-barra">
        <label className="seletor">
          <span>Modelo</span>
          <select
            value={opcoes.modelo ?? ""}
            onChange={(e) => aoMudarOpcoes({ ...opcoes, modelo: e.target.value || null })}
          >
            <option value="">Automático</option>
            {disponiveis.map((m) => (
              <option key={m.id} value={m.id}>
                {m.nome}
                {m.tipo === "local" ? " (local)" : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="seletor">
          <span>Para</span>
          <select
            value={opcoes.agente ?? ""}
            onChange={(e) => aoMudarOpcoes({ ...opcoes, agente: e.target.value || null })}
          >
            <option value="">Comandante</option>
            {agentes.map((a) => (
              <option key={a.nome} value={a.nome}>
                {a.nome}
              </option>
            ))}
          </select>
        </label>
        <label
          className={"pilula" + (opcoes.salvar_arquivos ? " ligada" : "")}
          title="Grava na pasta do projeto os arquivos que o agente escrever."
        >
          <input
            type="checkbox"
            checked={opcoes.salvar_arquivos}
            onChange={(e) => aoMudarOpcoes({ ...opcoes, salvar_arquivos: e.target.checked })}
          />
          Arquivos
        </label>
        <label
          className={"pilula" + (opcoes.permitir_anonimos ? " ligada" : "")}
          title="Inclui endpoints sem chave (LLM7, OVHcloud). Seus prompts vão a terceiros sem cadastro."
        >
          <input
            type="checkbox"
            checked={opcoes.permitir_anonimos}
            onChange={(e) => aoMudarOpcoes({ ...opcoes, permitir_anonimos: e.target.checked })}
          />
          Anônimos
        </label>
        <label
          className={"pilula" + (opcoes.permitir_pagos ? " ligada" : "")}
          title="Permite usar APIs pagas no fallback."
        >
          <input
            type="checkbox"
            checked={opcoes.permitir_pagos}
            onChange={(e) => aoMudarOpcoes({ ...opcoes, permitir_pagos: e.target.checked })}
          />
          Pagos
        </label>
        <span className="espaco" />
        {transmitindo ? (
          <button className="enviar parar" onClick={aoCancelar} aria-label="Parar" title="Parar resposta">
            <span className="quadrado" />
          </button>
        ) : (
          <button
            className="enviar"
            onClick={enviar}
            disabled={!texto.trim()}
            aria-label="Enviar"
            title="Enviar (Enter)"
          >
            <Icon nome="send" tamanho={16} />
          </button>
        )}      </div>
    </div>
  );
}

