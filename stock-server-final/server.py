
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import pathlib

app = FastAPI()

INDEX = pathlib.Path(__file__).parent / "index.html"

@app.get("/")
def root():
    return HTMLResponse(INDEX.read_text(encoding="utf-8"))

@app.get("/api/health")
def health():
    return {"status": "ok"}
