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

function GithubIcon({ className = "size-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.6 7.6 0 0 1 2-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
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
    title: "Analise a estratégia de pneus",
    text: "Quais foram os stints de pneu de cada piloto no GP de Mônaco de 2024?",
  },
  {
    icon: "trophy" as const,
    title: "Compare o ritmo de dois pilotos",
    text: "Compare o ritmo de corrida de Verstappen e Hamilton no GP de Abu Dhabi de 2021",
  },
  {
    icon: "bolt" as const,
    title: "Compare a telemetria de uma volta",
    text: "Compare velocidade, freio e marcha de Leclerc e Sainz na volta mais rápida de Monza 2023",
  },
  {
    icon: "flag" as const,
    title: "Veja o resultado de uma sessão",
    text: "Qual foi a classificação final do GP de Interlagos de 2024?",
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

      <a
        className="credit"
        href="https://github.com/ThallesNonato1123"
        target="_blank"
        rel="noopener noreferrer"
      >
        <span>Criado por ThallesNonato1123</span>
        <GithubIcon className="size-4" />
      </a>
    </div>
  );
}
