import { FormEvent, useState } from "react";

type IconProps = {
  className?: string;
};

function Icon({
  name,
  className = "size-5",
}: IconProps & {
  name:
    | "arrow"
    | "bolt"
    | "chat"
    | "chevron"
    | "flag"
    | "menu"
    | "more"
    | "new"
    | "paperclip"
    | "search"
    | "settings"
    | "sparkles"
    | "strategy"
    | "trophy"
    | "user"
    | "x";
}) {
  const paths = {
    arrow: <><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>,
    bolt: <path d="m13 2-9 12h7l-1 8 9-12h-7z" />,
    chat: <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z" />,
    chevron: <path d="m9 18 6-6-6-6" />,
    flag: <><path d="M5 22V4" /><path d="M5 4h12l-2 4 2 4H5" /></>,
    menu: <><path d="M4 7h16" /><path d="M4 12h16" /><path d="M4 17h16" /></>,
    more: <><circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" /></>,
    new: <><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z" /></>,
    paperclip: <path d="m21.4 11.6-8.9 8.9a6 6 0 0 1-8.5-8.5l9.6-9.6a4 4 0 0 1 5.7 5.7l-9.6 9.6a2 2 0 0 1-2.8-2.8l8.9-8.9" />,
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" /></>,
    sparkles: <><path d="m12 3 1.2 3.8L17 8l-3.8 1.2L12 13l-1.2-3.8L7 8l3.8-1.2Z" /><path d="m19 14 .7 2.3L22 17l-2.3.7L19 20l-.7-2.3L16 17l2.3-.7Z" /><path d="m5 14 .6 1.9 1.9.6-1.9.6L5 19l-.6-1.9-1.9-.6 1.9-.6Z" /></>,
    strategy: <><circle cx="12" cy="12" r="9" /><path d="M12 3v4m0 10v4M3 12h4m10 0h4" /><circle cx="12" cy="12" r="3" /></>,
    trophy: <><path d="M8 4h8v5a4 4 0 0 1-8 0Z" /><path d="M12 13v5m-4 3h8m-6-3h4M8 6H4v2a4 4 0 0 0 4 4m8-6h4v2a4 4 0 0 1-4 4" /></>,
    user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
    x: <><path d="m6 6 12 12" /><path d="M18 6 6 18" /></>,
  };

  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

const prompts = [
  {
    icon: "strategy" as const,
    title: "Analise uma estratégia",
    text: "Explique o undercut e o overcut em uma corrida",
  },
  {
    icon: "trophy" as const,
    title: "Compare pilotos",
    text: "Senna ou Schumacher: compare os estilos de pilotagem",
  },
  {
    icon: "bolt" as const,
    title: "Entenda a tecnologia",
    text: "Como o DRS e a aerodinâmica afetam uma ultrapassagem?",
  },
  {
    icon: "flag" as const,
    title: "Reviva grandes momentos",
    text: "Conte a história da maior corrida da Fórmula 1",
  },
];

const history = ["Estratégia em Mônaco", "Novo regulamento de 2026", "Maiores rivalidades da F1"];

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [sentMessage, setSentMessage] = useState("");

  function sendMessage(event: FormEvent) {
    event.preventDefault();
    const cleanMessage = message.trim();
    if (!cleanMessage) return;
    setSentMessage(cleanMessage);
    setMessage("");
  }

  function choosePrompt(prompt: string) {
    setMessage(prompt);
    window.setTimeout(() => document.querySelector<HTMLTextAreaElement>("#chat-input")?.focus(), 0);
  }

  return (
    <div className="app-shell">
      {sidebarOpen && (
        <button
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-label="Fechar menu"
        />
      )}

      <aside className={`sidebar ${sidebarOpen ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0`}>
        <div className="flex items-center justify-between px-4 pt-5">
          <a href="#" className="logo" aria-label="F1 GPT">
            <span className="logo-mark"><span>F1</span></span>
            <span className="font-semibold tracking-tight text-white">F1 LLM</span>
          </a>
          <button className="icon-button lg:hidden" onClick={() => setSidebarOpen(false)} aria-label="Fechar menu">
            <Icon name="x" />
          </button>
        </div>

        <div className="px-3 pt-7">
          <button className="new-chat" onClick={() => setSentMessage("")}>
            <Icon name="new" className="size-[18px]" />
            Nova conversa
          </button>
          <button className="side-action">
            <Icon name="search" className="size-[18px]" />
            Buscar conversas
          </button>
        </div>

        <div className="mt-7 flex-1 overflow-y-auto px-3">
          <p className="eyebrow px-3">Recentes</p>
          <div className="mt-2 space-y-1">
            {history.map((item, index) => (
              <button className={`history-item ${index === 0 ? "active" : ""}`} key={item}>
                <span className="truncate">{item}</span>
                {index === 0 && <Icon name="more" className="size-4 shrink-0" />}
              </button>
            ))}
          </div>
        </div>

        <div className="border-t border-white/[0.07] p-3">
          <button className="profile">
            <span className="avatar"><Icon name="user" className="size-4" /></span>
            <span className="min-w-0 flex-1 text-left">
              <span className="block truncate text-sm font-medium text-white">Visitante</span>
              <span className="block text-xs text-[#85858b]">Plano gratuito</span>
            </span>
            <Icon name="settings" className="size-[18px] text-[#85858b]" />
          </button>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <button className="icon-button lg:hidden" onClick={() => setSidebarOpen(true)} aria-label="Abrir menu">
            <Icon name="menu" />
          </button>
          <button className="model-switcher">
            F1 LLM
            <span className="model-badge">F1</span>
            <Icon name="chevron" className="size-4 rotate-90 text-[#77777e]" />
          </button>
        </header>

        <section className="conversation">
          {!sentMessage ? (
            <div className="welcome">
              <div className="hero-icon">
                <Icon name="sparkles" className="size-6" />
              </div>
              <p className="eyebrow mb-3 text-[#e10600]">SEU ENGENHEIRO DE PISTA</p>
              <h1>O que vamos explorar hoje?</h1>
              <p className="subtitle">
                Estratégia, história, tecnologia e tudo sobre o mundo da Fórmula 1.
              </p>

              <div className="prompt-grid">
                {prompts.map((prompt) => (
                  <button className="prompt-card" key={prompt.title} onClick={() => choosePrompt(prompt.text)}>
                    <span className="prompt-icon"><Icon name={prompt.icon} className="size-[19px]" /></span>
                    <span>
                      <strong>{prompt.title}</strong>
                      <small>{prompt.text}</small>
                    </span>
                    <Icon name="arrow" className="prompt-arrow size-4" />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="messages">
              <div className="user-message">{sentMessage}</div>
              <div className="assistant-message">
                <span className="assistant-avatar"><Icon name="flag" className="size-4" /></span>
                <div>
                  <strong>F1 LLM</strong>
                  <p>
                    Ótima pergunta. Estou preparando uma análise com contexto histórico, dados de pista e os principais fatores estratégicos para responder sobre <span>{sentMessage.toLowerCase()}</span>.
                  </p>
                  <div className="typing"><i /><i /><i /></div>
                </div>
              </div>
            </div>
          )}
        </section>

        <div className="composer-wrap">
          <form className="composer" onSubmit={sendMessage}>
            <textarea
              id="chat-input"
              rows={1}
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage(event);
                }
              }}
              placeholder="Pergunte qualquer coisa sobre Fórmula 1"
              aria-label="Mensagem"
            />
            <div className="composer-actions">
              <button type="button" className="attach-button" aria-label="Anexar arquivo">
                <Icon name="paperclip" className="size-[19px]" />
              </button>
              <span className="mode"><Icon name="bolt" className="size-3.5" /> Modo análise</span>
              <button type="submit" className="send-button" disabled={!message.trim()} aria-label="Enviar mensagem">
                <Icon name="arrow" className="size-[19px]" />
              </button>
            </div>
          </form>
          <p className="disclaimer">A IA pode cometer erros. Confira informações importantes.</p>
        </div>
      </main>
    </div>
  );
}
