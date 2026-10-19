import os
from pathlib import Path

import anthropic
import fastf1
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from f1llm import fastf1_client
from f1llm.llm.chat import answer
from f1llm.llm.production import DEFAULT_EFFORT, DEFAULT_MODEL, claude_create_message

UPSTREAM_ERROR_TEXT = "Não foi possível completar a análise agora. Tente novamente."

fastf1.set_log_level("ERROR")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["POST"])


class ChatRequest(BaseModel):
    question: str
    history: list[dict] = []


class ChatResponse(BaseModel):
    text: str
    charts: list[dict]
    history: list[dict]


def get_create_message():
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise HTTPException(status_code=503, detail=UPSTREAM_ERROR_TEXT)
    model = os.environ.get("F1LLM_MODEL", DEFAULT_MODEL)
    effort = os.environ.get("F1LLM_EFFORT", DEFAULT_EFFORT)
    return claude_create_message(anthropic.Anthropic(), model=model, effort=effort)


def get_loaders():
    return fastf1_client


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, create_message=Depends(get_create_message), loaders=Depends(get_loaders)):
    try:
        result = answer(body.history, body.question, create_message=create_message, loaders=loaders)
    except anthropic.APIError:
        raise HTTPException(status_code=503, detail=UPSTREAM_ERROR_TEXT)
    return ChatResponse(text=result.text, charts=result.charts, history=result.history)


# ADR 0006: the frontend is now a separate React+Vite project, built into
# frontend/dist (gitignored) by `pnpm build`; FastAPI just serves that output.
_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"

# Mounted last so it never shadows /chat or /health: FastAPI matches routes in
# registration order, and a root mount would otherwise catch everything first.
# check_dir=False: don't crash on import before the frontend has been built.
app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True, check_dir=False), name="static")
