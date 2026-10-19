import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

function jsonResponse(body: unknown, ok = true, status = 200) {
  return { ok, status, json: async () => body } as Response;
}

function mockBackend({
  healthy = true,
  chatResponse,
  chatOk = true,
}: {
  healthy?: boolean;
  chatResponse?: unknown;
  chatOk?: boolean;
} = {}) {
  const fetchMock = vi.fn().mockImplementation((url: string) => {
    if (url === "/health") {
      return healthy ? Promise.resolve(jsonResponse({ status: "ok" })) : Promise.reject(new Error("down"));
    }
    if (url === "/chat") {
      return Promise.resolve(jsonResponse(chatResponse, chatOk, chatOk ? 200 : 503));
    }
    throw new Error(`unexpected fetch to ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function sendMessage(text: string) {
  await userEvent.type(screen.getByLabelText("Mensagem"), text);
  await userEvent.click(screen.getByLabelText("Enviar mensagem"));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

it("shows the user's message and the assistant's reply", async () => {
  mockBackend({
    chatResponse: { text: "Ele largou em 4º.", charts: [], history: [] },
  });
  render(<App />);
  await waitFor(() => expect(screen.getByText("Conectado")).toBeInTheDocument());

  await sendMessage("De onde o Hamilton largou em Monza?");

  expect(screen.getByText("De onde o Hamilton largou em Monza?")).toBeInTheDocument();
  expect(await screen.findByText("Ele largou em 4º.")).toBeInTheDocument();
});

it("shows the backend's error message when the request fails", async () => {
  mockBackend({
    chatOk: false,
    chatResponse: { detail: "Não foi possível completar a análise agora." },
  });
  render(<App />);
  await waitFor(() => expect(screen.getByText("Conectado")).toBeInTheDocument());

  await sendMessage("Qualquer pergunta");

  expect(await screen.findByText("Não foi possível completar a análise agora.")).toBeInTheDocument();
});

it("renders a chart returned alongside the answer", async () => {
  const newPlot = vi.fn();
  window.Plotly = { newPlot };
  mockBackend({
    chatResponse: {
      text: "Aqui está o gráfico.",
      charts: [{ data: [{ y: [1, 2, 3] }], layout: { title: "Teste" } }],
      history: [],
    },
  });
  render(<App />);
  await waitFor(() => expect(screen.getByText("Conectado")).toBeInTheDocument());

  await sendMessage("Mostra o gráfico");
  await screen.findByText("Aqui está o gráfico.");

  await waitFor(() => expect(newPlot).toHaveBeenCalledTimes(1));
  expect(newPlot.mock.calls[0][1]).toEqual([{ y: [1, 2, 3] }]);
  expect(newPlot.mock.calls[0][2]).toEqual({ title: "Teste" });
});

it("clears the thread when starting a new conversation", async () => {
  mockBackend({ chatResponse: { text: "Resposta.", charts: [], history: [] } });
  render(<App />);
  await waitFor(() => expect(screen.getByText("Conectado")).toBeInTheDocument());

  await sendMessage("Primeira pergunta");
  await screen.findByText("Resposta.");

  await userEvent.click(screen.getByText("Nova conversa"));

  expect(screen.queryByText("Primeira pergunta")).not.toBeInTheDocument();
  expect(screen.getByText("O que vamos explorar hoje?")).toBeInTheDocument();
});

it("disables the composer when the backend is unreachable", async () => {
  mockBackend({ healthy: false });
  render(<App />);

  await waitFor(() => expect(screen.getByText("Desconectado")).toBeInTheDocument());
  expect(screen.getByLabelText("Mensagem")).toBeDisabled();
});
