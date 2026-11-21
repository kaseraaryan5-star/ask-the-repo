"""HTTP API for Ask the Repo."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.ask import answer

app = FastAPI(title="Ask the Repo")


class AskRequest(BaseModel):
    question: str
    k: int = 5


@app.get("/")
def root():
    return {"status": "ok", "service": "ask-the-repo"}


@app.post("/ask")
def ask_endpoint(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question is empty")
    try:
        return answer(req.question, req.k)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")