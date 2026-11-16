import type {
  Agente,
  ChaveStatus,
  Diagnostico,
  EventoDownload,
  EventoMensagem,
  ModeloStatus,
  Opcoes,
  Tarefa,
  TarefaResumo,
} from "./types";

// Exigido pela API nas ações que mexem no disco ou em chaves (bloqueia outros sites).
const PAINEL = { "X-Allun-Painel": "1" };

const MSG_API_OFF = "Não foi possível falar com a API. Rode `python -m allun servir`.";

async function erroDe(resp: Response): Promise<Error> {
  let detalhe = `Erro ${resp.status}`;
  try {
    const corpo = await resp.json();
    if (typeof corpo.detail === "string") detalhe = corpo.detail;
  } catch {
    /* corpo sem JSON */
  }
  return new Error(detalhe);
}

async function chamar<T>(caminho: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(caminho, init);
  } catch {
    throw new Error(MSG_API_OFF);
  }
  if (!resp.ok) throw await erroDe(resp);
  return resp.status === 204 ? (undefined as T) : ((await resp.json()) as T);
}

const json = (corpo: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(corpo),
});

/** Lê uma resposta SSE ("data: {...}\n\n") e chama `aoEvento` para cada evento. */
async function lerSSE<T>(caminho: string, init: RequestInit, aoEvento: (e: T) => void) {
  let resp: Response;
  try {
    resp = await fetch(caminho, init);
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new Error(MSG_API_OFF);
  }
  if (!resp.ok || !resp.body) throw await erroDe(resp);

  const leitor = resp.body.getReader();
  const decodificador = new TextDecoder();
  let resto = "";
  for (;;) {
    const { done, value } = await leitor.read();
    if (done) break;
    resto += decodificador.decode(value, { stream: true });
    const blocos = resto.split("\n\n");
    resto = blocos.pop() ?? "";
    for (const bloco of blocos) {
      const linha = bloco.split("\n").find((l) => l.startsWith("data: "));
      if (linha) aoEvento(JSON.parse(linha.slice(6)) as T);
    }
  }
}

export const api = {
  saude: () => chamar<{ versao: string; ollama: boolean }>("/api/saude"),
  diagnostico: () => chamar<Diagnostico>("/api/diagnostico"),
  agentes: () => chamar<Agente[]>("/api/agentes"),
  modelos: () => chamar<{ ollama_ativo: boolean; modelos: ModeloStatus[] }>("/api/modelos"),

  // O cabeçalho obriga o navegador a pedir permissão (CORS) antes; a API só aceita do painel local.
  definirChave: (nome: string, valor: string) =>
    chamar<ChaveStatus>(`/api/chaves/${nome}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", "X-Allun-Painel": "1" },
      body: JSON.stringify({ valor }),
    }),
  apagarChave: (nome: string) =>
    chamar<ChaveStatus>(`/api/chaves/${nome}`, {
      method: "DELETE",
      headers: { "X-Allun-Painel": "1" },
    }),

  tarefas: {
    listar: () => chamar<TarefaResumo[]>("/api/tarefas"),
    criar: (titulo: string, pasta?: string) =>
      chamar<TarefaResumo>("/api/tarefas", {
        ...json({ titulo, pasta: pasta || null }),
        headers: { "Content-Type": "application/json", ...(pasta ? PAINEL : {}) },
      }),
    definirPasta: (id: string, pasta: string | null) =>
      chamar<TarefaResumo>(`/api/tarefas/${id}/pasta`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...PAINEL },
        body: JSON.stringify({ pasta }),
      }),
    abrirPasta: (id: string) =>
      chamar<{ pasta: string }>(`/api/tarefas/${id}/abrir-pasta`, { method: "POST", headers: PAINEL }),
    obter: (id: string) => chamar<Tarefa>(`/api/tarefas/${id}`),
    remover: (id: string) => chamar<void>(`/api/tarefas/${id}`, { method: "DELETE" }),
  },

  enviarMensagem: (
    tarefaId: string,
    texto: string,
    opcoes: Opcoes,
    sinal: AbortSignal,
    aoEvento: (e: EventoMensagem) => void,
  ) =>
    lerSSE<EventoMensagem>(
      `/api/tarefas/${tarefaId}/mensagens`,
      { ...json({ texto, ...opcoes }), signal: sinal },
      aoEvento,
    ),

  baixarModelo: (
    modelo: string,
    sinal: AbortSignal,
    aoEvento: (e: EventoDownload) => void,
  ) =>
    lerSSE<EventoDownload>(
      "/api/modelos/baixar",
      { ...json({ modelo, confirmar: true }), signal: sinal },
      aoEvento,
    ),
};

