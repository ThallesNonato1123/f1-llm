import { FormEvent, useEffect, useRef, useState } from "react";
import { checkHealth, ChatMessage, PlotlyFigure, sendChatMessage } from "./api";

declare global {
  interface Window {
    Plotly?: {
      newPlot: (el: HTMLElement, data: unknown[], layout: Record<string, unknown>, config?: Record<string, unknown>) => void;
    };
  }
}

type DisplayMessage =
  | { role: "user"; text: string }
  | { role: "assistant"; text: string; charts: PlotlyFigure[]; error?: boolean };

type IconProps = {
  className?: string;
};

function Icon({
  name,
  className = "size-5",
}: IconProps & {
  name: "arrow" | "bolt" | "chevron" | "flag" | "new" | "sparkles" | "strategy" | "trophy";
}) {
  const paths = {
    arrow: <><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>,
    bolt: <path d="m13 2-9 12h7l-1 8 9-12h-7z" />,
    chevron: <path d="m9 18 6-6-6-6" />,
    flag: <><path d="M5 22V4" /><path d="M5 4h12l-2 4 2 4H5" /></>,
    new: <><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z" /></>,
    sparkles: <><path d="m12 3 1.2 3.8L17 8l-3.8 1.2L12 13l-1.2-3.8L7 8l3.8-1.2Z" /><path d="m19 14 .7 2.3L22 17l-2.3.7L19 20l-.7-2.3L16 17l2.3-.7Z" /><path d="m5 14 .6 1.9 1.9.6-1.9.6L5 19l-.6-1.9-1.9-.6 1.9-.6Z" /></>,
    strategy: <><circle cx="12" cy="12" r="9" /><path d="M12 3v4m0 10v4M3 12h4m10 0h4" /><circle cx="12" cy="12" r="3" /></>,
    trophy: <><path d="M8 4h8v5a4 4 0 0 1-8 0Z" /><path d="M12 13v5m-4 3h8m-6-3h4M8 6H4v2a4 4 0 0 0 4 4m8-6h4v2a4 4 0 0 1-4 4" /></>,
  };

  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

function Chart({ figure }: { figure: PlotlyFigure }) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (container.current && window.Plotly) {
      window.Plotly.newPlot(container.current, figure.data, figure.layout, { responsive: true });
    }
  }, [figure]);

  return <div className="plot" ref={container} />;
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

export default function App() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(true);

  useEffect(() => {
    checkHealth().then(setIsConnected);
  }, []);

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    const question = message.trim();
    if (!question || isLoading) return;

    setMessage("");
    setMessages((previous) => [...previous, { role: "user", text: question }]);
    setIsLoading(true);

    try {
      const result = await sendChatMessage(question, chatHistory);
      setChatHistory(result.history);
      setMessages((previous) => [...previous, { role: "assistant", text: result.text, charts: result.charts }]);
    } catch (error) {
      setMessages((previous) => [
        ...previous,
        { role: "assistant", text: (error as Error).message, charts: [], error: true },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  function newConversation() {
    setMessages([]);
    setChatHistory([]);
  }

  function choosePrompt(prompt: string) {
    setMessage(prompt);
    window.setTimeout(() => document.querySelector<HTMLTextAreaElement>("#chat-input")?.focus(), 0);
  }

  const hasMessages = messages.length > 0;

  return (
    <div className="app-shell">
      <main className="main-panel">
        <header className="topbar">
          <a href="#" className="logo" aria-label="F1 LLM">
            <span className="logo-mark"><span>F1</span></span>
            <span className="font-semibold tracking-tight text-white">F1 LLM</span>
          </a>

          <button className="model-switcher">
            F1 LLM
            <span className="model-badge">F1</span>
            <Icon name="chevron" className="size-4 rotate-90 text-[#77777e]" />
          </button>

          <div className="flex items-center gap-2">
            <span className={`status ${isConnected ? "connected" : "disconnected"}`}>
              <span className="status-dot" />
              {isConnected ? "Conectado" : "Desconectado"}
            </span>
            <button className="new-chat-button" onClick={newConversation} disabled={!hasMessages}>
              <Icon name="new" className="size-4" />
              Nova conversa
            </button>
          </div>
        </header>

        <section className="conversation">
          {!hasMessages ? (
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
              {messages.map((entry, index) =>
                entry.role === "user" ? (
                  <div className="user-message" key={index}>{entry.text}</div>
                ) : (
                  <div className={`assistant-message ${entry.error ? "is-error" : ""}`} key={index}>
                    <span className="assistant-avatar"><Icon name="flag" className="size-4" /></span>
                    <div>
                      <strong>F1 LLM</strong>
                      <p>{entry.text}</p>
                      {entry.charts.map((figure, chartIndex) => (
                        <Chart figure={figure} key={chartIndex} />
                      ))}
                    </div>
                  </div>
                ),
              )}
              {isLoading && (
                <div className="assistant-message">
                  <span className="assistant-avatar"><Icon name="flag" className="size-4" /></span>
                  <div>
                    <strong>F1 LLM</strong>
                    <div className="typing"><i /><i /><i /></div>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        <div className="composer-wrap">
          <form className="composer" onSubmit={sendMessage}>
            <textarea
              id="chat-input"
              rows={1}
              value={message}
              disabled={!isConnected}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage(event);
                }
              }}
              placeholder={isConnected ? "Pergunte qualquer coisa sobre Fórmula 1" : "Servidor indisponível no momento"}
              aria-label="Mensagem"
            />
            <div className="composer-actions">
              <button
                type="submit"
                className="send-button"
                disabled={!message.trim() || isLoading || !isConnected}
                aria-label="Enviar mensagem"
              >
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
