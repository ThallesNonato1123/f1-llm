export type ChatMessage = { role: "user" | "assistant"; content: string };

export type PlotlyFigure = { data: unknown[]; layout: Record<string, unknown> };

export type ChatResponse = {
  text: string;
  charts: PlotlyFigure[];
  history: ChatMessage[];
};

export const NETWORK_ERROR_TEXT =
  "Não foi possível conectar ao servidor. Verifique se ele ainda está rodando.";

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch("/health");
    return response.ok;
  } catch {
    return false;
  }
}

export async function sendChatMessage(
  question: string,
  history: ChatMessage[],
): Promise<ChatResponse> {
  let response: Response;
  try {
    response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history }),
    });
  } catch {
    throw new Error(NETWORK_ERROR_TEXT);
  }

  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail || NETWORK_ERROR_TEXT);
  }
  return body;
}
