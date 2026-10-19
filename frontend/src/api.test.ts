import { afterEach, describe, expect, it, vi } from "vitest";
import { checkHealth, NETWORK_ERROR_TEXT, sendChatMessage } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(body: unknown, ok = true, status = 200) {
  return { ok, status, json: async () => body } as Response;
}

describe("checkHealth", () => {
  it("returns true when the backend responds ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ status: "ok" })));

    await expect(checkHealth()).resolves.toBe(true);
  });

  it("returns false when the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    await expect(checkHealth()).resolves.toBe(false);
  });
});

describe("sendChatMessage", () => {
  it("posts the question and history, and returns the parsed response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ text: "Ele largou em 4º.", charts: [], history: [{ role: "user", content: "oi" }] }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await sendChatMessage("E de onde ele largou?", [{ role: "user", content: "oi" }]);

    expect(fetchMock).toHaveBeenCalledWith("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: "E de onde ele largou?",
        history: [{ role: "user", content: "oi" }],
      }),
    });
    expect(result.text).toBe("Ele largou em 4º.");
  });

  it("throws the backend's error detail when the request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "Não foi possível completar a análise agora." }, false, 503)),
    );

    await expect(sendChatMessage("oi", [])).rejects.toThrow("Não foi possível completar a análise agora.");
  });

  it("throws a network error message when fetch itself fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    await expect(sendChatMessage("oi", [])).rejects.toThrow(NETWORK_ERROR_TEXT);
  });
});
