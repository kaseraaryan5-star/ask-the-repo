"""Answer a question about a repo using retrieved code chunks, citing file:line."""

import os
import sys
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors

from app.indexer import search

load_dotenv()
MODELS = [
    m for m in (os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
                os.getenv("GEMINI_FALLBACK_MODEL"))
    if m
]
RETRYABLE = (429, 500, 503)

PROMPT = """You are a code assistant. Answer the question using ONLY the code chunks below.
Cite every claim like [file:start-end], using the exact ranges given.
If the chunks do not contain the answer, say you could not find it in the retrieved code.
Do not invent files or functions.

Code chunks:
{context}

Question: {question}
Answer:"""


def generate(prompt, retries=3):
    """Try each model in order; retry with backoff on overload/rate-limit errors."""
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    last_error = None
    for model in MODELS:
        for attempt in range(retries):
            try:
                return client.models.generate_content(model=model, contents=prompt).text
            except errors.APIError as e:
                last_error = e
                if e.code in RETRYABLE:
                    print(f"[{model}] error {e.code}, retry {attempt + 1}/{retries}...")
                    time.sleep(2 ** attempt)
                    continue
                raise
        print(f"[{model}] still failing, trying next model...")
    raise last_error


def ask(question, k=5):
    hits = search(question, k=k)
    context = "\n\n".join(
        f"[{h.payload['file']}:{h.payload['start_line']}-{h.payload['end_line']}] "
        f"{h.payload['symbol']}\n{h.payload['code']}"
        for h in hits
    )
    return generate(PROMPT.format(context=context, question=question))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python3 -m app.ask "your question"')
    else:
        print("\n--- Answer ---")
        print(ask(" ".join(sys.argv[1:])))