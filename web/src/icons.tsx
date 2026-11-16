import type { ReactNode } from "react";

const caminhos: Record<string, ReactNode> = {
  plus: <path d="M12 5v14M5 12h14" />,
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </>
  ),
  team: (
    <>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
      <path d="M16 5.5a3 3 0 0 1 0 5.6M18 14.4c1.9.8 3 2.6 3 5.6" />
    </>
  ),
  chip: (
    <>
      <rect x="6" y="6" width="12" height="12" rx="2" />
      <path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3" />
    </>
  ),
  plug: (
    <>
      <path d="M9 3v5M15 3v5" />
      <path d="M6 8h12v3a6 6 0 0 1-12 0V8Z" />
      <path d="M12 17v4" />
    </>
  ),
  send: <path d="m4 12 16-8-6 16-2.5-6.5L4 12Z" />,
  trash: <path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />,
  copy: (
    <>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V6a2 2 0 0 1 2-2h9" />
    </>
  ),
  check: <path d="m5 12.5 4.5 4.5L19 7" />,
  chevron: <path d="m9 6 6 6-6 6" />,
  chat: <path d="M4 5h16v11H9l-5 4V5Z" />,
};

export function Icon({ nome, tamanho = 16 }: { nome: keyof typeof caminhos; tamanho?: number }) {
  return (
    <svg
      width={tamanho}
      height={tamanho}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {caminhos[nome]}
    </svg>
  );
}

export function Logo({ tamanho = 26 }: { tamanho?: number }) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="8" fill="#4f46e5" />
      <path
        d="M16 6 8 24h4l1.6-4h4.8l1.6 4h4L16 6Zm0 8.5 1.7 4.5h-3.4L16 14.5Z"
        fill="#fff"
      />
    </svg>
  );
}
