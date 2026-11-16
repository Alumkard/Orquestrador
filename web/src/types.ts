export interface Agente {
  nome: string;
  descricao: string;
  prompt_sistema: string;
}

export interface ModeloLLM {
  id: string;
  nome: string;
  tipo: "local" | "online";
  provedor: string;
  qualidade: number;
  memoria_min_gb: number;
  custo: "gratuito" | "pago";
  tamanho_gb: number | null;
  chaves_env: string[];
  api_base: string | null;
  observacao: string | null;
  chave_url: string | null;
  anonimo: boolean;
}

export interface ChaveStatus {
  nome: string;
  definida: boolean;
  mascara: string | null;
  origem: ".env" | "ambiente" | null;
}

export interface ModeloStatus extends ModeloLLM {
  chaves?: ChaveStatus[];
  disponivel: boolean;
  cabe?: boolean;
  instalado?: boolean;
  chaves_ausentes?: string[];
}

export interface GPU {
  nome: string;
  fabricante: string | null;
  vram_gb: number | null;
  dedicada: boolean;
}

export interface Diagnostico {
  hardware: {
    ram_total_gb: number;
    ram_disponivel_gb: number;
    nucleos: number;
    gpus: GPU[];
    memoria_modelo_gb: number;
  };
  perfil: "leve" | "medio" | "potente";
  recomendacao: {
    principal: ModeloLLM | null;
    alternativas_locais: ModeloLLM[];
    online_gratuitos: ModeloLLM[];
    online_pagos: ModeloLLM[];
  };
  avisos: string[];
}

export interface ArquivoGravado {
  caminho: string;
  bytes: number;
  situacao: "criado" | "alterado" | "igual";
}

export interface ResultadoArquivos {
  pasta: string;
  gravados: ArquivoGravado[];
  rejeitados: { caminho: string; motivo: string }[];
  erro?: string;
}

export interface ArquivosLidos {
  arquivos_lidos: string[];
  arquivos_cortados: string[];
  arquivos_fora: string[];
}

export interface Mensagem {
  id: string;
  lidos?: ArquivosLidos; // só na sessão atual; não fica salvo
  arquivos?: ResultadoArquivos | null;
  papel: "usuario" | "allun";
  texto: string;
  agente?: string;
  modelo?: string | null;
  duracao_s?: number;
  erro?: boolean;
}

export interface TarefaResumo {
  id: string;
  titulo: string;
  criada: number; // segundos desde 1970 (servidor)
  pasta: string | null; // escolhida pelo usuário; null = automática
  pasta_efetiva: string;
  pasta_automatica: boolean;
}

export interface MemoriaTarefa {
  resumo: string;
  fatos: string[];
  cobertas: number;
}

export interface Tarefa extends TarefaResumo {
  mensagens: Mensagem[];
  memoria?: MemoriaTarefa | null;
}

export type EventoMensagem =
  | { tipo: "agente"; agente: string }
  | { tipo: "trecho"; texto: string }
  | ({ tipo: "arquivos" } & ResultadoArquivos)
  | ({ tipo: "contexto" } & ArquivosLidos)
  | { tipo: "fim"; modelo: string | null; duracao_s: number; falhas: string[] }
  | { tipo: "erro"; mensagem: string };

export type EventoDownload =
  | { tipo: "progresso"; status: string; completed: number; total: number }
  | { tipo: "fim" }
  | { tipo: "erro"; mensagem: string };

export interface Opcoes {
  agente: string | null;
  modelo: string | null;
  permitir_pagos: boolean;
  permitir_anonimos: boolean;
  salvar_arquivos: boolean;
}
export type Tela = "chat" | "equipe" | "hardware" | "modelos";




