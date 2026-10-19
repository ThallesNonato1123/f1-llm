import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// FastAPI backend, started separately (`uv run uvicorn f1llm.api.app:app --reload`).
const BACKEND_URL = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/chat": BACKEND_URL,
      "/health": BACKEND_URL,
    },
  },
});
