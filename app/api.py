"""HTTP API for Ask the Repo."""

import subprocess

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.ask import answer
from app.github import clone
from app.indexer import index_repo

MAX_CHUNKS = 1500

app = FastAPI(title="Ask the Repo")


class AskRequest(BaseModel):
    question: str
    k: int = 5


class IndexRequest(BaseModel):
    repo_url: str


@app.get("/")
def root():
    return {"status": "ok", "service": "ask-the-repo"}


@app.post("/index")
def index_endpoint(req: IndexRequest):
    try:
        with clone(req.repo_url) as (path, base_url):
            n = index_repo(path, base_url=base_url, max_chunks=MAX_CHUNKS)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise HTTPException(
            status_code=400, detail="Could not clone the repo. Is it public and is the URL correct?")
    return {"status": "indexed", "repo": req.repo_url, "chunks": n}


@app.post("/ask")
def ask_endpoint(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question is empty")
    try:
        return answer(req.question, req.k)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not answer: {e}")